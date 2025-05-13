# AI Tool Usage Log

This document outlines the usage of AI tools, libraries, and models across the agents and services in the Multi-Agent Finance Assistant project.

---

## 1. Language Agent

- **Framework**: LangChain
- **Model Used**: OpenAI GPT-4 (via `openai.ChatCompletion`)
- **Prompt Engineering**:
  - Initial system prompt: `"You are a market analyst. Use retrieved chunks and numerical data to generate a concise, informative market brief."`
  - Dynamic prompt template incorporates:
    - AUM distribution
    - Earnings summary
    - Regional sentiment

- **RAG Interface**:
  - Retrieval pipeline built with LangChain’s `Retriever` and `ConversationalRetrievalChain`.
  - Utilizes FAISS as the vector store for top-k chunk retrieval.

---

## 2. Retriever Agent

- **Libraries**: LangChain, FAISS
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Vector Store**: FAISS
- **Tool Usage**:
  - Chunking and embedding of text documents (e.g., scraped filings or news).
  - Indexed documents via LangChain’s `FAISS.from_documents()`.
  - Retrieval confidence scored using cosine similarity.

---

## 3. Voice Agent

- **Speech-to-Text (STT)**:
  - **Tool**: OpenAI Whisper
  - **Model**: `base.en` used via `whisper` Python package
  - **Prompt Context**: Not needed (Whisper handles general STT)

- **Text-to-Speech (TTS)**:
  - **Tool**: pyttsx3 (offline TTS) / gTTS (Google TTS fallback)
  - **Custom Configurations**:
    - pyttsx3 rate and voice configured to sound professional and neutral.
  
- **Pipeline**:
  - Audio → Whisper → Text → LLM → Response → pyttsx3/gTTS → Audio output

---

## 4. API Agent

- **Toolkit**: `yfinance`, `alphavantage`, `pandas`
- **AI Tool Assistance**:
  - Code to extract and format risk exposure data was partially generated using GitHub Copilot.
  - Prompt to Copilot: _“Write a function that calculates Asia tech stock allocation based on AUM data from yfinance.”_

---

## 5. Scraping Agent

- **Toolkits Used**:
  - `BeautifulSoup` + `requests` for light HTML parsing
  - `newspaper3k` for simplified article text extraction (used for MCP)

- **AI Usage**:
  - GPT-4 used to generate the initial scraping logic and refine XPath queries.
  - Prompt example: _“Write a Python script to extract earnings surprise data from recent SEC filings.”_

---

## 6. Analysis Agent

- **Toolkit**: `pandas`, `numpy`, `scipy`
- **LLM Involvement**:
  - GPT-4 used to help design functions for calculating earnings surprises (difference between estimated vs actual).
  - Code suggestion prompt: _“Given earnings estimate and actual data, calculate percent surprise and summarize major outliers.”_

---

## 7. Orchestration (FastAPI + Routing Logic)

- **Agent Routing**: GPT-4 used to design the orchestration flow based on input type (voice/text) and fallback conditions.
- **Voice fallback logic**:
  - Retrieval confidence threshold set at 0.65.
  - Prompt to GPT-4: _“Suggest fallback logic when RAG confidence is low for market data queries.”_

---

## Summary

| Agent            | AI Tool Used             | Purpose                                     |
|------------------|--------------------------|---------------------------------------------|
| Language Agent   | GPT-4, LangChain         | Narrative synthesis from structured + RAG   |
| Retriever Agent  | FAISS, sentence-transformers | Embedding, document search                 |
| Voice Agent      | Whisper, pyttsx3/gTTS    | Voice input/output                          |
| API Agent        | GitHub Copilot, yfinance | Market data extraction                      |
| Scraping Agent   | GPT-4, BeautifulSoup     | Article/filing parsing                      |
| Analysis Agent   | GPT-4, pandas            | Quantitative summaries                      |
| Orchestrator     | GPT-4                    | Agent flow routing, fallback logic          |

---

> **Note**: All AI usage was responsibly logged, and no proprietary or paid LLMs were embedded in real-time inference without proper attribution or API keys.
