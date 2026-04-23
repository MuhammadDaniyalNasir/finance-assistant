import os
import json
import uuid
import tempfile
import pdfplumber
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv
import streamlit as st
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
load_dotenv()

# ── Embeddings (shared) ───────────────────────────────────────────────────────
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

# ── Module-level store references ─────────────────────────────────────────────
_bank_vector_store:   Chroma | None = None
_upload_vector_store: Chroma | None = None


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Shared PDF extraction helpers
# ═════════════════════════════════════════════════════════════════════════════

def clamp_bbox(bbox, page_bbox):
    x0, top, x1, bottom = bbox
    px0, ptop, px1, pbottom = page_bbox
    return (max(x0, px0), max(top, ptop), min(x1, px1), min(bottom, pbottom))


def table_to_text(headers: list, rows: list[dict]) -> str:
    lines = ["Table columns: " + ", ".join(headers)]
    for row in rows:
        lines.append(" | ".join(f"{k}: {v}" for k, v in row.items() if v))
    return "\n".join(lines)


def get_bank_name(filename: str) -> str:
    name_map = {
        "SOC": "State Bank of Pakistan (SBP)",
        "UBL": "United Bank Limited (UBL)",
        "HBL": "Habib Bank Limited (HBL)",
        "MCB": "MCB Bank",
        "ABL": "Allied Bank Limited (ABL)",
        "NBP": "National Bank of Pakistan (NBP)",
    }
    for key, full_name in name_map.items():
        if key in filename.upper():
            return full_name
    return filename.replace(".pdf", "")


def extract_docs_from_pdf(pdf_path: str, source_label: str | None = None) -> list[Document]:
    """Extract text + table chunks from a PDF. source_label overrides metadata."""
    docs = []
    filename  = os.path.basename(pdf_path)
    label     = source_label or filename
    bank_name = get_bank_name(filename) if not source_label else label

    print(f"[extract_docs] '{label}'...")
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables       = page.find_tables()
            table_bboxes = [t.bbox for t in tables]

            text_page = page
            for bbox in table_bboxes:
                try:
                    text_page = text_page.outside_bbox(clamp_bbox(bbox, page.bbox))
                except ValueError:
                    pass

            raw_text = text_page.extract_text()
            if raw_text and raw_text.strip():
                docs.append(Document(
                    page_content=raw_text.strip(),
                    metadata={"source": label, "bank_name": bank_name,
                              "page": page_num, "type": "text"}
                ))

            for tbl_idx, table in enumerate(tables):
                rows = table.extract()
                if not rows or len(rows) < 2:
                    continue
                headers = [
                    (str(h).strip() if h and str(h).strip() else f"col_{i}")
                    for i, h in enumerate(rows[0])
                ]
                structured_rows = [
                    {headers[i] if i < len(headers) else f"col_{i}":
                     (str(cell).strip() if cell else "")
                     for i, cell in enumerate(row)}
                    for row in rows[1:]
                ]
                docs.append(Document(
                    page_content=table_to_text(headers, structured_rows),
                    metadata={
                        "source": label, "bank_name": bank_name,
                        "page": page_num, "type": "table",
                        "table_index": tbl_idx,
                        "headers": json.dumps(headers),
                        "raw_json": json.dumps(structured_rows)
                    }
                ))

    print(f"[extract_docs] → {len(docs)} chunks")
    return docs


