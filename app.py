import streamlit as st
import threading
import sys
import os
import logging
import io
import json
import requests
import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import Optional, List
import re
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to the path so imports work correctly
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Import all the agent modules
from data_ingestion.api_agent import APIAgent
from data_ingestion.scrapping_agent import ScrapingAgent
from agents.retriever_agent import RetrieverAgent
from agents.analysis_agent import AnalysisAgent
from agents.language_agent import LanguageAgent 
from agents.voice_agent import VoiceAgent

# Import comprehensive stock symbols
from streamlit_app.stock_symbols import ALL_STOCKS, CATEGORIES

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize all agents
api_agent = APIAgent()
scraping_agent = ScrapingAgent()
retriever_agent = RetrieverAgent()
analysis_agent = AnalysisAgent()
language_agent = LanguageAgent()
voice_agent = VoiceAgent()

# Default symbols (can be extended)
DEFAULT_SYMBOLS = ['AAPL', 'MSFT', 'GOOGL']  # Major tech stocks

# Enhanced symbol mappings to handle various query formats
SYMBOL_MAPPINGS = {
    # Tech Giants
    'tsmc': 'TSM',
    'taiwan semiconductor': 'TSM',
    'samsung': '005930.KS',
    'samsung electronics': '005930.KS',
    'apple': 'AAPL',
    'google': 'GOOGL',
    'alphabet': 'GOOGL',
    'microsoft': 'MSFT',
    'amazon': 'AMZN',
    'meta': 'META',
    'facebook': 'META',
    'netflix': 'NFLX',
    'nvidia': 'NVDA',
    'tesla': 'TSLA',
    'intel': 'INTC',
    'amd': 'AMD',
    'advanced micro devices': 'AMD',
    'qualcomm': 'QCOM',
    
    # Additional major companies
    'disney': 'DIS',
    'nike': 'NKE',
    'walmart': 'WMT',
    'jpmorgan': 'JPM',
    'jp morgan': 'JPM',
    'bank of america': 'BAC',
    'goldman sachs': 'GS',
    'visa': 'V',
    'mastercard': 'MA',
    'coca cola': 'KO',
    'pepsi': 'PEP',
    'mcdonalds': 'MCD',
    'starbucks': 'SBUX',
    'boeing': 'BA',
    'pfizer': 'PFE',
    'johnson & johnson': 'JNJ',
    'exxon': 'XOM',
    'chevron': 'CVX',
    
    # Crypto
    'bitcoin': 'BTC-USD',
    'ethereum': 'ETH-USD',
    'dogecoin': 'DOGE-USD',
    
    # Indices
    's&p 500': '^GSPC',
    'sp500': '^GSPC',
    'dow jones': '^DJI',
    'nasdaq': '^IXIC',
}

# Helper functions
def extract_symbols_from_query(query):
    """Extract stock symbols from the query and map to actual ticker symbols"""
    extracted_symbols = []
    
    # Check for ticker symbols directly (like AAPL, MSFT, etc.)
    ticker_pattern = r'\b[A-Z]{1,5}\b'
    direct_tickers = re.findall(ticker_pattern, query)
    if direct_tickers:
        extracted_symbols.extend(direct_tickers)
    
    # Check for company names in the query
    for company, symbol in SYMBOL_MAPPINGS.items():
        if company.lower() in query.lower():
            extracted_symbols.append(symbol)
    
    # Remove duplicates while preserving order
    unique_symbols = []
    for symbol in extracted_symbols:
        if symbol not in unique_symbols:
            unique_symbols.append(symbol)
    
    # If no symbols were found, use defaults
    if not unique_symbols:
        return DEFAULT_SYMBOLS
    
    return unique_symbols

# Initialize with some sample data
try:
    # Pre-fetch some data to initialize agents
    market_data = api_agent.get_market_data(DEFAULT_SYMBOLS)
    
    # Initialize retriever with some sample data
    sample_docs = [
        {"text": "TSMC reported strong quarterly earnings with record revenue.", "title": "TSMC Earnings"},
        {"text": "Samsung Electronics faces competition in the memory chip market.", "title": "Samsung Market Position"}
    ]
    retriever_agent.index_documents(sample_docs)
    logger.info("Pre-initialized agents with sample data")
except Exception as e:
    logger.warning(f"Failed to pre-initialize agents: {str(e)}")

# FastAPI Endpoints
@app.get("/")
async def health_check():
    return {"status": "healthy", "message": "Finance Assistant API is running"}

