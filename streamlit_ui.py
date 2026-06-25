import streamlit as st
import requests
import chromadb
import sqlite3
import uuid
import json
from datetime import datetime

# --- CONFIGURATION ---
OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "qwen2.5:1.5b"

st.set_page_config(page_title="Corporate Semantic Memory POC", layout="wide", page_icon="🧠")

# --- INITIALIZE DATABASES ---
@st.cache_resource
def get_chroma_client():
    client = chromadb.PersistentClient(path="./semantic_vault")
    return client.get_or_create_collection(name="corporate_knowledge")

collection = get_chroma_client()

def init_sqlite():
    conn = sqlite3.connect("facts_vault.db", check_same_thread=False)
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

# --- BACKEND LOGIC FUNCTIONS ---
def get_embedding(text):
    url = f"{OLLAMA_URL}/api/embeddings"
    try:
        response = requests.post(url, json={"model": EMBED_MODEL, "prompt": text})
        return response.json().get("embedding", [])
    except:
        return []

def save_fact_to_both_dbs(fact_text, specific_id=None):
    memory_id = specific_id if specific_id else f"fact_{uuid.uuid4().hex[:8]}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    vector = get_embedding(fact_text)
    if vector:
        collection.add(embeddings=[vector], documents=[fact_text], ids=[memory_id])
    
    conn = sqlite3.connect("facts_vault.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO remembered_facts (id, timestamp, fact_text) VALUES (?, ?, ?)",
        (memory_id, timestamp, fact_text)
    )
    conn.commit()
    conn.close()

def evaluate_and_extract(user_message):
    """The Self-Editing Manager with FULL Few-Shot Prompting."""
    conn = sqlite3.connect("facts_vault.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT id, fact_text FROM remembered_facts")
    current_memory = cursor.fetchall()
    
    memory_context = "Empty." if not current_memory else "\n".join([f"ID: {row[0]} | Fact: {row[1]}" for row in current_memory])

    # --- UPGRADED PROMPT WITH UPDATE EXAMPLE ---
    eval_prompt = f"""You are a strict data extractor. Extract permanent profile facts (company, job, skills).

--- EXAMPLES ---

Example 1:
Current Profile: Empty.
User: "I am fixing a bug today"
{{
    "action": "IGNORE",
    "target_id": null,
    "fact": null
}}

Example 2:
Current Profile: Empty.
User: "I work at NSE India"
{{
    "action": "ADD",
    "target_id": null,
    "fact": "The user works at NSE India."
}}

Example 3:
Current Profile:
ID: fact_8273 | Fact: The user's primary programming language is Python.
User: "I actually switched my stack, I only use Rust now."
{{
    "action": "UPDATE",
    "target_id": "fact_8273",
    "fact": "The user's primary programming language is Rust."
}}

--- REAL TASK ---
Current Profile:
{memory_context}

User: "{user_message}"
"""

    try:
        response = requests.post(f"{OLLAMA_URL}/api/chat", json={
            "model": CHAT_MODEL,
            "messages": [{"role": "system", "content": eval_prompt}],
            "stream": False,
            "format": "json" 
        })
        
        raw_content = response.json()['message']['content'].strip()
        
        # Diagnostic printing to the VS Code terminal
        print(f"\n[AI LOGIC TRIGGERED] Message: '{user_message}'")
        print(f"[AI RAW JSON OUTPUT]: {raw_content}\n")
        
        if raw_content.startswith("```"):
            raw_content = raw_content.strip("`").replace("json", "", 1).strip()
            
        decision = json.loads(raw_content)
        action = str(decision.get("action")).upper() 
        new_fact = decision.get("fact")
        target_id = decision.get("target_id")

        if action == "ADD" and new_fact:
            save_fact_to_both_dbs(new_fact)
            st.toast(f"💾 Added New Fact: '{new_fact}'", icon="✨")
            
        elif action == "UPDATE" and new_fact and target_id:
            collection.delete(ids=[target_id])
            cursor.execute("DELETE FROM remembered_facts WHERE id = ?", (target_id,))
            conn.commit()
            save_fact_to_both_dbs(new_fact)
            st.toast(f"🔄 Overwrote Outdated Fact with: '{new_fact}'", icon="♻️")

    except Exception as e:
        print(f"[BACKGROUND ERROR]: {e}")
    finally:
        conn.close()

def search_memory(query, limit=1):
    query_vector = get_embedding(query)
    if not query_vector:
        return None
    results = collection.query(query_embeddings=[query_vector], n_results=limit)
    if results['documents'] and len(results['documents'][0]) > 0:
        return results['documents'][0][0]
    return None

# --- STREAMLIT UI LAYOUT ---
left_col, right_col = st.columns([3, 2], gap="large")

with left_col:
    header_col, btn_col = st.columns([3, 1])
    with header_col:
        st.subheader("💬 Corporate Assistant")
    with btn_col:
        if st.button("🗑️ New Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if user_input := st.chat_input("Message the AI assistant..."):
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        evaluate_and_extract(user_input)
        relevant_memory = search_memory(user_input)
        
        system_prompt = "You are a helpful corporate assistant. Use the context to inform your response if relevant. Be concise."
        if relevant_memory:
            system_prompt += f"\n\n[RELEVANT PROFILE FACT]: {relevant_memory}"
            st.info(f"🔍 **Context Injected:** {relevant_memory}")

        messages_payload = [{"role": "system", "content": system_prompt}] + [
            {"role": m["role"], "content": m["content"]} for m in st.session_state.messages
        ]
        
        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                try:
                    res = requests.post(f"{OLLAMA_URL}/api/chat", json={
                        "model": CHAT_MODEL,
                        "messages": messages_payload,
                        "stream": False
                    })
                    ai_reply = res.json()['message']['content']
                    st.markdown(ai_reply)
                    st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                except Exception as e:
                    st.error(f"Execution Error: {e}")
        st.rerun()

with right_col:
    st.subheader("📋 Active Semantic Profile")
    conn = sqlite3.connect("facts_vault.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, fact_text FROM remembered_facts ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        st.info("The profile is currently empty. Provide enduring facts to build the persona.")
    else:
        for idx, row in enumerate(rows):
            with st.expander(f"📌 Profile Fact #{len(rows) - idx}", expanded=True):
                st.write(f"**{row[1]}**")
                st.caption(f"Last updated: {row[0]}")