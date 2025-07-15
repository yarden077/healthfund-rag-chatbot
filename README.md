# healthfund-rag-chatbot
Microservice-based multilingual chatbot for Israeli health fund medical services (Maccabi, Meuhedet, Clalit) using Azure OpenAI, Pinecone, and Streamlit.
---

## Project Overview

This project is a stateless, microservice-based chatbot system for answering user questions about Israeli health fund medical services.
It supports **user identity verification**, advanced natural language Q&A, and retrieves answers from a knowledge base of real medical service documents (HTML files) using RAG (Retrieval-Augmented Generation).

**Key Features:**
- Stateless FastAPI backend (no server-side user state)
- Azure OpenAI GPT-based info collection & medical Q&A
- RAG with Pinecone for grounded, explainable answers
- Multilingual (Hebrew & English)
- Streamlit-based chat UI
- Structured user information flow (identity, HMO, tier)
- Comprehensive logging and error handling

---

##  Architecture

- **Backend:** FastAPI microservice (stateless), Pinecone RAG, Azure OpenAI API
- **Frontend:** Streamlit (pure client-side session)
- **Knowledge base:** Israeli health fund HTML service files, parsed and embedded
- **Data flow:** All state is managed on the frontend; all requests contain user info and conversation history.

---

##  Features

- **User Onboarding:**  
  Conversational collection of:
    - Full name
    - ID number (valid 9 digits)
    - Gender
    - Age (0-120)
    - HMO name (מכבי | מאוחדת | כללית)
    - HMO card number (9 digits)
    - Insurance tier (זהב | כסף | ארד)
    - Confirmation step before allowing Q&A

- **Medical Q&A:**  
  Answers questions about benefits, services, and coverage, tailored to user HMO/tier, grounded in the official knowledge base (RAG).

- **Hebrew/English support:**  
  Language auto-detection and reply in user’s language.

- **Robust Logging & Error Handling:**  
  Full trace logging (stdout) for API/RAG requests, errors, and debugging context.

---

##  Project Structure
```
├── app.py                # Streamlit frontend (UI)
├── server.py             # FastAPI backend (chat + RAG)
├── parse_html.py         # HTML parsing and data prep
├── upload_to_pinecone.py # Script to embed & upload KB to Pinecone
├── phase2_data/          # Folder with health fund HTML files (the KB)
├── requirements.txt      # All Python deps (see below)
├── .env                  # (not committed) Azure/Pinecone api keys
└── README.md
```
---

##  Setup Instructions

### 1. Clone & Install

```bash
git clone https://github.com/yarden077/healthfund-rag-chatbot.git
cd healthfund-rag-chatbot
pip install -r requirements.txt
```

### 2. Environment Variables
```bash
AZURE_OPENAI_KEY1=your-azure-openai-key
AZURE_OPENAI_ENDPOINT=your-azure-endpoint
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=your-embeddings-deployment-name
PINECONE_API_KEY=your-pinecone-key
PINECONE_ENVIRONMENT=your-pinecone-env
PINECONE_INDEX=your-pinecone-index
```

### Run
```bash
uvicorn server:app --reload
streamlit run app.py
```
