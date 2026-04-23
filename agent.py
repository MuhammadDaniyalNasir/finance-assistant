# import os
# import json
# import pdfplumber
# from langchain_openai import OpenAIEmbeddings, ChatOpenAI
# from langchain_chroma import Chroma
# from langchain_core.documents import Document
# from langchain_core.tools import tool
# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langgraph.prebuilt import create_react_agent
# from langgraph.checkpoint.memory import MemorySaver
# from dotenv import load_dotenv
# load_dotenv()
# # ── 1. Embeddings + Vector Store ───────────────────────────────────────────
# embeddings = OpenAIEmbeddings(
#     model="text-embedding-3-small",
#     openai_api_key=os.getenv("OPENAI_API_KEY")
# )

# vector_store = Chroma(
#     collection_name="banking-app",
#     embedding_function=embeddings,
#     persist_directory="./chroma_db_new"
# )


# # ── 2. Helper Functions (MUST be defined before use) ──────────────────────
# def clamp_bbox(bbox, page_bbox):
#     print(f"[clamp_bbox] Clamping bbox {bbox} within page_bbox {page_bbox}")
#     x0, top, x1, bottom = bbox
#     px0, ptop, px1, pbottom = page_bbox
#     result = (
#         max(x0, px0),
#         max(top, ptop),
#         min(x1, px1),
#         min(bottom, pbottom)
#     )
#     print(f"[clamp_bbox] Result: {result}")
#     return result



# def table_to_text(headers: list, rows: list[dict]) -> str:
#     print(f"[table_to_text] Converting table with {len(headers)} headers and {len(rows)} rows")
#     lines = ["Table columns: " + ", ".join(headers)]
#     for row in rows:
#         lines.append(" | ".join(f"{k}: {v}" for k, v in row.items() if v))
#     result = "\n".join(lines)
#     print(f"[table_to_text] Generated {len(lines)} lines of text")
#     return result





# def get_bank_name(filename: str) -> str:
#     print(f"[get_bank_name] Processing filename: {filename}")
#     name_map = {
#         "SOC":  "State Bank of Pakistan (SBP)",
#         # "SOBC": "Bank of China (SOBC)",
#         "UBL":  "United Bank Limited (UBL)",
#         "HBL":  "Habib Bank Limited (HBL)",
#         "MCB":  "MCB Bank",
#         "ABL":  "Allied Bank Limited (ABL)",
#         "NBP":  "National Bank of Pakistan (NBP)",
#     }
#     filename_upper = filename.upper()
#     for key, full_name in name_map.items():
#         if key in filename_upper:
#             print(f"[get_bank_name] Matched '{key}' -> {full_name}")
#             return full_name
#     fallback = filename.replace(".pdf", "")  # fallback
#     print(f"[get_bank_name] No match found, using fallback: {fallback}")
#     return fallback



# def extract_docs_from_pdf(pdf_path: str) -> list[Document]:
#     print(f"[extract_docs_from_pdf] Starting extraction from: {pdf_path}")
#     docs = []
#     filename = os.path.basename(pdf_path)
#     print(f"[extract_docs_from_pdf] Filename: {filename}")
#     bank_name = get_bank_name(filename)
#     print(f"[extract_docs_from_pdf] Bank name identified: {bank_name}")

#     with pdfplumber.open(pdf_path) as pdf:
#         print(f"[extract_docs_from_pdf] PDF opened. Total pages: {len(pdf.pages)}")
#         for page_num, page in enumerate(pdf.pages, start=1):
#             print(f"[extract_docs_from_pdf] Processing page {page_num}")
#             tables       = page.find_tables()
#             table_bboxes = [t.bbox for t in tables]
#             print(f"[extract_docs_from_pdf] Found {len(tables)} tables on page {page_num}")

#             # ── Text (excluding table regions) ──
#             text_page = page
#             for bbox in table_bboxes:
#                 clamped = clamp_bbox(bbox, page.bbox)
#                 try:
#                     text_page = text_page.outside_bbox(clamped)
#                 except ValueError:
#                     pass

#             raw_text = text_page.extract_text()
#             if raw_text and raw_text.strip():
#                 print(f"[extract_docs_from_pdf] Page {page_num}: Added text document ({len(raw_text)} chars)")
#                 docs.append(Document(
#                     page_content=raw_text.strip(),
#                     metadata={
#                         "source":    filename,
#                         "bank_name": bank_name,
#                         "page":      page_num,
#                         "type":      "text"
#                     }
#                 ))

