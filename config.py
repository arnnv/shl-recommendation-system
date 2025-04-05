"""
Configuration settings for the SHL Assessment Recommendation System
"""
import os

# Path to the SHL assessments JSON file
ASSESSMENTS_FILE_PATH = "crawler/shl_assessments.json"

# LLM model configuration
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-2.0-flash")  # Use "gemini-1.5-flash" for best performance
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.2"))  # Lower for more factual responses, higher for more creative

# Embedding model configuration
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# Retrieval configuration
MAX_RESULTS = int(os.environ.get("MAX_RESULTS", "10"))  # Maximum number of assessments to retrieve

# Application settings
APP_NAME = "SHL Assessment Recommendation System"
VERSION = "1.0.0" 