# SHL Assessment Recommender

An intelligent tool that recommends SHL assessments based on job descriptions using LangGraph, LangChain, and Vector Search with a FastAPI backend and Streamlit frontend.

## Overview

This project helps recruiters and HR professionals quickly identify the most relevant SHL assessments for their job openings. It uses:

- A web crawler to extract assessment data from SHL's product catalog
- Hybrid retrieval combining vector search (FAISS via Qdrant) and BM25 for optimal semantic matching
- LangGraph for orchestrating an intelligent multi-step workflow
- FastAPI backend for the recommendation engine
- Streamlit web interface for easy interaction

## Project Structure

```
├── app.py               # FastAPI backend service
├── main.py              # Core recommendation engine using LangGraph
├── crawler/             # Web crawler for SHL assessment data
│   ├── crawler.py       # Crawler implementation
│   ├── shl_assessments.json        # Crawled assessment data
│   └── shl_crawl_state.json        # Crawler state tracking
├── frontend/            # Streamlit frontend
│   ├── streamlit_app.py # Streamlit web application
│   ├── requirements.txt # Frontend-specific dependencies
│   └── Dockerfile       # Frontend Docker configuration
├── Dockerfile           # Backend Docker configuration
├── requirements.txt     # Project dependencies
├── .env                 # Environment variables (API keys, etc.)
└── .env.example         # Example environment variables template
```

## Features

- **Web Crawler**: Extracts assessment details from SHL's catalog, including name, URL, remote testing support, adaptive/IRT support, duration, and test types
- **Hybrid Semantic Search**: Combines dense (vector via Qdrant) and sparse (BM25) retrieval for optimal results
- **Intelligent Recommendation**: Uses LangGraph workflow with multiple steps to parse job descriptions, retrieve relevant assessments, and rerank results
- **Microservice Architecture**: Separate FastAPI backend and Streamlit frontend services
- **Web Interface**: User-friendly Streamlit app with support for direct text input or job URL parsing
- **Docker Support**: Containerized deployment for both frontend and backend services

## Requirements

- Python 3.10+
- Dependencies listed in requirements.txt
- Docker (optional, for containerized deployment)
- Qdrant vector database (cloud or self-hosted)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/arnnv/shl-recommendation-system.git
   cd shl-recommendation-system
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux/Mac
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Add your Anthropic API key, OpenAI API key, Qdrant URL, and Qdrant API key

## Usage

### Running the Application

1. Start the backend service using Uvicorn:
   ```
   # Run directly with uvicorn
   uvicorn app:app --host 0.0.0.0 --port 8000 --reload
   
   # Alternatively, you can run the app.py script
   python app.py
   ```

2. In a separate terminal, start the Streamlit frontend:
   ```
   cd frontend
   streamlit run streamlit_app.py
   ```

3. Open your browser and navigate to: `http://localhost:8501`

### Docker Deployment

1. Build and run the backend container:
   ```
   docker build -t shl-backend .
   docker run -p 8000:8000 --env-file .env shl-backend
   ```

2. Build and run the frontend container:
   ```
   cd frontend
   docker build -t shl-frontend .
   docker run -p 8501:8501 -e API_URL=http://host.docker.internal:8000 shl-frontend
   ```

### Using the Crawler

To update the assessment database:

```
cd crawler
python crawler.py
```

This will crawl SHL's product catalog, extract assessment information, and save it to `shl_assessments.json`.

## How It Works

1. **User Input**: Enter a job description or provide a URL to a job posting
2. **Query Processing**: The system extracts key information from the job description
3. **Hybrid Retrieval**: Combines vector search and BM25 to find relevant assessments
4. **Reranking**: Uses an LLM to select and rank the most appropriate assessments
5. **Results**: Displays recommended assessments with details and links

## Technologies

- **LangGraph**: Orchestrates the recommendation workflow with multiple steps
- **LangChain**: Connects the LLM components and provides document handling
- **Claude 3.7 Sonnet**: Powers the language understanding and reasoning components
- **OpenAI Embeddings**: Generates vector embeddings for semantic search
- **Qdrant**: Vector database for storing and retrieving embeddings
- **BM25**: Sparse retrieval algorithm for keyword-based search
- **FastAPI**: Backend API service
- **Uvicorn**: ASGI server for running the FastAPI backend
- **Streamlit**: Web interface
- **BeautifulSoup**: Web scraping for the crawler and job description extraction
- **Docker**: Containerization for deployment
- **Rich**: Console output formatting and logging

## Acknowledgments

- SHL for their comprehensive assessment catalog
- The LangChain and LangGraph communities for their excellent tools