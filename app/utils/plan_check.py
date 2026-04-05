import streamlit as st
from datetime import datetime, timezone


PLAN_LIMITS = {
    "free": {
        "watchlist":    3,
        "ai_queries":   0,
        "alerts":       0,
        "whatsapp":     False,
        "daily_brief":  False,
        "simulator":    False,
        "ask_ai":       False,
        "signal_scores":False,
        "earnings":     False,
        "dividends":    True,
        "sectors":      True,
    },
    "starter": {
        "watchlist":    10,
        "ai_queries":   0,
        "alerts":       5,
        "whatsapp":     True,
        "daily_brief":  True,
        "simulator":    True,
        "ask_ai":       False,
        "signal_scores":True,
        "earnings":     True,
        "dividends":    True,
        "sectors":      True,
    },
    "trader": {
        "watchlist":    30,
        "ai_queries":   30,
        "alerts":       999,
        "whatsapp":     True,
        "daily_brief":  True,
        "simulator":    True,
        "ask_ai":       True,
        "signal_scores":True,
        "earnings":     True,
        "dividends":    True,
        "sectors":      True,
    },
    "pro": {
        "watchlist":    999,
        "ai_queries":   999,
        "alerts":       999,
        "whatsapp":     True,
        "daily_brief":  True,
        "simulator":    True,
        "ask_ai":       True,
        "signal_scores":True,
        "earnings":     True,
        "dividends":    True,
        "sectors":      True,
    },
}


def get_user_plan() -> str:
    profile = st.session_state.get("profile", {})
    if not profile:
        return "free"
    plan = profile.get("plan", "free")
    status = profile.get("plan_status", "active")

    if status == "trial":
        trial_ends = profile.get("trial_ends_at")
        if trial_ends:
            try:
                ends = datetime.fromisoformat(
                    trial_ends.replace("Z", "+00:00")
                )
                if datetime.now(timezone.utc) > ends:
                    return "free"
            except Exception:
                pass
    return plan


def can_access(feature: str) -> bool:
    plan = get_user_plan()
    return bool(PLAN_LIMITS.get(plan, {}).get(feature, False))


def watchlist_limit() -> int:
    plan = get_user_plan()
    return PLAN_LIMITS.get(plan, {}).get("watchlist", 3)


def ai_query_limit() -> int:
    plan = get_user_plan()
    return PLAN_LIMITS.get(plan, {}).get("ai_queries", 0)


def show_upgrade_prompt(feature_name: str, min_plan: str = "starter"):
    plan_colors = {
        "starter": "#1a5fa8",
        "trader":  "#1a7a4a",
        "pro":     "#c9860a"
    }
    color = plan_colors.get(min_plan, "#1a5fa8")
    st.markdown(f"""
    <div class="lock-overlay">
      <div style="font-size:28px; margin-bottom:8px">🔒</div>
      <div style="font-weight:700; color:#1a1612; font-size:15px; margin-bottom:4px">
        {feature_name}
      </div>
      <div style="font-size:13px; color:#5a524a; margin-bottom:14px">
        Available on <strong style="color:{color}">
        {min_plan.title()} plan</strong> and above
      </div>
      <div style="font-size:12px; color:#9a9088;">
        Click <strong>Settings</strong> in the sidebar to upgrade
      </div>
    </div>
    """, unsafe_allow_html=True)


def get_trial_days_remaining() -> int:
    profile = st.session_state.get("profile", {})
    trial_ends = profile.get("trial_ends_at")
    if not trial_ends:
        return 0
    try:
        ends = datetime.fromisoformat(trial_ends.replace("Z", "+00:00"))
        remaining = (ends - datetime.now(timezone.utc)).days
        return max(0, remaining)
    except Exception:
        return 0
