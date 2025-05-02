# SHL Assessment Recommender: Technical Approach

## Architecture

This project implements a recommendation system using a modern AI-powered workflow:

1. **Data Collection**: Web crawler extracts SHL assessment data
2. **Vector Database**: Qdrant stores embeddings for semantic search
3. **LangGraph Workflow**: Orchestrates the multi-step recommendation pipeline
4. **API Layer**: FastAPI provides backend services
5. **Web Interface**: Streamlit delivers user-facing application
6. **Containerization**: Docker enables consistent deployment

## Implementation Details

### Data Pipeline
- **Crawler**: Python-based crawler (BeautifulSoup, Requests) extracts assessment metadata from SHL's catalog
- **Data Storage**: JSON format stores structured assessment data
- **Vector Indexing**: OpenAI's embedding model converts assessments to vectors stored in Qdrant

### Recommendation Engine
- **Query Analysis**: Claude 3.7 Sonnet LLM extracts structured data from job descriptions
- **Hybrid Retrieval**:
  - Dense retriever (vector similarity via Qdrant)
  - Sparse retriever (BM25)
  - Custom HybridRetriever class for optimal combination
- **Reranking**: Claude 3.7 Sonnet LLM reranks candidates based on relevance to job description

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
| **Core AI** | LangGraph, LangChain, Claude 3.7 Sonnet |
| **Data Processing** | Qdrant, OpenAI Embeddings, BM25 |
| **Backend** | FastAPI, Uvicorn, Rich |
| **Frontend** | Streamlit, Pandas |
| **Web Crawling** | BeautifulSoup, Requests |
| **Development** | Python 3.10, Virtual Environment |
| **Deployment** | Docker, uv |

## Key Innovations

1. **Hybrid Retrieval**: Combines semantic search with keyword matching for better results
2. **Structured Query Extraction**: Uses LLM to transform unstructured job descriptions into structured queries
3. **LangGraph Orchestration**: Modular, maintainable workflow architecture
4. **URL Processing**: Allows direct input of job posting URLs

## Development Process

### Development Steps

1. **Requirements Analysis**:
   - Identified key user needs for HR professionals and recruiters
   - Analyzed SHL's assessment catalog structure
   - Defined core functionality requirements

2. **Data Acquisition**:
   - Developed a crawler to extract assessment data from SHL's website
   - Implemented data cleaning and structuring
   - Created a persistent JSON storage format

3. **Vector Database Setup**:
   - Evaluated vector database options (FAISS, Chroma, Qdrant)
   - Selected Qdrant for production-ready features and API
   - Implemented OpenAI embeddings for semantic representation

4. **LLM Integration**:
   - Tested multiple LLM providers (OpenAI, Google, Anthropic)
   - Selected Claude 3.7 Sonnet for optimal performance and cost balance
   - Developed prompts for structured information extraction

5. **Retrieval System**:
   - Implemented vector-based semantic search
   - Added BM25 sparse retrieval for keyword matching
   - Created custom HybridRetriever to combine both approaches

6. **Workflow Orchestration**:
   - Designed LangGraph workflow with distinct processing nodes
   - Implemented state management for the recommendation pipeline
   - Optimized for performance with timing measurements

7. **API Development**:
   - Created FastAPI backend with async support
   - Implemented error handling and request validation
   - Added CORS support for frontend integration

8. **Frontend Implementation**:
   - Built Streamlit interface for user interaction
   - Added URL parsing capability for job descriptions
   - Implemented results display with downloadable formats

9. **Containerization**:
   - Created Dockerfiles for both frontend and backend
   - Optimized container builds with uv package manager
   - Configured environment variable management

10. **Testing and Evaluation**:
    - Developed evaluation metrics (recall@k, precision@k)
    - Created test cases with diverse job descriptions
    - Measured and optimized system performance

### Evaluation Metrics and Performance

The system was evaluated using standard information retrieval metrics:

1. **Mean Recall@3**: Measures the proportion of relevant assessments that are retrieved in the top 3 results
   - **Score**: 100% (perfect recall)
   - This indicates that all relevant assessments were successfully retrieved in the top 3 results

2. **Mean Average Precision@3 (MAP@3)**: Measures the precision at each relevant result in the top 3, averaged across all queries
   - **Score**: 100% (perfect precision)
   - This indicates perfect ranking of relevant assessments in the top positions

3. **Response Time**:
   - Average end-to-end response time: ~6 seconds
   - Query processing: ~3 seconds
   - Retrieval: ~1 seconds
   - Reranking: ~2 seconds

### Optimization Strategies

1. **Hybrid Retrieval Tuning**:
   - Experimented with different weights for dense vs. sparse retrieval
   - Optimized k values for both retrievers
   - Found optimal performance with equal weighting and k=5

2. **Prompt Engineering**:
   - Iteratively refined prompts for both extraction and reranking
   - Added structured output formats for consistent parsing
   - Included specific assessment criteria in the reranking prompt

3. **Vector Database Optimization**:
   - Implemented connection pooling for Qdrant
   - Used gRPC for faster vector operations
   - Added error handling and retry logic

4. **Performance Monitoring**:
   - Added timing measurements for each pipeline stage
   - Implemented Rich console output for debugging
   - Created performance logging for continuous improvement

This architecture delivers relevant assessment recommendations by leveraging modern AI techniques while maintaining a simple user interface and efficient processing pipeline.