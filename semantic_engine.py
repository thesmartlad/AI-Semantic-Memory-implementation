import requests
import chromadb
import sqlite3
import uuid
from datetime import datetime

# --- CONFIGURATION ---
OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "qwen2.5:1.5b"

# --- 1. INITIALIZE DATABASES ---
print("[SYSTEM] Booting Dual-Database Semantic Engine...")

# Initialize ChromaDB (Vector Space for semantic search matching)
chroma_client = chromadb.PersistentClient(path="./semantic_vault")
collection = chroma_client.get_or_create_collection(name="auto_knowledge")

# Initialize SQLite (Relational Database for human visual auditing)
def init_sqlite():
    conn = sqlite3.connect("facts_vault.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS remembered_facts (
            id TEXT PRIMARY KEY,
            timestamp TEXT,
            fact_text TEXT
        )
    """)
    conn.commit()
    conn.close()

init_sqlite()

# --- 2. CORE FUNCTIONS ---
def get_embedding(text):
    """Converts a string of text into a mathematical vector using Ollama."""
    url = f"{OLLAMA_URL}/api/embeddings"
    try:
        response = requests.post(url, json={"model": EMBED_MODEL, "prompt": text})
        return response.json().get("embedding", [])
    except Exception as e:
        print(f" -> [!] Connection error generating embeddings: {e}")
        return []

def save_fact_to_both_dbs(fact_text):
    """Saves the extracted fact to ChromaDB for AI search AND SQLite for human review."""
    memory_id = f"fact_{uuid.uuid4().hex[:8]}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Layer A: Save to Vector DB (ChromaDB)
    vector = get_embedding(fact_text)
    if not vector:
        return
    collection.add(embeddings=[vector], documents=[fact_text], ids=[memory_id])
    
    # Layer B: Save to Normal DB (SQLite)
    conn = sqlite3.connect("facts_vault.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO remembered_facts (id, timestamp, fact_text) VALUES (?, ?, ?)",
        (memory_id, timestamp, fact_text)
    )
    conn.commit()
    conn.close()
    
    print(f"\n[DB WRITE SUCCESS]")
    print(f" -> 🟢 Vector Added to ChromaDB (ID: {memory_id})")
    print(f" -> 🟢 Row Added to SQLite facts_vault.db")
    print(f" -> [FACT DETECTED]: {fact_text}\n")

def print_sqlite_table():
    """Fetches and displays the normal SQLite database rows cleanly."""
    conn = sqlite3.connect("facts_vault.db")
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, fact_text FROM remembered_facts ORDER BY timestamp ASC")
    rows = cursor.fetchall()
    conn.close()
    
    print("\n" + "="*60)
    print(" 📋 RELATIONAL DATABASE SNAPSHOT (facts_vault.db) ")
    print("="*60)
    if not rows:
        print(" [Empty] No facts recorded yet.")
    else:
        for index, row in enumerate(rows, 1):
            print(f" [{index}] Recorded at {row[0]}")
            print(f"     Fact: {row[1]}")
    print("="*60 + "\n")

def evaluate_and_extract(user_message):
    """Hidden background agent that evaluates text and extracts standalone facts."""
    eval_prompt = f"""You are a strict data extraction system.
Analyze the following user message. Does it contain a personal fact, preference, project detail, or important structural information worth remembering for the future?
If YES: Output ONLY the extracted fact in a short, third-person declarative sentence (e.g., "The user lives in Mumbai"). Do not include any greeting, preamble, or punctuation marks.
If NO: Output exactly the word NO_FACT. Do not output anything else.

User message: {user_message}"""

    try:
        response = requests.post(f"{OLLAMA_URL}/api/chat", json={
            "model": CHAT_MODEL,
            "messages": [{"role": "system", "content": eval_prompt}],
            "stream": False
        })
        extracted_text = response.json()['message']['content'].strip()
        
        if "NO_FACT" not in extracted_text.upper() and len(extracted_text) > 4:
            save_fact_to_both_dbs(extracted_text)
    except Exception as e:
        print(f" -> [!] Background evaluation failed: {e}")

def search_memory(query, limit=1):
    """Searches the vector vault for relevant facts using distance scoring."""
    query_vector = get_embedding(query)
    if not query_vector:
        return None
    results = collection.query(query_embeddings=[query_vector], n_results=limit)
    if results['documents'] and len(results['documents'][0]) > 0:
        return results['documents'][0][0]
    return None

def ask_ai(user_query):
    """Generates the final conversational response injected with retrieved long-term memory."""
    relevant_fact = search_memory(user_query)
    
    system_prompt = "You are a helpful assistant. Use the provided context to inform your response if it is relevant. Otherwise, answer normally based on your knowledge base."
    if relevant_fact:
        system_prompt += f"\n\n[RELEVANT MEMORY FOUND]: {relevant_fact}"
        print(f" 🔍 [MEMORY RETRIEVED VIA CHROMADB]: {relevant_fact}")
    else:
        print(" -> [NO RELEVANT MEMORY FOUND]")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]

    try:
        response = requests.post(f"{OLLAMA_URL}/api/chat", json={
            "model": CHAT_MODEL,
            "messages": messages,
            "stream": False
        })
        print(f"\nAI: {response.json()['message']['content']}\n")
    except Exception as e:
        print(f" -> [!] Primary model execution failed: {e}")

# --- 3. INTERACTIVE TESTING LOOP ---
if __name__ == "__main__":
    print("\n--- Dual-Database Semantic Memory Active ---")
    print("Talk normally. The background agent will automatically evaluate input.")
    print("Type '/showfacts' at any time to view the normal SQLite database.")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() == 'exit':
            break
            
        # Catches "/showfacts" cleanly even with trailing spaces or casing differences
        if user_input.lower().startswith('/showfacts'):
            print_sqlite_table()
            continue
            
        # Execute the automated memory loop
        evaluate_and_extract(user_input)
        ask_ai(user_input)