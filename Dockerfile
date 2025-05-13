FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Set environment variable to tell the Streamlit app where to find the API
# In container environments, FastAPI service will be available at fastapi:8000
ENV API_URL=http://fastapi:8000

# Expose both ports - FastAPI and Streamlit
EXPOSE 8000 8501

# Create an entrypoint script to start both services
RUN echo '#!/bin/bash\n\
uvicorn orchestrator.orchestrator:app --host 0.0.0.0 --port 8000 &\n\
FASTAPI_PID=$!\n\
echo "FastAPI started with PID $FASTAPI_PID"\n\
# Wait a moment for FastAPI to start\n\
sleep 5\n\
# Start Streamlit\n\
streamlit run streamlit_app/app.py --server.port 8501 --server.address 0.0.0.0\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Run the entrypoint script
CMD ["/app/entrypoint.sh"]