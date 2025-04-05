# SHL Assessment Recommendation System

A RAG (Retrieval-Augmented Generation) application that recommends SHL assessments based on job descriptions or natural language queries.

## Features

- Takes natural language job descriptions or requirements as input
- Uses RAG with FAISS vector search to find relevant SHL assessments
- Leverages Google's Gemini 2.0 Flash model for generating recommendations
- Returns a formatted table of up to 10 most relevant assessments
- Provides explanation of why each assessment is relevant to the query

## Prerequisites

- Python 3.8+
- Required packages:
  - langchain
  - langchain-google-genai
  - faiss-cpu
  - pandas
  - sentence-transformers
  - python-dotenv

## Setup

1. Install requirements:
```
pip install langchain langchain-google-genai faiss-cpu pandas sentence-transformers python-dotenv
```

2. Set up Google API key:
```
cp .env.example .env
```
Then edit the `.env` file and add your Google API key.

3. Ensure the `shl_assessments.json` file is in the `crawler` directory

## Usage

1. Run the application:
```
python main.py
```

2. Enter a job description or requirements when prompted

3. View the recommended SHL assessments in a table format

4. Type 'exit' to quit the application

## Example

```
Enter job description or requirements: I need to hire a customer service representative for our call center who will handle customer inquiries and complaints.

Finding relevant assessments...

| Name | Test Types | Duration | Relevance |
|------|------------|----------|-----------|
| Contact Center Customer Service + 8.0 | Ability, Behavioral, Cognitive, Personality, Situational | 41 minutes | Specifically designed for contact center customer service roles, assessing all key competencies needed for handling customer inquiries and complaints. |
| Contact Center Customer Service 8.0 | Situational, Behavioral | 31 minutes | Focuses on situational judgment and behavioral aspects critical for customer service representatives handling inquiries. |
| Customer Service Professional Solution | Ability, Behavioral, Personality | 45 minutes | Evaluates essential customer service skills for representatives responding to inquiries and resolving complaints. |
... (additional results)
```

## Architecture

- **Document Processing**: Converts SHL assessment data into searchable documents
- **Vector Storage**: Uses FAISS for efficient similarity searching
- **Embedding Model**: Uses Sentence Transformers to create vector embeddings
- **LLM Integration**: Leverages Google's Gemini 2.0 Flash for intelligent recommendations
- **RAG Chain**: Combines retrieval with generation for context-aware responses 