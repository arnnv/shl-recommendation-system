import asyncio
import json
import os
import re
import time
from typing import Any, Dict, List, Optional

import grpc
from dotenv import load_dotenv
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from rich.console import Console
from rich.panel import Panel

from langchain.prompts import PromptTemplate
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_deepseek import ChatDeepSeek
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langgraph.graph import StateGraph

# Load environment variables
load_dotenv()

console = Console()

# --- Environment Variable Loading and Validation ---
required_env_vars = [
    "DEEPSEEK_API_KEY",
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "OPENAI_API_KEY",
]

missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    console.print(f"[bold red]Error: Missing required environment variables: {', '.join(missing_vars)}[/bold red]")
    raise ValueError(f"Missing environment variables: {', '.join(missing_vars)}")

deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")
openai_api_key = os.getenv("OPENAI_API_KEY")

# --- LLM and Embedding Model Initialization ---
console.print("[cyan]Initializing LLM and Embedding Model...[/cyan]")
llm = ChatDeepSeek(model="deepseek-chat", temperature=0, api_key=deepseek_api_key)
embedding_model = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=openai_api_key)
console.print("[green]LLM and Embedding Model Initialized.[/green]")

SHL_FILE = "shl_assessments.json"
QDRANT_COLLECTION_NAME = "shl_assessments"

# --- Load SHL Data ---
console.print(f"[cyan]Loading SHL data from {SHL_FILE}...[/cyan]")
with open(SHL_FILE, "r", encoding="utf-8") as f:
    shl_data = json.load(f)
console.print(f"[green]Loaded {len(shl_data)} entries from {SHL_FILE}.[/green]")

# --- Prepare Documents ---
console.print("[cyan]Preparing LangChain documents...[/cyan]")
documents = [
    Document(
        page_content=(
            f"{entry['name']} - {entry['description']} "
            f"Type: {', '.join(entry.get('test_types', []))}. "
            f"Duration: {entry.get('duration', 'N/A')}. "
            f"Remote: {entry.get('remote_testing_support', 'Unknown')}. "
            f"Adaptive: {entry.get('adaptive_irt_support', 'Unknown')}. "
            f"URL: {entry.get('url', 'N/A')}."
        ),
        metadata=entry
    )
    for entry in shl_data
]
console.print(f"[green]Prepared {len(documents)} documents.[/green]")

# --- Qdrant Initialization (Optimized with Timing) ---
start_time_qdrant = time.perf_counter()
console.print(f"[cyan]Checking for Qdrant collection '{QDRANT_COLLECTION_NAME}' at {qdrant_url}...[/cyan]")
try:
    client = QdrantClient(
        url=qdrant_url,
        api_key=qdrant_api_key,
        prefer_grpc=True,
    )
    client.get_collection(collection_name=QDRANT_COLLECTION_NAME) # Check existence, ignore result
    console.print(f"[yellow]Found existing collection '{QDRANT_COLLECTION_NAME}'. Connecting...[/yellow]")
    vectorstore = QdrantVectorStore(
        client=client,
        collection_name=QDRANT_COLLECTION_NAME,
        embedding=embedding_model, 
    )
    qdrant_op = "Connected to existing"
except (UnexpectedResponse, ValueError, grpc._channel._InactiveRpcError) as e: 
    console.print(f"[yellow]Collection '{QDRANT_COLLECTION_NAME}' not found or connection error ({type(e).__name__}) ... Creating and populating...[/yellow]")
    start_time_create = time.perf_counter()
    vectorstore = QdrantVectorStore.from_documents(
        documents,
        embedding_model, 
        url=qdrant_url,
        prefer_grpc=True,
        api_key=qdrant_api_key,
        collection_name=QDRANT_COLLECTION_NAME,
    )
    end_time_create = time.perf_counter()
    console.print(f"[green]Created and populated collection in {end_time_create - start_time_create:.2f} seconds.[/green]")
    qdrant_op = "Created and populated new"

end_time_qdrant = time.perf_counter()
console.print(Panel(f"[green]Qdrant Setup Complete ({qdrant_op}).[/green]\nCollection: '{QDRANT_COLLECTION_NAME}'\nURL: {qdrant_url}\n[bold yellow]Total Time: {end_time_qdrant - start_time_qdrant:.2f} seconds[/bold yellow]", title="Vector Store Status", border_style="blue"))