def _split_and_ingest(vs: Chroma, docs: list[Document]) -> int:
    """Split text docs, keep tables intact, bulk-ingest into Chroma."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    final = []
    for doc in docs:
        if doc.metadata.get("type") == "table":
            final.append(doc)
        else:
            final.extend(splitter.split_documents([doc]))

    BATCH = 500
    for i in range(0, len(final), BATCH):
        vs.add_documents(documents=final[i:i + BATCH])
    return len(final)


def _format_docs(docs: list[Document]) -> str:
    if not docs:
        return "No relevant content found."
    parts = []
    for doc in docs:
        meta = doc.metadata
        src  = meta.get("bank_name", meta.get("source", "Unknown"))
        if meta.get("type") == "table":
            try:
                hdrs = json.loads(meta.get("headers", "[]"))
                text = (f"[TABLE] Source: {src} | Page: {meta['page']}\n"
                        f"Columns: {', '.join(hdrs)}\n{doc.page_content}")
            except Exception:
                text = doc.page_content
        else:
            text = f"[TEXT] Source: {src} | Page {meta.get('page')}\n{doc.page_content}"
        parts.append(text)
    return "\n\n---\n\n".join(parts)


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Bank vector store (persistent)
# ═════════════════════════════════════════════════════════════════════════════

def _get_bank_vector_store() -> Chroma:
    global _bank_vector_store
    if _bank_vector_store is not None:
        return _bank_vector_store

    print("[bank_vs] Initialising...")
    vs = Chroma(
        collection_name="banking-app",
        embedding_function=embeddings,
        persist_directory="./chroma_db_new"
    )

    try:
        count = vs._collection.count()
    except Exception:
        count = 0

    if count > 0:
        print(f"[bank_vs] Already populated ({count} docs). Skipping ingestion.")
        _bank_vector_store = vs
        return vs

    banks_dir = "banks-data/"
    if not os.path.isdir(banks_dir):
        print(f"[bank_vs] WARNING: '{banks_dir}' not found.")
        _bank_vector_store = vs
        return vs

    all_docs = []
    for fname in os.listdir(banks_dir):
        if fname.endswith(".pdf"):
            all_docs.extend(extract_docs_from_pdf(os.path.join(banks_dir, fname)))

    if all_docs:
        n = _split_and_ingest(vs, all_docs)
        print(f"[bank_vs] Ingested {n} chunks.")
    else:
        print(f"[bank_vs] No PDFs found in '{banks_dir}'.")

    _bank_vector_store = vs
    return vs


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Upload vector store (ephemeral, in-memory)
# ═════════════════════════════════════════════════════════════════════════════

def ingest_uploaded_pdf(pdf_bytes: bytes, filename: str) -> int:
    """
    Called by app.py when the user uploads a PDF.
    Builds an in-memory Chroma collection from the file.
    Returns number of chunks created.
    """
    global _upload_vector_store

    print(f"[upload_vs] Ingesting '{filename}'...")

    # Write to temp file so pdfplumber can open it
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        docs = extract_docs_from_pdf(tmp_path, source_label=filename)
    finally:
        os.unlink(tmp_path)

    # Fresh in-memory collection (unique name avoids stale data)
    vs = Chroma(
        collection_name=f"upload-{uuid.uuid4().hex[:8]}",
        embedding_function=embeddings,
        # No persist_directory → ephemeral / in-memory
    )
    n = _split_and_ingest(vs, docs)
    _upload_vector_store = vs
    print(f"[upload_vs] Ready — {n} chunks.")
    return n


def clear_upload_vector_store():
    """Call this when the user removes/replaces their uploaded PDF."""
    global _upload_vector_store
    if _upload_vector_store is not None:
        try:
            _upload_vector_store.delete_collection()
        except Exception:
            pass
        _upload_vector_store = None
    print("[upload_vs] Cleared.")


def has_uploaded_pdf() -> bool:
    return _upload_vector_store is not None


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 4 — RAG tools
# ═════════════════════════════════════════════════════════════════════════════

@tool(response_format="content_and_artifact")
def retrieve_bank_context(query: str):
    """Retrieve relevant information from the pre-loaded Pakistani bank documents."""
    print(f"[tool:bank] '{query}'")
    vs   = _get_bank_vector_store()
    docs = vs.similarity_search(query, k=8)
    print(f"[tool:bank] → {len(docs)} docs")
    return _format_docs(docs), docs


@tool(response_format="content_and_artifact")
def retrieve_uploaded_pdf_context(query: str):
    """Retrieve relevant information from the user's uploaded PDF document."""
    print(f"[tool:upload] '{query}'")
    if _upload_vector_store is None:
        return "No uploaded PDF is available.", []
    docs = _upload_vector_store.similarity_search(query, k=8)
    print(f"[tool:upload] → {len(docs)} docs")
    return _format_docs(docs), docs


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 5 — Agent factory
# ═════════════════════════════════════════════════════════════════════════════

_BANK_SYSTEM_PROMPT = """You are a car-buying and banking assistant with access to Pakistani banking documents.

STRICT RULES:
- Always call 'retrieve_bank_context' before answering.
- Every numerical value MUST have a citation: (Bank: <name>, Page: <n>, Source: <file>)
- NEVER invent data — use ONLY what the tool returns.
- Refer to banks by their full real name from metadata, never as "Bank A" etc.
- Compare multiple banks whenever possible.
- Only answer banking-related queries. Politely decline everything else.
- Respond in English only.

Bank name mapping (from filenames):
  SOC → State Bank of Pakistan (SBP)
  UBL → United Bank Limited (UBL)
  HBL → Habib Bank Limited (HBL)
  MCB → MCB Bank
  ABL → Allied Bank Limited (ABL)
  NBP → National Bank of Pakistan (NBP)
"""

_UPLOAD_SYSTEM_PROMPT = """You are a helpful general-purpose assistant. The user has uploaded a PDF document and wants to discuss its contents.

RULES:
- Always call 'retrieve_uploaded_pdf_context' first to find relevant passages.
- Base every answer ONLY on what is retrieved — do not guess or add outside knowledge.
- Cite the page number for every factual claim: (Page: <n>)
- If the PDF does not contain the answer, say so clearly.
- You may answer any question the user has about the document.
- Respond in English.
"""


def answer_query(use_uploaded_pdf: bool = False):
    """
    Returns a LangGraph ReAct agent.

    use_uploaded_pdf=False (default)
        → Banking specialist that queries the pre-loaded bank vector store.
    use_uploaded_pdf=True
        → General assistant that queries the user's uploaded PDF.
    """
    mode = "UPLOAD-PDF" if use_uploaded_pdf else "BANK-RAG"
    print(f"[answer_query] Creating agent — mode: {mode}")

    model = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )

    if use_uploaded_pdf:
        tools, system_prompt = [retrieve_uploaded_pdf_context], _UPLOAD_SYSTEM_PROMPT
    else:
        tools, system_prompt = [retrieve_bank_context], _BANK_SYSTEM_PROMPT

    agent = create_react_agent(
        model,
        tools,
        prompt=system_prompt,
        checkpointer=MemorySaver()
    )
    print(f"[answer_query] Agent ({mode}) ready.")
    return agent


def run_agent(agent, messages):
    response = agent.invoke(
        {"messages": messages},
        {"configurable": {"thread_id": "session-1"}}
    )
    return response["messages"][-1].content


# ── Pre-warm bank store at import time ────────────────────────────────────────
print("[agent.py] Pre-warming bank vector store...")
_get_bank_vector_store()
print("[agent.py] Startup complete.")
