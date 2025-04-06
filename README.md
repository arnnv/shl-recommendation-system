# SHL Assessment Recommender

An intelligent tool that recommends SHL assessments based on job descriptions using LangGraph, LangChain, and Vector Search.

## Overview

This project helps recruiters and HR professionals quickly identify the most relevant SHL assessments for their job openings. It uses:

- A web crawler to extract assessment data from SHL's product catalog
- Vector search and BM25 retrieval for semantic matching
- LangGraph for orchestrating an intelligent workflow
- Streamlit web interface for easy interaction

## Project Structure

```
├── app.py               # Streamlit web application
├── backend.py           # FastAPI backend service
├── main.py              # Core recommendation engine using LangGraph
├── crawler/             # Web crawler for SHL assessment data
│   ├── crawler.py       # Crawler implementation
│   ├── shl_assessments.json        # Crawled assessment data
│   └── shl_crawl_state.json        # Crawler state tracking
├── shl_faiss_index/     # Vector database for semantic search
├── requirements.txt     # Project dependencies
└── .env                 # Environment variables (API keys, etc.)
```

## Features

- **Web Crawler**: Extracts assessment details from SHL's catalog, including name, URL, remote testing support, adaptive/IRT support, duration, and test types
- **Semantic Search**: Combines dense (vector) and sparse (BM25) retrieval for optimal results
- **Intelligent Recommendation**: Uses LangGraph workflow to parse job descriptions and match to relevant assessments
- **Web Interface**: User-friendly Streamlit app with support for direct text input or job URL parsing

## Requirements

- Python 3.10+
- Dependencies listed in requirements.txt

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
   - Add your Google Gemini API key and other required credentials

## Usage

### Running the Application

1. Start the backend service using Uvicorn:
   ```
   # Run directly with uvicorn
   uvicorn backend:app --host 0.0.0.0 --port 8000 --reload
   
   # Alternatively, you can run the backend.py script
   python backend.py
   ```

2. In a separate terminal, start the Streamlit app:
   ```
   streamlit run app.py
   ```

3. Open your browser and navigate to: `http://localhost:8501`

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

- **LangGraph**: Orchestrates the recommendation workflow
- **LangChain**: Connects the LLM components
- **Google Gemini**: Powers the language understanding components
- **FAISS**: Vector database for semantic search
- **FastAPI**: Backend API service
- **Uvicorn**: ASGI server for running the FastAPI backend
- **Streamlit**: Web interface
- **BeautifulSoup**: Web scraping for the crawler and job description extraction

## Acknowledgments

- SHL for their comprehensive assessment catalog
- The LangChain and LangGraph communities for their excellent tools 