# --- Retriever Initialization ---
console.print("[cyan]Initializing Retrievers...[/cyan]")
bm25_retriever = BM25Retriever.from_documents(documents)
bm25_retriever.k = 5

dense_retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 5})

class HybridRetriever(BaseModel):
    dense: Any 
    sparse: Any

    async def invoke(self, query):
        # Get results from both retrievers asynchronously
        dense_task = self.dense.ainvoke(query) 
        sparse_task = self.sparse.ainvoke(query) 
        
        dense_results, sparse_results = await asyncio.gather(dense_task, sparse_task)
        
        # Combine and re-rank (same logic as before)
        all_docs_map = {doc.metadata.get('name', doc.page_content[:50]): doc for doc in dense_results + sparse_results}

        combined_scores = {}
        for doc in dense_results:
            doc_id = doc.metadata.get('name', doc.page_content[:50])
            combined_scores[doc_id] = combined_scores.get(doc_id, 0) + 0.7
        for doc in sparse_results:
            doc_id = doc.metadata.get('name', doc.page_content[:50])
            combined_scores[doc_id] = combined_scores.get(doc_id, 0) + 0.3

        ranked_ids = sorted(combined_scores.items(), key=lambda item: item[1], reverse=True)

        final_results = []
        seen_ids = set()
        for doc_id, _ in ranked_ids: # Ignore unused score
            if doc_id not in seen_ids:
                final_results.append(all_docs_map[doc_id])
                seen_ids.add(doc_id)
            if len(final_results) >= 10: 
                break
        return final_results

retriever = HybridRetriever(dense=dense_retriever, sparse=bm25_retriever)

query_prompt = PromptTemplate.from_template("""
Extract the following structured information from the job description below.
Important: When listing skills or preferences, identify multi-word technical terms (e.g., 'Java Script', 'SQL Server', 'Machine Learning') and keep them as single strings. Do not split them.

Fields to extract:
- role (job title or general function)
- skills (list of technologies, concepts, or traits expected)
- preferences (assessment-related preferences like adaptive, coding, remote etc.)
- duration (if mentioned)
- test_types (type of assessments expected like coding, numerical, etc.)

Respond only in this format:
{{
    "role": "...",
    "skills": ["...", "..."],
    "preferences": ["...", "..."],
    "duration": "...",
    "test_types": ["...", "..."]
}}

Job description:
<job_description>
{job_description}
</job_description>
""")

async def extract_query_info(state):
    query = state.input
    console.print(Panel(f"[cyan]Step 1: Extracting Info from Job Description:[/cyan]\n{query}", title="Workflow Step", border_style="blue"))
    prompt = query_prompt.format(job_description=query)
    
    start_time_llm_extract = time.perf_counter()
    response = (await llm.ainvoke(prompt)).content
    end_time_llm_extract = time.perf_counter()
    console.print(f"[magenta]LLM Info Extraction took: {end_time_llm_extract - start_time_llm_extract:.2f} seconds[/magenta]")
    
    response = re.sub(r"```json|```", "", response.strip())

    try:
        parsed = json.loads(response)
        console.print("[green]Successfully parsed LLM response for query info.[/green]")
    except Exception as e:
        console.print(f"[bold red]❌ Failed to parse query info JSON:[/bold red] {e}")
        console.print(f"[red]Raw LLM Response:[/red]\n{response}")
        parsed = {"role": "", "skills": [], "preferences": [], "duration": "", "test_types": []}

    query_str = f"{parsed['role']} " + " ".join(parsed["skills"] + parsed["preferences"] + parsed["test_types"])
    console.print(f"[yellow]Generated Search Query:[/yellow] '{query_str}'")
    return {"query_info": query_str, "input": query}

async def perform_rag(state):
    query_info = state.query_info
    console.print(Panel(f"[cyan]Step 2: Performing Hybrid RAG for:[/cyan] '{query_info}'", title="Workflow Step", border_style="blue"))
    start_time_rag = time.perf_counter()
    # Use the async invoke method of HybridRetriever
    retrieved_docs = await retriever.invoke(query_info) 
    end_time_rag = time.perf_counter()
    console.print(f"[magenta]Hybrid Retrieval took: {end_time_rag - start_time_rag:.2f} seconds, got {len(retrieved_docs)} docs[/magenta]")
    return {"retrieved_docs": retrieved_docs, "query_info": query_info}

