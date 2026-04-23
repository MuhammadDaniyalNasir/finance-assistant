import streamlit as st
from agent import answer_query, run_agent, ingest_uploaded_pdf, clear_upload_vector_store

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Agent Chatbot",
    page_icon="🤖",
    layout="centered",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&display=swap');

:root {
    --bg:        #0d0f14;
    --surface:   #161a22;
    --border:    #252a36;
    --accent:    #4f8ef7;
    --accent2:   #a78bfa;
    --green:     #22c55e;
    --amber:     #f59e0b;
    --text:      #e8eaf0;
    --muted:     #6b7280;
    --user-bg:   #1e2435;
    --bot-bg:    #161a22;
    --radius:    14px;
    --font-head: 'Syne', sans-serif;
    --font-body: 'DM Sans', sans-serif;
}

html, body, .stApp { background: var(--bg) !important; color: var(--text); font-family: var(--font-body); }
.block-container { padding-top: 2rem !important; max-width: 800px !important; }
#MainMenu, footer, header { visibility: hidden; }

/* Title */
h1 {
    font-family: var(--font-head) !important;
    font-size: 1.9rem !important;
    font-weight: 700 !important;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0 !important;
    letter-spacing: -0.02em;
}

/* Status bar */
.status-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.78rem;
    color: var(--muted);
    margin: 4px 0 18px;
    font-family: var(--font-body);
}
.status-dot {
    width: 7px; height: 7px; border-radius: 50%;
    flex-shrink: 0;
}
.dot-bank   { background: var(--green);  box-shadow: 0 0 6px #22c55e88; }
.dot-upload { background: var(--accent); box-shadow: 0 0 6px #4f8ef788; }
.dot-busy   { background: var(--amber);  box-shadow: 0 0 6px #f59e0b88; }

/* Mode badge */
.mode-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-family: var(--font-head);
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    padding: 3px 10px;
    border-radius: 20px;
    margin-left: auto;
}
.badge-bank   { background: #0f2818; color: var(--green);  border: 1px solid #1a4a2a; }
.badge-upload { background: #0f1e40; color: var(--accent); border: 1px solid #1e3a6a; }

/* Upload section */
.upload-card {
    background: var(--surface);
    border: 1.5px dashed var(--border);
    border-radius: var(--radius);
    padding: 1rem 1.25rem 0.75rem;
    margin-bottom: 1rem;
    transition: border-color .2s;
}
.upload-card:hover { border-color: var(--accent); }
.upload-card.has-file { border-style: solid; border-color: #2d4060; }

.upload-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
}
.upload-label {
    font-family: var(--font-head);
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
}

/* File pill */
.file-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #1e2a40;
    border: 1px solid #2d4060;
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.8rem;
    color: var(--accent);
    font-weight: 500;
    margin: 4px 0 8px;
}

/* Progress / ingestion status */
.ingest-status {
    font-size: 0.78rem;
    color: var(--muted);
    margin: 4px 0;
    font-style: italic;
}

/* Chat messages */
.stChatMessage {
    background: var(--bot-bg) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    padding: 1rem 1.25rem !important;
    margin-bottom: 10px !important;
}
[data-testid="stChatMessageContent"] p { font-size: 0.95rem; line-height: 1.65; color: var(--text); }
.stChatMessage:has([data-testid="chatAvatarIcon-user"]) {
    background: var(--user-bg) !important;
    border-color: #2d3a55 !important;
}

/* Chat input */
.stChatInputContainer { margin-top: 4px; }
.stChatInputContainer > div {
    background: var(--surface) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: 12px !important;
}
.stChatInputContainer textarea {
    font-family: var(--font-body) !important;
    font-size: 0.93rem !important;
    color: var(--text) !important;
}

hr { border-color: var(--border) !important; margin: 0.6rem 0 !important; }
.stSpinner > div { border-top-color: var(--accent) !important; }
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 10px; }
</style>
""", unsafe_allow_html=True)


# ── Session state bootstrap ───────────────────────────────────────────────────
def _init_state():
    defaults = {
        "messages":            [],           # chat history (plain text dicts)
        "agent":               None,         # current LangGraph agent
        "mode":                "bank",       # "bank" | "upload"
        "pdf_name":            None,         # filename of active upload
        "pdf_chunks":          0,            # chunks ingested
        "pdf_ingested":        False,        # ingestion done flag
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# Lazy-init bank agent on first load
if st.session_state.agent is None and st.session_state.mode == "bank":
    st.session_state.agent = answer_query(use_uploaded_pdf=False)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 🤖 AI Agent")

mode        = st.session_state.mode
dot_class   = "dot-upload" if mode == "upload" else "dot-bank"
badge_class = "badge-upload" if mode == "upload" else "badge-bank"
mode_label  = f"📄 PDF Mode — {st.session_state.pdf_name}" if mode == "upload" else "🏦 Bank RAG Mode"
status_text = "Chatting with your uploaded PDF" if mode == "upload" else "Ready · Ask about Pakistani bank products"

st.markdown(f"""
<div class="status-bar">
    <div class="status-dot {dot_class}"></div>
    {status_text}
    <span class="mode-badge {badge_class}">{mode_label}</span>
</div>
""", unsafe_allow_html=True)


# ── PDF Upload panel ──────────────────────────────────────────────────────────
has_file = st.session_state.pdf_name is not None
card_cls = "upload-card has-file" if has_file else "upload-card"

st.markdown(f'<div class="{card_cls}">', unsafe_allow_html=True)
st.markdown("""
<div class="upload-header">
    <span class="upload-label">📄 Upload PDF (optional)</span>
</div>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    label="Upload PDF",
    type=["pdf"],
    label_visibility="collapsed",
    help="Upload any PDF to switch to document Q&A mode. Remove it to go back to bank mode.",
)

# ── Handle new upload ─────────────────────────────────────────────────────────
if uploaded_file is not None:
    is_new_file = st.session_state.pdf_name != uploaded_file.name

    if is_new_file:
        st.session_state.pdf_ingested = False       # reset flag for new file

    if not st.session_state.pdf_ingested:
        pdf_bytes = uploaded_file.read()
        st.markdown('<p class="ingest-status">⚙️ Building embeddings…</p>', unsafe_allow_html=True)

        with st.spinner(f"Ingesting '{uploaded_file.name}'…"):
            # Clear any previous upload store
            if st.session_state.pdf_name and is_new_file:
                clear_upload_vector_store()

            n_chunks = ingest_uploaded_pdf(pdf_bytes, uploaded_file.name)

        # Switch agent to upload mode & reset chat
        st.session_state.pdf_name    = uploaded_file.name
        st.session_state.pdf_chunks  = n_chunks
        st.session_state.pdf_ingested = True
        st.session_state.mode        = "upload"
        st.session_state.messages    = []
        st.session_state.agent       = answer_query(use_uploaded_pdf=True)
        st.rerun()

    # Show active file pill
    size_kb = uploaded_file.size // 1024 if hasattr(uploaded_file, "size") else "?"
    st.markdown(
        f'<div class="file-pill">'
        f'📎 {st.session_state.pdf_name}'
        f' &nbsp;·&nbsp; {size_kb} KB'
        f' &nbsp;·&nbsp; {st.session_state.pdf_chunks} chunks'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.caption("Remove the file above to switch back to Bank RAG mode.")

# ── Handle file removal ───────────────────────────────────────────────────────
elif st.session_state.pdf_name is not None:
    # File was removed — revert to bank mode
    clear_upload_vector_store()
    st.session_state.pdf_name     = None
    st.session_state.pdf_chunks   = 0
    st.session_state.pdf_ingested = False
    st.session_state.mode         = "bank"
    st.session_state.messages     = []
    st.session_state.agent        = answer_query(use_uploaded_pdf=False)
    st.rerun()

st.markdown("</div>", unsafe_allow_html=True)


# ── Chat history ──────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# ── Chat input ────────────────────────────────────────────────────────────────
if st.session_state.mode == "upload":
    placeholder = f'Ask anything about "{st.session_state.pdf_name}"…'
else:
    placeholder = "Ask about car loans, interest rates, bank products…"

user_input = st.chat_input(placeholder)

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            response = st.session_state.agent.invoke(
                {"messages": st.session_state.messages},
                {"configurable": {"thread_id": "session-1"}},
            )
            response_text = response["messages"][-1].content
        st.markdown(response_text)

    st.session_state.messages.append({"role": "assistant", "content": response_text})