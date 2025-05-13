import streamlit as st
import requests
import io
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                health_check = requests.get("http://localhost:8000/")
                if health_check.status_code != 200:
                    st.error(f"FastAPI server not reachable: {health_check.status_code} - {health_check.text}")
                    logger.error(f"FastAPI health check failed: {health_check.status_code} - {health_check.text}")
                else:
                    st.info("FastAPI server is healthy. Processing your request...")
                    logger.info("FastAPI server is healthy")
                    
                    # Step 1: Retrieve relevant documents with explicit symbols if selected
                    logger.info(f"Sending retrieve request with query: {query}")
                    
                    # Add selected symbols as query parameters if they exist
                    params = {"query": query}
                    if selected_symbols:
                        params["symbols"] = ",".join(selected_symbols)
                        st.info(f"Explicitly requesting analysis for: {', '.join(selected_symbols)}")
                    
                    retrieve_response = requests.get("http://localhost:8000/retrieve/retrieve", params=params)
                    logger.info(f"Retrieve response status: {retrieve_response.status_code}")
                    
                    if retrieve_response.status_code != 200:
                        st.error(f"Retrieval failed with status {retrieve_response.status_code}")
                        logger.error(f"Retrieval failed: {retrieve_response.status_code} - {retrieve_response.text}")
                        
                        # Add detailed error information
                        try:
                            error_details = retrieve_response.json()
                            if "error" in error_details:
                                st.code(f"Error details: {error_details['error']}")
                        except:
                            st.code(f"Raw response: {retrieve_response.text[:500]}...")
                    else:
                        retrieve_data = retrieve_response.json()
                        logger.info(f"Retrieved data successfully")
                        
                        if "error" in retrieve_data:
                            st.error(f"Retrieval error: {retrieve_data['error']}")
                            logger.error(f"Retrieval error: {retrieve_data['error']}")
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
                            logger.info(f"Analyze response status: {analyze_response.status_code}")
                            
                            if analyze_response.status_code != 200:
                                st.error(f"Analysis failed with status {analyze_response.status_code}")
                                logger.error(f"Analysis failed: {analyze_response.status_code} - {analyze_response.text}")
                                
                                # Add detailed error information
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
                                    logger.error(f"Analysis error: {analyze_data['error']}")
                                else:
                                    st.subheader("Market Brief:")
                                    st.markdown(analyze_data["summary"])
                                    st.success("Query processed successfully!")
            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to FastAPI server. Make sure it's running on http://localhost:8000")
                logger.error("Connection error: Failed to connect to FastAPI server")
        except Exception as e:
            st.error(f"Failed to process query: {str(e)}")
            logger.error(f"Exception in query processing: {str(e)}")

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
            logger.info(f"Audio process_query response status: {response.status_code}")
            
            if response.status_code == 200:
                audio_bytes = io.BytesIO(response.content)
                st.audio(audio_bytes, format="audio/mp3")
                st.success("Audio query processed successfully!")
            else:
                try:
                    error_msg = response.json().get("error", "Unknown error")
                    st.error(f"Audio processing error: {error_msg}")
                    logger.error(f"Audio processing error: {error_msg}")
                except:
                    st.error(f"Audio processing failed with status {response.status_code}")
                    logger.error(f"Audio processing failed with status {response.status_code}")
        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to FastAPI server. Make sure it's running on http://localhost:8000")
            logger.error("Connection error: Failed to connect to FastAPI server")
        except Exception as e:
            st.error(f"Failed to process audio query: {str(e)}")
            logger.error(f"Exception in audio query processing: {str(e)}")

# Add a section to explain how to debug the application
with st.expander("Troubleshooting"):
    st.write("""
    ### Common issues and solutions:
    
    1. **FastAPI server not reachable**: Make sure the FastAPI server is running on port 8000 with:
       ```
       uvicorn orchestrator.orchestrator:app --host 0.0.0.0 --port 8000
       ```
       
    2. **Internal Server Error (500)**: Check the logs of the FastAPI server for more details.
    
    3. **JSON serialization errors**: These often happen with pandas DataFrames. The updated code should handle this.
    
    4. **Empty or incorrect responses**: The system now has fallback data to ensure you always get a response.
    
    5. **Stock not recognized**: Try using the ticker symbol directly (e.g., AAPL instead of Apple) in your query.
    """)