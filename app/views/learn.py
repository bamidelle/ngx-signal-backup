import streamlit as st
from app.utils.supabase_client import get_supabase


MODULES = [
    {
        "id": "module_1",
        "title": "How the Nigerian Stock Market Works",
        "emoji": "🏦",
        "duration": "5 min read",
        "level": "Beginner",
        "level_color": "#16a34a",
        "case_study_name": "Chidi from Enugu",
        "case_study": (
            "Chidi is a 28-year-old teacher in Enugu earning ₦150,000/month. "
            "He heard his colleague made money from stocks and wanted to learn. "
            "He started by putting ₦20,000 into GTCO shares — the same bank "
            "where he has his salary account. Within 8 months, his ₦20,000 "
            "became ₦31,400 — a 57% return — plus he received a ₦1,200 dividend."
        ),
        "lessons": [
            {
                "title": "What is the NGX?",
                "content": (
                    "The Nigerian Exchange (NGX) is Nigeria's stock market — "
                    "a marketplace where you can buy tiny pieces (called shares) "
                    "of real Nigerian companies like Dangote Cement, GTBank, "
                    "and MTN Nigeria.\n\n"
                    "When you buy shares, you become a part-owner of that company. "
                    "If the company makes profit, your shares become more valuable. "
                    "If they pay dividends, you receive cash directly into your "
                    "account — just like rent from a property you own."
                ),
            },
            {
                "title": "How do I make money from stocks?",
                "content": (
                    "There are two ways to make money:\n\n"
                    "1. **Price Growth** — You buy GTCO at ₦45 per share. "
                    "The price rises to ₦60. You sell and pocket the ₦15 profit "
                    "per share.\n\n"
                    "2. **Dividends** — Companies share their profits with "
                    "shareholders. GTCO paid ₦3 per share in 2023. "
                    "If you owned 1,000 shares, you received ₦3,000 in cash "
                    "— without selling anything."
                ),
            },
            {
                "title": "Who controls the NGX?",
                "content": (
                    "The NGX is regulated by the Securities and Exchange "
                    "Commission (SEC Nigeria). Think of SEC as the CBN of "
                    "the stock market — they make the rules and protect investors.\n\n"
                    "Trading happens weekdays from 10AM to 2:30PM WAT. "
                    "You need a stockbroker (like Meristem, CardinalStone, "
                    "or Stanbic IBTC) to buy and sell shares on your behalf."
                ),
            },
        ],
        "quiz": [
            {
                "question": "What does it mean to own shares in GTBank?",
                "options": [
                    "You work at GTBank",
                    "You own a small piece of GTBank",
                    "You have a GTBank account",
                    "You borrowed money from GTBank",
                ],
                "answer": 1,
            },
            {
                "question": "What is a dividend?",
                "options": [
                    "A type of bank loan",
                    "A fee you pay to buy stocks",
                    "Cash paid to shareholders from company profits",
                    "The price of one share",
                ],
                "answer": 2,
            },
        ],
    },
    {
        "id": "module_2",
        "title": "How to Analyze NGX Stocks",
        "emoji": "🔍",
        "duration": "8 min read",
        "level": "Beginner",
        "level_color": "#16a34a",
        "case_study_name": "Amaka from Lagos",
        "case_study": (
            "Amaka is a 35-year-old civil servant in Lagos. She noticed Dangote "
            "Cement was building new factories in Ghana and Ethiopia. She bought "
            "500 shares at ₦400 each — spending ₦200,000. Two years later, "
            "the shares traded at ₦612. She sold 300 shares for ₦183,600 — "
            "making ₦63,600 profit while keeping 200 shares for the long term."
        ),
        "lessons": [
            {
                "title": "What is P/E Ratio?",
                "content": (
                    "P/E (Price-to-Earnings) ratio tells you how expensive "
                    "a stock is relative to its profits.\n\n"
                    "**Simple formula:** Share Price ÷ Earnings Per Share\n\n"
                    "**Example:** If DANGCEM trades at ₦500 and earned ₦50 "
                    "per share last year, P/E = 500 ÷ 50 = 10.\n\n"
                    "A P/E of 10 means you're paying ₦10 for every ₦1 of "
                    "earnings. Lower P/E = potentially cheaper stock. "
                    "NGX average P/E is around 8-12. "
                    "If a stock has P/E of 5, it may be undervalued."
                ),
            },
            {
                "title": "What is EPS?",
                "content": (
                    "EPS (Earnings Per Share) = Total Company Profit ÷ "
                    "Number of Shares.\n\n"
                    "**Example:** If ZENITHBANK made ₦230 billion profit and "
                    "has 31.4 billion shares, EPS = ₦7.32 per share.\n\n"
                    "Rising EPS year after year = healthy growing company. "
                    "Falling EPS = warning sign. Always compare EPS over "
                    "3-5 years, not just one year."
                ),
            },
            {
                "title": "Technical vs Fundamental Analysis",
                "content": (
                    "**Fundamental Analysis** — Look at the company's finances. "
                    "Is it profitable? Does it have debt? Is management good? "
                    "This is for long-term investors.\n\n"
                    "**Technical Analysis** — Look at price charts and patterns. "
                    "Is the price trending up? Where is support/resistance? "
                    "This is for short-term traders.\n\n"
                    "For most Nigerian retail investors, fundamental analysis "
                    "is safer and more reliable. Buy good companies at fair "
                    "prices and hold them."
                ),
            },
        ],
        "quiz": [
            {
                "question": "A stock has P/E of 5 when the market average is 12. What does this suggest?",
                "options": [
                    "The stock is overpriced",
                    "The stock may be undervalued",
                    "The company has no profits",
                    "You should sell immediately",
                ],
                "answer": 1,
            },
            {
                "question": "EPS stands for?",
                "options": [
                    "Expected Payment Schedule",
                    "Exchange Per Share",
                    "Earnings Per Share",
                    "Equity Price Standard",
                ],
                "answer": 2,
            },
        ],
    },
    {
        "id": "module_3",
        "title": "Dividend Investing for Nigerians",
        "emoji": "💰",
        "duration": "6 min read",
        "level": "Intermediate",
        "level_color": "#d97706",
        "case_study_name": "Emeka from Port Harcourt",
        "case_study": (
            "Emeka is a 42-year-old engineer earning ₦800,000/month. He invested "
            "₦2,000,000 across ZENITHBANK, UBA and GTCO in 2021. By 2024, "
            "he was receiving approximately ₦180,000 per year in dividends alone — "
            "without selling a single share. He calls it his 'second salary'."
        ),
        "lessons": [
            {
                "title": "What makes a great dividend stock?",
                "content": (
                    "Look for these 4 things:\n\n"
                    "1. **Consistent payment** — Has the company paid dividends "
                    "for at least 5 consecutive years?\n\n"
                    "2. **Affordable payout ratio** — Payout ratio = "
                    "Dividend ÷ EPS. Below 70% is healthy. Above 90% is risky "
                    "(company is paying more than it can sustain).\n\n"
                    "3. **Growing dividends** — The best companies increase "
                    "dividends every year. GTCO has done this consistently.\n\n"
                    "4. **Strong business** — Banks, telecoms and consumer goods "
                    "companies tend to pay the most reliable NGX dividends."
                ),
            },
            {
                "title": "The Power of DRIP (Dividend Reinvestment)",
                "content": (
                    "DRIP means instead of spending your dividend cash, "
                    "you use it to buy more shares.\n\n"
                    "**Example without DRIP:**\n"
                    "₦500,000 in ZENITHBANK at 8% yield = ₦40,000/year income\n\n"
                    "**Example with DRIP for 10 years:**\n"
                    "Year 1: ₦500,000 → Year 5: ₦735,000 → Year 10: ₦1,079,000\n\n"
                    "Your money more than doubled — without adding a single kobo — "
                    "just by reinvesting dividends. This is compound interest "
                    "working for you."
                ),
            },
            {
                "title": "NGX Dividend Calendar — Key Dates",
                "content": (
                    "Three dates matter for dividend investors:\n\n"
                    "1. **Declaration Date** — Company announces the dividend\n\n"
                    "2. **Record Date** — You must OWN shares by this date "
                    "to qualify for the dividend. Buy at least 3 days before "
                    "(T+3 settlement rule on NGX).\n\n"
                    "3. **Payment Date** — Cash arrives in your stockbroker "
                    "account. Usually 2-6 weeks after record date."
                ),
            },
        ],
        "quiz": [
            {
                "question": "To qualify for a dividend, you must own shares by which date?",
                "options": [
                    "Declaration Date",
                    "Payment Date",
                    "Record Date",
                    "Any date",
                ],
                "answer": 2,
            },
            {
                "question": "What is DRIP?",
                "options": [
                    "A type of stock chart pattern",
                    "Reinvesting dividends to buy more shares",
                    "A government savings program",
                    "Daily Rate of Interest Payment",
                ],
                "answer": 1,
            },
        ],
    },
    {
        "id": "module_4",
        "title": "Long-Term Wealth Building in Nigeria",
        "emoji": "🏆",
        "duration": "7 min read",
        "level": "Intermediate",
        "level_color": "#d97706",
        "case_study_name": "Fatima from Kano",
        "case_study": (
            "Fatima is a 30-year-old pharmacist from Kano. She decided to invest "
            "₦50,000 every month — skipping one outing per week. After 10 years "
            "of consistent investing across 5 NGX stocks, her total investment "
            "of ₦6,000,000 grew to approximately ₦18,400,000. Her secret: "
            "she never panicked during market downturns and kept buying consistently."
        ),
        "lessons": [
            {
                "title": "The 3 Rules of NGX Wealth Building",
                "content": (
                    "Rule 1 — **Start Early.** ₦100,000 invested at 25 "
                    "becomes ~₦1.1M by 55 (at 8% annual return). "
                    "The same ₦100,000 invested at 35 becomes only ~₦466,000.\n\n"
                    "Rule 2 — **Be Consistent.** Invest a fixed amount every month "
                    "regardless of market conditions. This is called "
                    "Naira-Cost Averaging — you automatically buy more shares "
                    "when prices fall.\n\n"
                    "Rule 3 — **Never Panic Sell.** Every market crash in NGX "
                    "history has been followed by recovery. The 2020 COVID crash "
                    "— ASI fell 30%. By 2021 it recovered 100%."
                ),
            },
            {
                "title": "How to build your first NGX portfolio",
                "content": (
                    "A simple starter portfolio for beginners:\n\n"
                    "**Banking (40%)** — GTBank, Zenith, or UBA. "
                    "Reliable dividends, liquid, well-regulated.\n\n"
                    "**Telecoms (20%)** — MTN Nigeria or Airtel Africa. "
                    "Defensive, growing data revenue.\n\n"
                    "**Consumer Goods (20%)** — Dangote Sugar or BUA Foods. "
                    "People always need food.\n\n"
                    "**Energy/Cement (20%)** — Dangote Cement or Seplat. "
                    "Benefits from infrastructure growth.\n\n"
                    "Review your portfolio every 6 months. Rebalance if "
                    "any single stock exceeds 30% of your total value."
                ),
            },
            {
                "title": "Common mistakes Nigerian investors make",
                "content": (
                    "1. **Following WhatsApp tips blindly** — By the time "
                    "a stock tip reaches your WhatsApp group, insiders have "
                    "already bought and the price is already high.\n\n"
                    "2. **Putting all money in one stock** — Even good companies "
                    "have bad years. Spread across at least 5 stocks.\n\n"
                    "3. **Panic selling during crashes** — Every crash is "
                    "temporary. Selling locks in your loss permanently.\n\n"
                    "4. **Ignoring dividends** — Many investors only chase price "
                    "gains and miss the consistent income from dividends.\n\n"
                    "5. **Not starting** — The biggest mistake is waiting for "
                    "the 'perfect time.' The best time to start was 5 years ago. "
                    "The second best time is today."
                ),
            },
        ],
        "quiz": [
            {
                "question": "What is Naira-Cost Averaging?",
                "options": [
                    "Investing a fixed amount every month regardless of price",
                    "Averaging the cost of living in Nigeria",
                    "Selling stocks at the average market price",
                    "Comparing NGX returns to CBN rates",
                ],
                "answer": 0,
            },
            {
                "question": "What should you do when the stock market crashes?",
                "options": [
                    "Sell everything immediately",
                    "Wait and do nothing",
                    "Keep investing consistently",
                    "Move all money to crypto",
                ],
                "answer": 2,
            },
        ],
    },
]


