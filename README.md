# 🤖 AI Banking Chatbot

A dual-mode AI-powered document assistant built with **Streamlit**, **LangGraph**, and **ChromaDB**. 

## 🎯 Features

### 🏦 Bank RAG Mode (Default)
- Query a pre-loaded vector database of Pakistani banking documents
- Compare interest rates, fees, and products across multiple banks
- Retrieve citations with bank name, page number, and source file
- Strict adherence to banking data — no invented information

**Supported Banks:**
- State Bank of Pakistan (SBP)
- United Bank Limited (UBL)
- Habib Bank Limited (HBL)
- MCB Bank
- Allied Bank Limited (ABL)
- National Bank of Pakistan (NBP)

### 📄 PDF Upload Mode
- Switch context by uploading any PDF document
- Ask questions about the uploaded document's content
- All answers grounded in the document with page citations
- Automatic mode switching and chat history reset

### 🔧 Technical Highlights
- **LangGraph ReAct Agent** — Agentic reasoning with tool use
- **Persistent + Ephemeral Vector Stores** — Bank docs (persistent) vs. uploads (in-memory)
- **RAG Tools** — Semantic search with metadata filtering
- **Streamlit Frontend** — Real-time chat with custom CSS theming

---

## 📦 Installation

### Prerequisites
- Python 3.9+
- OpenAI API key

### Steps

1. **Clone/navigate to the project:**
   ```bash
   cd banking-app
   ```

2. **Create a virtual environment:**
   ```bash
   python3 -m venv librariesenv
   source librariesenv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create a `.env` file** in the project root:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

---

## 🚀 Running the Application

### Start the Streamlit app:
```bash
streamlit run app.py
```

The app will open at `http://localhost:8501` by default.

### What happens on startup:
1. **agent.py** is imported and pre-warms the bank vector store
2. Bank PDFs from `banks-data/` are extracted and indexed (only on first run)
3. The Streamlit UI loads with Bank RAG mode active

---

## 📂 Project Structure

```
banking-app/
├── agent.py                 # LangGraph agent + RAG logic
├── app.py                   # Streamlit frontend
├── requirements.txt         # Python dependencies
├── README.md               # This file
├── .env                    # (local) OpenAI API key
├── banks-data/             # (optional) Banking PDFs
├── chroma_db_new/          # Persistent vector store
├── chroma_db_new/chroma.sqlite3
└── main.ipynb              # Jupyter notebook (legacy)
```

---

## 🔄 Usage Modes

### **Bank RAG Mode** (Default)
```
User: "What are the car loan interest rates at HBL?"
Agent: 
  1. Calls retrieve_bank_context("car loan interest rates HBL")
  2. Searches persistent bank vector store
  3. Returns results with citations
```

### **PDF Upload Mode**
```
User: [uploads document.pdf]
App switches to "Upload PDF Mode"

User: "Summarize the key points"
Agent:
  1. Calls retrieve_uploaded_pdf_context("key points")
  2. Searches ephemeral upload vector store
  3. Returns document excerpts with page numbers
```

---

## 🛠️ Key Components

### **agent.py**

#### Sections:
1. **Shared Helpers** — PDF extraction, table parsing, bank name mapping
2. **Bank Vector Store** — Persistent Chroma collection (pre-loads on import)
3. **Upload Vector Store** — Ephemeral in-memory collection per upload
4. **RAG Tools** — Two LangChain tools:
   - `retrieve_bank_context()` — Query banking docs
   - `retrieve_uploaded_pdf_context()` — Query uploaded PDFs
5. **Agent Factory** — Dual system prompts and agent builders

#### Key Functions:
- `_get_bank_vector_store()` — Lazy-loads bank docs on first access
- `ingest_uploaded_pdf()` — Temporary ingestion for uploaded files
- `clear_upload_vector_store()` — Cleanup on file removal
- `answer_query(use_uploaded_pdf)` — Returns appropriate agent

### **app.py**

#### Features:
- Responsive Streamlit UI with custom CSS
- Mode detection and auto-switch between Bank/Upload modes
- File upload with progress feedback
- Chat history management per mode
- Status indicators (bank 🟢 / upload 🔵)

#### Session State:
```python
st.session_state = {
    "messages":       [...],      # Chat history
    "agent":          agent,      # Current LangGraph agent
    "mode":           "bank",     # "bank" | "upload"
    "pdf_name":       filename,  # Active upload (or None)
    "pdf_chunks":     count,      # Chunks ingested
    "pdf_ingested":   bool,       # Flag for ingestion success
}
```

