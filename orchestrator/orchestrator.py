import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
from data_ingestion.api_agent import APIAgent
from data_ingestion.scrapping_agent import ScrapingAgent
from agents.retriever_agent import RetrieverAgent
from agents.analysis_agent import AnalysisAgent
from agents.language_agent import LanguageAgent
from agents.voice_agent import VoiceAgent
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

api_agent = APIAgent()
scraping_agent = ScrapingAgent()
retriever_agent = RetrieverAgent()
analysis_agent = AnalysisAgent()
language_agent = LanguageAgent()
voice_agent = VoiceAgent()

@app.post("/process_query")
async def process_query(audio: UploadFile = File(...)):
    try:
        # Step 1: Convert speech to text
        query = voice_agent.speech_to_text(audio.file)

        # Step 2: Fetch market data
        symbols = ['TSM', '005930.KS']  # TSMC, Samsung
        market_data = api_agent.get_market_data(symbols)

        # Step 3: Scrape news
        news_urls = ["https://finance.yahoo.com/quote/TSM/news/"]  # Example
        articles = scraping_agent.scrape_news(news_urls)

        # Step 4: Index and retrieve
        retriever_agent.index_documents(articles)
        context = retriever_agent.retrieve(query, k=3)

        # Step 5: Analyze risk
        exposure = analysis_agent.analyze_risk_exposure(market_data)

        # Step 6: Get earnings
        earnings = {symbol: api_agent.get_earnings(symbol) for symbol in symbols}

        # Step 7: Generate brief
        brief = language_agent.generate_brief(context, exposure, earnings)

        # Step 8: Convert to speech
        audio_response = voice_agent.text_to_speech(brief)

        logger.info("Query processed successfully")
        return StreamingResponse(audio_response, media_type="audio/mp3")
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        return {"error": str(e)}