#             # ── Tables ──
#             for tbl_idx, table in enumerate(tables):
#                 rows = table.extract()
#                 if not rows or len(rows) < 2:
#                     print(f"[extract_docs_from_pdf] Page {page_num}, Table {tbl_idx}: Skipped (insufficient rows)")
#                     continue
#                 print(f"[extract_docs_from_pdf] Page {page_num}, Table {tbl_idx}: Processing {len(rows)} rows")

#                 raw_headers = rows[0]
#                 headers = [
#                     (str(h).strip() if h and str(h).strip() else f"col_{i}")
#                     for i, h in enumerate(raw_headers)
#                 ]
#                 structured_rows = []
#                 for row in rows[1:]:
#                     record = {
#                         headers[i] if i < len(headers) else f"col_{i}":
#                         (str(cell).strip() if cell else "")
#                         for i, cell in enumerate(row)
#                     }
#                     structured_rows.append(record)

#                 print(f"[extract_docs_from_pdf] Page {page_num}, Table {tbl_idx}: Added table document with {len(headers)} headers")
#                 docs.append(Document(
#                     page_content=table_to_text(headers, structured_rows),
#                     metadata={
#                         "source":      filename,
#                         "bank_name":   bank_name,
#                         "page":        page_num,
#                         "type":        "table",
#                         "table_index": tbl_idx,
#                         "headers":     json.dumps(headers),
#                         "raw_json":    json.dumps(structured_rows)
#                     }
#                 ))
#     print(f"[extract_docs_from_pdf] Extraction complete. Total documents: {len(docs)}")
#     return docs


# def setup_vector_store():
#     print("[setup_vector_store] Starting vector store setup...")
#     # ── 3. Load all PDFs ───────────────────────────────────────────────────────
#     all_docs = []
#     print("[setup_vector_store] Scanning banks-data/ directory...")
#     for filename in os.listdir("banks-data/"):
#         if filename.endswith(".pdf"):
#             path = os.path.join("banks-data/", filename)
#             print(f"[setup_vector_store] Processing: {filename}")
#             extracted = extract_docs_from_pdf(path)
#             print(f"[setup_vector_store]  → {len(extracted)} chunks (text + tables)")
#             all_docs.extend(extracted)

#     print(f"[setup_vector_store] Total chunks extracted: {len(all_docs)}")



#     # ── 4. Split text chunks only (tables stay intact) ────────────────────────
#     print(f"[setup_vector_store] Initializing text splitter...")
#     text_splitter = RecursiveCharacterTextSplitter(
#         chunk_size=1000,
#         chunk_overlap=200,
#         add_start_index=True,
#     )

#     final_chunks = []
#     for doc in all_docs:
#         if doc.metadata.get("type") == "table":
#             final_chunks.append(doc)
#         else:
#             final_chunks.extend(text_splitter.split_documents([doc]))

#     print(f"[setup_vector_store] Final chunks after splitting: {len(final_chunks)}")




#     # ── 5. Ingest into ChromaDB in batches ────────────────────────────────────
#     print(f"[setup_vector_store] Starting batch ingestion into ChromaDB...")
#     BATCH_SIZE = 500
#     document_ids = []

#     for i in range(0, len(final_chunks), BATCH_SIZE):
#         batch = final_chunks[i:i + BATCH_SIZE]
#         ids = vector_store.add_documents(documents=batch)
#         document_ids.extend(ids)
#         print(f"[setup_vector_store] Inserted batch {i // BATCH_SIZE + 1} ({len(batch)} chunks)")

#     print(f"[setup_vector_store] Total inserted: {len(document_ids)} chunks")
#     print(f"[setup_vector_store] Vector store setup complete!")

#     return vector_store



