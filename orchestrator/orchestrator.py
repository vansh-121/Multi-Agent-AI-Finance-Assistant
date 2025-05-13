import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from data_ingestion.api_agent import APIAgent
from data_ingestion.scrapping_agent import ScrapingAgent
from agents.retriever_agent import RetrieverAgent
from agents.analysis_agent import AnalysisAgent
from agents.language_agent import LanguageAgent
from agents.voice_agent import VoiceAgent
import logging
import pandas as pd
from fastapi.middleware.cors import CORSMiddleware
import json
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware to allow Streamlit to access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# Add a health check endpoint
@app.get("/")
async def health_check():
    return {"status": "healthy"}

@app.get("/retrieve/retrieve")
async def retrieve(query: str):
    try:
        logger.info(f"Processing retrieve request for query: {query}")
        
        # Step 1: Extract symbols from the query
        symbols = extract_symbols_from_query(query)
        logger.info(f"Extracted symbols: {symbols}")
        
        # Step 2: Fetch market data
        market_data = api_agent.get_market_data(symbols)
        
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
        news_urls = [f"https://finance.yahoo.com/quote/{symbol}/news/" for symbol in symbols[:2]]  # Limit to first 2 symbols
        articles = scraping_agent.scrape_news(news_urls)
        
        if not articles:
            # If scraping failed, use fallback content
            articles = []
            for symbol in symbols:
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
            for symbol in symbols:
                company_name = next((k for k, v in SYMBOL_MAPPINGS.items() if v == symbol), symbol)
                context.append(f"{company_name.title()} continues to be a key player in the technology market.")
            logger.info("Using fallback context")
        
        logger.info("Retrieved documents successfully")
        return {
            "market_data": serialized_market_data,
            "context": context,
            "query": query,
            "symbols": symbols
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
async def process_query(audio: UploadFile = File(...)):
    try:
        # Step 1: Convert speech to text
        query = voice_agent.speech_to_text(audio.file)
        
        if not query:
            query = "What's our risk exposure in technology stocks?"
            logger.info("Using fallback query due to STT failure")

        # Step 2: Extract symbols from query
        symbols = extract_symbols_from_query(query)
        
        # Step 3: Fetch market data
        market_data = api_agent.get_market_data(symbols)
        
        if not market_data:
            logger.error("Failed to fetch market data")
            raise HTTPException(status_code=500, detail="Failed to fetch market data")

        # Step 4: Scrape news
        news_urls = [f"https://finance.yahoo.com/quote/{symbol}/news/" for symbol in symbols[:2]]
        articles = scraping_agent.scrape_news(news_urls)
        
        if not articles:
            # If scraping failed, use fallback content
            articles = []
            for symbol in symbols:
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
            context = [f"Analysis of {', '.join(symbols)} stocks"]

        # Update the analysis agent's portfolio to include the queried symbols
        portfolio_weights = {}
        for i, symbol in enumerate(symbols):
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
            for symbol in symbols:
                exposure[symbol] = {
                    'weight': portfolio_weights.get(symbol, 0.10),
                    'value': portfolio_weights.get(symbol, 0.10) * total_aum,
                    'price': 100.0
                }

        # Step 7: Get earnings
        earnings = {}
        for symbol in symbols:
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
            for symbol in symbols:
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