---

## 🔍 Vector Store Strategy

### Bank Store (Persistent)
```
Location:    ./chroma_db_new/
Collection:  banking-app
Scope:       Pre-loaded PDF documents from banks-data/
Lifespan:    Session to session (persisted to disk)
Access:      _get_bank_vector_store() [lazy]
```

### Upload Store (Ephemeral)
```
Location:    In-memory (no persist_directory)
Collection:  upload-{random_uuid}
Scope:       User's uploaded file only
Lifespan:    Duration of upload; cleared on file removal
Access:      ingest_uploaded_pdf() [on file select]
```

---

## 📋 System Prompts

### Bank RAG Mode
- Specializes in Pakistani banking queries
- Requires citations for all numerical values
- Compares multiple banks when possible
- Rejects non-banking queries

### Upload Mode
- General-purpose document assistant
- Grounds all answers in PDF content
- Cites page numbers
- Accepts any question about the document

---

## 🐛 Debugging & Logging

Both `agent.py` and `app.py` include `print()` statements with `[tag]` prefixes for debugging:

```python
# agent.py
[extract_docs]
[bank_vs]
[upload_vs]
[tool:bank]
[tool:upload]
[answer_query]

# app.py
[sidebar]
[session_state]
[file_processing]
[reset]
[main_ui]
[display_chat]
[chat_input]
[response_generation]
```

Run with `streamlit run app.py` to see logs in the terminal.

---

## ⚙️ Configuration

### Environment Variables (.env)
```ini
OPENAI_API_KEY=sk-...
```

### Tunable Parameters (agent.py)
```python
# Text splitting
chunk_size=1000
chunk_overlap=200

# Retrieval
k=8  # Number of documents to retrieve per query

# Batching
BATCH_SIZE=500  # Chunks per ChromaDB insertion
```

---

## 🚨 Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'langchain'` | Run `pip install -r requirements.txt` |
| `OPENAI_API_KEY` not found | Create `.env` file with your key |
| `No PDFs found in 'banks-data/'` | Create `banks-data/` folder and add PDF files |
| Vector store persists old data | Delete `chroma_db_new/` directory to reset |
| Chat mode stuck in Upload | Remove the uploaded file to auto-reset to Bank mode |

---

## 🔐 Security Notes

- **API Keys**: Store `OPENAI_API_KEY` in `.env` — never commit to git
- **PDF Data**: Uploaded PDFs are stored in ephemeral in-memory collections; they are cleared on file removal or session end
- **Vector Store**: Bank PDFs are persisted to disk; consider access controls for sensitive data

---

## 📈 Performance

- **First Load**: ~5–10s (bank store initialization)
- **Query Response**: ~2–4s (LLM reasoning + retrieval)
- **Upload Ingestion**: ~1–3s per 100 pages (depends on file size)

---

## 🎨 UI Customization

Edit the CSS in `app.py` under the `<style>` tag to customize:
- Colors (`:root` variables)
- Fonts (`--font-head`, `--font-body`)
- Chat bubble styles
- Upload card appearance
- Scrollbar styling

---

## 📚 Dependencies Overview

| Package | Purpose |
|---------|---------|
| `streamlit` | Web UI framework |
| `langchain` | LLM orchestration & tools |
| `langgraph` | Agentic reasoning (ReAct) |
| `pdfplumber` | PDF text/table extraction |
| `chromadb` | Vector database |
| `langchain-openai` | OpenAI integration |
| `langchain-chroma` | Chroma integration |
| `python-dotenv` | Environment variable loading |
| `openai` | OpenAI API client |

---

## 🤝 Contributing

Suggestions for improvements:
1. Add support for more document formats (DOCX, TXT)
2. Implement export-to-PDF for chat transcripts
3. Add user authentication & multi-user support
4. Integrate with more LLM providers (Claude, Llama)
5. Add advanced RAG features (reranking, query expansion)

---

## 📝 License

This project is provided as-is for educational and commercial use.

---

## 📞 Support

For issues or questions, check the logs in the terminal where you ran `streamlit run app.py`.

Look for `[tag]` prefixed print statements to trace execution flow.

---

**Last Updated:** April 2024  
**Python Version:** 3.9+  
**Status:** ✅ Production Ready
