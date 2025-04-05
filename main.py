import json
import os
from dotenv import load_dotenv
from pathlib import Path

from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.chains import create_retrieval_chain, LLMChain
from langchain.chains.combine_documents import create_stuff_documents_chain

# Import configuration
import config

# Load environment variables from .env file
load_dotenv()

# Path for saved vector database
VECTOR_DB_PATH = "vectordb"

# Set up LLM model with lower temperature for document enrichment
def get_llm(temperature=0.2):
    return ChatGoogleGenerativeAI(
        model=config.LLM_MODEL,
        temperature=temperature
    )

# Use LLM to enrich document content
def enrich_document_with_llm(record: dict, llm):
    # Extract the basic information
    name = record['name']
    test_types = record.get('test_types', [])
    duration = record.get('duration', 'N/A')
    description = record.get('description', 'N/A')
    
    # Create a prompt for the LLM to analyze and enrich the document
    prompt = PromptTemplate(
        template="""
        You are an AI assistant helping to enrich assessment descriptions to improve search relevance.
        
        Please analyze the following SHL assessment information:
        
        Name: {name}
        Test Types: {test_types}
        Duration: {duration}
        Description: {description}
        
        Generate the following:
        1. Duration Category: Categorize as "short assessment (under 20 minutes)", "medium-length assessment (20-40 minutes)", or "longer assessment (over 40 minutes)"
        2. Keywords: Generate 5-10 relevant keywords for this assessment, focusing on skills assessed, job roles it's suitable for, and industries
        3. Summary: A 1-2 sentence summary that highlights the key aspects of this assessment
        
        Format your response as JSON with the following structure:
        {{
          "duration_category": "",
          "keywords": [],
          "summary": ""
        }}
        
        Only return the JSON, nothing else.
        """,
        input_variables=["name", "test_types", "duration", "description"]
    )
    
    # Create a chain for document enrichment
    enrichment_chain = LLMChain(llm=llm, prompt=prompt)
    
    # Run the chain
    try:
        test_types_str = ', '.join(test_types) if test_types else ''
        result = enrichment_chain.invoke({
            "name": name,
            "test_types": test_types_str,
            "duration": duration,
            "description": description
        })
        
        # Parse the JSON response
        import json
        enrichment = json.loads(result['text'])
        
        # Create the enhanced content
        enhanced_content = f"""
        Name: {name}
        Test Types: {test_types_str}
        Duration: {duration}
        Duration Category: {enrichment.get('duration_category', '')}
        Remote Testing Support: {record.get('remote_testing_support', 'N/A')}
        Adaptive IRT Support: {record.get('adaptive_irt_support', 'N/A')}
        Description: {description}
        Summary: {enrichment.get('summary', '')}
        Keywords: {', '.join(enrichment.get('keywords', []))}
        """
        
        return enhanced_content
    
    except Exception as e:
        print(f"Error enriching document {name}: {e}")
        # Fallback to basic content in case of error
        return f"""
        Name: {name}
        Test Types: {', '.join(test_types) if test_types else ''}
        Duration: {duration}
        Remote Testing Support: {record.get('remote_testing_support', 'N/A')}
        Adaptive IRT Support: {record.get('adaptive_irt_support', 'N/A')}
        Description: {description}
        """

# Function to extract metadata from JSON
def extract_metadata(record: dict) -> dict:
    return {
        "name": record['name'],
        "url": record.get('url', ''),
        "duration": record.get('duration', 'N/A'),
        "test_types": record.get('test_types', []),
        "remote_testing_support": record.get('remote_testing_support', 'N/A'),
        "adaptive_irt_support": record.get('adaptive_irt_support', 'N/A')
    }

# Set up the RAG system with FAISS vector store
def setup_rag_system():
    # Use HuggingFace embeddings (sentence-transformers) for document vectors
    embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
    
    # Check if we have a saved vector database (check for the actual index file)
    index_file_path = os.path.join(VECTOR_DB_PATH, "index.faiss")
    if os.path.exists(index_file_path):
        print(f"Loading existing vector database from {VECTOR_DB_PATH}")
        try:
            vector_store = FAISS.load_local(
                VECTOR_DB_PATH, 
                embeddings,
                allow_dangerous_deserialization=True  # Set to True as we trust our own files
            )
            print("Vector database loaded successfully")
        except Exception as e:
            print(f"Error loading vector database: {e}")
            print("Creating new vector database...")
            return create_new_vectordb(embeddings)
    else:
        print("Vector database not found. Creating new vector database...")
        return create_new_vectordb(embeddings)
    
    # Create retriever with search type and k value
    retriever = vector_store.as_retriever(
        search_type="mmr",  # Use Maximum Marginal Relevance for better diversity
        search_kwargs={
            "k": config.MAX_RESULTS,
            "fetch_k": config.MAX_RESULTS * 3,  # Fetch more documents then filter down
            "lambda_mult": 0.7  # Balance between relevance and diversity
        }
    )
    
    return retriever

