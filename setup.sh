#!/bin/bash

# This script helps set up and run the Morning Market Brief Assistant
# in various configurations based on your needs.

show_help() {
    echo "Morning Market Brief Assistant Setup Script"
    echo ""
    echo "Usage: ./setup.sh [options]"
    echo ""
    echo "Options:"
    echo "  --docker        Run using Docker Compose (both services)"
    echo "  --local         Run both services locally (no Docker)"
    echo "  --fastapi       Run only the FastAPI service locally"
    echo "  --streamlit     Run only the Streamlit service locally"
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./setup.sh --docker     # Run both services with Docker"
    echo "  ./setup.sh --local      # Run both services locally"
    echo ""
}

setup_secrets() {
    # Create .streamlit directory if it doesn't exist
    if [ ! -d ".streamlit" ]; then
        echo "Creating .streamlit directory..."
        mkdir -p .streamlit
    fi

    # Create secrets.toml if it doesn't exist
    if [ ! -f ".streamlit/secrets.toml" ]; then
        echo "Creating .streamlit/secrets.toml file..."
        echo '[server]
API_URL = "http://localhost:8000"' > .streamlit/secrets.toml
        echo "Secrets file created successfully."
    else
        echo "Secrets file already exists."
    fi
}

run_docker() {
    echo "Starting services with Docker Compose..."
    docker-compose up --build
}

run_local() {
    echo "Setting up for local development..."
    setup_secrets
    
    # Check if Python virtual environment exists
    if [ ! -d "venv" ]; then
        echo "Creating Python virtual environment..."
        python -m venv venv
    fi
    
    # Activate virtual environment
    echo "Activating virtual environment..."
    source venv/bin/activate
    
    # Install requirements
    echo "Installing requirements..."
    pip install -r requirements.txt
    
    # Run both services
    echo "Starting FastAPI and Streamlit services..."
    echo "Starting FastAPI on port 8000..."
    uvicorn orchestrator.orchestrator:app --host 0.0.0.0 --port 8000 &
    FASTAPI_PID=$!
    
    # Wait for FastAPI to start
    echo "Waiting for FastAPI to start..."
    sleep 5
    
    echo "Starting Streamlit on port 8501..."
    streamlit run streamlit_app/app.py
    
    # When Streamlit exits, kill FastAPI
    kill $FASTAPI_PID
}

run_fastapi() {
    echo "Setting up for FastAPI service..."
    
    # Check if Python virtual environment exists
    if [ ! -d "venv" ]; then
        echo "Creating Python virtual environment..."
        python -m venv venv
    fi
    
    # Activate virtual environment
    echo "Activating virtual environment..."
    source venv/bin/activate
    
    # Install requirements
    echo "Installing requirements..."
    pip install -r requirements.txt
    
    # Run FastAPI service
    echo "Starting FastAPI on port 8000..."
    uvicorn orchestrator.orchestrator:app --host 0.0.0.0 --port 8000
}

run_streamlit() {
    echo "Setting up for Streamlit service..."
    setup_secrets
    
    # Check if Python virtual environment exists
    if [ ! -d "venv" ]; then
        echo "Creating Python virtual environment..."
        python -m venv venv
    fi
    
    # Activate virtual environment
    echo "Activating virtual environment..."
    source venv/bin/activate
    
    # Install requirements
    echo "Installing requirements..."
    pip install -r requirements.txt
    
    # Run Streamlit service
    echo "Starting Streamlit on port 8501..."
    streamlit run streamlit_app/app.py
}

# Process command line arguments
if [ $# -eq 0 ]; then
    show_help
    exit 0
fi

case "$1" in
    --docker)
        run_docker
        ;;
    --local)
        run_local
        ;;
    --fastapi)
        run_fastapi
        ;;
    --streamlit)
        run_streamlit
        ;;
    --help)
        show_help
        ;;
    *)
        echo "Unknown option: $1"
        show_help
        exit 1
        ;;
esac