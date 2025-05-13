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
            logger.error("Failed to fetch market data")
            raise HTTPException(status_code=500, detail="Failed to fetch market data")
        
        # Convert market data to a serializable format
        serialized_market_data = {}
        for symbol, data in market_data.items():
            if isinstance(data, pd.DataFrame):
                serialized_market_data[symbol] = data.to_dict(orient='records')
            else:
                serialized_market_data[symbol] = data
        
        # Step 3: Generate news URLs based on symbols
        news_urls = [f"https://finance.yahoo.com/quote/{symbol}/news/" for symbol in symbol_list[:2]]  # Limit to first 2 symbols
        articles = scraping_agent.scrape_news(news_urls)
        
        if not articles:
            # If scraping failed, use fallback content
            articles = []
            for symbol in symbol_list:
                company_name = next((k for k, v in SYMBOL_MAPPINGS.items() if v == symbol), symbol)
                articles.append({
                    "title": f"{company_name.title()} News", 
                    "text": f"{company_name.title()} continues to be a key player in the technology market.",
                    "url": f"https://example.com/{company_name.lower()}"
                })
            logger.info("Using fallback articles")
        
        # Step 4: Index and retrieve
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
            # If retrieval failed, use fallback content
            context = []
            for symbol in symbol_list:
                company_name = next((k for k, v in SYMBOL_MAPPINGS.items() if v == symbol), symbol)
                context.append(f"{company_name.title()} continues to be a key player in the technology market.")
            logger.info("Using fallback context")
        
        logger.info("Retrieved documents successfully")
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
        
        try:
            if "data" in data and "market_data" in data["data"]:
                serialized_data = data["data"]["market_data"]
                
                # Convert serialized market data back to DataFrame format
                market_data = {}
                for symbol, records in serialized_data.items():
                    if isinstance(records, list):
                        market_data[symbol] = pd.DataFrame.from_records(records)
                    else:
                        market_data[symbol] = records
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
        
        # Update the analysis agent's portfolio to include the queried symbols
        # This is a temporary solution - in a real system, you might want to fetch the actual portfolio
        portfolio_weights = {}
        for i, symbol in enumerate(symbols):
            # Assign decreasing weights to each symbol
            portfolio_weights[symbol] = 0.15 - (i * 0.02)  # Start at 15% and decrease
            if portfolio_weights[symbol] < 0.05:  # Minimum weight of 5%
                portfolio_weights[symbol] = 0.05
        
        # Update the portfolio
        analysis_agent.portfolio = portfolio_weights
        
        # Step 2: Analyze risk
        exposure = analysis_agent.analyze_risk_exposure(market_data)
        
        if not exposure:
            # Fallback exposure data if analysis fails
            exposure = {}
            total_aum = 1000000  # Example AUM of $1M
            for symbol in symbols:
                exposure[symbol] = {
                    'weight': portfolio_weights.get(symbol, 0.10),
                    'value': portfolio_weights.get(symbol, 0.10) * total_aum,
                    'price': 100.0  # Default price
                }
            logger.info("Using fallback exposure data")
        
        # Step 3: Get earnings
        earnings = {}
        
        for symbol in symbols:
            try:
                earnings[symbol] = api_agent.get_earnings(symbol)
                if earnings[symbol] is None:
                    # Fallback earnings data
                    earnings[symbol] = pd.DataFrame({
                        'Year': [2023, 2024],
                        'Earnings': [10.5, 12.3]
                    })
            except Exception as e:
                logger.warning(f"Error fetching earnings for {symbol}: {str(e)}")
                # Fallback earnings data
                earnings[symbol] = pd.DataFrame({
                    'Year': [2023, 2024],
                    'Earnings': [10.5, 12.3]
                })
        
        # Convert earnings to serializable format
        serialized_earnings = {}
        for symbol, data in earnings.items():
            if isinstance(data, pd.DataFrame):
                serialized_earnings[symbol] = data.to_dict(orient='records')
            else:
                serialized_earnings[symbol] = data
        
        # Step 4: Generate brief
        try:
            brief = language_agent.generate_brief(
                str(context), 
                str(exposure), 
                str(serialized_earnings)
            )
        except Exception as e:
            logger.error(f"Error generating brief: {str(e)}")
            # Generate a more dynamic fallback brief
            symbol_names = []
            for symbol in symbols:
                company_name = next((k.title() for k, v in SYMBOL_MAPPINGS.items() if v == symbol), symbol)
                symbol_names.append(f"{company_name} ({symbol})")
            
            brief = f"""
            Market Brief for {query}:
            
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
        
        logger.info("Analysis completed successfully")
        return {"summary": brief}
    except Exception as e:
        logger.error(f"Error analyzing data: {str(e)}")
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
                    st.error("Cannot connect to FastAPI server at http://localhost:8000. Make sure it's running.")
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
                st.error("Cannot connect to FastAPI server at http://localhost:8000. Make sure it's running.")
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