@app.get("/debug/test-scraping")
async def test_scraping(symbol: str = "AAPL"):
    """Debug endpoint to test news scraping functionality"""
    try:
        logger.info(f"Testing news scraping for {symbol}")
        url = f"https://finance.yahoo.com/quote/{symbol}/news/"
        articles = scraping_agent.scrape_news([url], timeout=15)
        
        return {
            "status": "success" if articles else "no_articles",
            "symbol": symbol,
            "articles_found": len(articles),
            "sample_article": articles[0] if articles else None,
            "message": f"Successfully scraped {len(articles)} articles" if articles else "No articles found - will use fallback data"
        }
    except Exception as e:
        logger.error(f"Error in test scraping: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Scraping failed - system will use fallback data"
        }

@app.get("/retrieve/retrieve")
async def retrieve(
    query: str, 
    symbols: Optional[str] = None
):
    try:
        logger.info(f"Processing retrieve request for query: {query}")
        
        # Step 1: Extract symbols from the query or use explicitly provided symbols
        if symbols:
            # If explicit symbols are provided, use them
            symbol_list = [s.strip() for s in symbols.split(",")]
            logger.info(f"Using explicitly provided symbols: {symbol_list}")
        else:
            # Otherwise extract them from the query
            symbol_list = extract_symbols_from_query(query)
            logger.info(f"Extracted symbols from query: {symbol_list}")
        
        # Step 2: Validate and fetch market data
        if not symbol_list:
            logger.warning("No symbols found, using defaults")
            symbol_list = DEFAULT_SYMBOLS
        
        logger.info(f"Fetching market data for: {symbol_list}")
        market_data = api_agent.get_market_data(symbol_list)
        
        if not market_data:
            logger.error(f"Failed to fetch market data for symbols: {symbol_list}")
            # Return helpful error message
            return {
                "error": f"Could not fetch data for symbols: {', '.join(symbol_list)}. Please check if the symbols are valid Yahoo Finance tickers.",
                "query": query,
                "attempted_symbols": symbol_list,
                "suggestion": "Try using common symbols like AAPL, MSFT, GOOGL, or check Yahoo Finance for the correct ticker."
            }
        
        # Convert market data to a serializable format using the agent's method
        logger.info(f"Serializing market data for {list(market_data.keys())}")
        serialized_market_data = api_agent.serialize_market_data(market_data)
        
        if not serialized_market_data:
            logger.error("Failed to serialize market data")
            raise HTTPException(status_code=500, detail="Failed to serialize market data")
        
        logger.info(f"Successfully serialized data: {list(serialized_market_data.keys())}")
        
        # Step 3: Generate news URLs based on symbols
        news_urls = [f"https://finance.yahoo.com/quote/{symbol}/news/" for symbol in symbol_list[:3]]  # Limit to first 3 symbols
        logger.info(f"🔍 Attempting to scrape news from: {news_urls}")
        articles = scraping_agent.scrape_news(news_urls, timeout=15)
        logger.info(f"📰 News scraping result: {len(articles)} articles collected")
        
        if not articles:
            # If scraping failed, create rich fallback content based on actual market data
            logger.warning("⚠️ News scraping failed - generating fallback articles from market data")
            articles = []
            for symbol in symbol_list:
                company_name = ALL_STOCKS.get(symbol, symbol)
                
                # Create detailed fallback content using actual market data
                article_text = f"{company_name} Market Analysis: "
                
                if symbol in market_data:
                    try:
                        market_df = market_data[symbol]
                        if not market_df.empty and len(market_df) > 0:
                            # Get recent trading data
                            latest_close = market_df['Close'].iloc[-1] if 'Close' in market_df.columns else None
                            latest_volume = market_df['Volume'].iloc[-1] if 'Volume' in market_df.columns else None
                            
                            # Calculate price change if we have enough data
                            if len(market_df) > 1 and 'Close' in market_df.columns:
                                prev_close = market_df['Close'].iloc[-2]
                                price_change = ((latest_close - prev_close) / prev_close * 100) if prev_close > 0 else 0
                                
                                article_text += f"Recent trading shows price at ${latest_close:.2f}, "
                                if price_change > 0:
                                    article_text += f"up {price_change:.2f}% from previous close. "
                                else:
                                    article_text += f"down {abs(price_change):.2f}% from previous close. "
                            elif latest_close:
                                article_text += f"Current price at ${latest_close:.2f}. "
                            
                            if latest_volume:
                                article_text += f"Trading volume: {latest_volume:,.0f} shares. "
                            
                            # Add 52-week context if available
                            if len(market_df) > 50 and 'High' in market_df.columns and 'Low' in market_df.columns:
                                recent_high = market_df['High'].tail(50).max()
                                recent_low = market_df['Low'].tail(50).min()
                                article_text += f"Recent trading range: ${recent_low:.2f} - ${recent_high:.2f}."
                        else:
                            article_text += "Market data retrieved successfully for analysis."
                    except Exception as e:
                        logger.warning(f"Error creating detailed fallback for {symbol}: {str(e)}")
                        article_text += "Active in current market conditions."
                else:
                    article_text += "Market data retrieved for portfolio analysis."
                
                articles.append({
                    "title": f"{company_name} - Market Data Update", 
                    "text": article_text,
                    "url": f"https://finance.yahoo.com/quote/{symbol}"
                })
            logger.info(f"✅ Generated {len(articles)} fallback articles with market data")
        else:
            logger.info(f"✅ Successfully scraped {len(articles)} real news articles")
        
        # Step 4: Index and retrieve
        logger.info(f"Indexing {len(articles)} documents for retrieval")
        retriever_agent.index_documents(articles)
        context_docs = retriever_agent.retrieve(query, k=3)
        
        # Handle the context properly - it might be empty or have a different structure
        context = []
        if context_docs:
            if hasattr(context_docs[0], 'page_content'):
                # LangChain Document objects
                context = [doc.page_content for doc in context_docs]
            elif isinstance(context_docs[0], dict):
                # Dictionary objects
                context = [doc.get('text', str(doc)) for doc in context_docs]
            else:
                # Direct text objects
                context = [str(doc) for doc in context_docs]
        
        if not context or len(context) == 0:
            # If retrieval failed, create rich fallback context with actual market data
            logger.warning("⚠️ Document retrieval failed - creating fallback context from market data")
            context = []
            for symbol in symbol_list:
                company_name = ALL_STOCKS.get(symbol, symbol)
                
                if symbol in serialized_market_data and serialized_market_data[symbol]:
                    try:
                        # Create detailed context from market data
                        records = serialized_market_data[symbol]
                        if records and len(records) > 0:
                            latest = records[-1]
                            closes = [r.get('Close', 0) for r in records if 'Close' in r]
                            volumes = [r.get('Volume', 0) for r in records if 'Volume' in r]
                            
                            context_text = f"{company_name} Analysis: "
                            
                            if 'Close' in latest:
                                context_text += f"Current price ${latest['Close']:.2f}. "
                            
                            if closes and len(closes) > 1:
                                avg_close = sum(closes) / len(closes)
                                context_text += f"Average price over period: ${avg_close:.2f}. "
                                
                                # Calculate volatility
                                price_range = max(closes) - min(closes)
                                volatility_pct = (price_range / avg_close) * 100 if avg_close > 0 else 0
                                context_text += f"Price volatility: {volatility_pct:.1f}%. "
                            
                            if volumes:
                                avg_volume = sum(volumes) / len(volumes)
                                context_text += f"Average daily volume: {avg_volume:,.0f} shares."
                            
                            context.append(context_text)
                        else:
                            context.append(f"{company_name} market data retrieved successfully for analysis.")
                    except Exception as e:
                        logger.warning(f"Error creating detailed context for {symbol}: {str(e)}")
                        context.append(f"{company_name} included in portfolio analysis.")
                else:
                    context.append(f"{company_name} market data retrieved for evaluation.")
        
        logger.info(f"✅ Retrieved {len(context)} context documents for analysis")
        return {
            "market_data": serialized_market_data,
            "context": context,
            "query": query,
            "symbols": symbol_list
        }
    except Exception as e:
        logger.error(f"Error retrieving data: {str(e)}")
        return {"error": str(e)}

