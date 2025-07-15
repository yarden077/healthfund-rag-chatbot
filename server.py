# server.py
from fastapi import FastAPI, Request
import os
from openai import AzureOpenAI
from dotenv import load_dotenv
from pinecone import Pinecone
import os, sys, logging  

logging.basicConfig(
    level=logging.INFO,                          
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
load_dotenv()

app = FastAPI()

# ENV and INIT
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY1")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT")
deployment_name = "gpt-4o"
AZURE_OPENAI_API_VERSION = "2024-02-15-preview"

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENVIRONMENT")
PINECONE_INDEX = os.getenv("PINECONE_INDEX")
pc = Pinecone(api_key = PINECONE_API_KEY, environment = PINECONE_ENV)
index = pc.Index(PINECONE_INDEX)

client = AzureOpenAI(
    api_key = AZURE_OPENAI_KEY,
    azure_endpoint = AZURE_OPENAI_ENDPOINT,
    api_version = AZURE_OPENAI_API_VERSION
)

# RAG HELPERS 
def get_query_embedding(query):
    """
    Gets the embedding vector for a query using Azure OpenAI.
    """
    response = client.embeddings.create(
        input = query,
        model = AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT
    )
    return response.data[0].embedding

def rag_retrieve(query, namespace, maslul, top_k = 5):
    """
    Retrieves relevant chunks from Pinecone by semantic similarity and filter (maslul).
    """
    logging.info(f"RAG: ns={namespace} | maslul={maslul} | q={query[:80]}")
    emb = get_query_embedding(query)
    filter_obj = {"maslul": {"$eq": maslul}} if maslul else None
    results = index.query(
        vector = emb,
        top_k = top_k,
        namespace = namespace,
        include_metadata = True,
        filter = filter_obj
    )
    return [m["metadata"] for m in results["matches"]]

# FASTAPI ENDPOINT
@app.post("/chat")
async def chat_endpoint(request: Request):
    """
    Main chat endpoint for the bot.
    Handles both phases:
    1. Info collection (collecting user identity/profile fields).
    2. Q&A (with RAG retrieval).
    Returns the LLM reply and, for debugging, also the RAG context and filters.
    """
    data = await request.json()
    history = data.get("history", [])
    phase = data.get("phase", "user_info")
    user_data = data.get("user_data", {})

    # System prompts
    user_info_system_prompt = (
        "You are a helpful assistant for health fund services in Israel. "
        "Before answering any service-related questions, you must verify the user's identity by collecting the following details through a natural, step-by-step conversation (not a form):\n"
        "- Full name (first and last)\n"
        "- ID number (9 digits)\n"
        "- Gender\n"
        "- Age (0-120)\n"
        "- HMO name (מכבי | מאוחדת | כללית)\n"
        "- HMO card number (9 digits)\n"
        "- Insurance membership tier (זהב | כסף | ארד)\n"
        "After collecting all details, summarize the information and ask the user for confirmation. "
        "Do not answer any service-related questions until the identity has been confirmed."
    )
    qa_system_prompt = (
        "You are an expert assistant for Israeli HMO (health-fund) services. "
        "Rely ONLY on the retrieved knowledge-base snippets and the user-provided profile to answer. "
        "If the answer is not found in those snippets, reply clearly that you don't have the information.\n\n"
        "Always reply in the same language as the user's question (Hebrew or English). "
        "If a question cannot be answered from the data, say so clearly."
        """ When relevant, add the HMO's phone and website at the end:
            טלפון: 
           לקישור לחץ [כאן>>](URL)"""
    )

    # RAG Retrieval for QA phase
    retrieved_docs = []     
    namespace = ""
    maslul = ""
    query = ""              
    context_text = ""

    if phase == "qa" and user_data:
        # Map HMO names from Hebrew to english for Pinecone namespaces
        kupa_map = {
            "מכבי": "maccabi",
            "מאוחדת": "meuhedet",
            "כללית": "clalit"
        }
        namespace = kupa_map.get(user_data.get("hmo_name", ""), "general")
        maslul = user_data.get("membership_tier", "")
        # Last user message as RAG query
        for msg in reversed(history):
            if msg["role"] == "user":
                query = msg["content"]
                break
        retrieved_docs = rag_retrieve(query, namespace, maslul, top_k=4)

        # Build context for the LLM 
        if retrieved_docs:
            for c in retrieved_docs:
                # Add intro (if exists and not empty)
                intro = c.get('intro', '').strip()
                intro_line = ""
                if intro:
                    intro_line = f"\nרקע: {intro}\n"
                context_text += f"{intro_line}● {c.get('service', '')} - {c.get('benefit', '')}\n"
                if c.get("phones"):
                    context_text += f"טלפון: {c['phones']}\n"
                if c.get("links"):
                    context_text += f"[לקישור לחץ כאן>>]({c['links']})\n"
            context_text = f"\nמידע רלוונטי מהידע שנשאב (RAG):\n{context_text}\n"

    # Construct OpenAI prompt
    messages = [{"role": "system", "content": qa_system_prompt if phase == "qa" else user_info_system_prompt}]
    if context_text and phase == "qa":
        # Insert context just before last user message
        new_history = []
        found_user = False
        for msg in reversed(history):
            if not found_user and msg["role"] == "user":
                found_user = True
                new_history.append({"role": "assistant", "content": context_text})
            new_history.append(msg)
        messages.extend(reversed(new_history))
    else:
        messages.extend(history)

    # OpenAI Completion 
    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=messages,
            max_tokens=512,
            temperature=0.2,
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        import logging
        logging.exception("OpenAI call failed")
        answer = "Internal server error. Please try again later."

    # Return: LLM reply + RAG debug info
    return {
        "answer": answer,
        "retrieved_docs": retrieved_docs,
        "namespace": namespace,
        "maslul": maslul,
        "rag_query": query   
    }
#  User info extraction for app.py 
def get_user_data(chat_history):
    """
    Sends a system message to the LLM requesting only the extracted user info as a Python dict.
    Returns the dict (not shown in UI).
    """
    prompt = """
        Extract only the following user information as a Python dictionary from the conversation below.
        Do NOT add any text, explanations, or comments — only output a Python dict with these keys:
        'first_name', 'last_name', 'id_number', 'gender', 'age', 'hmo_name', 'hmo_card_number', 'membership_tier'.

        If a field is missing, use an empty string. Conversation:
    """
    history_text = ""
    for m in chat_history:
        prefix = "User:" if m["role"] == "user" else "Bot:"
        history_text += f"{prefix} {m['content']}\n"
    prompt += history_text

    response = client.chat.completions.create(
        model = deployment_name,
        messages = [
            {"role": "system", "content": "Extract user info for coding. Return only Python dict as requested."},
            {"role": "user", "content": prompt}
        ],
        max_tokens = 256,
        temperature = 0.0
    )
    answer = response.choices[0].message.content.strip()
    # Remove code fences if present
    if answer.startswith("```python"):
        answer = answer[9:]
    if answer.startswith("```"):
        answer = answer[3:]
    if answer.endswith("```"):
        answer = answer[:-3]
    answer = answer.strip()
    import ast
    try:
        user_info = ast.literal_eval(answer)
        return user_info
    except Exception:
        return {}

@app.post("/extract_user_data")
async def extract_user_data_endpoint(request: Request):
    """
    Receives chat history and extracts user info as a dict (returns JSON).
    """
    data = await request.json()
    history = data.get("history", [])
    user_info = get_user_data(history)  
    return {"user_data": user_info}