def render():
    sb = get_supabase()
    user = st.session_state.get("user")
    profile = st.session_state.get("profile", {})

    st.markdown("""
    <div style="padding:10px 0 20px 0;">
      <h2 style="margin:0;font-size:22px;color:#FFFFFF;">📚 NGX Learning Hub</h2>
      <p style="margin:4px 0 0 0;color:#A0A0A0;font-size:14px;">
        Master Nigerian stock market investing — one lesson at a time
      </p>
    </div>
    """, unsafe_allow_html=True)

    # Get user progress
    progress_res = sb.table("learning_progress")\
        .select("module_id, completed")\
        .eq("user_id", user.id)\
        .execute()
    completed_modules = {
        p["module_id"] for p in (progress_res.data or [])
        if p.get("completed")
    }

    total = len(MODULES)
    done = len(completed_modules)

    # Progress bar
    pct = int((done / total) * 100) if total > 0 else 0
    st.markdown(f"""
    <div style="background:#111111;border:1px solid #2A2A2A;border-radius:12px;
                padding:16px;margin-bottom:20px;">
      <div style="display:flex;justify-content:space-between;
                  align-items:center;margin-bottom:8px;">
        <span style="font-weight:700;color:#FFFFFF;">Your Progress</span>
        <span style="color:#f5b942;font-weight:700;">{done}/{total} modules</span>
      </div>
      <div style="background:#f0ebe4;border-radius:8px;height:10px;">
        <div style="background:#f5b942;border-radius:8px;height:10px;
                    width:{pct}%;transition:width 0.3s;"></div>
      </div>
      <div style="font-size:12px;color:#666666;margin-top:6px;">
        {pct}% complete
        {"🎉 You've completed all modules!" if done == total else ""}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Check if a module is selected
    selected_module = st.session_state.get("selected_module", None)

    if selected_module is None:
        # ── MODULE GRID ──────────────────────────────
        st.markdown("### Choose a Module")
        col1, col2 = st.columns(2)

        for i, module in enumerate(MODULES):
            is_done = module["id"] in completed_modules
            with col1 if i % 2 == 0 else col2:
                done_badge = (
                    "<span style='background:#16a34a;color:#fff;font-size:10px;"
                    "font-weight:700;padding:2px 8px;border-radius:12px;"
                    "margin-left:8px;'>✓ DONE</span>"
                    if is_done else ""
                )
                st.markdown(f"""
                <div style="background:#111111;border:1px solid #2A2A2A;
                            border-radius:12px;padding:16px;margin-bottom:12px;
                            {'border-left:4px solid #16a34a;' if is_done else ''}">
                  <div style="font-size:28px;margin-bottom:8px;">
                    {module['emoji']}
                  </div>
                  <div style="font-weight:700;font-size:15px;color:#FFFFFF;">
                    {module['title']}{done_badge}
                  </div>
                  <div style="margin-top:6px;display:flex;gap:8px;
                              align-items:center;flex-wrap:wrap;">
                    <span style="background:{module['level_color']}22;
                                 color:{module['level_color']};font-size:11px;
                                 font-weight:600;padding:2px 8px;
                                 border-radius:12px;">
                      {module['level']}
                    </span>
                    <span style="color:#666666;font-size:11px;">
                      ⏱️ {module['duration']}
                    </span>
                  </div>
                </div>
                """, unsafe_allow_html=True)
                if st.button(
                    f"{'Review' if is_done else 'Start'} →",
                    key=f"start_{module['id']}",
                    use_container_width=True,
                ):
                    st.session_state.selected_module = module["id"]
                    st.session_state.lesson_index = 0
                    st.session_state.quiz_mode = False
                    st.session_state.quiz_answers = {}
                    st.session_state.quiz_submitted = False
                    st.rerun()

    else:
        # ── MODULE CONTENT ───────────────────────────
        module = next(
            (m for m in MODULES if m["id"] == selected_module), None
        )
        if not module:
            st.session_state.selected_module = None
            st.rerun()
            return

        # Back button
        if st.button("← Back to modules", key="back_modules"):
            st.session_state.selected_module = None
            st.rerun()

        st.markdown(f"""
        <div style="background:#1a1612;border-radius:16px;padding:24px;
                    margin-bottom:20px;color:#fff;">
          <div style="font-size:36px;margin-bottom:8px;">{module['emoji']}</div>
          <div style="font-size:20px;font-weight:700;">{module['title']}</div>
          <div style="color:#666666;font-size:13px;margin-top:6px;">
            {module['level']} · {module['duration']}
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Case study
        st.markdown(f"""
        <div style="background:#fffdf7;border:1px solid #f0d88a;
                    border-left:4px solid #f5b942;border-radius:12px;
                    padding:16px;margin-bottom:20px;">
          <div style="font-size:12px;font-weight:700;color:#d97706;
                      margin-bottom:6px;">
            📖 REAL STORY — {module['case_study_name']}
          </div>
          <div style="font-size:13px;color:#FFFFFF;line-height:1.7;">
            {module['case_study']}
          </div>
        </div>
        """, unsafe_allow_html=True)

        quiz_mode = st.session_state.get("quiz_mode", False)
        quiz_submitted = st.session_state.get("quiz_submitted", False)

        if not quiz_mode:
            # ── LESSONS ──────────────────────────────
            lesson_idx = st.session_state.get("lesson_index", 0)
            lessons = module["lessons"]
            lesson = lessons[lesson_idx]

            # Progress dots
            dots = " ".join([
                "🟡" if j == lesson_idx else
                "🟢" if j < lesson_idx else "⚪"
                for j in range(len(lessons))
            ])
            st.markdown(
                f"<div style='font-size:16px;margin-bottom:12px;'>{dots}</div>",
                unsafe_allow_html=True
            )

            st.markdown(f"""
            <div style="background:#111111;border:1px solid #2A2A2A;
                        border-radius:12px;padding:20px;margin-bottom:16px;">
              <div style="font-weight:700;font-size:17px;color:#FFFFFF;
                          margin-bottom:12px;">
                {lesson['title']}
              </div>
              <div style="font-size:14px;color:#FFFFFF;line-height:1.8;">
                {lesson['content'].replace(chr(10), '<br>').replace('**', '<strong>').replace('</strong><strong>', '')}
              </div>
            </div>
            """, unsafe_allow_html=True)

            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if lesson_idx > 0:
                    if st.button("← Previous", key="prev_lesson",
                                 use_container_width=True):
                        st.session_state.lesson_index = lesson_idx - 1
                        st.rerun()
            with col3:
                if lesson_idx < len(lessons) - 1:
                    if st.button("Next →", key="next_lesson",
                                 type="primary", use_container_width=True):
                        st.session_state.lesson_index = lesson_idx + 1
                        st.rerun()
                else:
                    if st.button("Take Quiz →", key="start_quiz",
                                 type="primary", use_container_width=True):
                        st.session_state.quiz_mode = True
                        st.rerun()

        else:
            # ── QUIZ ─────────────────────────────────
            st.markdown("### 🧠 Quick Quiz")
            st.markdown(
                "<p style='color:#A0A0A0;font-size:13px;'>"
                "Answer these questions to complete the module.</p>",
                unsafe_allow_html=True
            )

            quiz = module["quiz"]
            quiz_answers = st.session_state.get("quiz_answers", {})

            for qi, q in enumerate(quiz):
                st.markdown(f"""
                <div style="font-weight:600;font-size:14px;color:#FFFFFF;
                            margin:16px 0 8px 0;">
                  Q{qi+1}: {q['question']}
                </div>
                """, unsafe_allow_html=True)

                answer = st.radio(
                    f"q{qi}",
                    q["options"],
                    key=f"quiz_{selected_module}_{qi}",
                    label_visibility="collapsed",
                    disabled=quiz_submitted,
                )
                quiz_answers[qi] = q["options"].index(answer) \
                    if answer in q["options"] else -1

            st.session_state.quiz_answers = quiz_answers

            if not quiz_submitted:
                if st.button(
                    "Submit Answers →",
                    key="submit_quiz",
                    type="primary"
                ):
                    st.session_state.quiz_submitted = True
                    st.rerun()
            else:
                # Show results
                correct = sum(
                    1 for qi, q in enumerate(quiz)
                    if quiz_answers.get(qi) == q["answer"]
                )
                total_q = len(quiz)
                score_pct = int((correct / total_q) * 100)
                passed = score_pct >= 50

                result_color = "#16a34a" if passed else "#dc2626"
                result_emoji = "🎉" if passed else "📚"

                st.markdown(f"""
                <div style="background:{result_color}11;border:2px solid {result_color};
                            border-radius:16px;padding:24px;text-align:center;
                            margin:16px 0;">
                  <div style="font-size:40px;">{result_emoji}</div>
                  <div style="font-size:24px;font-weight:700;color:{result_color};">
                    {correct}/{total_q} correct — {score_pct}%
                  </div>
                  <div style="color:#A0A0A0;font-size:14px;margin-top:8px;">
                    {"Excellent! Module completed! 🏆" if passed else
                     "Review the lessons and try again."}
                  </div>
                </div>
                """, unsafe_allow_html=True)

                # Show correct answers
                for qi, q in enumerate(quiz):
                    user_ans = quiz_answers.get(qi, -1)
                    correct_ans = q["answer"]
                    is_correct = user_ans == correct_ans
                    color = "#16a34a" if is_correct else "#dc2626"
                    icon = "✅" if is_correct else "❌"

                    st.markdown(f"""
                    <div style="background:#fff;border:1px solid {color}33;
                                border-left:3px solid {color};border-radius:8px;
                                padding:10px 14px;margin-bottom:8px;">
                      <div style="font-size:13px;color:#FFFFFF;font-weight:600;">
                        {icon} Q{qi+1}: {q['question']}
                      </div>
                      <div style="font-size:12px;color:{color};margin-top:4px;">
                        Correct answer: {q['options'][correct_ans]}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("← Back to Lessons", key="back_lessons",
                                 use_container_width=True):
                        st.session_state.quiz_mode = False
                        st.session_state.quiz_submitted = False
                        st.session_state.lesson_index = 0
                        st.rerun()
                with col2:
                    if passed:
                        if st.button("✅ Complete Module",
                                     key="complete_module",
                                     type="primary",
                                     use_container_width=True):
                            try:
                                sb.table("learning_progress").upsert({
                                    "user_id": user.id,
                                    "module_id": selected_module,
                                    "completed": True,
                                    "completed_at": "now()",
                                }, on_conflict="user_id,module_id").execute()
                                st.session_state.selected_module = None
                                st.success("🎉 Module completed!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Could not save progress: {e}")
                    else:
                        if st.button("🔄 Try Again", key="retry_quiz",
                                     type="primary", use_container_width=True):
                            st.session_state.quiz_submitted = False
                            st.session_state.quiz_answers = {}
                            st.rerun()