# Create a new vector database
def create_new_vectordb(embeddings):
    # Load and process documents
    documents = load_assessments()
    print(f"Loaded {len(documents)} SHL assessments")
    
    # Create vector store
    vector_store = FAISS.from_documents(documents, embeddings)
    
    # Save vector store for future use
    print(f"Saving vector database to {VECTOR_DB_PATH}")
    vector_store.save_local(VECTOR_DB_PATH)
    print("Vector database saved successfully")
    
    # Create retriever with search type and k value
    retriever = vector_store.as_retriever(
        search_type="mmr",  # Use Maximum Marginal Relevance for better diversity
        search_kwargs={
            "k": config.MAX_RESULTS,
            "fetch_k": config.MAX_RESULTS * 3,  # Fetch more documents then filter down
            "lambda_mult": 0.7  # Balance between relevance and diversity
        }
    )
    
    return retriever

# Set up the LLM and RAG chain
def setup_llm_chain(retriever):
    # Set up Gemini model
    llm = get_llm(temperature=config.LLM_TEMPERATURE)
    
    # Create prompt for generating recommendations with improved guidance
    prompt_template = """
    You are an expert career advisor who specializes in SHL assessment recommendations.
    
    Based on the following job description or requirements:
    ```
    {input}
    ```
    
    And using only the following SHL assessment information:
    ```
    {context}
    ```
    
    Your task is to recommend the most relevant SHL assessment solutions that match the job requirements.
    
    When analyzing the job description, consider:
    1. Skills and competencies mentioned (technical, soft skills, etc.)
    2. Time constraints or duration requirements
    3. Types of assessments that would be helpful (cognitive, behavioral, personality, etc.)
    
    Recommend at most 10 (minimum 1) most relevant SHL assessment solutions.
    
    For each recommendation, provide the following in a clear narrative format:
    
    1. Name of the assessment
    2. Test types included
    3. Duration of the assessment
    4. Why this assessment is relevant to the job description (1-2 sentences)
    
    Format each recommendation as a numbered item with a clear heading and details in paragraph form.
    Do not use a table format. Use clear section breaks between recommendations.
    
    Only include assessments that are truly relevant to the query. If a job description mentions a time constraint, prioritize assessments that fit within that timeframe.
    """
    
    prompt = PromptTemplate(template=prompt_template, input_variables=["context", "input"])
    
    # Create RAG chain
    document_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, document_chain)
    
    return rag_chain

# Function to recommend assessments based on a query
def recommend_assessments(query: str, rag_chain):
    response = rag_chain.invoke({"input": query})
    return response["answer"]

# Load and process SHL assessments manually
def load_assessments():
    with open(config.ASSESSMENTS_FILE_PATH, 'r', encoding='utf-8') as f:
        assessments_data = json.load(f)
    
    # Initialize LLM for enrichment with very low temperature for consistency
    enrichment_llm = get_llm(temperature=0.1)
    
    print("Enriching assessment documents with LLM...")
    documents = []
    total = len(assessments_data)
    
    for i, assessment in enumerate(assessments_data):
        if i % 10 == 0:
            print(f"Processed {i}/{total} assessments")
            
        # Use LLM to enrich the document content
        content = enrich_document_with_llm(assessment, enrichment_llm)
        metadata = extract_metadata(assessment)
        documents.append(Document(page_content=content, metadata=metadata))
    
    print(f"Completed enrichment of {total} assessments")
    return documents

# Function to rebuild the vector database
def rebuild_vector_db():
    print("Rebuilding vector database...")
    
    # Delete existing vector database if it exists
    if os.path.exists(VECTOR_DB_PATH):
        import shutil
        shutil.rmtree(VECTOR_DB_PATH)
        print(f"Removed existing vector database at {VECTOR_DB_PATH}")
    
    # Create embeddings model
    embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
    
    # Create new vector database
    return create_new_vectordb(embeddings)

# Main function
def main():
    # Check for Google API key
    if not os.environ.get("GOOGLE_API_KEY"):
        print("WARNING: GOOGLE_API_KEY environment variable is not set.")
        print("Please add it to your .env file: GOOGLE_API_KEY=your_api_key")
        return
    
    # Create vectordb directory if it doesn't exist
    Path(VECTOR_DB_PATH).mkdir(exist_ok=True, parents=True)
    
    # Set up RAG system (will load or create vector database)
    retriever = setup_rag_system()
    
    # Set up LLM chain
    rag_chain = setup_llm_chain(retriever)
    
    # Interactive loop
    print(f"\n{config.APP_NAME} v{config.VERSION}")
    print("=" * len(f"{config.APP_NAME} v{config.VERSION}"))
    print("Enter a job description or requirements, and get recommended SHL assessments.")
    print("Type 'exit' to quit or 'rebuild' to recreate the vector database.")
    
    while True:
        query = input("\nEnter job description or requirements: ").strip()
        if query.lower() == 'exit':
            break
        elif query.lower() == 'rebuild':
            retriever = rebuild_vector_db()
            rag_chain = setup_llm_chain(retriever)
            continue
        
        print("\nFinding relevant assessments...")
        try:
            recommendations = recommend_assessments(query, rag_chain)
            print("\n" + recommendations)
        except Exception as e:
            print(f"Error generating recommendations: {e}")

if __name__ == "__main__":
    main()
