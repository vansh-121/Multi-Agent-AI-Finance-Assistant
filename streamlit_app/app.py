import streamlit as st
import requests
import io
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.title("🧠 Morning Market Brief Assistant")

# Text query input
query = st.text_input("Ask something:", "What’s our risk exposure in Asia tech stocks today?")

if st.button("Get Brief"):
    with st.spinner("Processing query..."):
        try:
            # Check if FastAPI is reachable
            health_check = requests.get("http://localhost:8000")
            if health_check.status_code != 200:
                st.error(f"FastAPI server not reachable: {health_check.status_code} - {health_check.text}")
                logger.error(f"FastAPI health check failed: {health_check.status_code} - {health_check.text}")
            else:
                # Step 1: Retrieve relevant documents
                retrieve_response = requests.get("http://localhost:8000/retrieve/retrieve", params={"query": query})
                if retrieve_response.status_code != 200:
                    st.error(f"Retrieval failed with status {retrieve_response.status_code}: {retrieve_response.text}")
                    logger.error(f"Retrieval failed: {retrieve_response.status_code} - {retrieve_response.text}")
                else:
                    retrieve_data = retrieve_response.json()
                    logger.info(f"Retrieve response: {retrieve_data}")
                    
                    if "error" in retrieve_data:
                        st.error(f"Retrieval error: {retrieve_data['error']}")
                        logger.error(f"Retrieval error: {retrieve_data['error']}")
                    else:
                        # Step 2: Analyze and get summary
                        analyze_response = requests.post("http://localhost:8000/analyze/analyze", json={"data": retrieve_data})
                        if analyze_response.status_code != 200:
                            st.error(f"Analysis failed with status {analyze_response.status_code}: {analyze_response.text}")
                            logger.error(f"Analysis failed: {analyze_response.status_code} - {analyze_response.text}")
                        else:
                            analyze_data = analyze_response.json()
                            logger.info(f"Analyze response: {analyze_data}")
                            
                            if "error" in analyze_data:
                                st.error(f"Analysis error: {analyze_data['error']}")
                                logger.error(f"Analysis error: {analyze_data['error']}")
                            else:
                                st.write(analyze_data["summary"])
                                st.success("Query processed successfully!")
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
            response = requests.post("http://localhost:8000/process_query", files=files, stream=True)
            logger.info(f"Audio process_query response status: {response.status_code}")
            
            if response.status_code == 200:
                audio_bytes = io.BytesIO(response.content)
                st.audio(audio_bytes, format="audio/mp3")
                st.success("Audio query processed successfully!")
            else:
                error_msg = response.json().get("error", "Unknown error")
                st.error(f"Audio processing error: {error_msg}")
                logger.error(f"Audio processing error: {error_msg}")
        except Exception as e:
            st.error(f"Failed to process audio query: {str(e)}")
            logger.error(f"Exception in audio query processing: {str(e)}")