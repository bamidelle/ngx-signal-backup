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
                "generationConfig": {"maxOutputTokens": 1024, "temperature": 0.7},
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
                "max_tokens": 1024,
                "temperature": 0.7,
            }
            res = http_requests.post(url, json=payload, headers=headers, timeout=20)
            data = res.json()
            return data["choices"][0]["message"]["content"]
        except Exception:
            pass

    return "AI temporarily unavailable. Please try again."


def render():
    sb = get_supabase()
    profile = st.session_state.get("profile", {})
    plan = profile.get("plan", "free")

    st.markdown("""
    <div style="padding:10px 0 20px 0;">
      <h2 style="margin:0;font-size:22px;color:#1a1612;">📈 AI Stock Discovery</h2>
      <p style="margin:4px 0 0 0;color:#6b6560;font-size:14px;">
        Find Nigerian stocks that match your goals — powered by AI
      </p>
    </div>
    """, unsafe_allow_html=True)

    # ── DISCOVERY THEMES ────────────────────────────
    st.markdown("### 🔍 Discover by Theme")

    themes = [
        ("🏦 Undervalued Banks", "undervalued Nigerian banking stocks with strong fundamentals"),
        ("📈 Momentum Stocks", "Nigerian stocks with strong upward price momentum this week"),
        ("💰 High Dividend Yields", "Nigerian stocks with high dividend yields and reliable payouts"),
        ("🛡️ Defensive Stocks", "stable Nigerian stocks that hold value during market downturns"),
        ("🚀 Growth Opportunities", "Nigerian stocks with strong earnings growth potential"),
        ("⚡ Most Active Today", "most actively traded Nigerian stocks today by volume"),
    ]

    col1, col2, col3 = st.columns(3)
    cols = [col1, col2, col3]
    selected_theme = st.session_state.get("selected_theme", None)

    for i, (label, description) in enumerate(themes):
        with cols[i % 3]:
            if st.button(label, key=f"theme_{i}", use_container_width=True):
                st.session_state.selected_theme = description
                st.session_state.theme_label = label
                st.rerun()

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── CUSTOM SEARCH ────────────────────────────────
    st.markdown("### 💬 Or Ask Your Own Question")
    custom_query = st.text_input(
        "What are you looking for?",
        placeholder="e.g. Show me cement stocks with good dividends",
        key="discover_query"
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        search_btn = st.button(
            "🔍 Discover Stocks →",
            key="discover_search",
            type="primary",
            use_container_width=True
        )
    with col2:
        if st.button("Clear", key="discover_clear", use_container_width=True):
            st.session_state.selected_theme = None
            st.session_state.theme_label = None
            st.rerun()

    # ── FETCH MARKET DATA FOR AI ──────────────────────
    active_query = custom_query if search_btn and custom_query.strip() \
        else st.session_state.get("selected_theme")
    active_label = custom_query if search_btn and custom_query.strip() \
        else st.session_state.get("theme_label", "")

    if active_query:
        st.markdown(f"""
        <div style="background:#fffdf7;border:1px solid #f0d88a;
                    border-radius:8px;padding:10px 16px;margin-bottom:16px;">
          🔍 Discovering: <strong>{active_label or active_query}</strong>
        </div>
        """, unsafe_allow_html=True)

        # Get market data
        prices_res = sb.table("stock_prices")\
            .select("symbol, price, change_percent, volume")\
            .order("trading_date", desc=True)\
            .limit(200).execute()

        seen = set()
        prices = []
        for p in (prices_res.data or []):
            if p["symbol"] not in seen:
                seen.add(p["symbol"])
                prices.append(p)

        signals_res = sb.table("signal_scores")\
            .select("symbol, stars, signal, reasoning")\
            .order("score_date", desc=True)\
            .limit(200).execute()

        seen2 = set()
        signals = []
        for s in (signals_res.data or []):
            if s["symbol"] not in seen2:
                seen2.add(s["symbol"])
                signals.append(s)

        signal_map = {s["symbol"]: s for s in signals}

        # Build market summary for AI
        market_summary = "\n".join([
            f"{p['symbol']}: ₦{p['price']:,.2f}, "
            f"change {p['change_percent']:+.2f}%, "
            f"signal: {signal_map.get(p['symbol'], {}).get('signal', 'HOLD')}, "
            f"stars: {signal_map.get(p['symbol'], {}).get('stars', 3)}"
            for p in prices[:50]
        ])

        prompt = f"""You are an expert Nigerian stock market analyst.
A user is looking for: "{active_query}"

Here is today's NGX market data:
{market_summary}

Based on this data, identify the TOP 5 most relevant stocks for the user's query.
For each stock provide:
1. Symbol and why it matches the query
2. Key metric (price, signal, change)
3. Plain English explanation of the opportunity (2 sentences max)
4. Risk level: Low / Medium / High

Format your response clearly with each stock as a separate section.
Be specific to Nigerian market context. Keep language simple.
End with one overall market insight relevant to the query.
Do not give financial advice — frame as educational insights."""

        with st.spinner("🤖 AI is analyzing the Nigerian market..."):
            result = call_ai(prompt)

        if result:
            import re
            formatted = re.sub(
                r'\*\*(.+?)\*\*', r'<strong>\1</strong>', result
            )
            formatted = formatted.replace("\n\n", "<br><br>")
            formatted = formatted.replace("\n", "<br>")

            st.markdown(f"""
            <div style="background:#fff;border:1px solid #e5e0da;
                        border-radius:12px;padding:24px;line-height:1.8;
                        font-size:14px;color:#3a3028;">
              {formatted}
            </div>
            """, unsafe_allow_html=True)

            st.caption(
                "⚠️ This is educational analysis only — not financial advice. "
                "Always do your own research before investing."
            )

    else:
        # Show top signals as default
        st.markdown("### ⭐ Top Signals Right Now")

        signals_res = sb.table("signal_scores")\
            .select("symbol, stars, signal, reasoning")\
            .order("score_date", desc=True)\
            .order("stars", desc=True)\
            .limit(100).execute()

        seen = set()
        top = []
        for s in (signals_res.data or []):
            if s["symbol"] not in seen and s.get("signal") in ("STRONG BUY", "BUY"):
                seen.add(s["symbol"])
                top.append(s)
                if len(top) >= 6:
                    break

        if not top:
            st.info("No signal data yet. Run the scraper to generate signals.")
        else:
            col1, col2 = st.columns(2)
            for i, s in enumerate(top):
                signal = s.get("signal", "HOLD")
                color = "#166534" if signal == "STRONG BUY" else "#16a34a"
                bg = "#dcfce7" if signal == "STRONG BUY" else "#f0fdf4"
                stars = "⭐" * int(s.get("stars", 3))

                with col1 if i % 2 == 0 else col2:
                    st.markdown(f"""
                    <div style="background:{bg};border:1px solid {color}33;
                                border-left:4px solid {color};border-radius:10px;
                                padding:14px;margin-bottom:10px;">
                      <div style="display:flex;justify-content:space-between;
                                  align-items:center;margin-bottom:6px;">
                        <span style="font-weight:700;font-size:16px;
                                     color:#1a1612;">{s['symbol']}</span>
                        <span style="background:{color};color:#fff;font-size:10px;
                                     font-weight:700;padding:2px 8px;
                                     border-radius:12px;">{signal}</span>
                      </div>
                      <div style="font-size:12px;margin-bottom:4px;">{stars}</div>
                      <div style="font-size:12px;color:#3a3028;line-height:1.5;">
                        {s.get('reasoning', '')[:120]}...
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
