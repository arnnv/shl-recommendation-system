# SHL Assessment Recommender: Technical Approach

## Architecture

This project implements a recommendation system using a modern AI-powered workflow:

1. **Data Collection**: Web crawler extracts SHL assessment data
2. **Vector Database**: FAISS stores embeddings for semantic search
3. **LangGraph Workflow**: Orchestrates the recommendation pipeline
4. **API Layer**: FastAPI provides backend services
5. **Web Interface**: Streamlit delivers user-facing application

## Implementation Details

### Data Pipeline
- **Crawler**: Python-based crawler (BeautifulSoup, Requests) extracts assessment metadata from SHL's catalog
- **Data Storage**: JSON format stores structured assessment data
- **Vector Indexing**: Google's embedding model converts assessments to vectors stored in FAISS

### Recommendation Engine
- **Query Analysis**: LLM extracts structured data from job descriptions
- **Hybrid Retrieval**:
  - Dense retriever (vector similarity)
  - Sparse retriever (BM25)
  - Combined ranking with weighted scores
- **Reranking**: LLM reranks candidates based on relevance to job description

### Backend Architecture
- **LangGraph**: Defines workflow as a directed graph with state management
- **State Nodes**:
  1. `extract_info`: Parses job descriptions into structured queries
  2. `rag`: Retrieves relevant assessments using hybrid search
  3. `filter`: Reranks and filters to final recommendations
- **API Layer**: FastAPI exposes recommendation endpoint

### Frontend Interface
- **Streamlit App**: Provides simple UI for job description input
- **URL Parser**: Optional extraction of job descriptions from URLs
- **Results Display**: Tabular view of recommended assessments

## Technologies

| Component | Technologies |
|-----------|-------------|
| **Core AI** | LangGraph, LangChain, Google Gemini |
| **Data Processing** | FAISS, BM25 |
| **Backend** | FastAPI, Uvicorn |
| **Frontend** | Streamlit, Pandas |
| **Web Crawling** | BeautifulSoup, Requests |
| **Development** | Python 3.10, Virtual Environment |

## Key Innovations

1. **Hybrid Retrieval**: Combines semantic search with keyword matching for better results
2. **Structured Query Extraction**: Uses LLM to transform unstructured job descriptions into structured queries
3. **LangGraph Orchestration**: Modular, maintainable workflow architecture
4. **URL Processing**: Allows direct input of job posting URLs

This architecture delivers relevant assessment recommendations by leveraging modern AI techniques while maintaining a simple user interface and efficient processing pipeline. 