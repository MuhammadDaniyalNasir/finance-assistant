import streamlit as st
import base64
import io
from agent import answer_query, run_agent

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Agent Chatbot",
    page_icon="🤖",
    layout="centered",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&display=swap');

/* ── Root tokens ── */
:root {
    --bg:        #0d0f14;
    --surface:   #161a22;
    --border:    #252a36;
    --accent:    #4f8ef7;
    --accent2:   #a78bfa;
    --text:      #e8eaf0;
    --muted:     #6b7280;
    --user-bg:   #1e2435;
    --bot-bg:    #161a22;
    --radius:    14px;
    --font-head: 'Syne', sans-serif;
    --font-body: 'DM Sans', sans-serif;
}

/* ── Global reset ── */
html, body, .stApp { background: var(--bg) !important; color: var(--text); font-family: var(--font-body); }
.block-container { padding-top: 2rem !important; max-width: 780px !important; }

/* ── Hide default Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }

/* ── Title ── */
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

/* ── Subtitle / status bar ── */
.status-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.78rem;
    color: var(--muted);
    margin: 4px 0 18px;
    font-family: var(--font-body);
    letter-spacing: 0.01em;
}
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 6px #22c55e88; flex-shrink: 0; }

/* ── Upload section ── */
.upload-section {
    background: var(--surface);
    border: 1.5px dashed var(--border);
    border-radius: var(--radius);
    padding: 1rem 1.25rem;
    margin-bottom: 1rem;
    transition: border-color .2s;
}
.upload-section:hover { border-color: var(--accent); }
.upload-label {
    font-family: var(--font-head);
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 6px;
}

/* ── File pill ── */
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
    font-family: var(--font-body);
    font-weight: 500;
    margin-top: 6px;
}

/* ── Chat messages ── */
.stChatMessage {
    background: var(--bot-bg) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    padding: 1rem 1.25rem !important;
    margin-bottom: 10px !important;
}
[data-testid="stChatMessageContent"] p { font-size: 0.95rem; line-height: 1.65; color: var(--text); }

/* User bubble override */
.stChatMessage:has([data-testid="chatAvatarIcon-user"]) {
    background: var(--user-bg) !important;
    border-color: #2d3a55 !important;
}

/* ── Chat input ── */
.stChatInputContainer { margin-top: 4px; }
.stChatInputContainer > div {
    background: var(--surface) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: 12px !important;
}
.stChatInputContainer textarea { font-family: var(--font-body) !important; font-size: 0.93rem !important; color: var(--text) !important; }
.stChatInputContainer textarea:focus { border-color: var(--accent) !important; }

/* ── Expander (PDF context) ── */
.streamlit-expanderHeader {
    font-family: var(--font-head) !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--muted) !important;
}
.streamlit-expanderContent { background: var(--surface) !important; border-radius: 0 0 10px 10px; }

/* ── Divider ── */
hr { border-color: var(--border) !important; margin: 0.6rem 0 !important; }

/* ── Spinner ── */
.stSpinner > div { border-top-color: var(--accent) !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 10px; }
</style>
""", unsafe_allow_html=True)


# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("# 🤖 AI Agent")
st.markdown("""
<div class="status-bar">
    <div class="status-dot"></div>
    Ready · Ask anything, or upload a PDF to chat with your document
</div>
""", unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

if "agent" not in st.session_state:
    st.session_state.agent = answer_query()

if "uploaded_pdf_bytes" not in st.session_state:
    st.session_state.uploaded_pdf_bytes = None

if "uploaded_pdf_name" not in st.session_state:
    st.session_state.uploaded_pdf_name = None


# ── PDF Upload panel ──────────────────────────────────────────────────────────
with st.container():
    st.markdown('<div class="upload-section">', unsafe_allow_html=True)
    st.markdown('<div class="upload-label">📄 PDF Context (optional)</div>', unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        label="Upload PDF",
        type=["pdf"],
        label_visibility="collapsed",
        help="Upload a PDF to chat with its contents. You can also chat without any PDF.",
    )

    if uploaded_file is not None:
        pdf_bytes = uploaded_file.read()
        if st.session_state.uploaded_pdf_name != uploaded_file.name:
            # New file — store and reset chat
            st.session_state.uploaded_pdf_bytes = pdf_bytes
            st.session_state.uploaded_pdf_name = uploaded_file.name
            st.session_state.messages = []
            st.success(f"PDF loaded — chat history cleared for new document.")

        st.markdown(
            f'<div class="file-pill">📎 {uploaded_file.name} &nbsp;·&nbsp; {len(st.session_state.uploaded_pdf_bytes) // 1024} KB</div>',
            unsafe_allow_html=True,
        )
    else:
        if st.session_state.uploaded_pdf_name is not None:
            st.markdown(
                f'<div class="file-pill">📎 {st.session_state.uploaded_pdf_name} &nbsp;·&nbsp; active</div>',
                unsafe_allow_html=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)


# ── Chat history ──────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# ── Chat input ────────────────────────────────────────────────────────────────
placeholder = (
    f'Ask about "{st.session_state.uploaded_pdf_name}" or anything else…'
    if st.session_state.uploaded_pdf_name
    else "Ask me anything…"
)

user_input = st.chat_input(placeholder)

if user_input:
    # Save & display user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # ── Build messages list for agent ────────────────────────────────────────
    # If a PDF is loaded, inject it as a document block in the first user turn
    if st.session_state.uploaded_pdf_bytes:
        b64_pdf = base64.standard_b64encode(st.session_state.uploaded_pdf_bytes).decode("utf-8")
        pdf_document_block = {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": b64_pdf,
            },
            "title": st.session_state.uploaded_pdf_name or "Uploaded PDF",
            "context": "The user has uploaded this PDF. Use its contents to answer questions when relevant.",
            "citations": {"enabled": True},
        }

        # Attach PDF to the most recent user message content
        agent_messages = []
        for i, m in enumerate(st.session_state.messages):
            if i == len(st.session_state.messages) - 1 and m["role"] == "user":
                # Last user turn — inject PDF alongside text
                agent_messages.append({
                    "role": "user",
                    "content": [
                        pdf_document_block,
                        {"type": "text", "text": m["content"]},
                    ],
                })
            else:
                agent_messages.append(m)
    else:
        agent_messages = st.session_state.messages

    # ── Invoke agent ──────────────────────────────────────────────────────────
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            response = st.session_state.agent.invoke(
                {"messages": agent_messages},
                {"configurable": {"thread_id": "session-1"}},
            )
            response_text = response["messages"][-1].content

        st.markdown(response_text)

    st.session_state.messages.append({"role": "assistant", "content": response_text})