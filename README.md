# AI-Semantic-Memory-implementation


```markdown
# 🧠 Self-Editing Corporate Semantic Memory POC

An enterprise-grade Proof of Concept (POC) demonstrating a local, context-aware AI chatbot featuring a self-editing Semantic Persona Engine. This system is designed for internal corporate environments where daily conversational history is wiped for privacy, but enduring user profile states must be maintained persistently without database bloat.

## 🚀 Architectural Overview

Unlike typical episodic memory systems that continuously append conversational logs (leading to massive database growth and context-window pollution), this system implements a strict **JSON-driven CRUD (Create, Read, Update, Delete)** pipeline. 

A background agent evaluates incoming user messages against the existing profile using a local LLM, dynamically deciding whether to **IGNORE** conversational noise, **ADD** a newly discovered standing trait, or **UPDATE** an existing fact to reflect a state change.

### Tech Stack
* **Frontend UI:** Streamlit (Dual-column split-screen layout)
* **Vector Space (Semantic Retrieval):** ChromaDB + `nomic-embed-text`
* **Relational Storage (Visual Auditing):** SQLite (`facts_vault.db`)
* **Local Inference Engine:** Ollama + `qwen2.5:1.5b` (Optimized with Few-Shot Pattern Matching)

---

## ✨ Features

* **Dual-Database Layering:** Syncs high-dimensional embeddings to ChromaDB for mathematical semantic injection, while simultaneously maintaining a human-readable ledger in SQLite.
* **Strict Noise Filtering:** Automatically filters out temporary daily tasks, greetings, and generic questions to keep the permanent memory clean.
* **Autonomous Conflict Resolution:** If a user states a change in their role, tech stack, or location, the background engine identifies the conflicting old data, drops the outdated vector, and overwrites it to maintain a 1:1 state mapping.
* **Side-by-Side Live Dashboard:** Interactive chat screen on the left, with an auto-refreshing profile expander ledger on the right.

---

## 🛠️ Installation & Setup

### 1. Clone & Clean Environment
Ensure your project folder contains the main script named `streamlit_ui.py`.

### 2. Install Dependencies
Run the following command in your terminal to install the required application frameworks:
```bash
pip install streamlit chromadb requests

```

### 3. Pull Local AI Models

Ensure your local [Ollama](https://ollama.com/) service is active and running, then pull the specific model ecosystem used by this project:

```bash
ollama pull qwen2.5:1.5b
ollama pull nomic-embed-text

```

---

## 🚦 How to Run & Test

1. Launch the local web server from your project terminal:
```bash
streamlit run streamlit_ui.py

```


2. Open your browser to `http://localhost:8501`.

### Verification Protocol

* **Test 1 (Data Insertion):** Type *"My primary programming language for all projects is Python."* The right-hand panel will instantly update, capturing the trait.
* **Test 2 (Noise Rejection):** Type *"Can you help me fix a syntax error in this loop today?"* The chatbot will assist you, but the right-hand panel will completely ignore the temporary task.
* **Test 3 (Self-Editing Overwrite):** Type *"I actually switched my stack entirely. I only use Rust now."* The background agent will locate the old Python entry, delete it from both ChromaDB and SQLite, and insert the Rust profile fact—preventing database bloat.

---

## 🔒 Security & Data Privacy Note

This repository includes a `.gitignore` file configuration to ensure that local user data vaults are **never** accidentally pushed to a public cloud repository.

The following local data blocks remain strictly on your machine:

* `facts_vault.db` (SQLite relational profile file)
* `semantic_vault/` (ChromaDB vector embedding directory)

```

```