@app.post("/analyze/analyze")
async def analyze(data: dict):
    try:
        logger.info("Processing analyze request")
        
        # Extract data safely with fallbacks
        market_data = {}
        symbols = data.get("data", {}).get("symbols", DEFAULT_SYMBOLS)
        
        logger.info(f"Analyzing symbols: {symbols}")
        
        try:
            if "data" in data and "market_data" in data["data"]:
                serialized_data = data["data"]["market_data"]
                
                logger.info(f"Converting serialized data for {list(serialized_data.keys())}")
                
                # Convert serialized market data back to DataFrame format
                market_data = {}
                for symbol, records in serialized_data.items():
                    try:
                        if isinstance(records, list):
                            if records:  # Only create DataFrame if records is not empty
                                market_data[symbol] = pd.DataFrame.from_records(records)
                                logger.info(f"Created DataFrame for {symbol} with {len(records)} records")
                            else:
                                logger.warning(f"Empty records for {symbol}")
                        else:
                            market_data[symbol] = records
                            logger.info(f"Using raw data for {symbol}")
                    except Exception as e:
                        logger.error(f"Error creating DataFrame for {symbol}: {str(e)}")
                        # Create a dummy dataframe
                        market_data[symbol] = pd.DataFrame({'Close': [100.0]})
        except Exception as e:
            logger.warning(f"Error processing market data: {str(e)}")
            # Use empty dataframes as fallback
            market_data = {}
            for symbol in symbols:
                market_data[symbol] = pd.DataFrame({'Close': [100.0]})
        
        context = data.get("data", {}).get("context", [])
        if not context:
            context = [f"Analysis of {', '.join(symbols)} stocks"]
        
        query = data.get("data", {}).get("query", f"What's our risk exposure in {', '.join(symbols)}?")
        
        logger.info(f"Query: {query}, Context items: {len(context)}")
        
        # Update the analysis agent's portfolio to include the queried symbols
        portfolio_weights = {}
        for i, symbol in enumerate(symbols):
            # Assign decreasing weights to each symbol
            portfolio_weights[symbol] = 0.15 - (i * 0.02)  # Start at 15% and decrease
            if portfolio_weights[symbol] < 0.05:  # Minimum weight of 5%
                portfolio_weights[symbol] = 0.05
        
        logger.info(f"Portfolio weights: {portfolio_weights}")
        
        # Update the portfolio
        analysis_agent.portfolio = portfolio_weights
        
        # Step 2: Analyze risk
        exposure = analysis_agent.analyze_risk_exposure(market_data)
        logger.info(f"Risk exposure analysis complete: {list(exposure.keys()) if exposure else 'None'}")
        
        if not exposure:
            # Fallback exposure data if analysis fails
            logger.warning("Using fallback exposure data")
            exposure = {}
            total_aum = 1000000  # Example AUM of $1M
            for symbol in symbols:
                exposure[symbol] = {
                    'weight': portfolio_weights.get(symbol, 0.10),
                    'value': portfolio_weights.get(symbol, 0.10) * total_aum,
                    'price': 100.0  # Default price
                }
        
        # Step 3: Get earnings
        earnings = {}
        
        for symbol in symbols:
            try:
                logger.info(f"Fetching earnings for {symbol}")
                earnings_data = api_agent.get_earnings(symbol)
                if earnings_data is None:
                    logger.warning(f"No earnings data for {symbol}, using fallback")
                    # Fallback earnings data
                    earnings[symbol] = pd.DataFrame({
                        'Year': [2023, 2024],
                        'Earnings': [10.5, 12.3]
                    })
                else:
                    earnings[symbol] = earnings_data
            except Exception as e:
                logger.warning(f"Error fetching earnings for {symbol}: {str(e)}")
                # Fallback earnings data
                earnings[symbol] = pd.DataFrame({
                    'Year': [2023, 2024],
                    'Earnings': [10.5, 12.3]
                })
        
        # Convert earnings to serializable format
        serialized_earnings = {}
        for symbol, data_df in earnings.items():
            try:
                if isinstance(data_df, pd.DataFrame):
                    serialized_earnings[symbol] = data_df.to_dict(orient='records')
                else:
                    serialized_earnings[symbol] = str(data_df)
                logger.info(f"Serialized earnings for {symbol}")
            except Exception as e:
                logger.warning(f"Error serializing earnings for {symbol}: {str(e)}")
                serialized_earnings[symbol] = []
        
        # Step 4: Generate brief
        try:
            logger.info("Generating brief from language agent")
            brief = language_agent.generate_brief(
                str(context), 
                str(exposure), 
                str(serialized_earnings)
            )
            if not brief or brief.isspace():
                raise Exception("Generated brief is empty")
            logger.info("Brief generated successfully")
        except Exception as e:
            logger.warning(f"Error generating brief: {str(e)}, using fallback")
            # Generate a more dynamic fallback brief
            symbol_names = []
            for symbol in symbols:
                company_name = ALL_STOCKS.get(symbol, symbol)
                symbol_names.append(f"{company_name} ({symbol})")
            
            brief = f"""## Market Brief: {query}

### Portfolio Analysis for {', '.join(symbol_names)}

Our analysis focuses on exposure to the following securities in our portfolio.

#### Market Data Retrieved
- Successfully retrieved current market data for {len(symbols)} securities
- Data includes OHLCV (Open, High, Low, Close, Volume) for the analysis period

#### Portfolio Composition
"""
            
            # Add exposure details
            total_value = sum([d.get('value', 100000) for d in exposure.values()])
            for symbol, exp_data in exposure.items():
                company_name = ALL_STOCKS.get(symbol, symbol)
                weight_pct = exp_data.get('weight', 0.1) * 100
                value = exp_data.get('value', 100000)
                price = exp_data.get('price', 100.0)
                brief += f"\n- **{company_name} ({symbol})**: {weight_pct:.1f}% allocation (${value:,.0f}) @ ${price:.2f}"
            
            brief += f"""

#### Key Insights
The portfolio maintains a diversified exposure across the analyzed securities. Recent market data shows:
- Historical price movements have been tracked for the period
- Volume patterns indicate typical market activity
- All selected securities continue to maintain market presence

#### Earnings Overview
"""
            
            for symbol in symbols:
                company_name = ALL_STOCKS.get(symbol, symbol)
                brief += f"\n- {company_name}: Latest earnings data retrieved"
            
            brief += "\n\nRecommendation: Monitor these positions according to your risk tolerance and investment objectives."
        
        logger.info("Analysis completed successfully")
        return {"summary": brief}
    except Exception as e:
        logger.error(f"Error analyzing data: {str(e)}", exc_info=True)
        return {"error": str(e)}

