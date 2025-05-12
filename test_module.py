import sys
import os
print("Python path:", sys.path)
print("Current directory:", os.getcwd())
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
print("Updated path:", sys.path)
from data_ingestion.api_agent import APIAgent
print("Import successful")