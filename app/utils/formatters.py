def format_naira(amount: float) -> str:
    """Format number as Nigerian Naira"""
    if amount is None:
        return "₦—"
    if amount >= 1_000_000_000_000:
        return f"₦{amount/1_000_000_000_000:.1f}T"
    if amount >= 1_000_000_000:
        return f"₦{amount/1_000_000_000:.1f}B"
    if amount >= 1_000_000:
        return f"₦{amount/1_000_000:.1f}M"
    if amount >= 1_000:
        return f"₦{amount:,.0f}"
    return f"₦{amount:.2f}"


def format_change(change_percent: float) -> str:
    if change_percent is None:
        return "—"
    arrow = "▲" if change_percent >= 0 else "▼"
    return f"{arrow} {abs(change_percent):.2f}%"


def change_color(change_percent: float) -> str:
    if change_percent is None:
        return "#9a9088"
    return "#1a7a4a" if change_percent >= 0 else "#c0392b"


def signal_to_stars(stars: int) -> str:
    stars = max(1, min(5, stars or 1))
    return "★" * stars + "☆" * (5 - stars)


def plan_display_name(plan: str) -> str:
    names = {
        "free":    "Free",
        "starter": "Starter",
        "trader":  "Trader",
        "pro":     "Pro"
    }
    return names.get(plan, "Free")
