import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class APIAgent:
    def __init__(self):
        self.cache = {}

    def get_market_data(self, symbols, start_date=None, end_date=None):
        """
        Fetch market data from Yahoo Finance with proper error handling and date parsing.
        
        Args:
            symbols: List of stock symbols to fetch
            start_date: Start date (YYYY-MM-DD format or None for 30 days ago)
            end_date: End date (YYYY-MM-DD format or None for today)
            
        Returns:
            Dictionary with symbol keys and DataFrame values, or empty dict if all fail
        """
        try:
            # Parse dates properly
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

            logger.info(f"Fetching market data for {symbols} from {start_date} to {end_date}")
            
            data = {}
            failed_symbols = []
            
            for symbol in symbols:
                try:
                    if symbol not in self.cache:
                        logger.info(f"Fetching data for {symbol}...")
                        ticker = yf.Ticker(symbol)
                        hist = ticker.history(start=start_date, end=end_date)
                        
                        if hist.empty:
                            logger.warning(f"No data returned for {symbol}")
                            failed_symbols.append(symbol)
                            continue
                        
                        # Reset index to make the date a column for easier serialization
                        hist = hist.reset_index()
                        hist['Date'] = hist['Date'].astype(str)
                        self.cache[symbol] = hist
                        logger.info(f"Successfully cached {symbol}: {len(hist)} rows")
                    
                    data[symbol] = self.cache[symbol]
                    
                except Exception as e:
                    logger.error(f"Error fetching data for {symbol}: {str(e)}")
                    failed_symbols.append(symbol)
                    continue
            
            if failed_symbols:
                logger.warning(f"Failed to fetch data for: {failed_symbols}")
            
            if not data:
                logger.error(f"Failed to fetch data for any symbols: {symbols}")
                return {}
            
            logger.info(f"Successfully fetched market data for {list(data.keys())}")
            return data
            
        except Exception as e:
            logger.error(f"Error in get_market_data: {str(e)}", exc_info=True)
            return {}

    def get_earnings(self, symbol):
        """
        Fetch earnings data for a given symbol using income statement.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Earnings DataFrame or None if failed
        """
        try:
            logger.info(f"Fetching earnings/income statement for {symbol}...")
            ticker = yf.Ticker(symbol)
            
            # Try to get income statement (new API)
            try:
                income_stmt = ticker.income_stmt
                if income_stmt is not None and not income_stmt.empty:
                    # Extract Net Income row if available
                    if 'Net Income' in income_stmt.index:
                        net_income = income_stmt.loc['Net Income']
                        # Convert to DataFrame with Year and Earnings columns
                        earnings_df = pd.DataFrame({
                            'Year': net_income.index.year if hasattr(net_income.index, 'year') else range(len(net_income)),
                            'Earnings': net_income.values
                        })
                        logger.info(f"Successfully fetched income statement for {symbol}")
                        return earnings_df
            except Exception as e:
                logger.warning(f"Could not fetch income_stmt for {symbol}: {str(e)}")
            
            # Try financials as fallback
            try:
                financials = ticker.financials
                if financials is not None and not financials.empty:
                    if 'Net Income' in financials.index:
                        net_income = financials.loc['Net Income']
                        earnings_df = pd.DataFrame({
                            'Year': net_income.index.year if hasattr(net_income.index, 'year') else range(len(net_income)),
                            'Earnings': net_income.values
                        })
                        logger.info(f"Successfully fetched financials for {symbol}")
                        return earnings_df
            except Exception as e:
                logger.warning(f"Could not fetch financials for {symbol}: {str(e)}")
            
            logger.warning(f"No earnings/financial data found for {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching earnings for {symbol}: {str(e)}")
            return None
    
    def serialize_market_data(self, data):
        """
        Convert market data DataFrames to JSON-serializable format.
        
        Args:
            data: Dictionary with symbol keys and DataFrame values
            
        Returns:
            Dictionary with symbol keys and serializable data
        """
        try:
            serialized = {}
            for symbol, df in data.items():
                if isinstance(df, pd.DataFrame):
                    # Convert to records format
                    records = df.to_dict(orient='records')
                    # Ensure all values are JSON serializable
                    serialized_records = []
                    for record in records:
                        serialized_record = {}
                        for key, value in record.items():
                            if pd.isna(value):
                                serialized_record[key] = None
                            elif isinstance(value, (int, float, str, bool, type(None))):
                                serialized_record[key] = value
                            else:
                                # Convert other types to string
                                serialized_record[key] = str(value)
                        serialized_records.append(serialized_record)
                    serialized[symbol] = serialized_records
                else:
                    serialized[symbol] = str(df)
            
            return serialized
        except Exception as e:
            logger.error(f"Error serializing market data: {str(e)}", exc_info=True)
            return {}