# # ── 6. RAG Tool ───────────────────────────────────────────────────────────
# @tool(response_format="content_and_artifact")
# def retrieve_context(query: str):
#     """Retrieve relevant banking information including tables and text."""
#     print(f"[retrieve_context] Query received: '{query}'")
#     print(f"[retrieve_context] Searching vector store for 8 similar documents...")
#     retrieved_docs = vector_store.similarity_search(query, k=8)
#     print(f"[retrieve_context] Retrieved {len(retrieved_docs)} documents")
#     parts = []
#     for idx, doc in enumerate(retrieved_docs):
#         meta = doc.metadata
#         bank_name = meta.get("bank_name", meta.get("source", "Unknown Bank"))
#         print(f"[retrieve_context] Doc {idx + 1}: Type={meta.get('type')}, Bank={bank_name}, Page={meta.get('page')}")

#         if meta.get("type") == "table":
#             try:
#                 headers = json.loads(meta.get("headers", "[]"))
#                 table_str  = f"[SOURCE]\nBank: {bank_name}\nFile: {meta['source']}\nPage: {meta['page']}\n\n"
#                 table_str += f"Columns: {', '.join(headers)}\n"
#                 table_str += doc.page_content
#             except Exception as e:
#                 print(f"[retrieve_context] Error parsing table headers: {e}")
#                 table_str = doc.page_content
#             parts.append(table_str)
#         else:
#             parts.append(
#                 f"[TEXT] Bank: {bank_name} | Page {meta.get('page')}\n"
#                 f"{doc.page_content}"
#             )

#     print(f"[retrieve_context] Formatted {len(parts)} document parts for response")
#     return "\n\n---\n\n".join(parts), retrieved_docs


# def answer_query():
#     print("[answer_query] Initializing LLM agent...")
#     # ── 7. LLM + Agent ────────────────────────────────────────────────────────
#     print("[answer_query] Creating ChatOpenAI model (gpt-4o-mini)...")
#     model = ChatOpenAI(
#         model="gpt-4o-mini",
#         temperature=0,
#         openai_api_key=os.getenv("OPENAI_API_KEY")
#     )
#     print("[answer_query] Model created successfully")

#     tools = [retrieve_context]
#     print(f"[answer_query] Registered {len(tools)} tool(s)")

#     system_prompt = """You are a car buying assistant using the data with access to Pakistani banking documents.
# Always Check before saying that this queries relevant data don't actually exists in db.
# STRICT RULES (MANDATORY):
# - Every numerical value MUST include citation.
# - Citation format MUST be exactly:
#   (Bank: <bank_name>, Page: <page>, Source: <filename>)


# - NEVER write any number without citation.
# - If multiple banks are compared, EACH row must include citation.

# - DO NOT summarize without attribution.

# When answering:
# 1. Always use the 'retrieve_context' tool first.
# 2. ALWAYS refer to banks by their REAL name from the metadata (bank_name field), never as "Bank A" or "Bank B".
# 3. Compare multiple banks in every response.
# 4. Cite the source document, bank name, and page number for every claim.
# 5. Use tables from retrieved data for interest rates and fees.

# NO RESPONSE EXCEPT FOR THE QUERIES RELATED TO THE BANKING NO OTHER QUERIES SHOULD BE ENTERTAINED AND ALSO MAKE SURE THAT YOU ONLY USE THE VECTOR DATABASE TO RESPOND.
# NO SELF MADE RESPONSE ONLY RESPONSE FROM THE VECTOR DATABASE WITH ITS META DATA SHOULD BE MENTIONED.
# YOU ARE ENGLISH AGENT AND ALL THE RELEVANT QUERIES SHOULD BE ENTERTAINED NO SELF MADE INFORMATION.

# Use the following mapping to identify banks from filenames:
#         "SOC":  "State Bank of Pakistan (SBP)",

#         "UBL":  "United Bank Limited (UBL)",
#         "HBL":  "Habib Bank Limited (HBL)",
#         "MCB":  "MCB Bank",
#         "ABL":  "Allied Bank Limited (ABL)",
#         "NBP":  "National Bank of Pakistan (NBP)", 
# """

#     print("[answer_query] Creating ReAct agent with system prompt...")
#     agent = create_react_agent(
#         model,
#         tools,
#         prompt=system_prompt,
#         checkpointer=MemorySaver()
#     )
#     print("[answer_query] Agent created successfully")
#     return agent

# def run_agent(agent, messages):
#     print(f"[run_agent] Running agent with {len(messages)} message(s)")
#     print(f"[run_agent] Invoking agent...")
#     response = agent.invoke(
#         {"messages": messages},
#         {"configurable": {"thread_id": "session-1"}}
#     )
#     print(f"[run_agent] Agent response received with {len(response['messages'])} message(s)")
#     final_content = response["messages"][-1].content
#     print(f"[run_agent] Response length: {len(final_content)} characters")
#     print(f"[run_agent] Returning final response")
#     return final_content



