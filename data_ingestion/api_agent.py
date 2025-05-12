import yfinance as yf
import pandas as pd
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class APIAgent:
    def __init__(self):
        self.cache = {}

    def get_market_data(self, symbols, start_date=None, end_date=None):
        try:
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if not start_date:
                start_date = (datetime.now() - pd.Timedelta(days=30)).strftime('%Y-%m-%d')

            data = {}
            for symbol in symbols:
                if symbol not in self.cache:
                    ticker = yf.Ticker(symbol)
                    self.cache[symbol] = ticker.history(start=start_date, end=end_date)
                data[symbol] = self.cache[symbol]
            logger.info(f"Fetched market data for {symbols}")
            return data
        except Exception as e:
            logger.error(f"Error fetching market data: {str(e)}")
            return None

    def get_earnings(self, symbol):
        try:
            ticker = yf.Ticker(symbol)
            earnings = ticker.earnings
            logger.info(f"Fetched earnings for {symbol}")
            return earnings
        except Exception as e:
            logger.error(f"Error fetching earnings: {str(e)}")
            return None