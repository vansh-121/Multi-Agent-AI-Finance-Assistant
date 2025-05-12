# Multi-Agent AI Finance Assistant
A Streamlit-based AI finance assistant that delivers spoken market briefs using a multi-agent architecture.

## Architecture
- **API Agent**: Fetches market data via yfinance
- **Scraping Agent**: Crawls news using newspaper3k
- **Retriever Agent**: Indexes and retrieves using FAISS and HuggingFace embeddings
- **Analysis Agent**: Calculates risk exposure
- **Language Agent**: Generates narratives using HuggingFace LLM
- **Voice Agent**: Handles STT/TTS using speechrecognition and gTTS
- **Orchestrator**: FastAPI microservices
- **UI**: Streamlit

## Setup
1. Clone repository
2. Install requirements: `pip install -r requirements.txt`
3. Run FastAPI: `uvicorn orchestrator.orchestrator:app --host 0.0.0.0 --port 8000`
4. Run Streamlit: `streamlit run streamlit_app/app.py`
5. Or use Docker: `docker-compose up`