import os
import json
import pdfplumber
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv

load_dotenv()

# ── 1. Embeddings ─────────────────────────────────────────────────────────────
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

# ── 2. Helper Functions ───────────────────────────────────────────────────────
def clamp_bbox(bbox, page_bbox):
    x0, top, x1, bottom = bbox
    px0, ptop, px1, pbottom = page_bbox
    return (
        max(x0, px0),
        max(top, ptop),
        min(x1, px1),
        min(bottom, pbottom)
    )


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
    filename_upper = filename.upper()
    for key, full_name in name_map.items():
        if key in filename_upper:
            return full_name
    return filename.replace(".pdf", "")


def extract_docs_from_pdf(pdf_path: str) -> list[Document]:
    print(f"[extract_docs_from_pdf] Extracting: {pdf_path}")
    docs = []
    filename = os.path.basename(pdf_path)
    bank_name = get_bank_name(filename)

    with pdfplumber.open(pdf_path) as pdf:
        print(f"  → {len(pdf.pages)} pages")
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.find_tables()
            table_bboxes = [t.bbox for t in tables]

            # Text (excluding table regions)
            text_page = page
            for bbox in table_bboxes:
                clamped = clamp_bbox(bbox, page.bbox)
                try:
                    text_page = text_page.outside_bbox(clamped)
                except ValueError:
                    pass

            raw_text = text_page.extract_text()
            if raw_text and raw_text.strip():
                docs.append(Document(
                    page_content=raw_text.strip(),
                    metadata={
                        "source": filename,
                        "bank_name": bank_name,
                        "page": page_num,
                        "type": "text"
                    }
                ))

            # Tables
            for tbl_idx, table in enumerate(tables):
                rows = table.extract()
                if not rows or len(rows) < 2:
                    continue

                raw_headers = rows[0]
                headers = [
                    (str(h).strip() if h and str(h).strip() else f"col_{i}")
                    for i, h in enumerate(raw_headers)
                ]
                structured_rows = [
                    {
                        headers[i] if i < len(headers) else f"col_{i}":
                        (str(cell).strip() if cell else "")
                        for i, cell in enumerate(row)
                    }
                    for row in rows[1:]
                ]

                docs.append(Document(
                    page_content=table_to_text(headers, structured_rows),
                    metadata={
                        "source": filename,
                        "bank_name": bank_name,
                        "page": page_num,
                        "type": "table",
                        "table_index": tbl_idx,
                        "headers": json.dumps(headers),
                        "raw_json": json.dumps(structured_rows)
                    }
                ))

    print(f"  → {len(docs)} chunks extracted")
    return docs


def _is_vector_store_populated(vs: Chroma) -> bool:
    """Check if the ChromaDB collection already has documents."""
    try:
        count = vs._collection.count()
        print(f"[vector_store] Collection has {count} documents")
        return count > 0
    except Exception as e:
        print(f"[vector_store] Could not check count: {e}")
        return False


def setup_vector_store() -> Chroma:
    """
    Initialize ChromaDB. If it's already populated (persisted from a prior run),
    skip re-ingestion. Otherwise ingest all PDFs from banks-data/.
    """
    print("[setup_vector_store] Initializing vector store...")
    vs = Chroma(
        collection_name="banking-app",
        embedding_function=embeddings,
        persist_directory="./chroma_db_new"
    )

    if _is_vector_store_populated(vs):
        print("[setup_vector_store] Vector store already populated — skipping ingestion.")
        return vs

    print("[setup_vector_store] Vector store is empty — ingesting PDFs...")
    banks_dir = "banks-data/"

    if not os.path.isdir(banks_dir):
        print(f"[setup_vector_store] WARNING: '{banks_dir}' directory not found. "
              "Create it and add PDF files.")
        return vs

    pdf_files = [f for f in os.listdir(banks_dir) if f.endswith(".pdf")]
    if not pdf_files:
        print(f"[setup_vector_store] WARNING: No PDF files found in '{banks_dir}'.")
        return vs

    all_docs = []
    for filename in pdf_files:
        path = os.path.join(banks_dir, filename)
        extracted = extract_docs_from_pdf(path)
        all_docs.extend(extracted)

    print(f"[setup_vector_store] Total raw chunks: {len(all_docs)}")

    # Split text chunks; keep table chunks intact
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        add_start_index=True,
    )

    final_chunks = []
    for doc in all_docs:
        if doc.metadata.get("type") == "table":
            final_chunks.append(doc)
        else:
            final_chunks.extend(splitter.split_documents([doc]))

    print(f"[setup_vector_store] Final chunks after splitting: {len(final_chunks)}")

    BATCH_SIZE = 500
    for i in range(0, len(final_chunks), BATCH_SIZE):
        batch = final_chunks[i:i + BATCH_SIZE]
        vs.add_documents(documents=batch)
        print(f"[setup_vector_store] Inserted batch {i // BATCH_SIZE + 1} ({len(batch)} chunks)")

    print("[setup_vector_store] Ingestion complete!")
    return vs


