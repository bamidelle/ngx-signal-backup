import streamlit as st
import requests as http_requests
from app.utils.supabase_client import get_supabase


def call_ai(prompt: str) -> str:
    gemini_key = st.secrets.get("GEMINI_API_KEY", "")
    if gemini_key:
        try:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-1.5-flash-latest:generateContent?key={gemini_key}"
            )
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": 512,
                    "temperature": 0.7
                },
            }
            res = http_requests.post(url, json=payload, timeout=20)
            data = res.json()
            if "candidates" in data and data["candidates"]:
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            pass

    groq_key = st.secrets.get("GROQ_API_KEY", "")
    if groq_key:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 512,
                "temperature": 0.7,
            }
            res = http_requests.post(
                url, json=payload, headers=headers, timeout=20
            )
            data = res.json()
            return data["choices"][0]["message"]["content"]
        except Exception:
            pass

    return "Sorry, AI is temporarily unavailable. Please try again shortly."


def render():
    sb = get_supabase()
    profile = st.session_state.get("profile", {})
    plan = profile.get("plan", "free")

    st.markdown("""
    <div style="padding:10px 0 20px 0;">
      <h2 style="margin:0;font-size:22px;color:#1a1612;">🤖 Ask AI</h2>
      <p style="margin:4px 0 0 0;color:#6b6560;font-size:14px;">
        Ask anything about Nigerian stocks and the market
      </p>
    </div>
    """, unsafe_allow_html=True)

    if plan not in ("trader", "pro"):
        st.markdown("""
        <div style="background:#fffbeb;border:1px solid #fde68a;
                    border-radius:12px;padding:20px;text-align:center;">
          <div style="font-size:32px;margin-bottom:8px;">🤖</div>
          <div style="font-weight:700;font-size:16px;color:#1a1612;
                      margin-bottom:8px;">
            Ask AI on Trader plan
          </div>
          <div style="color:#6b6560;font-size:14px;">
            Upgrade to Trader to ask unlimited questions
            about any NGX stock or market condition.
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    if "ask_ai_history" not in st.session_state:
        st.session_state.ask_ai_history = []

    SYSTEM = (
        "You are a friendly Nigerian stock market expert. "
        "Answer questions about NGX stocks and investing "
        "in simple plain English. Keep answers under 200 words. "
        "Always end with: 'This is not financial advice.'"
    )

    # Chat history display
    for msg in st.session_state.ask_ai_history:
        if msg["role"] == "user":
            st.markdown(f"""
            <div style="background:#1a1612;color:#fff;border-radius:12px 12px 2px 12px;
                        padding:12px 16px;margin:8px 0 8px auto;max-width:80%;
                        font-size:14px;width:fit-content;">
              {msg['content']}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background:#fff;border:1px solid #e5e0da;
                        border-radius:12px 12px 12px 2px;padding:12px 16px;
                        margin:8px 0;max-width:90%;font-size:14px;
                        line-height:1.6;color:#3a3028;">
              {msg['content']}
            </div>
            """, unsafe_allow_html=True)

    # Suggested questions when empty
    if not st.session_state.ask_ai_history:
        st.markdown(
            "<div style='color:#9a9088;font-size:13px;margin-bottom:8px;'>"
            "Try asking:</div>",
            unsafe_allow_html=True
        )
        suggestions = [
            "Is GTCO a good buy right now?",
            "Which banking stocks should I watch?",
            "What is the NGX All Share Index?",
            "Explain dividend investing simply",
        ]
        cols = st.columns(2)
        for i, q in enumerate(suggestions):
            with cols[i % 2]:
                if st.button(q, key=f"suggest_{i}"):
                    st.session_state.ask_ai_history.append(
                        {"role": "user", "content": q}
                    )
                    with st.spinner("Thinking..."):
                        response = call_ai(f"{SYSTEM}\n\nUser: {q}")
                    st.session_state.ask_ai_history.append(
                        {"role": "assistant", "content": response}
                    )
                    st.rerun()

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    user_input = st.text_input(
        "Ask a question...",
        placeholder="e.g. Should I buy ZENITHBANK today?",
        key="ask_ai_input"
    )

    col1, col2 = st.columns([4, 1])
    with col1:
        if st.button("Ask →", key="ask_submit", type="primary",
                     use_container_width=True):
            if user_input.strip():
                st.session_state.ask_ai_history.append(
                    {"role": "user", "content": user_input}
                )
                with st.spinner("Thinking..."):
                    response = call_ai(f"{SYSTEM}\n\nUser: {user_input}")
                st.session_state.ask_ai_history.append(
                    {"role": "assistant", "content": response}
                )
                st.rerun()
    with col2:
        if st.button("Clear", key="ask_clear", use_container_width=True):
            st.session_state.ask_ai_history = []
            st.rerun()
