"""
NGX Signal — Webpushr Utility
================================
Two responsibilities:

1. inject_webpushr_tracking()
   Injects the Webpushr tracking + service worker registration snippet.
   Call once at the top of main.py (before any page renders).
   Triggers the browser 'Allow Notifications' prompt on first visit.

2. send_web_push() / maybe_push_signal()
   Server-side REST call to Webpushr's send API.
   Called from signals.py for STRONG_BUY / BUY / BREAKOUT_WATCH signals.

Secrets required in Streamlit Cloud → App Settings → Secrets:
    WEBPUSHR_TRACKING_ID = "your_tracking_id_here"
    WEBPUSHR_API_KEY     = "your_api_key_here"
    WEBPUSHR_AUTH_TOKEN  = "your_auth_token_here"

Service worker file required:
    static/webpushr-sw.js   (single line: importScripts('https://cdn.webpushr.com/sw-server.min.js');)
    Served at /webpushr-sw.js via serve_worker.py + nginx/Railway proxy.

Usage in main.py (add right after inject_design_system()):
    from app.utils.webpushr import inject_webpushr_tracking
    inject_webpushr_tracking()

Usage in signals.py (already integrated):
    from app.utils.webpushr import maybe_push_signal
    maybe_push_signal(symbol, signal_code, narrative, price, chg)
"""

import streamlit as st
import requests
import os


# ── Secret reader ─────────────────────────────────────────────────────────────
def _secret(key: str, default: str = "") -> str:
    """Read from st.secrets first, fall back to os.environ."""
    try:
        val = st.secrets.get(key)
        if val:
            return str(val)
    except Exception:
        pass
    return os.environ.get(key, default)


# ══════════════════════════════════════════════════════════════════════════════
# 1. TRACKING SNIPPET INJECTION
# ══════════════════════════════════════════════════════════════════════════════

def inject_webpushr_tracking() -> None:
    """
    Inject the Webpushr tracking snippet into the Streamlit page.

    Call once at the top of main.py, right after inject_design_system():

        from app.utils.webpushr import inject_webpushr_tracking
        inject_webpushr_tracking()

    This:
    - Loads the Webpushr SDK asynchronously (non-blocking, won't slow page)
    - Registers /webpushr-sw.js as the service worker (scope: root)
    - Triggers the browser 'Allow Notifications' prompt on first visit
    - On subsequent visits: silently re-registers, no prompt shown again
    - Session-state guarded — runs once per session regardless of reruns
    """
    if st.session_state.get("_webpushr_injected"):
        return

    tracking_id = _secret("WEBPUSHR_TRACKING_ID")

    if not tracking_id:
        # Not yet configured — skip silently, won't crash the app
        return

    # Inject via height=0 invisible iframe — runs JS without any visible element
    st.components.v1.html(
        f"""<!DOCTYPE html><html><head></head><body>
<script>
(function(w,d,s,id){{
  if(typeof(w.webpushr)!=='undefined') return;
  w.webpushr = w.webpushr || function(){{(w.webpushr.q=w.webpushr.q||[]).push(arguments)}};
  var js, fjs = d.getElementsByTagName(s)[0];
  js = d.createElement(s);
  js.id = id;
  js.async = true;
  js.src = 'https://cdn.webpushr.com/app.min.js';
  fjs.parentNode.insertBefore(js, fjs);
}}(window, document, 'script', 'webpushr-jssdk'));

webpushr('setup', {{
  'key': '{tracking_id}',
  'sw': '/webpushr-sw.js',
  'swScope': '/'
}});
</script>
</body></html>""",
        height=0,
        scrolling=False,
    )

    st.session_state["_webpushr_injected"] = True


# ══════════════════════════════════════════════════════════════════════════════
# 2. SERVER-SIDE PUSH NOTIFICATION
# ══════════════════════════════════════════════════════════════════════════════

# Deduplication: prevent the same signal firing twice in one session
_PUSHED: set = set()


def send_web_push(
    title:       str,
    message:     str,
    target_url:  str = "https://ngx-signal.streamlit.app",
    symbol:      str = "",
    signal_code: str = "",
    icon_url:    str = "",
) -> bool:
    """
    Send a web push notification via Webpushr REST API to ALL subscribers.

    Returns True on success, False on failure. Never raises.
    Silently skips if keys not configured or duplicate within session.
    """
    api_key    = _secret("WEBPUSHR_API_KEY")
    auth_token = _secret("WEBPUSHR_AUTH_TOKEN")

    if not api_key or not auth_token:
        return False

    # Deduplication key
    dedup = f"{symbol}_{signal_code}"
    if dedup and dedup in _PUSHED:
        return False

    # Webpushr max body length is 250 chars
    body = (message[:247] + "…") if len(message) > 250 else message

    payload: dict = {
        "title":       title,
        "message":     body,
        "target_url":  target_url,
        "send_to":     "all",
    }
    if icon_url:
        payload["icon"] = icon_url

    try:
        resp = requests.post(
            "https://api.webpushr.com/v1/notification/send/all",
            headers={
                "webpushrKey":       api_key,
                "webpushrAuthToken": auth_token,
                "Content-Type":      "application/json",
            },
            json=payload,
            timeout=10,
        )
        if resp.status_code in (200, 201):
            if dedup:
                _PUSHED.add(dedup)
            return True
        else:
            print(f"[Webpushr] {resp.status_code}: {resp.text[:200]}")
            return False
    except requests.Timeout:
        print(f"[Webpushr] Timeout sending '{title}'")
        return False
    except Exception as e:
        print(f"[Webpushr] Error: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# 3. SIGNALS.PY CONVENIENCE WRAPPER
# ══════════════════════════════════════════════════════════════════════════════

BULLISH_SIGNAL_CODES = {"STRONG_BUY", "BUY", "BREAKOUT_WATCH"}

_EMOJI = {
    "STRONG_BUY":     "🚀",
    "BUY":            "📈",
    "BREAKOUT_WATCH": "⚡",
}
_LABEL = {
    "STRONG_BUY":     "Strong Buy",
    "BUY":            "Buy Signal",
    "BREAKOUT_WATCH": "Breakout",
}


def maybe_push_signal(
    symbol:      str,
    signal_code: str,
    narrative:   str,
    price:       float = 0.0,
    chg:         float = 0.0,
) -> None:
    """
    Push a notification when a BULLISH or BREAKOUT signal is detected.

    Safe to call on every signal card render — built-in deduplication
    ensures each symbol+signal only fires once per session.

    Called from signals.py after rich_narrative is generated:
        maybe_push_signal(symbol, signal_code, rich_narrative, price, chg)
    """
    if signal_code not in BULLISH_SIGNAL_CODES:
        return

    emoji = _EMOJI.get(signal_code, "📈")
    label = _LABEL.get(signal_code, signal_code)

    title = f"{emoji} {symbol} — {label}!"

    # First 2 sentences of narrative, prefixed with price/change
    sentences = [s.strip() for s in narrative.replace("  ", " ").split(". ") if s.strip()]
    summary   = ". ".join(sentences[:2])
    if price > 0:
        body = f"₦{price:,.2f} ({chg:+.2f}%) — {summary}"
    else:
        body = summary

    send_web_push(
        title       = title,
        message     = body,
        target_url  = "https://ngx-signal.streamlit.app?page=signals",
        symbol      = symbol,
        signal_code = signal_code,
    )