# ── 3. Initialize vector store at module load time ───────────────────────────
# This runs once when the module is first imported (i.e. app startup).
print("[agent.py] Setting up vector store on startup...")
vector_store = setup_vector_store()
print("[agent.py] Vector store ready.")


# ── 4. RAG Tool ───────────────────────────────────────────────────────────────
@tool(response_format="content_and_artifact")
def retrieve_context(query: str):
    """Retrieve relevant banking information including tables and text."""
    print(f"[retrieve_context] Query: '{query}'")
    retrieved_docs = vector_store.similarity_search(query, k=8)
    print(f"[retrieve_context] Retrieved {len(retrieved_docs)} documents")

    if not retrieved_docs:
        return "No relevant documents found in the database.", []

    parts = []
    for idx, doc in enumerate(retrieved_docs):
        meta = doc.metadata
        bank_name = meta.get("bank_name", meta.get("source", "Unknown Bank"))

        if meta.get("type") == "table":
            try:
                headers = json.loads(meta.get("headers", "[]"))
                text = (
                    f"[TABLE] Bank: {bank_name} | File: {meta['source']} | Page: {meta['page']}\n"
                    f"Columns: {', '.join(headers)}\n"
                    f"{doc.page_content}"
                )
            except Exception:
                text = doc.page_content
            parts.append(text)
        else:
            parts.append(
                f"[TEXT] Bank: {bank_name} | Page {meta.get('page')}\n"
                f"{doc.page_content}"
            )

    return "\n\n---\n\n".join(parts), retrieved_docs


# ── 5. Agent Factory ──────────────────────────────────────────────────────────
def answer_query():
    print("[answer_query] Creating agent...")
    model = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )

    system_prompt = """You are a car buying assistant with access to Pakistani banking documents.
Always check the vector database before saying data doesn't exist.

STRICT RULES (MANDATORY):
- Every numerical value MUST include a citation.
- Citation format: (Bank: <bank_name>, Page: <page>, Source: <filename>)
- NEVER write any number without citation.
- If multiple banks are compared, EACH row must include citation.
- DO NOT summarize without attribution.

When answering:
1. Always use the 'retrieve_context' tool first.
2. ALWAYS refer to banks by their REAL name from the metadata (bank_name field).
3. Compare multiple banks in every response when possible.
4. Cite source document, bank name, and page number for every claim.
5. Use tables from retrieved data for interest rates and fees.

Only answer queries related to banking. For unrelated queries, politely decline.
Use ONLY information from the vector database — no self-made responses.
All responses must be in English.

Bank name mapping from filenames:
  SOC  → State Bank of Pakistan (SBP)
  UBL  → United Bank Limited (UBL)
  HBL  → Habib Bank Limited (HBL)
  MCB  → MCB Bank
  ABL  → Allied Bank Limited (ABL)
  NBP  → National Bank of Pakistan (NBP)
"""

    agent = create_react_agent(
        model,
        [retrieve_context],
        prompt=system_prompt,
        checkpointer=MemorySaver()
    )
    print("[answer_query] Agent ready.")
    return agent


def run_agent(agent, messages):
    print(f"[run_agent] Invoking agent with {len(messages)} message(s)...")
    response = agent.invoke(
        {"messages": messages},
        {"configurable": {"thread_id": "session-1"}}
    )
    return response["messages"][-1].content