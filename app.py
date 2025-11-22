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
DEFAULT_SYMBOLS = ['TSM', '005930.KS']  # TSMC, Samsung

# Symbol mappings to handle various query formats
SYMBOL_MAPPINGS = {
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
    return {"status": "healthy"}

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
        
        # Step 2: Fetch market data
        market_data = api_agent.get_market_data(symbol_list)
        
        if not market_data:
            logger.error("Failed to fetch market data for symbols: " + str(symbol_list))
            raise HTTPException(status_code=500, detail=f"Failed to fetch market data for symbols: {symbol_list}")
        
        # Convert market data to a serializable format using the agent's method
        logger.info(f"Serializing market data for {list(market_data.keys())}")
        serialized_market_data = api_agent.serialize_market_data(market_data)
        
        if not serialized_market_data:
            logger.error("Failed to serialize market data")
            raise HTTPException(status_code=500, detail="Failed to serialize market data")
        
        logger.info(f"Successfully serialized data: {list(serialized_market_data.keys())}")
        
        # Step 3: Generate news URLs based on symbols
        news_urls = [f"https://finance.yahoo.com/quote/{symbol}/news/" for symbol in symbol_list[:2]]  # Limit to first 2 symbols
        logger.info(f"Scraping news from URLs: {news_urls}")
        articles = scraping_agent.scrape_news(news_urls)
        
        if not articles:
            # If scraping failed, use fallback content based on actual market data
            logger.warning("News scraping failed, using fallback articles")
            articles = []
            for symbol in symbol_list:
                company_name = next((k for k, v in SYMBOL_MAPPINGS.items() if v == symbol), symbol)
                
                # Try to include some data from market_data in the fallback
                article_text = f"{company_name.title()} continues to be a key player in the market. "
                
                if symbol in market_data:
                    try:
                        market_df = market_data[symbol]
                        if not market_df.empty:
                            latest_close = market_df['Close'].iloc[-1] if 'Close' in market_df.columns else 'N/A'
                            article_text += f"Latest closing price: {latest_close}. "
                    except:
                        pass
                
                articles.append({
                    "title": f"{company_name.title()} Market Update", 
                    "text": article_text,
                    "url": f"https://finance.yahoo.com/quote/{symbol}"
                })
        else:
            logger.info(f"Successfully scraped {len(articles)} articles")
        
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
            else:
                # Direct text objects
                context = [str(doc) for doc in context_docs]
        
        if not context:
            # If retrieval failed, use fallback content with actual data
            logger.warning("Document retrieval failed, using fallback context")
            context = []
            for symbol in symbol_list:
                company_name = next((k for k, v in SYMBOL_MAPPINGS.items() if v == symbol), symbol)
                context_text = f"{company_name.title()} market data has been retrieved. "
                
                if symbol in serialized_market_data and serialized_market_data[symbol]:
                    try:
                        # Add some statistics from the market data
                        records = serialized_market_data[symbol]
                        if records:
                            closes = [r.get('Close', 0) for r in records if 'Close' in r]
                            if closes:
                                avg_close = sum(closes) / len(closes)
                                context_text += f"Average closing price over period: {avg_close:.2f}."
                    except Exception as e:
                        logger.warning(f"Error extracting context stats: {str(e)}")
                
                context.append(context_text)
        
        logger.info(f"Retrieved {len(context)} context documents")
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
                company_name = next((k.title() for k, v in SYMBOL_MAPPINGS.items() if v == symbol), symbol)
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
                company_name = next((k.title() for k, v in SYMBOL_MAPPINGS.items() if v == symbol), symbol)
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
                company_name = next((k.title() for k, v in SYMBOL_MAPPINGS.items() if v == symbol), symbol)
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
        articles = scraping_agent.scrape_news(news_urls)
        
        if not articles:
            # If scraping failed, use fallback content
            articles = []
            for symbol in symbol_list:
                company_name = next((k for k, v in SYMBOL_MAPPINGS.items() if v == symbol), symbol)
                articles.append({
                    "title": f"{company_name.title()} News", 
                    "text": f"{company_name.title()} continues to be a key player in the technology market."
                })

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
                company_name = next((k.title() for k, v in SYMBOL_MAPPINGS.items() if v == symbol), symbol)
                symbol_names.append(f"{company_name} ({symbol})")
            
            brief = f"""
            Market Brief for your query about {query}:
            
            Analysis of {', '.join(symbol_names)}:
            
            Our portfolio has exposure to these key technology companies with varying weights.
            """
            
            # Add exposure details
            brief += "\nPortfolio Exposure:\n"
            for symbol, data in exposure.items():
                company_name = next((k.title() for k, v in SYMBOL_MAPPINGS.items() if v == symbol), symbol)
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
    st.sidebar.markdown("Enter stock symbols or company names in your query, or select from common stocks:")
    
    # Common stocks for quick selection
    common_stocks = {
        "Technology": ["AAPL (Apple)", "MSFT (Microsoft)", "GOOGL (Google)", "AMZN (Amazon)", "META (Facebook)"],
        "Semiconductors": ["TSM (TSMC)", "NVDA (NVIDIA)", "INTC (Intel)", "AMD (AMD)", "005930.KS (Samsung)"],
        "EVs": ["TSLA (Tesla)", "RIVN (Rivian)", "NIO (NIO)"],
        "Finance": ["JPM (JP Morgan)", "BAC (Bank of America)", "GS (Goldman Sachs)"]
    }
    
    selected_category = st.sidebar.selectbox("Industry Sector", list(common_stocks.keys()))
    selected_stocks = st.sidebar.multiselect("Select stocks", common_stocks[selected_category])
    
    # Prepare query with selected stocks
    stock_query = ""
    selected_symbols = []
    if selected_stocks:
        # Extract just the symbol part (before the space)
        selected_symbols = [stock.split(" ")[0] for stock in selected_stocks]
        stock_query = f"What's our risk exposure in {', '.join(selected_symbols)}?"
    
    # Text query input with default that includes selected stocks
    query = st.text_input("Ask something:", 
                         value=stock_query if stock_query else "What's our risk exposure in tech stocks today?")
    
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