"""
Wake-up script for Streamlit Cloud apps.

Uses curl to check if apps are sleeping, then launches Selenium
(headless Chrome) only when needed to click the "Wake Up" button.

Based on: https://github.com/Aditya190803/st-awake-template
"""

import asyncio
import datetime
import json
import os
import threading
import time

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

from streamlit_apps import STREAMLIT_APPS


# ── Configuration (override via env vars) ────────────────────────────────────

BROWSER_PAGELOAD_TIMEOUT_SECONDS = float(
    os.getenv("BROWSER_PAGELOAD_TIMEOUT_SECONDS", "5")
)
SITE_WAIT_SECONDS = float(os.getenv("SITE_WAIT_SECONDS", "25"))
BUTTON_APPEAR_WAIT_SECONDS = float(os.getenv("BUTTON_APPEAR_WAIT_SECONDS", "12"))
WAKE_INTERVAL_HOURS = float(os.getenv("WAKE_INTERVAL_HOURS", "10"))
MAX_CONCURRENT_APPS = max(1, int(os.getenv("MAX_CONCURRENT_APPS", "5")))
STATE_FILE = os.getenv("WAKE_STATE_FILE", "wakeup_state.json")
LOG_FILE = os.getenv("WAKE_LOG_FILE", "wakeup_log.txt")
CHROME_BINARY = os.getenv("CHROME_BINARY", "/usr/bin/chromium").strip()
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH", "/usr/bin/chromedriver").strip()
CHROME_USER_DATA_DIR = os.getenv("CHROME_USER_DATA_DIR", "").strip()
CHROME_PROFILE_DIRECTORY = os.getenv("CHROME_PROFILE_DIRECTORY", "").strip()
ENFORCE_WAKE_INTERVAL = os.getenv("ENFORCE_WAKE_INTERVAL", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# ── Sleep detection markers ──────────────────────────────────────────────────

SLEEP_TEXT_MARKERS = (
    "yes, get this app back up!",
    "this app has gone to sleep due to inactivity",
    "zzzz",
)
WAKE_BUTTON_LOCATORS = (
    (By.CSS_SELECTOR, "button[data-testid='wakeup-button-viewer']"),
    (By.CSS_SELECTOR, "button[data-testid='wakeup-button-owner']"),
    (By.CSS_SELECTOR, "button[data-testid='wakeup-button']"),
    (By.XPATH, "//button[normalize-space()='Yes, get this app back up!']"),
)
APP_CONTENT_SELECTORS = (
    "[data-testid='stAppViewContainer']",
    "[data-testid='stSidebar']",
    "[data-testid='stHeader']",
    "section.main",
    "main",
)

UNIQUE_STREAMLIT_APPS = list(dict.fromkeys(STREAMLIT_APPS))
LOG_LOCK = threading.Lock()


# ── Helpers ──────────────────────────────────────────────────────────────────

def log_message(log_file, message: str) -> None:
    timestamped = f"[{datetime.datetime.now()}] {message}"
    with LOG_LOCK:
        log_file.write(f"{timestamped}\n")
        log_file.flush()
        print(timestamped, flush=True)


def should_run_interval(log_file) -> bool:
    if not ENFORCE_WAKE_INTERVAL or WAKE_INTERVAL_HOURS <= 0:
        return True
    if not os.path.exists(STATE_FILE):
        return True

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as state_file:
            state = json.load(state_file)
        last_run_raw = state.get("last_run_utc")
        if not last_run_raw:
            return True

        last_run = datetime.datetime.fromisoformat(last_run_raw)
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=datetime.timezone.utc)

        elapsed = datetime.datetime.now(datetime.timezone.utc) - last_run
        if elapsed.total_seconds() < WAKE_INTERVAL_HOURS * 3600:
            log_message(log_file, f"Skipping run; last run {elapsed} ago")
            return False
    except Exception:
        return True

    return True


def write_state() -> None:
    state = {"last_run_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with open(STATE_FILE, "w", encoding="utf-8") as state_file:
        json.dump(state, state_file)


# ── Browser / Selenium helpers ───────────────────────────────────────────────

def create_driver():
    options = Options()
    options.page_load_strategy = "none"
    if CHROME_BINARY:
        options.binary_location = CHROME_BINARY
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-component-update")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-gpu")
    options.add_argument("--dns-prefetch-disable")
    options.add_argument("--disable-sync")
    options.add_argument("--metrics-recording-only")
    if CHROME_USER_DATA_DIR:
        options.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
    if CHROME_PROFILE_DIRECTORY:
        options.add_argument(f"--profile-directory={CHROME_PROFILE_DIRECTORY}")
    service = Service(executable_path=CHROMEDRIVER_PATH)
    return webdriver.Chrome(service=service, options=options)