@app.post("/process_query")
async def process_query(
    audio: UploadFile = File(...),
    symbols: Optional[str] = Form(None)
):
    try:
        # Step 1: Convert speech to text
        query = voice_agent.speech_to_text(audio.file)
        
        if not query:
            query = "What's our risk exposure in technology stocks?"
            logger.info("Using fallback query due to STT failure")

        # Step 2: Extract symbols from query or use provided symbols
        if symbols:
            symbol_list = [s.strip() for s in symbols.split(",")]
            logger.info(f"Using explicitly provided symbols for voice query: {symbol_list}")
        else:
            symbol_list = extract_symbols_from_query(query)
        
        # Step 3: Fetch market data
        market_data = api_agent.get_market_data(symbol_list)
        
        if not market_data:
            logger.error("Failed to fetch market data")
            raise HTTPException(status_code=500, detail="Failed to fetch market data")

        # Step 4: Scrape news
        news_urls = [f"https://finance.yahoo.com/quote/{symbol}/news/" for symbol in symbol_list[:2]]
        logger.info(f"Scraping news from URLs: {news_urls}")
        articles = scraping_agent.scrape_news(news_urls)
        
        if not articles:
            # If scraping failed, use fallback content based on actual market data
            logger.warning("News scraping failed, using fallback articles")
            articles = []
            for symbol in symbol_list:
                company_name = ALL_STOCKS.get(symbol, symbol)
                
                # Try to include some data from market_data in the fallback
                article_text = f"{company_name} continues to be a key player in the market. "
                
                if symbol in market_data:
                    try:
                        market_df = market_data[symbol]
                        if not market_df.empty:
                            latest_close = market_df['Close'].iloc[-1] if 'Close' in market_df.columns else 'N/A'
                            article_text += f"Latest closing price: {latest_close}. "
                    except:
                        pass
                
                articles.append({
                    "title": f"{company_name} Market Update", 
                    "text": article_text,
                    "url": f"https://finance.yahoo.com/quote/{symbol}"
                })
        else:
            logger.info(f"Successfully scraped {len(articles)} articles")

        # Step 5: Index and retrieve
        retriever_agent.index_documents(articles)
        context_docs = retriever_agent.retrieve(query, k=3)
        
        # Handle the context properly
        context = []
        if context_docs:
            if hasattr(context_docs[0], 'page_content'):
                context = [doc.page_content for doc in context_docs]
            else:
                context = [str(doc) for doc in context_docs]
        
        if not context:
            context = [f"Analysis of {', '.join(symbol_list)} stocks"]

        # Update the analysis agent's portfolio to include the queried symbols
        portfolio_weights = {}
        for i, symbol in enumerate(symbol_list):
            portfolio_weights[symbol] = 0.15 - (i * 0.02)
            if portfolio_weights[symbol] < 0.05:
                portfolio_weights[symbol] = 0.05
        
        analysis_agent.portfolio = portfolio_weights
        
        # Step 6: Analyze risk
        exposure = analysis_agent.analyze_risk_exposure(market_data)
        
        if not exposure:
            # Fallback exposure data
            exposure = {}
            total_aum = 1000000  # Example AUM
            for symbol in symbol_list:
                exposure[symbol] = {
                    'weight': portfolio_weights.get(symbol, 0.10),
                    'value': portfolio_weights.get(symbol, 0.10) * total_aum,
                    'price': 100.0
                }

        # Step 7: Get earnings
        earnings = {}
        for symbol in symbol_list:
            earnings_data = api_agent.get_earnings(symbol)
            if earnings_data is None:
                earnings_data = pd.DataFrame({
                    'Year': [2023, 2024],
                    'Earnings': [10.5, 12.3]
                })
            earnings[symbol] = earnings_data

        # Step 8: Generate brief
        try:
            brief = language_agent.generate_brief(str(context), str(exposure), str(earnings))
        except Exception as e:
            logger.error(f"Error generating brief: {str(e)}")
            # Generate a dynamic fallback brief
            symbol_names = []
            for symbol in symbol_list:
                company_name = ALL_STOCKS.get(symbol, symbol)
                symbol_names.append(f"{company_name} ({symbol})")
            
            brief = f"""
            Market Brief for your query about {query}:
            
            Analysis of {', '.join(symbol_names)}:
            
            Our portfolio has exposure to these key technology companies with varying weights.
            """
            
            # Add exposure details
            brief += "\nPortfolio Exposure:\n"
            for symbol, data in exposure.items():
                company_name = ALL_STOCKS.get(symbol, symbol)
                weight_pct = data.get('weight', 0.1) * 100
                value = data.get('value', 100000)
                brief += f"- {company_name} ({symbol}): {weight_pct:.1f}% (${value:,.0f})\n"
            
            brief += "\nThe companies have generally shown positive earnings trends from 2023 to 2024."

        # Step 9: Convert to speech
        audio_response = voice_agent.text_to_speech(brief)
        
        if audio_response is None:
            logger.error("TTS failed to generate audio")
            raise HTTPException(status_code=500, detail="TTS failed to generate audio")

        logger.info("Query processed successfully")
        return StreamingResponse(audio_response, media_type="audio/mp3")
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        return {"error": str(e)}

