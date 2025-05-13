# Multi-Agent AI Finance Assistant

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Last Commit](https://img.shields.io/github/last-commit/vansh-121/Multi-Agent-AI-Finance-Assistant)
![Forks](https://img.shields.io/github/forks/vansh-121/Multi-Agent-AI-Finance-Assistant?style=social)
![Stars](https://img.shields.io/github/stars/vansh-121/Multi-Agent-AI-Finance-Assistant?style=social)
![Streamlit](https://img.shields.io/badge/Streamlit-Enabled-red?logo=streamlit)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green?logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)
![Status](https://img.shields.io/badge/status-active-green.svg)

## Overview

The **Multi-Agent AI Finance Assistant** is an open-source platform designed to provide intelligent financial analysis and decision-making support using a multi-agent AI framework. Leveraging large language models (LLMs) and advanced financial algorithms, this project enables users to perform tasks such as equity research, market forecasting, portfolio optimization, and document analysis. The system employs a modular, agent-based architecture where specialized AI agents collaborate to deliver precise and actionable financial insights.

This project is ideal for financial analysts, developers, and researchers looking to harness AI for financial applications. It demonstrates the power of multi-agent systems in tackling complex, real-world financial challenges.

---

## 🚀 Live Demo (Beta)

🟡 Under development: [multi-agent-ai-finance-assistant.streamlit.app](https://multi-agent-ai-finance-assistant.streamlit.app)  

---

## ⚠️ Note

> Due to limitations of **Render's free trial**, the **FastAPI backend may not load in the Streamlit frontend** (which is still under development).  
> **Recommended:** Clone the repo and run it locally for a seamless experience.

---

🧪 Try locally: Follow setup instructions below.

---



## Key Features

- **Multi-Agent Collaboration**: Specialized agents (e.g., Market Forecasting Agent, Document Analysis Agent) work together to process financial data and provide comprehensive insights.
- **LLM-Powered Analysis**: Integrates state-of-the-art LLMs (e.g., GPT-4, LLaMA) for natural language understanding and financial reasoning.
- **Financial Data Integration**: Supports real-time and historical market data via APIs (e.g., Financial Datasets API, Yahoo Finance).
- **Chain-of-Thought (CoT) Prompting**: Enhances decision-making by breaking down complex financial problems into logical steps.
- **Report Generation**: Automatically generates equity research reports in PDF format based on company financials (e.g., 10-K reports).
- **Extensible Architecture**: Modular design allows easy addition of new agents or data sources.
- **User-Friendly CLI**: Command-line interface for seamless interaction and task execution.

---

---
## 📸 Screenshots

### 🧠 Home Dashboard
![image](https://github.com/user-attachments/assets/8b79af26-ae82-4c42-92dd-abb3a8385d39)

### Processing Query, Generating results:
![image](https://github.com/user-attachments/assets/c214c12b-a62b-42e3-abd4-bd39228abde4)



### 📊 Financial Analysis Result
![image](https://github.com/user-attachments/assets/b1faa2a7-480b-4854-8a44-61e4d02486fc)
![image](https://github.com/user-attachments/assets/25a3b51b-8761-462b-ae07-dd25f931cd52)



---

## 🧰 Tech Stack

- **Frontend:** Streamlit + SpeechRecognition + Pyttsx3
- **Backend:** FastAPI (Microservices)
- **Web Scraping:** BeautifulSoup, Requests
- **RAG:** FAISS + LangChain + OpenAI
- **Voice I/O:** Python Speech Libraries
- **Deployment:** Localhost / Docker-ready
- **Language Model:** OpenAI GPT (via LangChain)

---

## 🧪 Microservices Overview

| Agent            | Role                                               |
|------------------|----------------------------------------------------|
| **API Agent**     | Routes requests and orchestrates the agents       |
| **Scraper Agent** | Scrapes live financial data from multiple sources |
| **Retriever Agent** | Retrieves relevant chunks from vector DB       |
| **Language Agent** | Generates answers using RAG + LLM                |
| **Analysis Agent** | Performs financial data summaries & charts       |
| **Voice Agent**    | Handles text-to-speech and speech recognition    |

---


## Project Motivation

The financial industry demands rapid, accurate, and data-driven decisions. Traditional tools often struggle with the volume and complexity of financial data. This project addresses these challenges by deploying a multi-agent AI system that combines domain expertise with cutting-edge AI technologies, inspired by platforms like FinRobot.

## Installation

### Prerequisites
- Python 3.10 or higher
- Git
- API keys for financial data providers (e.g., Financial Datasets API)
- Optional: Docker for containerized deployment

### Setup
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/vansh-121/Multi-Agent-AI-Finance-Assistant.git
   cd Multi-Agent-AI-Finance-Assistant
   ```

2. **Create a Virtual Environment:**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. **Install Dependencies:**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Run microservices (in separate terminals or use Docker Compose)**:
   ```bash
   uvicorn orchaestrator.orchaestrator:app --host 0.0.0.0 --port 8000
   ```
   or
   ```bash
   uvicorn api_agent.main:app --reload
   uvicorn scraper_agent.main:app --reload
   uvicorn retriever_agent.main:app --reload
   uvicorn language_agent.main:app --reload
   uvicorn analysis_agent.main:app --reload
   uvicorn voice_agent.main:app --reload
   ```
5. **Launch Streamlit frontend**:
   ```bash
   streamlit run streamlit_app\app.py
   ```
6. **Optional: Run with Docker:**
   ```bash
   docker build -t finance-assistant .
   docker run -v $(pwd)/config_api_keys.json:/app/config_api_keys.json finance-assistant
   ```
## Contact
For questions or feedback, reach out to Vansh at vansh.sethi98760@gmail.com or open an issue on GitHub.
      
     