prompt_template = PromptTemplate.from_template("""
You are a helpful assistant tasked with selecting the most relevant SHL assessments for a given job.

Here is a summary of the job description:
{query}

Below are some SHL assessments (with their details):
{docs}

Please select the minimum 1 and maximum 10 most relevant assessments and return them in JSON format with the following fields for each:
- name
- url
- remote_testing_support
- adaptive_irt_support
- duration
- test_types

Respond ONLY with a JSON code block like:
```json
[{{"name": "...", "url": "...", "remote_testing_support": "...", "adaptive_irt_support": "...", "duration": "...", "test_types": [...]}}]
```
""")

async def rerank_and_filter(state):
    query_info = state.query_info
    docs = state.retrieved_docs
    console.print(Panel(f"[cyan]Step 3: Re-ranking/Filtering {len(docs)} retrieved docs based on query:[/cyan] '{query_info}'", title="Workflow Step", border_style="blue"))

    # Optimized: Send only key info to LLM for re-ranking
    doc_strings = [
        f"Name: {doc.metadata['name']}\nDescription: {doc.metadata['description']}\nTest Types: {', '.join(doc.metadata.get('test_types', []))}\nDuration: {doc.metadata.get('duration', 'N/A')}\nURL: {doc.metadata.get('url', 'N/A')}\nRemote Testing Support: {doc.metadata.get('remote_testing_support', 'Unknown')}\nAdaptive/IRT Support: {doc.metadata.get('adaptive_irt_support', 'Unknown')}"
        for doc in docs
    ]

    doc_block = "\n\n".join([f"Assessment {i+1}:\n{s}" for i, s in enumerate(doc_strings)]) # Changed separator

    prompt = prompt_template.format(query=query_info, docs=doc_block)
    
    start_time_llm_rerank = time.perf_counter()
    response = (await llm.ainvoke(prompt)).content.strip()
    end_time_llm_rerank = time.perf_counter()
    console.print(f"[magenta]LLM Re-ranking/Filtering took: {end_time_llm_rerank - start_time_llm_rerank:.2f} seconds[/magenta]")

    try:
        match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if match:
            response = match.group(1).strip()
        parsed = json.loads(response)
        console.print(f"[green]Successfully parsed final {len(parsed)} recommendations from LLM.[/green]")
    except json.JSONDecodeError as e:
        console.print(f"[bold red]❌ Failed to parse final recommendations JSON:[/bold red] {e}")
        console.print(f"[red]Raw LLM Response:[/red]\n{response}")
        parsed = []

    return {"final_recommendations": parsed}

class GraphState(BaseModel):
    input: str
    query_info: Optional[str] = None
    retrieved_docs: Optional[List[Document]] = None
    final_recommendations: Optional[List[Dict[str, Any]]] = None

workflow = StateGraph(GraphState)
workflow.add_node("extract_info", extract_query_info)
workflow.add_node("rag", perform_rag)
workflow.add_node("filter", rerank_and_filter)

workflow.set_entry_point("extract_info")
workflow.add_edge("extract_info", "rag")
workflow.add_edge("rag", "filter")
workflow.set_finish_point("filter")

app = workflow.compile()

async def recommend_assessments(job_description: str
):
    console.print(Panel(f"[bold blue]Starting SHL Recommendation Workflow for Job Description:[/bold blue]\n{job_description}", title="Workflow Start", border_style="green"))
    start_time_workflow = time.perf_counter()
    # Use async invoke for the compiled graph
    result = await app.ainvoke({"input": job_description})
    end_time_workflow = time.perf_counter()
    console.print(Panel(f"[bold green]Workflow Complete.[/bold green]\n[bold yellow]Total Workflow Time: {end_time_workflow - start_time_workflow:.2f} seconds[/bold yellow]", title="Workflow End", border_style="green"))
    return result["final_recommendations"]

# --- Main Execution (Example) ---
if __name__ == "__main__":
    jd = """
    I am hiring for Java developers who can also collaborate effectively with my business teams. Looking
    for an assessment(s) that can be completed in 40 minutes
    """
    
    # Run the async function using asyncio.run
    final_recommendations = asyncio.run(recommend_assessments(jd))
    
    console.print(Panel("[bold blue]Final Recommendations:[/bold blue]", border_style="magenta"))
    console.print_json(data=final_recommendations)