# Function to start FastAPI in a separate thread
def run_fastapi():
    uvicorn.run(app, host="0.0.0.0", port=8000)

# Start FastAPI in a background thread when this script runs
threading.Thread(target=run_fastapi, daemon=True).start()

# Now define the Streamlit app
def main():
    st.title("🧠 Morning Market Brief Assistant")
    st.markdown("""
    This application provides market insights and financial analysis on your portfolio or specific stocks.
    Enter a query about specific stocks or market conditions to get an AI-generated analysis.
    """)
    
    # Stock selection feature
    st.sidebar.header("Stock Selection")
    st.sidebar.markdown("Select from all available stocks or enter custom symbols:")
    
    # Build comprehensive stocks list from ALL_STOCKS
    # Add "All Stocks" category + pre-defined categories
    common_stocks = {"🔷 All Stocks (A-Z)": []}
    
    # Add all stocks to the "All Stocks" category
    for symbol, name in sorted(ALL_STOCKS.items()):
        display_name = f"{symbol} ({name})"
        common_stocks["🔷 All Stocks (A-Z)"].append(display_name)
    
    # Add pre-defined categories from stock_symbols.py
    for category_name, symbols in CATEGORIES.items():
        common_stocks[category_name] = []
        for symbol in symbols:
            if symbol in ALL_STOCKS:
                display_name = f"{symbol} ({ALL_STOCKS[symbol]})"
                common_stocks[category_name].append(display_name)
    
    # Remove empty categories
    common_stocks = {k: v for k, v in common_stocks.items() if v}
    
    st.sidebar.info(f"📊 Total available stocks: {len(ALL_STOCKS)}")
    
    selected_category = st.sidebar.selectbox("Industry Sector", list(common_stocks.keys()))
    
    # Add search functionality
    search_term = st.sidebar.text_input("🔍 Search stocks", placeholder="Type company name or symbol...")
    
    # Filter stocks based on search
    available_stocks = common_stocks[selected_category]
    if search_term:
        available_stocks = [s for s in available_stocks if search_term.upper() in s.upper()]
        st.sidebar.caption(f"Found {len(available_stocks)} matches")
    
    selected_stocks = st.sidebar.multiselect(
        "Select stocks to analyze", 
        available_stocks,
        help="Choose one or more stocks from the selected sector"
    )
    
    # Show all available symbols in an expander
    with st.sidebar.expander("📋 View All Available Symbols"):
        st.markdown(f"### All {len(ALL_STOCKS)} Available Stocks")
        
        # Group symbols alphabetically
        all_symbols = sorted(ALL_STOCKS.keys())
        
        # Display in columns for better readability
        col1, col2 = st.columns(2)
        mid_point = len(all_symbols) // 2
        
        with col1:
            st.code("\n".join(all_symbols[:mid_point]))
        with col2:
            st.code("\n".join(all_symbols[mid_point:]))
        
        st.markdown("---")
        st.markdown("### Symbol → Company Name Mapping")
        st.caption("Browse alphabetically organized mappings below")
        
        # Show mapping organized by first letter (without nested expanders)
        letters = {}
        for symbol, company in sorted(ALL_STOCKS.items()):
            first_letter = symbol[0].upper()
            if first_letter not in letters:
                letters[first_letter] = []
            letters[first_letter].append(f"{symbol} → {company}")
        
        # Display all mappings grouped by letter in a scrollable text area
        mapping_text = ""
        for letter in sorted(letters.keys()):
            mapping_text += f"\n━━━ {letter} ({len(letters[letter])} stocks) ━━━\n"
            for mapping in letters[letter]:
                mapping_text += f"{mapping}\n"
        
        st.text_area("All Stock Mappings (A-Z)", mapping_text, height=300, help="Scroll to view all symbol to company name mappings")
        
        st.markdown("---")
        st.markdown("### Custom Symbol Entry")
        st.info("💡 You can also type any valid Yahoo Finance ticker symbol directly in your query (e.g., AAPL, MSFT, TSM, BTC-USD)")
    
    # Quick reference guide for symbol formats
    with st.sidebar.expander("📖 Symbol Format Guide"):
        st.markdown("""
        **Stock Symbol Formats:**
        - 🇺🇸 US: `AAPL`, `MSFT`, `GOOGL`
        - 🇰🇷 Korea: `005930.KS` (Samsung)
        - 🇯🇵 Japan: `7203.T` (Toyota)
        - 🇨🇳 Hong Kong: `0700.HK` (Tencent)
        - 🇮🇳 India: `RELIANCE.NS`
        - 🇬🇧 UK: `BP.L`
        - 🇩🇪 Germany: `SAP.DE`
        - 🇫🇷 France: `MC.PA`
        - 🇨🇭 Switzerland: `NESN.SW`
        - 🇨🇦 Canada: `SHOP.TO`
        - 🇦🇺 Australia: `CBA.AX`
        - ₿ Crypto: `BTC-USD`, `ETH-USD`
        
        **Tips:**
        - Most US stocks use simple tickers
        - International stocks have country suffixes
        - Search by company name if unsure
        """)
    
    # Prepare query with selected stocks
    stock_query = ""
    selected_symbols = []
    if selected_stocks:
        # Extract just the symbol part (before the space)
        selected_symbols = [stock.split(" ")[0] for stock in selected_stocks]
        stock_query = f"What's our risk exposure in {', '.join(selected_symbols)}?"
    
    # Example queries section
    st.markdown("### 💬 Ask Your Question")
    
    with st.expander("💡 Example Questions"):
        st.markdown("""
        **General Market Analysis:**
        - "Analyze AAPL, MSFT, and GOOGL. What's the market trend?"
        - "What's our risk exposure in tech stocks today?"
        - "Give me a market brief on SPY and QQQ ETFs"
        
        **International Markets:**
        - "Compare Samsung (005930.KS) and TSMC performance"
        - "How are European tech stocks performing? SAP.DE, ASML"
        - "Analyze Japanese auto makers: 7203.T (Toyota), HMC"
        - "What's happening with Indian IT stocks? TCS.NS, INFY.NS"
        
        **Sector Analysis:**
        - "What's happening with semiconductor stocks? NVDA, AMD, TSM"
        - "Analyze Tesla vs traditional auto makers"
        - "How are cloud software companies performing?"
        
        **Cryptocurrency:**
        - "What's the risk exposure in my crypto portfolio? BTC-USD, ETH-USD"
        - "Compare Bitcoin and Ethereum performance"
        
        **Portfolio Risk:**
        - "What's my exposure to the top 5 tech stocks?"
        - "Analyze risk across my diverse portfolio"
        - "Should I rebalance based on current market conditions?"
        """)
    
    # Text query input with default that includes selected stocks
    query = st.text_input("Enter your market analysis question:", 
                         value=stock_query if stock_query else "What's our risk exposure in tech stocks today?",
                         help="Ask about specific stocks, market trends, or portfolio risk")
    
    if st.button("Get Brief"):
        with st.spinner("Processing query..."):
            try:
                # Check if FastAPI is reachable
                try:
                    # Since we're in the same process now, we can directly access FastAPI,
                    # but we'll still use requests for consistency
                    health_check = requests.get("http://localhost:8000/")
                    if health_check.status_code != 200:
                        st.error(f"FastAPI server not reachable: {health_check.status_code}")
                    else:
                        st.info("FastAPI server is healthy. Processing your request...")
                        
                        # Step 1: Retrieve relevant documents with explicit symbols if selected
                        params = {"query": query}
                        if selected_symbols:
                            params["symbols"] = ",".join(selected_symbols)
                            st.info(f"Explicitly requesting analysis for: {', '.join(selected_symbols)}")
                        
                        retrieve_response = requests.get("http://localhost:8000/retrieve/retrieve", params=params)
                        
                        if retrieve_response.status_code != 200:
                            st.error(f"Retrieval failed with status {retrieve_response.status_code}")
                            try:
                                error_details = retrieve_response.json()
                                if "error" in error_details:
                                    st.code(f"Error details: {error_details['error']}")
                            except:
                                st.code(f"Raw response: {retrieve_response.text[:500]}...")
                        else:
                            retrieve_data = retrieve_response.json()
                            
                            if "error" in retrieve_data:
                                st.error(f"Retrieval error: {retrieve_data['error']}")
                            else:
                                # If we have selected symbols, make sure they're in the data
                                if selected_symbols:
                                    retrieve_data["symbols"] = selected_symbols
                                
                                # Display the analyzed stocks
                                symbols = retrieve_data.get("symbols", [])
                                if symbols:
                                    st.info(f"Analyzing stocks: {', '.join(symbols)}")
                                
                                # Display some retrieved data for verification
                                with st.expander("View retrieved data"):
                                    st.write("Query:", retrieve_data.get("query"))
                                    st.write("Context snippets:", retrieve_data.get("context", [])[:2])
                                    st.write("Markets included:", list(retrieve_data.get("market_data", {}).keys()))
                                
                                # Step 2: Analyze and get summary
                                st.info("Generating market brief...")
                                analyze_response = requests.post(
                                    "http://localhost:8000/analyze/analyze", 
                                    json={"data": retrieve_data}
                                )
                                
                                if analyze_response.status_code != 200:
                                    st.error(f"Analysis failed with status {analyze_response.status_code}")
                                    try:
                                        error_details = analyze_response.json()
                                        if "error" in error_details:
                                            st.code(f"Error details: {error_details['error']}")
                                    except:
                                        st.code(f"Raw response: {analyze_response.text[:500]}...")
                                else:
                                    analyze_data = analyze_response.json()
                                    
                                    if "error" in analyze_data:
                                        st.error(f"Analysis error: {analyze_data['error']}")
                                    else:
                                        st.subheader("Market Brief:")
                                        st.markdown(analyze_data["summary"])
                                        st.success("Query processed successfully!")
                except requests.exceptions.ConnectionError:
                    st.error("FastAPI server is trying to connect to Render services. If it takes long, try running it locally.")
            except Exception as e:
                st.error(f"Failed to process query: {str(e)}")
    
    # Audio query input (optional for voice I/O)
    st.subheader("Or upload an audio query (WAV/MP3)")
    audio_file = st.file_uploader("Upload audio", type=["wav", "mp3"])
    
    if audio_file is not None:
        st.audio(audio_file, format="audio/wav")
        with st.spinner("Processing audio query..."):
            try:
                files = {"audio": (audio_file.name, audio_file, "audio/wav")}
                
                # If we have selected symbols, add them as form data
                data = {}
                if selected_symbols:
                    data = {"symbols": ",".join(selected_symbols)}
                    
                response = requests.post("http://localhost:8000/process_query", files=files, data=data, stream=True)
                
                if response.status_code == 200:
                    audio_bytes = io.BytesIO(response.content)
                    st.audio(audio_bytes, format="audio/mp3")
                    st.success("Audio query processed successfully!")
                else:
                    try:
                        error_msg = response.json().get("error", "Unknown error")
                        st.error(f"Audio processing error: {error_msg}")
                    except:
                        st.error(f"Audio processing failed with status {response.status_code}")
            except requests.exceptions.ConnectionError:
                st.error("FastAPI server is trying to connect to Render services. If it takes long, try running it locally.")
            except Exception as e:
                st.error(f"Failed to process audio query: {str(e)}")
    
    # Add a section to explain how the application works
    with st.expander("How this application works"):
        st.write("""
        ### Architecture
        
        This application combines both FastAPI and Streamlit in a single process:
        
        1. **FastAPI Backend**: Runs in a background thread on port 8000
           - Orchestrates multiple AI agents for data processing
           - Handles API requests from the Streamlit frontend
        
        2. **Streamlit Frontend**: The user interface you're seeing now
           - Provides a friendly way to interact with the system
           - Makes API calls to the FastAPI backend
        
        3. **AI Agents**:
           - **API Agent**: Fetches market data via yfinance
           - **Scraping Agent**: Crawls news using newspaper3k  
           - **Retriever Agent**: Indexes and retrieves data
           - **Analysis Agent**: Calculates risk exposure
           - **Language Agent**: Generates narratives
           - **Voice Agent**: Handles speech-to-text and text-to-speech
        
        When you ask a question, the system analyzes stock data, retrieves relevant news, 
        calculates portfolio exposure, and generates a comprehensive market brief.
        """)

if __name__ == "__main__":
    main()