def find_wake_button(driver):
    for locator in WAKE_BUTTON_LOCATORS:
        try:
            for button in driver.find_elements(*locator):
                if button.is_displayed() and button.is_enabled():
                    return button
        except Exception:
            continue
    return None


def sleep_marker_present(driver) -> bool:
    button = find_wake_button(driver)
    if button is not None:
        return True

    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
    except Exception:
        body_text = ""

    return any(marker in body_text for marker in SLEEP_TEXT_MARKERS)


def click_wake_button_if_available(driver) -> bool:
    button = find_wake_button(driver)
    if button is None:
        return False

    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center'});",
        button,
    )
    try:
        button.click()
    except Exception:
        driver.execute_script("arguments[0].click();", button)
    return True


def app_content_loaded(driver) -> bool:
    try:
        ready_state = driver.execute_script("return document.readyState") or ""
    except Exception:
        ready_state = ""

    if ready_state not in {"interactive", "complete"}:
        return False

    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text.strip()
    except Exception:
        body_text = ""

    lowered_body = body_text.lower()
    if any(marker in lowered_body for marker in SLEEP_TEXT_MARKERS):
        return False

    if len(body_text) >= 40:
        return True

    try:
        return any(
            driver.find_elements(By.CSS_SELECTOR, selector)
            for selector in APP_CONTENT_SELECTORS
        )
    except Exception:
        return False


def check_site(url: str) -> tuple[str, str]:
    driver = create_driver()
    try:
        driver.set_page_load_timeout(BROWSER_PAGELOAD_TIMEOUT_SECONDS)
        try:
            driver.get(url)
        except (TimeoutException, WebDriverException):
            try:
                driver.execute_script("window.stop();")
            except Exception:
                pass

        deadline = time.time() + SITE_WAIT_SECONDS
        while time.time() < deadline:
            if sleep_marker_present(driver):
                button_deadline = time.time() + BUTTON_APPEAR_WAIT_SECONDS
                while time.time() < button_deadline:
                    if click_wake_button_if_available(driver):
                        break
                    time.sleep(1)
                else:
                    return "errors", "sleep markers found but wake button never appeared"
                return "woken", "sleep marker found and wake button clicked"

            if app_content_loaded(driver):
                return "awake", "app content loaded"

            time.sleep(1)

        return "errors", "timed out waiting for app content or sleep marker"
    finally:
        driver.quit()


# ── Async orchestration ──────────────────────────────────────────────────────

async def process_site(
    index: int, total: int, url: str, log_file, semaphore
) -> tuple[str, str, str]:
    async with semaphore:
        log_message(log_file, f"Checking app {index}/{total}: {url}")
        try:
            state, detail = await asyncio.to_thread(check_site, url)
        except Exception as exc:
            state, detail = "errors", f"unexpected error: {exc}"
        return url, state, detail


async def main() -> None:
    with open(LOG_FILE, "a", encoding="utf-8") as log_file:
        log_message(log_file, "Execution started")
        log_message(
            log_file,
            f"Configured wake interval: every {WAKE_INTERVAL_HOURS} hour(s)",
        )
        log_message(
            log_file,
            f"Configured concurrency: up to "
            f"{min(MAX_CONCURRENT_APPS, len(UNIQUE_STREAMLIT_APPS))} app(s)",
        )

        if not should_run_interval(log_file):
            log_message(log_file, "Execution finished")
            return

        summary = {"awake": 0, "woken": 0, "errors": 0}
        total = len(UNIQUE_STREAMLIT_APPS)
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_APPS)

        tasks = [
            asyncio.create_task(
                process_site(index, total, url, log_file, semaphore)
            )
            for index, url in enumerate(UNIQUE_STREAMLIT_APPS, start=1)
        ]

        for task in asyncio.as_completed(tasks):
            url, state, detail = await task
            summary[state] += 1

            if state == "awake":
                log_message(log_file, f"App is already awake: {url} ({detail})")
            elif state == "woken":
                log_message(
                    log_file, f"App was asleep and is now awake: {url} ({detail})"
                )
            else:
                log_message(log_file, f"Wake check failed: {url} ({detail})")

        write_state()
        log_message(log_file, f"Summary: {summary}")
        log_message(log_file, "Execution finished")


if __name__ == "__main__":
    asyncio.run(main())
