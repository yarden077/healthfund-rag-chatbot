# upload_to_pinecone
import os
from pinecone import Pinecone
from openai import AzureOpenAI
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

# Environment variables
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENVIRONMENT")
PINECONE_INDEX = os.getenv("PINECONE_INDEX")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY1")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT")
AZURE_OPENAI_API_VERSION = "2024-02-15-preview"

# Mapping Hebrew kupa names to ASCII-safe Pinecone namespaces
KUPA_NAMESPACE_MAP = {
    "מכבי": "maccabi",
    "מאוחדת": "meuhedet",
    "כללית": "clalit"
}

# Initialize Pinecone
pc = Pinecone(api_key = PINECONE_API_KEY, environment = PINECONE_ENV)
index = pc.Index(PINECONE_INDEX)

# Initialize Azure OpenAI client
openai_client = AzureOpenAI(
    api_key = AZURE_OPENAI_KEY,
    azure_endpoint = AZURE_OPENAI_ENDPOINT,
    api_version = AZURE_OPENAI_API_VERSION
)

def get_embedding(text):
    """
    Get embedding for the given text using Azure OpenAI.
    """
    response = openai_client.embeddings.create(
        input = text,
        model = AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT
    )
    return response.data[0].embedding

def upload_chunks_to_pinecone(chunks):
    """
    Uploads parsed HTML chunks to Pinecone, using healthFund as namespace.
    Embeds only service and benefit, but stores phones/links in metadata.
    """
    for i, chunk in enumerate(tqdm(chunks)):
        if chunk['chunk_type'] == "service":
            kupa_contacts = chunk.get("kupa_contacts", {})
            phones = ", ".join(kupa_contacts.get("phones", []))
            links = ", ".join(kupa_contacts.get("links", []))

            # Embed ONLY service and benefit
            embed_text = f"{chunk['service']} - {chunk['benefit']}"

            # Mapping hebrew healthFund names into English
            kupa_hebrew = chunk.get("kupa", "")
            kupa_namespace = KUPA_NAMESPACE_MAP.get(kupa_hebrew, "general")

            
            metadata = {
                "service": chunk.get("service", ""),
                "benefit": chunk.get("benefit", ""),
                "maslul": chunk.get("maslul", ""),
                "kupa": kupa_hebrew,
                "phones": phones,
                "links": links,
                "intro": chunk.get("intro", ""),
            }
            chunk_id = f"{kupa_namespace}_{i}"
            embedding = get_embedding(embed_text)
            index.upsert(
                vectors=[
                    {
                        "id": chunk_id,
                        "values": embedding,
                        "metadata": metadata
                    }
                ],
                namespace=kupa_namespace
            )
        elif chunk['chunk_type'] in ["intro", "outro"]:
            
            kupa_hebrew = chunk.get("kupa", "")
            kupa_namespace = KUPA_NAMESPACE_MAP.get(kupa_hebrew, "general")
            metadata = {
                "chunk_type": chunk["chunk_type"],
                "kupa": kupa_hebrew,
                "maslul": "",
                "service": "",
                "benefit": ""
            }
            chunk_id = f"{kupa_namespace}_{chunk['chunk_type']}"
            embedding = get_embedding(chunk['text'])
            index.upsert(
                vectors=[
                    {
                        "id": chunk_id,
                        "values": embedding,
                        "metadata": metadata
                    }
                ],
                namespace=kupa_namespace
            )

if __name__ == "__main__":
    from parse_html import parse_services_html
    import glob

    html_files = glob.glob("phase2_data/*.html")
    all_chunks = []
    for file in html_files:
        all_chunks.extend(parse_services_html(file))

    upload_chunks_to_pinecone(all_chunks)
    print("Upload finished!")