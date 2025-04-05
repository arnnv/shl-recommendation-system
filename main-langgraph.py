import os
from dotenv import load_dotenv

load_dotenv()

import json
from pathlib import Path
from typing import List, Optional, Dict, Any

from pydantic import BaseModel
from langgraph.graph import StateGraph, END
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate
import re
import json
import numpy as np

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
            f"Duration: {entry.get('duration', 'N/A')}."
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
\"\"\"
{job_description}
\"\"\"
""")

def extract_query_info(state):
    query = state.input
    prompt = query_prompt.format(job_description=query)
    response = llm.invoke(prompt).content

    # Strip code block if LLM returns it like ```json ... ```
    response = re.sub(r"```json|```", "", response.strip())

    try:
        parsed = json.loads(response)
    except Exception as e:
        print("Failed to parse query info:", e)
        parsed = {"role": "", "skills": [], "preferences": [], "duration": "", "test_types": []}

    # Embed only the values (combine into one string)
    query_str = f"{parsed['role']} " + " ".join(parsed["skills"] + parsed["preferences"] + parsed["test_types"])
    return {"query_info": query_str, "input": query}

def perform_rag(state):
    query_info = state.query_info

    docs_with_scores = vectorstore.similarity_search_with_score(query_info, k=10)

    results = []
    for doc, score in docs_with_scores:
        try:
            validated = SHLAssessment(**doc.metadata).model_dump()
            validated["score"] = score
            results.append(validated)
        except Exception as e:
            print("Validation failed for one result:", e)

    return {"results": results}

def clean_json(obj):
    """Recursively convert all NumPy types to native Python types."""
    if isinstance(obj, dict):
        return {k: clean_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_json(i) for i in obj]
    elif isinstance(obj, np.generic):
        return obj.item()
    else:
        return obj

def final_filtering(state):
    query_info = state.query_info
    assessments = state.results

    clean_assessments = clean_json(assessments)

    template = PromptTemplate.from_template("""
    You are a helpful assistant tasked with selecting the most relevant SHL assessments for a given job.

    Here is a summary of the job description:
    {query_info}

    Below are some SHL assessments (with their details):
    {assessments}

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

    prompt = template.format(
        query_info=query_info,
        assessments=json.dumps(clean_assessments, indent=2)
    )

    response = llm.invoke(prompt).content

    match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
    if match:
        response = match.group(1).strip()

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError as e:
        print("❌ Failed to parse LLM output as JSON:", e)
        print("Raw response:", response)
        return {"final_recommendations": []}

    return {"final_recommendations": parsed}

from typing import Optional, Dict, Any
from pydantic import BaseModel

class GraphState(BaseModel):
    input: str
    query_info: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    final_recommendations: Optional[List[Dict[str, Any]]] = None

workflow = StateGraph(GraphState)
workflow.add_node("extract_info", extract_query_info)
workflow.add_node("rag", perform_rag)
workflow.add_node("final_filtering", final_filtering)

workflow.set_entry_point("extract_info")
workflow.add_edge("extract_info", "rag")
workflow.add_edge("rag", "final_filtering")
workflow.set_finish_point("final_filtering")

app = workflow.compile()

app

def recommend_assessments(job_description: str):
    result = app.invoke({"input": job_description})
    return result["final_recommendations"]

jd = """
Looking to hire mid-level professionals who are proficient in Python, SQL and Java Script. Need an 
assessment package that can test all skills with max duration of 60 minutes. 
"""

print(json.dumps(recommend_assessments(jd), indent=2))
