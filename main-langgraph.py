from dotenv import load_dotenv

load_dotenv()

import json
import re
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Any

from pydantic import BaseModel
from langgraph.graph import StateGraph
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain.prompts import PromptTemplate

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
embedding_model = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

SHL_FILE = "shl_assessments.json"
VECTORSTORE_PATH = "shl_faiss_index"

class SHLAssessment(BaseModel):
    name: str
    url: str
    remote_testing_support: str
    adaptive_irt_support: str
    duration: Optional[str]
    test_types: List[str]
    description: str

with open(SHL_FILE, "r", encoding="utf-8") as f:
    shl_data = json.load(f)

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

if not Path(VECTORSTORE_PATH).exists():
    print("Creating FAISS vector store...")
    vectorstore = FAISS.from_documents(documents, embedding_model)
    vectorstore.save_local(VECTORSTORE_PATH)
else:
    print("Loading FAISS vector store...")
    vectorstore = FAISS.load_local(VECTORSTORE_PATH, embedding_model, allow_dangerous_deserialization=True)

bm25_retriever = BM25Retriever.from_documents(documents)
bm25_retriever.k = 10

dense_retriever = vectorstore.as_retriever(search_type="mmr", search_kwargs={"k": 10, "lambda_mult": 0.7})

class HybridRetriever:
    def __init__(self, dense_retriever, sparse_retriever, alpha=0.7):
        self.dense = dense_retriever
        self.sparse = sparse_retriever
        self.alpha = alpha

    def invoke(self, query):
        dense_results = self.dense.invoke(query)
        sparse_results = self.sparse.invoke(query)
        combined = {}
        for doc in dense_results:
            combined[doc.page_content] = self.alpha
        for doc in sparse_results:
            combined[doc.page_content] = combined.get(doc.page_content, 0) + (1 - self.alpha)
        ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)
        return [
            next(d for d in dense_results + sparse_results if d.page_content == content)
            for content, _ in ranked[:10]
        ]

retriever = HybridRetriever(dense_retriever, bm25_retriever)

query_prompt = PromptTemplate.from_template("""
Extract the following structured information from the job description below:
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

def extract_query_info(state):
    query = state.input
    prompt = query_prompt.format(job_description=query)
    response = llm.invoke(prompt).content
    response = re.sub(r"```json|```", "", response.strip())

    try:
        parsed = json.loads(response)
    except Exception as e:
        print("Failed to parse query info:", e)
        parsed = {"role": "", "skills": [], "preferences": [], "duration": "", "test_types": []}

    query_str = f"{parsed['role']} " + " ".join(parsed["skills"] + parsed["preferences"] + parsed["test_types"])
    return {"query_info": query_str, "input": query}

def perform_rag(state):
    query_info = state.query_info
    retrieved_docs = retriever.invoke(query_info)
    return {"retrieved_docs": retrieved_docs, "query_info": query_info}

def clean_json(obj):
    if isinstance(obj, dict):
        return {k: clean_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_json(i) for i in obj]
    elif isinstance(obj, np.generic):
        return obj.item()
    else:
        return obj

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

def rerank_and_filter(state):
    query_info = state.query_info
    docs = state.retrieved_docs

    doc_strings = [
        f"{doc.metadata['name']} - {doc.page_content}\nURL: {doc.metadata.get('url', 'N/A')}" for doc in docs
    ]
    doc_block = "\n".join([f"{i+1}. {s}" for i, s in enumerate(doc_strings)])

    prompt = prompt_template.format(query=query_info, docs=doc_block)
    response = llm.invoke(prompt).content.strip()

    try:
        match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if match:
            response = match.group(1).strip()
        parsed = json.loads(response)
    except json.JSONDecodeError as e:
        print("❌ Failed to parse LLM output as JSON:", e)
        print("Raw response:", response)
        parsed = []

    return {"final_recommendations": clean_json(parsed)}

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

def recommend_assessments(job_description: str):
    result = app.invoke({"input": job_description})
    return result["final_recommendations"]

jd = """
Looking to hire mid-level professionals who are proficient in Python, SQL and Java Script. Need an 
assessment package that can test all skills with max duration of 60 minutes. 
"""

print(json.dumps(recommend_assessments(jd), indent=2))