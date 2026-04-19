def render_global_pulse_strip(tier: str, location: str = "home") -> None:
    """
    Upgraded Fintech Dashboard Renderer.
    Focuses on dominant numerical display with fixed-height card architecture.
    """
    is_paid = tier in _PAID_TIERS

    try:
        pulse = get_global_pulse()
        data = pulse["data"]
        impacts = pulse["impacts"]
    except Exception:
        return

    # Helper for Arrows and Colors
    def _get_trend(v):
        if v > 0: return "▲", "#22C55E", "up"
        if v < 0: return "▼", "#EF4444", "down"
        return "–", "#6B7280", "neutral"

    # CSS Injection for the Premium Dashboard Look
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;700&display=swap');
        
        .gp-container {
            margin-bottom: 20px;
        }

        .ngx-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 10px;
            margin-top: 10px;
        }

        .ngx-card {
            background: #0A0C0F;
            border: 1px solid #1E2229;
            border-radius: 8px;
            padding: 10px 12px;
            height: 115px; /* Strict Fixed Height */
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            overflow: hidden;
            transition: border-color 0.3s ease;
        }

        .ngx-label {
            font-family: 'Inter', sans-serif;
            font-size: 10px;
            font-weight: 600;
            color: #4B5563;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            white-space: nowrap;
        }

        .ngx-price-xl {
            font-family: 'DM Mono', monospace;
            font-size: 42px; /* Dominant Number */
            font-weight: 600;
            color: #FFFFFF;
            line-height: 1;
            letter-spacing: -0.05em;
            margin: 4px 0;
            transform: scale(1.04);
            transform-origin: left center;
        }

        .ngx-pct {
            font-family: 'DM Mono', monospace;
            font-size: 13px;
            font-weight: 600;
        }

        .ngx-impact-mini {
            font-size: 10px;
            color: #9CA3AF;
            line-height: 1.2;
            margin-top: 5px;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        /* Mobile specific adjustments to prevent overflow */
        @media (max-width: 640px) {
            .ngx-price-xl { font-size: 34px; }
            .ngx-grid { grid-template-columns: 1fr 1fr; }
        }
    </style>
    """, unsafe_allow_html=True)

    # Signal Bar logic for "signals" location remains compact
    if location == "signals":
        # ... (You can keep your existing compact bar logic or apply the styles above)
        pass

    # Build Tile List
    tiles = []
    keys = [
        ("oil", "🛢️ Oil", "price", "${:,.2f}"),
        ("dxy", "💵 USD/NGN", "price", "N{:,.0f}"),
        ("btc", "₿ Bitcoin", "price", "${:,.0f}"),
        ("fg", "🌍 Mood", "score", "{:,.0f}/100")
    ]

    for key, label, val_key, fmt in keys:
        d = data.get(key, {})
        if d.get("ok"):
            val = d.get(val_key, 0)
            chg = d.get("change_pct", 0) if key != "fg" else (val - 50)
            arr, col, cls = _get_trend(chg)
            
            # Special case for F&G label
            display_val = fmt.format(val)
            if key == "fg": display_val = impacts.get("fg_label", "Neutral")

            impact_text = impacts.get(f"{key}_impact", "") if is_paid else "🔒 Upgrade for impact"

            tiles.append(f"""
                <div class="ngx-card" style="border-top: 2px solid {col}">
                    <div class="ngx-label">{label}</div>
                    <div class="ngx-price-xl">{display_val}</div>
                    <div style="display:flex; justify-content: space-between; align-items: flex-end;">
                        <div class="ngx-pct" style="color: {col}">{arr} {abs(chg):.1f}%</div>
                        <div style="font-size: 18px; opacity: 0.3;">{label.split()[0]}</div>
                    </div>
                </div>
            """)

    # Render Header
    st.markdown(f"""
    <div class="gp-container">
        <div style="display:flex; justify-content:space-between; align-items:baseline;">
            <div style="font-family:'Syne',sans-serif; font-size:16px; font-weight:800; color:white;">🌍 GLOBAL PULSE</div>
            <div style="font-size:10px; color:#4B5563; font-family:'DM Mono';">UPDATED {pulse.get('fetched_at','')}</div>
        </div>
        <div class="ngx-grid">
            {''.join(tiles)}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Summary Section (Paid Only)
    if is_paid:
        st.markdown(f"""
        <div style="background:#080A0D; border:1px solid #1E2229; border-left:4px solid #F0A500; 
                    padding:12px; border-radius:8px; font-family:'DM Mono'; font-size:13px; color:#C8C4BC;">
            <span style="color:#F0A500; font-weight:bold; font-size:10px; text-transform:uppercase;">Market Intelligence:</span><br>
            {impacts.get('summary', '')}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align:center; padding:10px; border:1px dashed #374151; border-radius:8px; font-size:11px; color:#6B7280;">
            🔒 Unlock <b>Naira Impact Analysis</b> with any paid plan.
        </div>
        """, unsafe_allow_html=True)
