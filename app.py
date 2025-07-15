import streamlit as st
import requests

st.set_page_config(page_title="Health Fund Bot", layout="centered")
st.title("🤖 Health Fund Chatbot")

# STATE
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "phase" not in st.session_state:
    st.session_state.phase = "user_info"
if "user_data" not in st.session_state:
    st.session_state.user_data = {}
if "last_retrieved_docs" not in st.session_state:
    st.session_state.last_retrieved_docs = []
if "last_namespace" not in st.session_state:
    st.session_state.last_namespace = ""
if "last_maslul" not in st.session_state:
    st.session_state.last_maslul = ""
if "last_rag_query" not in st.session_state:
    st.session_state.last_rag_query = ""
if "just_confirmed" not in st.session_state:
    st.session_state.just_confirmed = False  # tracks if we just confirmed the details 

# HELPERS 
CONFIRM_WORDS = {"אכן", "אמת", "כן", "מאשר", "אישרתי",
                 "אישור", "sure", "yes", "correct", "confirmed"}

def assistant_requested_confirmation(msg: str) -> bool:
    return any(x in msg for x in [
        "האם כל הפרטים נכונים", "האם המידע נכון", "אנא אשר",
        "please confirm", "are these details correct", "confirm"
    ])

def user_just_confirmed(history) -> bool:
    """True if last user msg is confirmation, and prev assistant msg is summary/confirmation-request."""
    if len(history) < 2:
        return False
    last_user = history[-1]
    prev_asst = next((m for m in reversed(history[:-1]) if m["role"] == "assistant"), None)
    return (last_user["role"] == "user" and
            any(w in last_user["content"].lower() for w in CONFIRM_WORDS) and
            prev_asst and assistant_requested_confirmation(prev_asst["content"]))

def fetch_user_data(history):
    try:
        r = requests.post("http://localhost:8000/extract_user_data", json={"history": history})
        if r.status_code == 200:
            return r.json().get("user_data", {})
    except Exception:
        pass
    return {}

#  SIDEBAR / DEBUG 
st.sidebar.markdown(f"**Current phase:** `{st.session_state.phase}`")
if st.session_state.phase == "qa" and st.session_state.user_data:
    st.sidebar.markdown("**Extracted user info (debug):**")
    for k, v in st.session_state.user_data.items():
        st.sidebar.markdown(f"**{k}:** {v}")

# MAIN CHAT HISTORY
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"], .block-container {direction:rtl;text-align:right;}
.stChatMessage.user      {background:#DCF8C6;border-radius:8px;padding:8px;}
.stChatMessage.assistant {background:#F1F0F0;border-radius:8px;padding:8px;}
</style>
""", unsafe_allow_html=True)

for m in st.session_state.chat_history:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# RAG DEBUG EXPANDER 
if (st.session_state.last_retrieved_docs or
        st.session_state.last_namespace or
        st.session_state.last_maslul or
        st.session_state.last_rag_query):
    with st.expander("Debug: RAG context", expanded=False):
        st.markdown(f"**RAG Query:** <span style='direction:ltr'>{st.session_state.last_rag_query}</span>", unsafe_allow_html=True)
        st.markdown(f"**Namespace:** `{st.session_state.last_namespace}` &nbsp;&nbsp; **מסלול:** `{st.session_state.last_maslul}`")
        st.markdown("---")
        for i, d in enumerate(st.session_state.last_retrieved_docs, 1):
            with st.container(border=True):
                for k, v in d.items():
                    if v:
                        st.markdown(f"**{k}:** {v}")

# CHAT INPUT 
user_msg = st.chat_input("Type your message here…")

if user_msg:
    st.session_state.chat_history.append({"role": "user", "content": user_msg})

    # if the user just confirm, then send confirmation message and move to QA phase.
    if (st.session_state.phase == "user_info" and user_just_confirmed(st.session_state.chat_history)):
        st.session_state.user_data = fetch_user_data(st.session_state.chat_history)
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "תודה! הפרטים נקלטו בהצלחה. כעת אפשר לשאול שאלות על ההטבות והכיסויים במסלול שלך."
        })
        st.session_state.phase = "qa"
        # Clear last rag context on phase switch
        st.session_state.last_retrieved_docs = []
        st.session_state.last_namespace = ""
        st.session_state.last_maslul = ""
        st.session_state.last_rag_query = ""
        st.rerun()

    # Otherwise normal backend call: if in QA phase, do RAG.
    else:
        try:
            r = requests.post(
                "http://localhost:8000/chat",
                json={
                    "history": st.session_state.chat_history,
                    "phase": st.session_state.phase,
                    "user_data": st.session_state.user_data
                })
            if r.status_code == 200:
                data = r.json()
                bot_reply = data["answer"]
                # debug info (may be empty in user-info phase)
                st.session_state.last_retrieved_docs = data.get("retrieved_docs", [])
                st.session_state.last_namespace = data.get("namespace", "")
                st.session_state.last_maslul = data.get("maslul", "")
                st.session_state.last_rag_query = data.get("rag_query", "")
            else:
                bot_reply = "Server error."
        except Exception as e:
            bot_reply = f"{e}"

        st.session_state.chat_history.append({"role": "assistant", "content": bot_reply})
        st.rerun()

#  BUTTON 
with st.sidebar:
    if st.button("Reset Conversation"):
        st.session_state.chat_history = []
        st.session_state.phase = "user_info"
        st.session_state.user_data = {}
        st.session_state.last_retrieved_docs = []
        st.session_state.last_namespace = ""
        st.session_state.last_maslul = ""
        st.session_state.last_rag_query = ""
        st.rerun()
    st.markdown("""---""")
    st.markdown(
        """
        ##### Example: Copy & Paste This to the Chat

        ```
        - שם מלא: יוסי כהן
        - מספר תעודת זהות: 123456789
        - מגדר: זכר
        - גיל: 35
        - קופת חולים: מכבי
        - מספר כרטיס קופה: 987654321
        - מסלול ביטוח: זהב
        ```
        """)