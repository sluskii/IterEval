"""
goveval/report/dashboard.py
Streamlit dashboard — reads directly from goveval.db, no Report object needed.

Pages:
  Overview    — risk tier, 7 metric cards, risk reasons
  Questions   — per-question verdict table with expandable detail
  Iterations  — metric timeline across loop iterations
"""

from __future__ import annotations

import json
from typing import Optional

import streamlit as st


# ── Shared helpers ────────────────────────────────────────────────────────────

_TIER_CFG = {
    "RED":   {"bg":"#fef2f2","border":"#fca5a5","text":"#991b1b","icon":"🔴","sub":"Deploy blocked"},
    "AMBER": {"bg":"#fffbeb","border":"#fcd34d","text":"#92400e","icon":"🟡","sub":"Review required"},
    "GREEN": {"bg":"#f0fdf4","border":"#86efac","text":"#166534","icon":"🟢","sub":"Ready to deploy"},
}

def _tier_html(tier: str) -> str:
    c = _TIER_CFG.get(tier, _TIER_CFG["GREEN"])
    return (
        f'<div class="risk-badge" style="background:{c["bg"]};border-color:{c["border"]};color:{c["text"]}">'
        f'<span style="font-size:1.5rem">{c["icon"]}</span>'
        f'<div>'
        f'<div class="risk-badge-label">{tier}</div>'
        f'<div class="risk-badge-sub">{c["sub"]}</div>'
        f'</div></div>'
    )

def _pct(v: float) -> str:
    return f"{v * 100:.1f}%"

def _section(icon: str, title: str) -> None:
    """Render a consistent section header."""
    st.markdown(
        f'<div class="goveval-section-header">'
        f'<span class="icon">{icon}</span>'
        f'<span class="title">{title}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

def _metric_status(key: str, value: float) -> str:
    """Return 'good'|'amber'|'red'|'neutral' based on thresholds."""
    if key == "hallucination_rate":
        return "red" if value > 0.20 else ("amber" if value > 0.10 else "good")
    if key == "refusal_recall":
        return "red" if value < 0.50 else ("amber" if value < 0.80 else "good")
    if key == "faithfulness_avg":
        return "red" if value < 2.5 else ("amber" if value < 3.5 else "good")
    if key == "singlish_gap":
        return "amber" if value > 0.15 else "good"
    if key == "calibration_ece":
        return "amber" if value > 0.20 else "good"
    if key == "transparency_avg":
        return "amber" if value < 0.60 else "good"
    return "neutral"

_STATUS_STYLE = {
    "good":    {"bg":"#f0fdf4","border":"#86efac","label":"#166534","value":"#15803d","note":"#4ade80"},
    "amber":   {"bg":"#fffbeb","border":"#fcd34d","label":"#92400e","value":"#d97706","note":"#fbbf24"},
    "red":     {"bg":"#fef2f2","border":"#fca5a5","label":"#991b1b","value":"#dc2626","note":"#f87171"},
    "neutral": {"bg":"#f8fafc","border":"#e2e8f0","label":"#64748b","value":"#1e293b","note":"#94a3b8"},
}

def _metric_card(label: str, value: str, key: str, raw: float, note: str = "") -> str:
    status = _metric_status(key, raw)
    s = _STATUS_STYLE[status]
    note_html = f'<div class="ge-metric-note" style="color:{s["note"]}">{note}</div>' if note else ""
    return (
        f'<div class="ge-metric-card" style="background:{s["bg"]};border-color:{s["border"]}">'
        f'<div class="ge-metric-label" style="color:{s["label"]}">{label}</div>'
        f'<div class="ge-metric-value" style="color:{s["value"]}">{value}</div>'
        f'{note_html}'
        f'</div>'
    )


def _get_question_verdicts(db, run_id: str, iteration: int | None = None) -> list[dict]:
    """Join questions → responses → verdicts into display rows.

    If iteration is given, returns only rows for that iteration.
    Otherwise deduplicates by keeping the latest iteration per question.
    """
    if iteration is not None:
        rows = db.query(
            """
            SELECT
                q.question_id,
                q.category,
                q.language,
                q.text        AS question_text,
                q.ground_truth,
                r.response_id,
                r.response_text,
                r.latency_ms,
                r.iteration,
                v.detail_json
            FROM questions q
            LEFT JOIN responses r
                ON r.question_id = q.question_id AND r.run_id = q.run_id
            LEFT JOIN verdicts v
                ON v.response_id = r.response_id
            WHERE q.run_id = %s AND r.iteration = %s
            ORDER BY q.question_id
            """,
            (run_id, iteration),
        )
    else:
        rows = db.query(
            """
            SELECT
                q.question_id,
                q.category,
                q.language,
                q.text        AS question_text,
                q.ground_truth,
                r.response_id,
                r.response_text,
                r.latency_ms,
                r.iteration,
                v.detail_json
            FROM questions q
            LEFT JOIN responses r
                ON r.question_id = q.question_id AND r.run_id = q.run_id
            LEFT JOIN verdicts v
                ON v.response_id = r.response_id
            WHERE q.run_id = %s
            ORDER BY q.question_id, r.iteration
            """,
            (run_id,),
        )

    seen: dict[str, dict] = {}
    for row in rows:
        qid = row["question_id"]
        detail = {}
        if row.get("detail_json"):
            try:
                detail = json.loads(row["detail_json"])
            except Exception:
                pass
        merged = dict(row)
        merged["detail"] = detail
        if iteration is not None:
            seen[qid] = merged
        elif qid not in seen or (row.get("iteration") or 0) >= (seen[qid].get("iteration") or 0):
            seen[qid] = merged
    return list(seen.values())


# ── Page renderers ────────────────────────────────────────────────────────────

def render_overview(metrics: dict, tier: str, risk_reasons: list[str], run_meta: dict, iterations: list[dict] | None = None) -> None:
    """Overview page: tier badge, coloured metric cards, run info, sparklines, executive summary."""
    import pandas as pd

    # ── Top row: badge + run info ─────────────────────────────────────────────
    col_tier, col_info = st.columns([1, 2])
    with col_tier:
        _section("🚦", "Risk Assessment")
        st.markdown(_tier_html(tier), unsafe_allow_html=True)
        if risk_reasons:
            st.markdown("")
            for r in risk_reasons:
                st.markdown(
                    f'<div style="font-size:0.8rem;color:#b45309;background:#fffbeb;'
                    f'border:1px solid #fde68a;border-radius:6px;padding:5px 10px;margin-top:4px">'
                    f'&#9888; {r}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("All metrics within thresholds")

    with col_info:
        _section("📋", "Run Info")
        ri1, ri2 = st.columns(2)
        ri1.markdown(f"**Run ID**  \n`{run_meta.get('run_id', '—')}`")
        ri1.markdown(f"**Target**  \n{run_meta.get('target_name', '—')}")
        created = run_meta.get("created_at", "")[:19].replace("T", " ")
        ri2.markdown(f"**Created**  \n{created}")
        ri2.markdown(f"**Status**  \n{run_meta.get('status', '—').upper()}")

    st.divider()

    # ── Metric cards ──────────────────────────────────────────────────────────
    _section("📊", "Metric Summary")

    hall  = metrics.get("hallucination_rate", 0)
    prec  = metrics.get("refusal_precision", 0)
    rec   = metrics.get("refusal_recall", 0)
    f1    = metrics.get("refusal_f1", 0)
    faith = metrics.get("faithfulness_avg", 0)
    gap   = metrics.get("singlish_gap", 0)
    ece   = metrics.get("calibration_ece", 0)
    trans = metrics.get("transparency_avg", 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(_metric_card("Hallucination Rate", _pct(hall),   "hallucination_rate", hall,  "target: 0%"), unsafe_allow_html=True)
    c2.markdown(_metric_card("Refusal Precision",  _pct(prec),   "neutral",            prec,  "true refusals / all refusals"), unsafe_allow_html=True)
    c3.markdown(_metric_card("Refusal Recall",     _pct(rec),    "refusal_recall",     rec,   "amber < 80%  red < 50%"), unsafe_allow_html=True)
    c4.markdown(_metric_card("Refusal F1",         _pct(f1),     "neutral",            f1,    "harmonic mean P+R"), unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)
    c5.markdown(_metric_card("Faithfulness",    f"{faith:.2f}/5", "faithfulness_avg",  faith, "amber < 3.5  red < 2.5"), unsafe_allow_html=True)
    c6.markdown(_metric_card("Singlish Gap",    _pct(gap),        "singlish_gap",      gap,   "amber > 15%"), unsafe_allow_html=True)
    c7.markdown(_metric_card("Calibration ECE", f"{ece:.4f}",     "calibration_ece",   ece,   "amber > 0.20"), unsafe_allow_html=True)
    c8.markdown(_metric_card("Transparency",    _pct(trans),      "transparency_avg",  trans, "amber < 60%"), unsafe_allow_html=True)

    # ── Threshold reference ───────────────────────────────────────────────────
    st.divider()
    _section("📏", "Threshold Reference")
    tbl = {
        "Metric": ["Hallucination Rate", "Refusal Recall", "Faithfulness", "Singlish Gap", "Calibration ECE", "Transparency"],
        "Your Value": [_pct(hall), _pct(rec), f"{faith:.2f}", _pct(gap), f"{ece:.4f}", _pct(trans)],
        "Amber if":   ["> 10%", "< 80%", "< 3.5", "> 15%", "> 0.20", "< 60%"],
        "Red if":     ["> 20%", "< 50%", "< 2.5", "—",     "—",      "—"],
    }
    st.dataframe(pd.DataFrame(tbl), width="stretch", hide_index=True)

    # ── Iteration sparklines ──────────────────────────────────────────────────
    if iterations and len(iterations) > 1:
        st.divider()
        _section("📈", "Metric Trend")
        df_spark = pd.DataFrame(iterations).set_index("iteration")
        spark_cols = ["hallucination_rate", "refusal_recall", "faithfulness_avg"]
        available = [c for c in spark_cols if c in df_spark.columns]
        if available:
            st.line_chart(df_spark[available], height=180)

    # ── Executive summary ─────────────────────────────────────────────────────
    st.divider()
    _section("💬", "Executive Summary")
    issues = []
    if hall  > 0.10: issues.append(f"high hallucination rate ({_pct(hall)})")
    if rec   < 0.80: issues.append(f"low refusal recall ({_pct(rec)})")
    if faith < 3.5:  issues.append(f"below-target faithfulness ({faith:.2f}/5)")
    if gap   > 0.15: issues.append(f"Singlish performance gap ({_pct(gap)})")
    if trans < 0.60: issues.append(f"low transparency ({_pct(trans)})")

    if not issues:
        st.success("All metrics are within acceptable thresholds. The bot is performing well across all evaluated dimensions.")
    elif tier == "RED":
        st.error(f"**Critical issues detected:** {'; '.join(issues)}. Deployment should be blocked until resolved.")
    else:
        st.warning(f"**Notable issues:** {'; '.join(issues)}. Consider running the improvement loop before broad rollout.")


def render_questions(db, run_id: str) -> None:
    """Questions page: filterable table + expandable per-question detail."""
    import pandas as pd

    # Iteration selector
    iter_rows = db.query(
        "SELECT DISTINCT iteration FROM responses WHERE run_id = %s ORDER BY iteration",
        (run_id,),
    )
    available_iters = [r["iteration"] for r in iter_rows if r["iteration"] is not None]

    selected_iter: int | None = None
    if available_iters:
        iter_labels = {
            i: f"Iteration {i}" + (" (latest)" if i == max(available_iters) else "")
            for i in available_iters
        }
        col_iter, _ = st.columns([1, 3])
        with col_iter:
            selected_iter = st.selectbox(
                "Iteration",
                options=available_iters,
                index=len(available_iters) - 1,
                format_func=lambda i: iter_labels[i],
            )

    rows = _get_question_verdicts(db, run_id, iteration=selected_iter)
    if not rows:
        st.info("No question verdicts found for this run.")
        return

    # Filters
    col_f1, col_f2, col_f3 = st.columns(3)
    categories = sorted({r["category"] for r in rows if r["category"]})
    languages  = sorted({r["language"]  for r in rows if r["language"]})

    with col_f1:
        cat_filter = st.multiselect("Category", categories, default=categories)
    with col_f2:
        lang_filter = st.multiselect("Language", languages, default=languages)
    with col_f3:
        hall_filter = st.selectbox("Hallucination", ["All", "Any hallucination", "Clean only"])

    filtered = [
        r for r in rows
        if r["category"] in cat_filter and r["language"] in lang_filter
    ]
    if hall_filter == "Any hallucination":
        filtered = [r for r in filtered if r["detail"].get("hallucination_rate", 0) > 0]
    elif hall_filter == "Clean only":
        filtered = [r for r in filtered if r["detail"].get("hallucination_rate", 0) == 0]

    st.caption(f"Showing {len(filtered)} of {len(rows)} questions")
    st.divider()

    for row in filtered:
        detail = row.get("detail", {})
        hall_rate = detail.get("hallucination_rate", 0)
        refusal   = detail.get("refusal", "—")
        faith     = detail.get("faithfulness")
        trans     = detail.get("transparency", 0)

        # Header line
        tier_icon = "🔴" if hall_rate > 0.20 else ("🟡" if hall_rate > 0 else "🟢")
        iter_tag = f" · iter {row.get('iteration', '?')}" if row.get("iteration") else ""
        label = (
            f"{tier_icon} **{row['question_id']}**{iter_tag} "
            f"— `{row['category']}` / `{row['language']}` "
            f"— Hall: {_pct(hall_rate)} · Refusal: {refusal}"
        )
        with st.expander(label, expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Question**")
                st.info(row["question_text"] or "—")
                if row.get("ground_truth"):
                    st.caption(f"Ground truth: {row['ground_truth']}")
            with c2:
                st.markdown("**Bot Response**")
                st.success(row["response_text"] or "—")
                if row.get("latency_ms"):
                    st.caption(f"Latency: {row['latency_ms']:.0f} ms")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Hallucination", _pct(hall_rate))
            m2.metric("Refusal", refusal)
            m3.metric("Faithfulness", f"{faith:.1f}/5" if faith is not None else "n/a")
            m4.metric("Transparency", _pct(trans))


def _run_reeval_iteration(
    db, run_id: str, api_key: str, iteration: int,
    bot_type: str, endpoint: str, run_meta: dict,
    use_improved_mock: bool = False,
    model: str = "",
) -> None:
    from goveval.storage.db import DB
    from goveval.eval.engine import run_eval
    from goveval.prober.bot_prober import probe_all
    from goveval.config.loader import GovEvalConfig, TargetConfig, KnowledgeBaseConfig, LLMConfig, EvalConfig, StorageConfig
    from goveval.questions.categories import Question

    llm = _make_pipeline_llm_client({"llm_api_key": api_key, "llm_model": model or ""}, fallback_key=api_key)

    raw_qs = db.get_questions(run_id)
    if not raw_qs:
        st.error("No questions found for this run in the database.")
        return

    questions = [
        Question(
            question_id=q["question_id"], run_id=run_id,
            category=q["category"], language=q["language"],
            text=q["text"], ground_truth=q.get("ground_truth"),
            gt_source=q.get("gt_source"),
            expected_behavior=q.get("expected_behavior", "answer"),
        )
        for q in raw_qs
    ]

    cfg = GovEvalConfig(
        target=TargetConfig(
            name=run_meta.get("target_name", "bot"),
            endpoint=endpoint,
            type="local" if bot_type == "mock" else "api",
        ),
        knowledge_base=KnowledgeBaseConfig(mode="connect"),
        llm=LLMConfig(provider=llm.provider, model=llm.model, api_key_env=""),
        eval=EvalConfig(
            question_bank_size=len(questions), held_out_size=0,
            human_label_sample=0, iterations=1,
            improvement_threshold=0.02, singlish=True,
            rate_limit_delay=0.0 if bot_type == "mock" else 0.3,
        ),
        storage=StorageConfig(db_path=db.path, results_dir="results"),
    )

    local_fn = None
    if bot_type == "mock":
        import sys as _sys, os as _os
        _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "demo"))
        from mock_bot import mock_bot as _mock_bot, improved_mock_bot as _improved_mock_bot
        local_fn = _improved_mock_bot if use_improved_mock else _mock_bot
    elif bot_type == "vica":
        local_fn = _make_vica_fn(
            page_url=run_meta.get("config_json_parsed", {}).get("vica_page_url", "https://www.tech.gov.sg/"),
            trigger_text=run_meta.get("config_json_parsed", {}).get("vica_trigger_text", "Ask a question"),
        )

    with st.status(f"Running iteration {iteration} for run `{run_id}`…", expanded=True) as status:
        st.write(f"Probing bot with {len(questions)} questions…")
        responses = probe_all(questions, cfg, run_id, iteration=iteration, db=db, local_fn=local_fn)
        st.write(f"Scoring {len(responses)} responses…")
        run_eval(
            run_id=run_id, iteration=iteration, questions=questions,
            responses=responses, kb=_SimpleKB([]), llm_client=llm, db=db,
        )
        status.update(label=f"Iteration {iteration} complete", state="complete")

    st.success(f"Iteration {iteration} saved. Refresh the page to see updated trends.")


def render_iterations(
    iterations: list[dict],
    db=None,
    run_id: str = "",
    api_key: str = "",
    run_meta: dict | None = None,
    model: str = "",
) -> None:
    """Iterations page: metric trend chart + table."""
    import pandas as pd

    if not iterations:
        st.info("No iteration data found.")
        return

    if len(iterations) == 1:
        st.info("Only one iteration completed. Run more iterations to see trends.")
        m = iterations[0]
        st.json({k: v for k, v in m.items() if k != "iteration"})

    # ── Re-evaluate: add another iteration ───────────────────────────────────
    if db and run_id:
        next_iter = max(it["iteration"] for it in iterations) + 1
        with st.expander(f"▶ Run Iteration {next_iter} (re-evaluate same run)"):
            st.caption(
                "Re-probes the same bot with the same questions and scores again. "
                "Use this after applying a fix (e.g. new system prompt) to track improvement."
            )
            # Pre-fill from stored config
            _cfg = {}
            try:
                import json as _j
                _cfg = _j.loads((run_meta or {}).get("config_json") or "{}")
            except Exception:
                pass
            _stored_type = _cfg.get("bot_type", "mock")
            _stored_endpoint = _cfg.get("bot_endpoint", "")
            _type_options = ["mock", "api", "chat (Playwright — not yet implemented)"]
            _type_index = _type_options.index(_stored_type) if _stored_type in _type_options else 0
            bot_type = st.selectbox(
                "Bot type", _type_options,
                index=_type_index,
                key=f"reeval_bot_type_{run_id}",
            )
            endpoint = ""
            if bot_type == "api":
                endpoint = st.text_input(
                    "Bot endpoint URL (POST /question → {answer: ...})",
                    value=_stored_endpoint,
                    key=f"reeval_endpoint_{run_id}",
                )
            use_improved = False
            if bot_type == "mock":
                use_improved = st.checkbox(
                    "Use improved mock bot (v2) — all 6 hallucinations fixed + source citations added",
                    key=f"reeval_improved_{run_id}",
                )
                if use_improved:
                    st.success(
                        "✓ Fixed: CPF OA rate (2.5%), Baby Bonus ($11k), Workfare age (30), "
                        "SkillsFuture PR eligibility, BTO 5-year MOP, GST Voucher URL  \n"
                        "✓ Added: source citations and gov portal redirects (improves transparency)"
                    )

            if not api_key:
                st.warning("Enter an API key in the sidebar to run another iteration.")
            elif "Playwright" in bot_type:
                st.info("Playwright chat UI probing is not yet implemented.")
            elif st.button(f"Run Iteration {next_iter}", key=f"reeval_btn_{run_id}"):
                _run_reeval_iteration(
                    db=db, run_id=run_id, api_key=api_key,
                    iteration=next_iter, bot_type=bot_type, endpoint=endpoint,
                    run_meta=run_meta or {}, use_improved_mock=use_improved, model=model,
                )

    if len(iterations) == 1:
        return

    df = pd.DataFrame(iterations)
    df = df.set_index("iteration")

    metric_cols = [
        "hallucination_rate", "refusal_precision", "refusal_recall",
        "faithfulness_avg", "singlish_gap", "calibration_ece", "transparency_avg",
    ]
    available = [c for c in metric_cols if c in df.columns]

    _section("📈", "Metric Trend")
    selected_metrics = st.multiselect(
        "Metrics to plot", available,
        default=["hallucination_rate", "refusal_recall", "faithfulness_avg"],
    )
    if selected_metrics:
        st.line_chart(df[selected_metrics])

    st.divider()
    _section("📋", "Iteration Table")
    display_df = df[available].copy()
    for col in display_df.columns:
        if "rate" in col or "gap" in col or "precision" in col or "recall" in col or "avg" == col[-3:]:
            display_df[col] = display_df[col].map(lambda x: f"{x*100:.1f}%" if isinstance(x, float) else x)
    st.dataframe(display_df, width="stretch")


def render_metrics(verdicts: list[dict], metrics: dict) -> None:
    """Metrics page: per-question charts for hallucination, refusal, faithfulness, transparency, calibration."""
    import pandas as pd

    if not verdicts:
        st.info("No verdict data available.")
        return

    # Hallucination per question
    _section("🔍", "Hallucination Rate by Question")
    hall_df = pd.DataFrame([
        {"Question": v["question_id"], "Hallucination %": round(v["detail"].get("hallucination_rate", 0) * 100, 1)}
        for v in verdicts
    ]).set_index("Question")
    st.bar_chart(hall_df)
    st.caption("Questions with any hallucination are shown above zero. Target: 0% for all questions.")

    # Refusal breakdown
    st.divider()
    _section("🚫", "Refusal Classification")
    c1, c2, c3 = st.columns(3)
    c1.metric("Precision", _pct(metrics.get("refusal_precision", 0)),
              help="True refusals / all refusals. High = bot doesn't refuse things it shouldn't.")
    c2.metric("Recall", _pct(metrics.get("refusal_recall", 0)),
              help="True refusals / should-have-refused. High = bot correctly declines out-of-scope.")
    c3.metric("F1", _pct(metrics.get("refusal_f1", 0)))

    ref_rows = [
        {"Question": v["question_id"],
         "Category": v.get("category", "—"),
         "Language": v.get("language", "—"),
         "Refusal Class": v["detail"].get("refusal", "—")}
        for v in verdicts
    ]
    st.dataframe(pd.DataFrame(ref_rows), hide_index=True, width="stretch")

    # Faithfulness per question
    st.divider()
    _section("📊", "Faithfulness Scores (out of 5)")
    faith_rows = [
        {"Question": v["question_id"], "Score": v["detail"].get("faithfulness") or 0}
        for v in verdicts
        if v["detail"].get("faithfulness") is not None
    ]
    if faith_rows:
        st.bar_chart(pd.DataFrame(faith_rows).set_index("Question"))
        st.caption("Composite of Accuracy + Completeness + Clarity + Actionability. Target: ≥ 3.5.")
    else:
        st.info("No faithfulness scores recorded (full refusals are excluded).")

    # Transparency per question
    st.divider()
    _section("📡", "Transparency Scores")
    trans_rows = [
        {"Question": v["question_id"], "Transparency %": round(v["detail"].get("transparency", 0) * 100, 1)}
        for v in verdicts
    ]
    st.bar_chart(pd.DataFrame(trans_rows).set_index("Question"))
    st.caption("Measures citation presence, accuracy, uncertainty flagging, and redirect quality. Target: ≥ 60%.")

    # Calibration
    st.divider()
    _section("🎯", "Confidence Calibration")
    ece = metrics.get("calibration_ece", 0)
    col_ece, col_info = st.columns([1, 3])
    col_ece.metric("ECE", f"{ece:.4f}", help="Expected Calibration Error — lower is better.")
    col_info.markdown(
        "**Expected Calibration Error (ECE)** measures how well the bot's expressed confidence "
        "matches its actual accuracy. A perfectly calibrated bot that says "
        "*'I'm 80% sure'* is correct 80% of the time.  \n"
        "**Thresholds:** < 0.10 = well-calibrated · > 0.20 = AMBER"
    )
    singlish_gap = metrics.get("singlish_gap", 0)
    st.divider()
    _section("🗣️", "Singlish Gap")
    col_sg, col_sg_info = st.columns([1, 3])
    col_sg.metric("Gap", _pct(singlish_gap),
                  help="Standard English score − Singlish score. Positive = Singlish performs worse.")
    col_sg_info.markdown(
        "Compares hallucination and faithfulness scores between formal English and Singlish "
        "variants of the same question. A large gap indicates the bot handles colloquial language poorly.  \n"
        "**Threshold:** > 15% → AMBER"
    )


@st.cache_resource
def _get_db(db_path: str):
    from goveval.storage.db import DB
    return DB(db_path)


def _client_from_key(api_key: str, model: str = ""):
    """Build a lightweight LLMClient inferred from key prefix, with optional model override."""
    from goveval.llm.client import LLMClient
    if api_key.startswith("gsk_"):
        m = model or "llama-3.3-70b-versatile"
        return LLMClient(model=m, api_key=api_key, rate_limit_delay=0.5, provider="groq")
    elif api_key.startswith("AIza"):
        m = model or "gemini-2.0-flash"
        return LLMClient(model=m, api_key=api_key, rate_limit_delay=0.5, provider="gemini")
    elif api_key.startswith("sk-ant-"):
        m = model or "claude-haiku-4-5-20251001"
        return LLMClient(model=m, api_key=api_key, rate_limit_delay=0.5, provider="anthropic")
    elif api_key.startswith("sk-"):
        m = model or "gpt-4o-mini"
        return LLMClient(model=m, api_key=api_key, rate_limit_delay=0.5, provider="openai")
    m = model or "claude-haiku-4-5-20251001"
    return LLMClient(model=m, api_key=api_key, rate_limit_delay=0.5, provider="anthropic")


def _make_pipeline_llm_client(p: dict, fallback_key: str = ""):
    """
    Build LLMClient from pipeline state, with key-prefix inference as fallback.

    Uses p["llm_provider"] / p["llm_model"] / p["llm_api_key"] when set (Step 1 wizard).
    Falls back to inferring provider from key prefix so a Groq key entered in the
    sidebar is never accidentally sent to the Anthropic client.
    """
    from goveval.llm.client import LLMClient

    key = p.get("llm_api_key") or fallback_key
    if not key:
        raise ValueError("No LLM API key found. Enter a key in the sidebar or Step 1.")

    # Infer provider from prefix when not explicitly set in pipeline state
    if p.get("llm_provider"):
        provider = p["llm_provider"]
    elif key.startswith("gsk_"):
        provider = "groq"
    elif key.startswith("AIza"):
        provider = "gemini"
    elif key.startswith("sk-ant-"):
        provider = "anthropic"
    elif key.startswith("sk-"):
        provider = "openai"
    else:
        provider = "anthropic"

    # Pick a sensible default model if none was configured
    _default_models = {
        "groq": "llama-3.3-70b-versatile",
        "gemini": "gemini-2.0-flash",
        "openai": "gpt-4o-mini",
        "anthropic": "claude-sonnet-4-6",
    }
    if p.get("llm_model"):
        model = p["llm_model"]
    else:
        model = _default_models.get(provider, "claude-sonnet-4-6")

    return LLMClient(model=model, api_key=key, rate_limit_delay=0.3, provider=provider)


_SEV_ICON = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}


def render_failures(db, run_id: str, api_key: str = "", model: str = "") -> None:
    """Failures page — failure detection, ML clustering, LLM hypotheses, training samples."""

    # ── Flow guide ────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="ge-flow-banner">'
        '<div class="flow-title">Failures tab — 3-step fix flow</div>'
        '<div class="flow-steps">'
        '① Analyze Failure Patterns &nbsp;→&nbsp; '
        '② Generate Improvement Hypotheses &nbsp;→&nbsp; '
        '③ Prompt Rewrite or Training Pairs'
        '</div>'
        '<div class="flow-note">Each step requires the API key set in the sidebar. '
        'Results are cached in session — refresh the page to clear them.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    verdicts = _get_question_verdicts(db, run_id)
    if not verdicts:
        st.info("No verdict data found.")
        return

    # ── Failure detection ────────────────────────────────────────────────────
    failures = []
    for v in verdicts:
        detail = v.get("detail", {})
        hall = detail.get("hallucination_rate") or 0
        faith = detail.get("faithfulness")
        refusal_cls = detail.get("refusal") or ""
        trans_raw = detail.get("transparency")
        trans = trans_raw if trans_raw is not None else 1.0

        failed_metrics = []
        if hall > 0:
            failed_metrics.append(f"Hallucination {_pct(hall)}")
        if faith is not None and faith < 3.0:
            failed_metrics.append(f"Faithfulness {faith:.1f}/5")
        if refusal_cls == "FALSE_REFUSAL":
            failed_metrics.append("False Refusal")
        if trans < 0.60:
            failed_metrics.append(f"Transparency {_pct(trans)}")

        if not failed_metrics:
            continue

        if hall > 0.20 or (faith is not None and faith < 2.5):
            severity = "HIGH"
        elif hall > 0 or (faith is not None and faith < 3.5):
            severity = "MEDIUM"
        else:
            severity = "LOW"

        failures.append({**v, "failed_metrics": failed_metrics, "severity": severity})

    if not failures:
        st.success("No failures detected — all questions passed evaluation criteria.")
        return

    high = sum(1 for f in failures if f["severity"] == "HIGH")
    med  = sum(1 for f in failures if f["severity"] == "MEDIUM")
    low  = sum(1 for f in failures if f["severity"] == "LOW")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Failures", len(failures), f"of {len(verdicts)} questions")
    c2.metric("High Severity", high)
    c3.metric("Medium Severity", med)
    c4.metric("Low Severity", low)

    # ── Failure Pattern Analysis (ML clustering + LLM labels) ────────────────
    st.divider()
    _section("🔬", "Step 1 — Failure Pattern Analysis")
    st.caption(
        "Groups failing questions using sentence embeddings + KMeans, then asks the LLM "
        "to label each cluster with a human-readable root cause."
    )

    fa_key = f"fa_{run_id}"
    fh_key = f"fh_{run_id}"

    if not api_key:
        st.info("Enter an API key in the sidebar to run ML-powered failure pattern analysis.")
    else:
        if fa_key not in st.session_state:
            if st.button("Analyze Failure Patterns", type="primary", key="btn_analyze"):
                with st.status("Analyzing failure patterns…", expanded=True) as status:
                    try:
                        from goveval.analysis.failure_analyser import analyse_failures
                        st.write("Loading sentence-transformer embedding model…")
                        llm = _client_from_key(api_key, model)
                        st.write(f"Embedding {len(failures)} failed questions…")
                        fa = analyse_failures(
                            verdicts=verdicts,
                            run_id=run_id,
                            iteration=1,
                            llm_client=llm,
                            n_clusters=min(4, max(1, len(failures) // 2)),
                        )
                        st.session_state[fa_key] = fa
                        status.update(
                            label=f"Found {len(fa.clusters)} failure cluster(s) — dominant: {fa.dominant_pattern}",
                            state="complete",
                        )
                        st.rerun()
                    except Exception as e:
                        status.update(label=f"Analysis failed: {e}", state="error")
                        st.error(str(e))

        if fa_key in st.session_state:
            fa = st.session_state[fa_key]
            st.success(
                f"**{len(fa.clusters)} cluster(s)** identified across {fa.total_failures} failures.  "
                f"Dominant pattern: **{fa.dominant_pattern}**"
            )
            for cluster in fa.clusters:
                sev_icon = _SEV_ICON.get(cluster.severity, "⚪")
                with st.expander(
                    f"{sev_icon} **{cluster.label}** — {cluster.failure_count} question(s) · {cluster.severity}",
                    expanded=True,
                ):
                    st.caption(f"Root cause: {cluster.root_cause}")
                    cols_m = st.columns(2)
                    cols_m[0].markdown(
                        f"**Failed metrics:** {', '.join(cluster.common_metrics) or '—'}"
                    )
                    cols_m[1].markdown(
                        f"**Questions in cluster:** {', '.join(cluster.question_ids)}"
                    )
                    if cluster.representative_questions:
                        st.markdown("**Representative questions:**")
                        for q in cluster.representative_questions:
                            st.markdown(f"- _{q}_")

            # ── LLM Improvement Hypotheses ────────────────────────────────────
            st.divider()
            _section("🧠", "Step 2 — Improvement Hypotheses")
            st.caption(
                "For each cluster the LLM diagnoses the root cause and produces targeted hypotheses: "
                "missing KB content, wrong prompt instruction, or retrieval parameter issue."
            )

            fh_err_key = f"{fh_key}_errors"
            if fh_key not in st.session_state:
                if st.button("Generate Improvement Hypotheses", type="primary", key="btn_hyp"):
                    with st.status("Generating hypotheses…", expanded=True) as status:
                        try:
                            from goveval.analysis.hypothesis import generate_hypotheses
                            llm = _client_from_key(api_key, model)
                            hyps, errs = generate_hypotheses(fa, llm)
                            st.session_state[fh_key] = hyps
                            st.session_state[fh_err_key] = errs
                            status.update(
                                label=f"Generated {len(hyps)} hypothesis/hypotheses",
                                state="complete",
                            )
                            st.rerun()
                        except Exception as e:
                            status.update(label=f"Failed: {e}", state="error")
                            st.error(str(e))

            if fh_key in st.session_state:
                hypotheses = st.session_state[fh_key]
                for err in st.session_state.get(fh_err_key, []):
                    st.warning(err)
                if not hypotheses:
                    st.info("No hypotheses generated — see warnings above for details.")
                _type_badge = {
                    "MISSING_KB":      ("🗂️", "#fef3c7", "#92400e"),
                    "WRONG_PROMPT":    ("📝", "#dbeafe", "#1e40af"),
                    "RETRIEVAL_PARAM": ("🔍", "#f3e8ff", "#6b21a8"),
                }
                for h in hypotheses:
                    icon, bg, fg = _type_badge.get(h.hypothesis_type, ("•", "#f1f5f9", "#334155"))
                    impact_icon = _SEV_ICON.get(h.estimated_impact, "⚪")
                    with st.expander(
                        f"{icon} **{h.hypothesis_type}** — {h.description}  {impact_icon} {h.estimated_impact}",
                        expanded=True,
                    ):
                        st.markdown(
                            f'<div style="background:{bg};color:{fg};padding:8px 14px;'
                            f'border-radius:6px;margin-bottom:8px">'
                            f'<strong>Cluster:</strong> {h.cluster_label}</div>',
                            unsafe_allow_html=True,
                        )
                        col_fix, col_comp = st.columns([3, 1])
                        col_fix.markdown(f"**Proposed fix:** {h.proposed_fix}")
                        col_comp.markdown(f"**Component:** `{h.fix_path}`")

                # Build a lookup used by all fix sections below
                failure_by_qid = {f.get("question_id", ""): f for f in failures}

                # ── Generate Prompt Rewrites (Path A) ────────────────────────
                prompt_hyps = [h for h in hypotheses if h.fix_path == "prompt_optimiser"]
                if prompt_hyps:
                    st.divider()
                    _section("📝", "Step 3A — Prompt Rewrites")
                    st.caption(
                        "For each WRONG_PROMPT hypothesis the LLM generates a targeted system "
                        "prompt edit: minimal change, explained diff, expected metric improvement, "
                        "and regression risk."
                    )

                    current_prompt_key = f"cur_prompt_{run_id}"
                    if current_prompt_key not in st.session_state:
                        st.session_state[current_prompt_key] = (
                            "You are a helpful Singapore government assistant. "
                            "Answer questions accurately based on the provided context."
                        )

                    with st.expander("Current system prompt (paste yours or use the default)", expanded=False):
                        st.session_state[current_prompt_key] = st.text_area(
                            "System prompt",
                            value=st.session_state[current_prompt_key],
                            height=120,
                            key=f"cur_prompt_input_{run_id}",
                        )

                    for h in prompt_hyps:
                        pr_key = f"pr_{run_id}_{h.hypothesis_id}"
                        impact_icon = _SEV_ICON.get(h.estimated_impact, "⚪")
                        st.markdown(
                            f"**{impact_icon} {h.cluster_label}** — _{h.description}_"
                        )

                        if pr_key not in st.session_state:
                            if st.button(
                                "Generate prompt rewrite",
                                key=f"btn_pr_{h.hypothesis_id}",
                            ):
                                with st.status("Generating prompt rewrite…", expanded=True) as status:
                                    try:
                                        from goveval.improvement.prompt_optimiser import (
                                            generate_candidates, diff_lines,
                                        )
                                        llm = _client_from_key(api_key, model)
                                        cluster = next(
                                            (c for c in fa.clusters if c.cluster_id == h.cluster_id), None
                                        )
                                        fail_examples = [
                                            failure_by_qid[qid]
                                            for qid in (cluster.question_ids if cluster else [])
                                            if qid in failure_by_qid
                                        ]
                                        candidates = generate_candidates(
                                            [h],
                                            st.session_state[current_prompt_key],
                                            fail_examples,
                                            llm,
                                        )
                                        st.session_state[pr_key] = candidates
                                        status.update(
                                            label=f"Generated {len(candidates)} candidate rewrite(s)",
                                            state="complete",
                                        )
                                    except Exception as e:
                                        status.update(label=f"Failed: {e}", state="error")
                                        st.error(str(e))
                                st.rerun()
                        else:
                            from goveval.improvement.prompt_optimiser import diff_lines
                            candidates = st.session_state[pr_key]
                            for cand in candidates:
                                with st.expander(
                                    f"📝 Candidate — {cand.change_description[:80]}",
                                    expanded=True,
                                ):
                                    # Diff view
                                    st.markdown("**Prompt diff:**")
                                    diff = diff_lines(cand.original_prompt, cand.modified_prompt)
                                    diff_md = []
                                    for kind, line in diff:
                                        if kind == "added":
                                            diff_md.append(f"+ {line}")
                                        elif kind == "removed":
                                            diff_md.append(f"- {line}")
                                        else:
                                            diff_md.append(f"  {line}")
                                    st.code("\n".join(diff_md), language="diff")

                                    col_exp, col_risk = st.columns(2)
                                    with col_exp:
                                        st.markdown("**Expected improvement:**")
                                        for metric, delta in cand.expected_improvement.items():
                                            st.markdown(f"- `{metric}`: {delta}")
                                    with col_risk:
                                        st.markdown("**Regression risk:**")
                                        st.caption(cand.regression_risk or "Not specified.")

                                    import json as _json
                                    dl_data = _json.dumps({
                                        "hypothesis_id": cand.hypothesis_id,
                                        "change_description": cand.change_description,
                                        "original_prompt": cand.original_prompt,
                                        "modified_prompt": cand.modified_prompt,
                                        "expected_improvement": cand.expected_improvement,
                                        "regression_risk": cand.regression_risk,
                                    }, indent=2)
                                    st.download_button(
                                        "Download prompt JSON",
                                        data=dl_data,
                                        file_name=f"prompt_fix_{cand.candidate_id}.json",
                                        mime="application/json",
                                        key=f"dl_pr_{cand.candidate_id}",
                                    )

                        st.markdown("---")

                # ── Generate Training Samples ─────────────────────────────────
                data_hyps = [h for h in hypotheses if h.fix_path == "data_generator"]
                if data_hyps:
                    st.divider()
                    _section("🗂️", "Step 3B — Supplementary KB Documents")
                    st.caption(
                        "For each MISSING_KB hypothesis the LLM drafts a supplementary KB document "
                        "and 5 follow-up evaluation questions that target the gap."
                    )

                    for h in data_hyps:
                        ts_key = f"ts_{run_id}_{h.hypothesis_id}"
                        impact_icon = _SEV_ICON.get(h.estimated_impact, "⚪")
                        st.markdown(
                            f"**{impact_icon} {h.cluster_label}** — _{h.description}_"
                        )

                        if ts_key not in st.session_state:
                            if st.button(
                                f"Generate KB document + questions",
                                key=f"btn_ts_{h.hypothesis_id}",
                            ):
                                with st.status("Generating training sample…", expanded=True) as status:
                                    try:
                                        from goveval.improvement.data_generator import generate_training_sample
                                        llm = _client_from_key(api_key, model)
                                        cluster = next(
                                            (c for c in fa.clusters if c.cluster_id == h.cluster_id), None
                                        )
                                        failure_examples = [
                                            failure_by_qid[qid]
                                            for qid in (cluster.question_ids if cluster else [])
                                            if qid in failure_by_qid
                                        ]
                                        sample = generate_training_sample(h, failure_examples, llm)
                                        st.session_state[ts_key] = sample
                                        status.update(
                                            label=f"Generated: {sample.doc.title}  ({len(sample.questions)} questions)",
                                            state="complete",
                                        )
                                    except Exception as e:
                                        status.update(label=f"Failed: {e}", state="error")
                                        st.error(str(e))
                                st.rerun()
                        else:
                            sample = st.session_state[ts_key]
                            doc = sample.doc
                            col_doc, col_dl = st.columns([5, 1])
                            with col_doc:
                                st.markdown(
                                    f'<div style="background:#f0fdf4;border-left:4px solid #16a34a;'
                                    f'padding:10px 16px;border-radius:4px">'
                                    f'<strong>📄 {doc.title}</strong><br>'
                                    f'<span style="font-size:0.8rem;color:#6b7280">{doc.source_label}</span>'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )
                                st.text_area(
                                    "Document content",
                                    value=doc.content,
                                    height=160,
                                    disabled=True,
                                    key=f"doc_content_{h.hypothesis_id}",
                                )
                            with col_dl:
                                import json as _json
                                dl_data = _json.dumps({
                                    "document": {
                                        "title": doc.title,
                                        "content": doc.content,
                                        "source_label": doc.source_label,
                                        "is_synthetic": True,
                                    },
                                    "evaluation_questions": [
                                        {"text": q.text, "category": q.category,
                                         "expected_behavior": q.expected_behavior}
                                        for q in sample.questions
                                    ],
                                }, indent=2)
                                st.download_button(
                                    "Download JSON",
                                    data=dl_data,
                                    file_name=f"training_sample_{h.hypothesis_id}.json",
                                    mime="application/json",
                                    key=f"dl_{h.hypothesis_id}",
                                )

                            if sample.questions:
                                st.markdown("**Follow-up evaluation questions:**")
                                for i, q in enumerate(sample.questions, 1):
                                    badge = {"in_scope": "🟢", "adversarial": "🔴",
                                             "out_of_scope": "⚫", "singlish": "🔵"}.get(q.category, "⚪")
                                    st.markdown(f"{i}. {badge} `{q.category}` — {q.text}")

                        st.markdown("---")

                # ── Generate QA Training Pairs (Path B extended) ──────────────
                if hypotheses:
                    st.divider()
                    _section("🎯", "Step 3C — (Q, ideal_response) Training Pairs")
                    st.caption(
                        "Generates 20 synthetic training pairs targeted at a specific failure pattern "
                        "— grounded in the knowledge base. Download as JSONL or CSV for "
                        "few-shot injection, fine-tuning, or regression test expansion."
                    )

                    for h in hypotheses[:3]:
                        qa_key = f"qa_{run_id}_{h.hypothesis_id}"
                        impact_icon = _SEV_ICON.get(h.estimated_impact, "⚪")
                        st.markdown(
                            f"**{impact_icon} {h.cluster_label}** — _{h.description}_"
                        )

                        if qa_key not in st.session_state:
                            if st.button(
                                "Generate 20 training pairs",
                                key=f"btn_qa_{h.hypothesis_id}",
                            ):
                                with st.status("Generating training pairs…", expanded=True) as status:
                                    try:
                                        from goveval.improvement.data_generator import generate_qa_pairs
                                        llm = _client_from_key(api_key, model)
                                        cluster = next(
                                            (c for c in fa.clusters if c.cluster_id == h.cluster_id), None
                                        )
                                        fail_examples = [
                                            failure_by_qid[qid]
                                            for qid in (cluster.question_ids if cluster else [])
                                            if qid in failure_by_qid
                                        ]
                                        # Pull KB chunks from current pipeline session if available
                                        kb_chunks = None
                                        if "pipeline" in st.session_state:
                                            raw = st.session_state["pipeline"].get("chunks", [])
                                            if raw:
                                                kb_chunks = [
                                                    {"source_name": getattr(c, "source_name", "Source"),
                                                     "text": getattr(c, "text", "")}
                                                    for c in raw[:8]
                                                ]
                                        qa_set = generate_qa_pairs(
                                            h, fail_examples, kb_chunks, llm, n_pairs=20
                                        )
                                        st.session_state[qa_key] = qa_set
                                        status.update(
                                            label=f"Generated {len(qa_set.pairs)} training pair(s)",
                                            state="complete",
                                        )
                                    except Exception as e:
                                        status.update(label=f"Failed: {e}", state="error")
                                        st.error(str(e))
                                st.rerun()
                        else:
                            from goveval.improvement.data_generator import qa_set_to_jsonl, qa_set_to_csv
                            qa_set = st.session_state[qa_key]

                            st.success(f"{len(qa_set.pairs)} pairs generated for: **{qa_set.cluster_label}**")
                            st.caption(f"Usage: {qa_set.usage_notes}")

                            style_icons = {
                                "formal": "🔵",
                                "singlish_mild": "🟡",
                                "singlish_heavy": "🟠",
                                "adversarial": "🔴",
                            }
                            for i, pair in enumerate(qa_set.pairs[:5], 1):
                                icon = style_icons.get(pair.phrasing_style, "⚪")
                                with st.expander(
                                    f"{icon} Example {i} [{pair.phrasing_style}] — {pair.question[:60]}…",
                                    expanded=(i == 1),
                                ):
                                    c1, c2 = st.columns(2)
                                    with c1:
                                        st.markdown("**Question**")
                                        st.info(pair.question)
                                    with c2:
                                        st.markdown("**Ideal response**")
                                        st.success(pair.ideal_response)

                            if len(qa_set.pairs) > 5:
                                st.caption(f"…and {len(qa_set.pairs) - 5} more pairs in the download.")

                            col_dl1, col_dl2, col_dl3 = st.columns(3)
                            with col_dl1:
                                st.download_button(
                                    "Download JSONL",
                                    data=qa_set_to_jsonl(qa_set),
                                    file_name=f"training_pairs_{h.hypothesis_id}.jsonl",
                                    mime="application/jsonl",
                                    key=f"dl_qa_jsonl_{h.hypothesis_id}",
                                )
                            with col_dl2:
                                st.download_button(
                                    "Download CSV",
                                    data=qa_set_to_csv(qa_set),
                                    file_name=f"training_pairs_{h.hypothesis_id}.csv",
                                    mime="text/csv",
                                    key=f"dl_qa_csv_{h.hypothesis_id}",
                                )
                            with col_dl3:
                                st.markdown(
                                    "**Usage options:**  \n"
                                    "Inject as few-shot examples  \n"
                                    "Fine-tuning data  \n"
                                    "Regression test expansion"
                                )

                        st.markdown("---")

    # ── Per-question failure details ─────────────────────────────────────────
    st.divider()
    _section("📋", "Failure Details")

    categories = sorted({f.get("category", "?") for f in failures})
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        cat_filter = st.multiselect("Category", categories, default=categories, key="fail_cat")
    with col_f2:
        sev_filter = st.multiselect("Severity", ["HIGH", "MEDIUM", "LOW"],
                                    default=["HIGH", "MEDIUM", "LOW"], key="fail_sev")

    filtered = [f for f in failures
                if f.get("category") in cat_filter and f["severity"] in sev_filter]
    st.caption(f"Showing {len(filtered)} of {len(failures)} failures")

    for f in filtered:
        icon = _SEV_ICON.get(f["severity"], "⚪")
        label = (
            f"{icon} **{f['question_id']}** [{f['severity']}] "
            f"— `{f.get('category', '?')}` / `{f.get('language', '?')}`  \n"
            f"Failed: {', '.join(f['failed_metrics'])}"
        )
        with st.expander(label):
            ca, cb = st.columns(2)
            with ca:
                st.markdown("**Question**")
                st.info(f.get("question_text") or "—")
                if f.get("ground_truth"):
                    st.caption(f"Ground truth: {f['ground_truth']}")
            with cb:
                st.markdown("**Bot Response**")
                st.warning(f.get("response_text") or "—")
            detail = f.get("detail", {})
            m1, m2, m3 = st.columns(3)
            m1.metric("Hallucination", _pct(detail.get("hallucination_rate", 0)))
            faith_v = detail.get("faithfulness")
            m2.metric("Faithfulness", f"{faith_v:.1f}/5" if faith_v is not None else "n/a")
            m3.metric("Transparency", _pct(detail.get("transparency", 0)))


# ── Pipeline wizard helpers ───────────────────────────────────────────────────

def _pipeline_progress(current: int) -> None:
    """Render a visual numbered step indicator."""
    steps = [
        ("Configure", "Bot + LLM"),
        ("Sources",   "Knowledge base"),
        ("Questions", "LLM generates"),
        ("Evaluate",  "7 metrics"),
        ("Results",   "Risk tier"),
    ]
    parts: list[str] = []
    for i, (title, sub) in enumerate(steps, start=1):
        if i < current:
            circle_cls = "step-circle-done"
            title_cls  = "step-title-done"
            num        = "✓"
        elif i == current:
            circle_cls = "step-circle-active"
            title_cls  = "step-title-active"
            num        = str(i)
        else:
            circle_cls = "step-circle-future"
            title_cls  = "step-title-future"
            num        = str(i)

        parts.append(
            f'<div class="goveval-step">'
            f'  <div class="step-circle {circle_cls}">{num}</div>'
            f'  <div class="step-label">'
            f'    <div class="{title_cls}">{title}</div>'
            f'    <div class="step-sub">{sub}</div>'
            f'  </div>'
            f'</div>'
        )
        if i < len(steps):
            conn = "connector-done" if i < current else ("connector-active" if i == current else "connector-future")
            parts.append(f'<div class="step-connector {conn}"></div>')

    st.markdown(
        f'<div class="goveval-stepper">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


def _pipeline_nav(p: dict, back_step: int | None, next_fn=None) -> None:
    """Render a Back button. Callers are responsible for column layout."""
    if back_step is not None:
        if st.button("← Back", key=f"back_{p['step']}", use_container_width=True):
            p["step"] = back_step
            st.rerun()


def _extract_chunks_from_pipeline(p: dict) -> list:
    """Run the appropriate extraction strategy and return Chunk objects."""
    from goveval.knowledge_base.chunker import Chunk

    _PARTIAL_KB_IDS = {"cpf_001", "cpf_002", "hdb_001", "bb_001", "cdc_001"}

    if p["source_mode"] in ("mock", "mock_partial"):
        import sys as _sys, os as _os
        _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "demo"))
        from demo_dataset import get_demo_kb_chunks
        from datetime import date
        today = date.today().isoformat()
        raw = get_demo_kb_chunks()
        if p["source_mode"] == "mock_partial":
            raw = [c for c in raw if c["chunk_id"] in _PARTIAL_KB_IDS]
        return [
            Chunk(
                chunk_id=c["chunk_id"],
                source_name=c["source_name"],
                source_url=c["source_url"],
                section_heading=c["section_heading"],
                text=c["text"],
                char_count=len(c["text"]),
                scraped_date=today,
                token_estimate=len(c["text"]) // 4,
            )
            for c in raw
        ]

    elif p["source_mode"] == "url":
        from goveval.knowledge_base.scraper import scrape
        from goveval.knowledge_base.chunker import chunk_pages
        from goveval.config.loader import ScrapeSource

        urls = [u.strip() for u in p.get("source_urls", "").splitlines() if u.strip()]
        depth = p.get("scrape_depth", 0)
        # Allow more chunks for deeper crawls: 60 at d=0, up to 300 at d=4
        chunk_cap = 60 + depth * 60
        all_chunks: list = []
        for url in urls[:5]:
            source = ScrapeSource(name=p.get("source_name", "Source"), url=url, depth=depth)
            pages = scrape(source)
            all_chunks.extend(chunk_pages(pages, source.name, url))
        return all_chunks[:chunk_cap]

    else:  # "text"
        from goveval.knowledge_base.scraper import RawPage
        from goveval.knowledge_base.chunker import chunk_pages

        raw_text = p.get("source_text", "").strip()
        if not raw_text:
            return []
        page = RawPage(source_name=p.get("source_name", "Pasted"), url="", text=raw_text, headings=[])
        return chunk_pages([page], p.get("source_name", "Pasted"), "")[:60]


class _SimpleKB:
    """Keyword-overlap retrieval over Chunk objects for eval."""
    def __init__(self, chunks):
        self._chunks = chunks

    def retrieve(self, query: str, n_results: int = 5):
        from goveval.knowledge_base.embedder import RetrievedChunk
        query_words = set(query.lower().split())
        scored = []
        for c in self._chunks:
            overlap = len(query_words & set(c.text.lower().split()))
            scored.append((overlap, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            RetrievedChunk(
                chunk_id=c.chunk_id,
                source_name=c.source_name,
                source_url=c.source_url,
                section_heading=c.section_heading,
                text=c.text,
                scraped_date=c.scraped_date,
                distance=1.0 / max(1, overlap),
            )
            for overlap, c in scored[:n_results]
        ]


# ── Step renderers ────────────────────────────────────────────────────────────

def _step1_configure(p: dict, api_key: str) -> None:
    import os
    st.markdown("### Step 1 — Configure Target Bot")
    st.caption(
        "Tell IterEval which chatbot to probe. You can test any bot that exposes an HTTP API, "
        "or use the built-in mock bot to explore the platform without a live URL."
    )
    st.divider()

    p["bot_name"] = st.text_input("Bot name / label", value=p.get("bot_name", "gov-bot"),
                                   placeholder="e.g. ask.gov.sg")

    p["bot_type"] = st.radio(
        "Bot interface",
        ["mock", "api"],
        format_func=lambda x: {
            "mock": "Mock bot  (built-in demo — no URL needed, 6 intentional hallucinations seeded)",
            "api":  "HTTP API endpoint  (POST {\"question\": \"...\"} → reads answer/response/text field)",
        }[x],
        index=["mock", "api"].index(p.get("bot_type", "mock")),
    )

    if p["bot_type"] == "api":
        p["bot_endpoint"] = st.text_input(
            "API endpoint URL",
            value=p.get("bot_endpoint", ""),
            placeholder="https://your-chatbot.gov.sg/api/chat",
        )
        st.caption("IterEval will POST `{\"question\": \"<text>\"}` and read the JSON response field `answer`, `response`, or `text`.")
        p["target_model_hint"] = st.text_input(
            "Target bot model (optional — used to detect judge-target collusion)",
            value=p.get("target_model_hint", ""),
            placeholder="e.g. claude-sonnet-4-6, gpt-4o, llama-3.3-70b",
            help=(
                "If the target bot and the judge LLM run on the same model family, "
                "the judge may share blind spots and undercount hallucinations. "
                "IterEval will warn you and suggest switching to a heterogeneous judge."
            ),
        )

    # LLM Judge configuration
    st.divider()
    _section("🤖", "LLM Judge")
    st.caption("Used for question generation and scoring all 7 metrics.")

    _providers = ["anthropic", "groq", "gemini", "openai"]
    _provider_labels = {
        "anthropic": "Anthropic (Claude) — strongest on nuanced Singapore policy text",
        "groq":      "Groq (Llama / Mixtral) — fast LPU inference; good heterogeneous judge",
        "gemini":    "Google Gemini — generous free tier; good general-purpose judge",
        "openai":    "OpenAI (GPT-4o) — strong reasoning; widely available API keys",
    }
    _current_provider = p.get("llm_provider", "anthropic")
    if _current_provider not in _providers:
        _current_provider = "anthropic"
    provider = st.radio(
        "Provider",
        _providers,
        format_func=lambda x: _provider_labels[x],
        index=_providers.index(_current_provider),
        horizontal=False,
    )
    p["llm_provider"] = provider

    _model_options = {
        "anthropic": ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
        "groq":      ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        "gemini":    ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
        "openai":    ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
    }
    _model_help = {
        "anthropic": "claude-sonnet-4-6: best accuracy. claude-haiku: faster and cheaper.",
        "groq":      "llama-3.3-70b-versatile: best quality. llama-3.1-8b-instant: low latency. mixtral: large context.",
        "gemini":    "gemini-2.0-flash: fast and cheap. gemini-1.5-flash: balanced. gemini-1.5-pro: highest quality.",
        "openai":    "gpt-4o-mini: cheapest. gpt-4o: strongest reasoning. gpt-3.5-turbo: legacy/fastest.",
    }
    _key_env = {
        "anthropic": "ANTHROPIC_API_KEY",
        "groq":      "GROQ_API_KEY",
        "gemini":    "GEMINI_API_KEY",
        "openai":    "OPENAI_API_KEY",
    }
    _key_help = {
        "anthropic": "Get a key at console.anthropic.com",
        "groq":      "Get a key at console.groq.com → API Keys",
        "gemini":    "Get a key at aistudio.google.com → Get API key",
        "openai":    "Get a key at platform.openai.com → API keys",
    }
    models = _model_options[provider]
    current_model = p.get("llm_model", models[0])
    p["llm_model"] = st.selectbox(
        "Model",
        models,
        index=models.index(current_model) if current_model in models else 0,
        help=_model_help[provider],
    )
    default_key = p.get("llm_api_key") or api_key or os.environ.get(_key_env[provider], "")
    p["llm_api_key"] = st.text_input(
        f"{provider.capitalize()} API key",
        value=default_key,
        type="password",
        help=_key_help[provider],
    )

    _llm_key = p.get("llm_api_key", "")
    endpoint_ok = (p["bot_type"] == "mock") or bool(p.get("bot_endpoint", "").strip())

    # Judge-target collusion warning
    target_hint = p.get("target_model_hint", "").strip()
    if target_hint and p.get("llm_model"):
        from goveval.llm.client import is_same_family
        if is_same_family(target_hint, p["llm_model"]):
            st.warning(
                "**Judge-Target Collusion Risk**  \n"
                f"The target bot (`{target_hint}`) and your judge (`{p['llm_model']}`) "
                "appear to be from the same model family. "
                "Models in the same family share architectural blind spots and may "
                "systematically miss the same hallucinations.  \n"
                "**Recommendation:** switch the judge to a different architecture family — "
                "e.g. use Groq Llama as judge when the target is Claude, or vice versa.  \n"
                "You can still proceed, but validate judge reliability in the "
                "**Judge Validation** tab before trusting the eval loop."
            )

    if st.button("Next: Knowledge Sources →", type="primary",
                 disabled=not (endpoint_ok and _llm_key)):
        p["step"] = 2
        st.rerun()


def _step2_sources(p: dict) -> None:
    st.markdown("### Step 2 — Knowledge Sources")
    st.caption(
        "IterEval extracts facts from your sources, chunks them, and uses them to "
        "**generate evaluation questions** and to **judge whether bot responses are grounded**. "
        "The richer your sources, the more meaningful the evaluation."
    )
    st.divider()

    p["source_mode"] = st.radio(
        "Knowledge source",
        ["mock", "mock_partial", "url", "text"],
        format_func=lambda x: {
            "mock":         "Demo KB — full (25 chunks: CPF, HDB, Baby Bonus, CDC, SkillsFuture, Workfare, GST Voucher…)",
            "mock_partial": "Demo KB — partial ⚠ (5 chunks only: missing Workfare, SkillsFuture, BTO rules, GST Voucher — use this to demo failure detection)",
            "url":          "Scrape URLs  (IterEval fetches and extracts text from government websites)",
            "text":         "Paste text  (paste policy documents, FAQ content, or any factual text)",
        }[x],
        index=["mock", "mock_partial", "url", "text"].index(p.get("source_mode", "mock")),
    )
    if p["source_mode"] == "mock_partial":
        st.info(
            "**Demo scenario:** The bot will fail on questions about Workfare, SkillsFuture, "
            "BTO 5-year rule, and GST Voucher portal — because those KB chunks are missing.  \n"
            "After running eval and seeing the failures, switch to **Demo KB — full** and "
            "run another iteration to see the improvement."
        )

    if p["source_mode"] == "url":
        p["source_name"] = st.text_input("Source label", value=p.get("source_name", "Gov Source"))
        p["source_urls"] = st.text_area(
            "URLs to scrape (one per line)",
            value=p.get("source_urls", ""),
            placeholder="https://www.cpf.gov.sg/member/faq\nhttps://www.hdb.gov.sg/residential/buying-a-flat",
            height=120,
        )
        p["scrape_depth"] = st.slider(
            "Crawl depth",
            min_value=0, max_value=4, value=p.get("scrape_depth", 0),
            help=(
                "0 = exact URLs only. "
                "1 = + links found on those pages (same domain). "
                "2 = + one more level. "
                "3 = + one more level. "
                "4 = deep crawl — can visit hundreds of pages, takes several minutes."
            ),
        )
        depth_labels = {
            0: "single page only",
            1: "page + directly linked pages",
            2: "2 levels deep",
            3: "3 levels deep — may take a few minutes",
            4: "4 levels deep — full site crawl, can be slow",
        }
        d = p["scrape_depth"]
        if d >= 3:
            st.warning(f"Depth {d}: may visit many pages and take several minutes depending on site size.")
        else:
            st.caption(f"Depth {d} — {depth_labels[d]}")

    elif p["source_mode"] == "text":
        p["source_name"] = st.text_input("Source label", value=p.get("source_name", "Pasted Content"))
        p["source_text"] = st.text_area(
            "Paste knowledge base content",
            value=p.get("source_text", ""),
            placeholder="Paste policy text, FAQ answers, eligibility criteria, grant amounts…",
            height=200,
        )

    can_proceed = (
        p["source_mode"] in ("mock", "mock_partial")
        or (p["source_mode"] == "url" and p.get("source_urls", "").strip())
        or (p["source_mode"] == "text" and p.get("source_text", "").strip())
    )

    col_b, col_n = st.columns([1, 3])
    with col_b:
        _pipeline_nav(p, back_step=1)
    with col_n:
        if st.button("Extract & Chunk →", type="primary", disabled=not can_proceed,
                     key="step2_next"):
            with st.spinner("Extracting and chunking knowledge sources…"):
                p["chunks"] = _extract_chunks_from_pipeline(p)
                p["questions"] = []  # reset downstream
            if not p["chunks"]:
                st.error("No content extracted. Check your URLs or pasted text.")
            else:
                p["step"] = 3
                st.rerun()


_CATEGORIES   = ["in_scope", "out_of_scope", "adversarial", "edge_case"]
_LANGUAGES    = ["formal_english", "singlish", "casual_english"]
_BEHAVIORS    = ["answer", "refuse", "correct", "caveat", "escalate"]
_CAT_BADGE    = {"in_scope": "🟢", "out_of_scope": "🔵", "adversarial": "🔴", "edge_case": "🟡"}
_BEHAVIOR_MAP = {  # expected_behavior that aligns with each category by default
    "in_scope": "answer", "out_of_scope": "refuse",
    "adversarial": "correct", "edge_case": "caveat",
}


def _qs_to_edit_state(questions: list) -> list[dict]:
    """Convert Question objects to plain dicts for the editor."""
    return [
        {
            "question_id":      q.question_id,
            "run_id":           q.run_id,
            "text":             q.text,
            "category":         q.category,
            "language":         q.language,
            "expected_behavior": getattr(q, "expected_behavior", "answer"),
            "ground_truth":     q.ground_truth or "",
            "gt_source":        getattr(q, "gt_source", "") or "",
            "singlish_pair_id": getattr(q, "singlish_pair_id", None),
            "is_held_out":      getattr(q, "is_held_out", False),
            "_deleted":         False,
        }
        for q in questions
    ]


def _edit_state_to_questions(edit_state: list[dict]) -> list:
    """Convert edited dicts back to Question objects."""
    import uuid as _uuid
    from goveval.questions.categories import Question

    return [
        Question(
            question_id=d["question_id"],
            run_id=d["run_id"],
            text=d["text"].strip(),
            category=d["category"],
            language=d["language"],
            expected_behavior=d["expected_behavior"],
            ground_truth=d["ground_truth"] or None,
            gt_source=d["gt_source"] or None,
            singlish_pair_id=d.get("singlish_pair_id"),
            is_held_out=d.get("is_held_out", False),
        )
        for d in edit_state
        if not d["_deleted"] and d["text"].strip()
    ]


def _render_question_editor(p: dict) -> None:
    """
    Inline question editor rendered inside Step 3.

    Lets users edit any field on existing questions, delete questions,
    and add new ones manually before proceeding to evaluation.
    """
    import uuid as _uuid

    run_key = p.get("run_id", "draft")
    edit_key = f"q_edit_{run_key}"

    # Initialise edit state from p["questions"] on first open
    if edit_key not in st.session_state:
        st.session_state[edit_key] = _qs_to_edit_state(p["questions"])

    state: list[dict] = st.session_state[edit_key]
    active = [d for d in state if not d["_deleted"]]

    _section("✏️", "Edit / Add Questions")
    st.caption(
        f"{len(active)} questions · Edit text, change category, delete rows, or add new questions below. "
        "Click **Apply Changes** to save before evaluating."
    )

    # ── Existing questions ────────────────────────────────────────────────────
    for idx, d in enumerate(state):
        if d["_deleted"]:
            continue

        badge = _CAT_BADGE.get(d["category"], "⚪")
        header = f"{badge} [{d['category']} / {d['language']}]  {d['text'][:60]}…"

        with st.expander(header, expanded=False):
            col_text, col_del = st.columns([9, 1])
            with col_text:
                new_text = st.text_area(
                    "Question text",
                    value=d["text"],
                    height=90,
                    key=f"qe_text_{idx}_{run_key}",
                )
                d["text"] = new_text

            with col_del:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("🗑️", key=f"qe_del_{idx}_{run_key}", help="Delete this question"):
                    d["_deleted"] = True
                    st.rerun()

            col_cat, col_lang, col_beh = st.columns(3)
            with col_cat:
                new_cat = st.selectbox(
                    "Category",
                    _CATEGORIES,
                    index=_CATEGORIES.index(d["category"]) if d["category"] in _CATEGORIES else 0,
                    key=f"qe_cat_{idx}_{run_key}",
                )
                d["category"] = new_cat
            with col_lang:
                new_lang = st.selectbox(
                    "Language",
                    _LANGUAGES,
                    index=_LANGUAGES.index(d["language"]) if d["language"] in _LANGUAGES else 0,
                    key=f"qe_lang_{idx}_{run_key}",
                )
                d["language"] = new_lang
            with col_beh:
                new_beh = st.selectbox(
                    "Expected behavior",
                    _BEHAVIORS,
                    index=_BEHAVIORS.index(d["expected_behavior"]) if d["expected_behavior"] in _BEHAVIORS else 0,
                    key=f"qe_beh_{idx}_{run_key}",
                )
                d["expected_behavior"] = new_beh

            new_gt = st.text_input(
                "Ground truth (optional — expected answer or correct fact)",
                value=d["ground_truth"],
                key=f"qe_gt_{idx}_{run_key}",
            )
            d["ground_truth"] = new_gt

    # ── Add new question ──────────────────────────────────────────────────────
    st.divider()
    _section("➕", "Add Question")
    with st.form(key=f"add_q_form_{run_key}", clear_on_submit=True):
        new_text = st.text_area("Question text", placeholder="Enter a new evaluation question…", height=80)
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            new_cat = st.selectbox("Category", _CATEGORIES)
        with col_b:
            new_lang = st.selectbox("Language", _LANGUAGES)
        with col_c:
            new_beh = st.selectbox("Expected behavior", _BEHAVIORS,
                                   index=_BEHAVIORS.index(_BEHAVIOR_MAP.get(new_cat, "answer")))
        new_gt = st.text_input("Ground truth (optional)")
        submitted = st.form_submit_button("Add Question", type="primary")

        if submitted and new_text.strip():
            st.session_state[edit_key].append({
                "question_id":      str(_uuid.uuid4())[:8],
                "run_id":           p.get("run_id", "draft"),
                "text":             new_text.strip(),
                "category":         new_cat,
                "language":         new_lang,
                "expected_behavior": new_beh,
                "ground_truth":     new_gt,
                "gt_source":        "",
                "singlish_pair_id": None,
                "is_held_out":      False,
                "_deleted":         False,
            })
            st.rerun()

    # ── Apply / discard ───────────────────────────────────────────────────────
    st.divider()
    col_apply, col_discard = st.columns([2, 1])
    with col_apply:
        remaining = [d for d in state if not d["_deleted"] and d["text"].strip()]
        if st.button(
            f"Apply Changes ({len(remaining)} questions)",
            type="primary",
            key=f"qe_apply_{run_key}",
        ):
            p["questions"] = _edit_state_to_questions(state)
            del st.session_state[edit_key]
            st.session_state[f"q_edit_open_{run_key}"] = False
            st.rerun()
    with col_discard:
        if st.button("Discard edits", key=f"qe_discard_{run_key}"):
            del st.session_state[edit_key]
            st.session_state[f"q_edit_open_{run_key}"] = False
            st.rerun()


def _step3_questions(p: dict, api_key: str) -> None:
    import os
    st.markdown("### Step 3 — Generate Evaluation Questions")
    st.caption(
        "The LLM reads your knowledge chunks and generates questions covering four types: "
        "**formal English**, **Singlish**, **out-of-scope** (should be refused), and "
        "**adversarial** (wrong premise to correct). This ensures broad coverage of failure modes."
    )
    st.divider()

    chunks = p.get("chunks", [])

    # KB stats
    sources = list({getattr(c, "source_name", "?") for c in chunks})
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Chunks extracted", len(chunks))
    col_b.metric("Sources", len(sources))
    col_c.metric("Est. tokens", sum(getattr(c, "token_estimate", 0) for c in chunks))

    with st.expander(f"Preview chunks ({min(3, len(chunks))} of {len(chunks)})"):
        for c in chunks[:3]:
            st.markdown(f"**{getattr(c, 'source_name', '?')}** — *{getattr(c, 'section_heading', '') or 'no heading'}*")
            preview = getattr(c, "text", "")[:300]
            st.code(preview + ("…" if len(getattr(c, "text", "")) > 300 else ""))

    st.divider()

    _key = api_key or os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")

    if p.get("questions"):
        qs = p["questions"]
        cats = {}
        for q in qs:
            cats[q.category] = cats.get(q.category, 0) + 1

        st.success(f"{len(qs)} questions ready")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("in_scope",    cats.get("in_scope", 0))
        c2.metric("out_of_scope", cats.get("out_of_scope", 0))
        c3.metric("adversarial", cats.get("adversarial", 0))
        c4.metric("edge_case",   cats.get("edge_case", 0))

        with st.expander(f"Preview questions ({min(8, len(qs))} of {len(qs)})"):
            for q in qs[:8]:
                badge = _CAT_BADGE.get(q.category, "⚪")
                st.markdown(f"{badge} **[{q.category} / {q.language}]** {q.text}")
                if q.ground_truth:
                    st.caption(f"Expected: {q.ground_truth[:120]}")

        # ── Edit / Add toggle ─────────────────────────────────────────────────
        run_key = p.get("run_id", "draft")
        edit_open_key = f"q_edit_open_{run_key}"
        if edit_open_key not in st.session_state:
            st.session_state[edit_open_key] = False

        col_edit_btn, _ = st.columns([2, 5])
        with col_edit_btn:
            toggle_label = "Close editor" if st.session_state[edit_open_key] else "Edit / Add Questions"
            if st.button(toggle_label, key=f"q_edit_toggle_{run_key}"):
                st.session_state[edit_open_key] = not st.session_state[edit_open_key]
                st.rerun()

        if st.session_state[edit_open_key]:
            st.divider()
            _render_question_editor(p)
            st.divider()

        # ── Navigation ────────────────────────────────────────────────────────
        col_regen, col_back2, col_next = st.columns([2, 1, 2])
        with col_regen:
            if st.button("Regenerate questions"):
                p["questions"] = []
                # Clear any pending edit state for this run
                run_key2 = p.get("run_id", "draft")
                for k in (f"q_edit_{run_key2}", f"q_edit_open_{run_key2}"):
                    if k in st.session_state:
                        del st.session_state[k]
                st.rerun()
        with col_back2:
            if st.button("← Back", key="back_step3b", use_container_width=True):
                p["step"] = 2
                st.rerun()
        with col_next:
            if st.button("Evaluate Bot →", type="primary"):
                p["step"] = 4
                st.rerun()
    else:
        _slider_max = max(1, min(len(chunks), 10))
        if _slider_max > 1:
            max_chunks = st.slider(
                "Chunks to generate questions from",
                min_value=1,
                max_value=_slider_max,
                value=min(len(chunks), 3),
                help="~4 questions per chunk. Keep low (3–5) for a fast demo run; raise for fuller coverage.",
            )
        else:
            max_chunks = 1
            st.info(f"1 chunk available — will generate ~4 questions from it.")
        est_q = max_chunks * 4
        est_min_lo = max(1, est_q * 8 // 60)
        est_min_hi = max(2, est_q * 15 // 60)
        st.caption(f"~{est_q} questions · estimated eval time {est_min_lo}–{est_min_hi} min (Groq) / {est_min_hi * 3}–{est_min_hi * 5} min (Anthropic/OpenAI)")

        col_b2, col_gen = st.columns([1, 3])
        with col_b2:
            _pipeline_nav(p, back_step=2)
        with col_gen:
            if st.button("Generate Questions with LLM →", type="primary", disabled=not _key,
                         key="step3_gen"):
                import uuid as _uuid
                run_id = str(_uuid.uuid4())[:8]
                p["run_id"] = run_id

                with st.status("Generating questions from knowledge chunks…", expanded=True) as status:
                    from goveval.questions.generator import generate_from_chunks
                    llm = _make_pipeline_llm_client(p, fallback_key=_key)
                    st.write(f"Calling LLM for up to {max_chunks} chunks (~{max_chunks * 4} questions)…")
                    questions, gen_errors = generate_from_chunks(chunks, run_id, llm, max_chunks=max_chunks)
                    p["questions"] = questions
                    state = "complete" if questions else "error"
                    status.update(label=f"Generated {len(questions)} questions", state=state)

                if gen_errors:
                    for err in gen_errors:
                        st.warning(f"⚠ {err}")
                if gen_errors and not questions:
                    st.error("Generation failed for all chunks.")
                elif not questions:
                    st.error("No questions returned — the LLM produced no valid output.")
                else:
                    st.rerun()


def _step4_evaluate(p: dict, api_key: str, db_path: str) -> None:
    import os
    st.markdown("### Step 4 — Run Evaluation")
    st.caption(
        "IterEval now probes the bot with all generated questions, then scores each response "
        "across 7 metrics using Claude as a judge: "
        "hallucination, refusal precision/recall, faithfulness, Singlish gap, calibration, and transparency."
    )
    st.divider()

    questions = p.get("questions", [])
    chunks = p.get("chunks", [])
    _key = api_key or os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")

    cats = {}
    for q in questions:
        cats[q.category] = cats.get(q.category, 0) + 1

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Bot", p.get("bot_name", "—"))
    c2.metric("Questions", len(questions))
    c3.metric("KB Chunks", len(chunks))
    c4.metric("Est. time", f"~{max(2, len(questions) * 15 // 60)}–{max(3, len(questions) * 20 // 60)} min")

    st.markdown(
        "**Pipeline that will run:**  \n"
        "1. Probe bot with all questions → collect responses  \n"
        "2. Score each response: Hallucination · Refusal · Faithfulness · Singlish · Calibration · Transparency  \n"
        "3. Aggregate → Risk Tier (RED / AMBER / GREEN)  \n"
        "4. Save results to database"
    )

    col_b, col_run = st.columns([1, 3])
    with col_b:
        _pipeline_nav(p, back_step=3)
    with col_run:
        if st.button("▶ Run Evaluation", type="primary", disabled=not _key,
                     key="step4_run"):
            _run_full_pipeline(p, _key, db_path)



def _run_full_pipeline(p: dict, api_key: str, db_path: str) -> None:
    import uuid as _uuid

    from goveval.storage.db import DB
    from goveval.prober.bot_prober import probe_all
    from goveval.eval.engine import run_eval
    from goveval.config.loader import (
        GovEvalConfig, TargetConfig, KnowledgeBaseConfig,
        LLMConfig, EvalConfig, StorageConfig,
    )

    llm = _make_pipeline_llm_client(p, fallback_key=api_key)

    run_id = p.get("run_id") or str(_uuid.uuid4())[:8]
    questions = p["questions"]
    chunks = p.get("chunks", [])

    cfg = GovEvalConfig(
        target=TargetConfig(name=p["bot_name"], endpoint=p.get("bot_endpoint", ""),
                            type=p["bot_type"] if p["bot_type"] != "mock" else "local"),
        knowledge_base=KnowledgeBaseConfig(mode="connect"),
        llm=LLMConfig(provider=llm.provider, model=llm.model, api_key_env=""),
        eval=EvalConfig(question_bank_size=len(questions), held_out_size=0, human_label_sample=0,
                        iterations=1, improvement_threshold=0.02, singlish=True,
                        rate_limit_delay=0.0 if p["bot_type"] == "mock" else 0.3),
        storage=StorageConfig(db_path=db_path, results_dir="results"),
    )

    db = DB(db_path)
    db.create_run(run_id, cfg.target.name, {
        "model": llm.model,
        "bot_type": p["bot_type"],
        "bot_endpoint": p.get("bot_endpoint", ""),
    })
    db.save_questions([
        {"question_id": q.question_id, "run_id": q.run_id, "category": q.category,
         "language": q.language, "text": q.text, "ground_truth": q.ground_truth or "",
         "gt_source": q.gt_source or "", "is_held_out": False}
        for q in questions
    ])

    kb = _SimpleKB(chunks) if chunks else _SimpleKB([])

    local_fn = None
    if p["bot_type"] == "mock":
        import sys as _sys, os as _os
        _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "..", "demo"))
        from mock_bot import mock_bot as _mock_bot
        local_fn = _mock_bot

    with st.status(f"Evaluating {p['bot_name']}  ·  run_id = {run_id}", expanded=True) as status:
        st.write(f"Step 1/3 — Probing {p['bot_name']} with {len(questions)} questions…")
        responses = probe_all(questions, cfg, run_id, iteration=1, db=db, local_fn=local_fn)

        st.write(f"Step 2/3 — Scoring {len(responses)} responses across 7 metrics (LLM judge)…")
        result = run_eval(
            run_id=run_id, iteration=1, questions=questions,
            responses=responses, kb=kb, llm_client=llm, db=db,
        )

        st.write("Step 3/3 — Saving results to database…")
        db.complete_run(run_id)
        status.update(label=f"Complete — Risk Tier: {result.risk_tier}  ·  {run_id}", state="complete")

    p["result"] = result
    p["run_id"] = run_id
    p["step"] = 5
    st.rerun()


def _step5_results(p: dict) -> None:
    result = p["result"]
    st.markdown("### Step 5 — Results")

    st.success(f"Evaluation complete for **{p['bot_name']}**  ·  run_id: `{p['run_id']}`")

    col_tier, col_metrics = st.columns([1, 3])
    with col_tier:
        _section("🏁", "Risk Tier")
        st.markdown(_tier_html(result.risk_tier), unsafe_allow_html=True)
    with col_metrics:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Hallucination", f"{result.hallucination_rate:.1%}")
        m2.metric("Refusal Recall", f"{result.refusal_recall:.1%}")
        m3.metric("Faithfulness", f"{result.faithfulness_avg:.2f}/5")
        m4.metric("Transparency", f"{result.transparency_avg:.1%}")

    if result.risk_reasons:
        st.divider()
        for r in result.risk_reasons:
            st.warning(f"⚠ {r}")

    st.divider()
    _section("➡️", "What's Next")

    tier = result.risk_tier
    if tier in ("RED", "AMBER"):
        st.markdown(
            "**Your bot has failures to diagnose and fix. Here's the path:**"
        )
        st.markdown(
            '<div style="background:#fef9c3;border-left:4px solid #eab308;'
            'padding:12px 16px;border-radius:0 6px 6px 0;margin-bottom:10px">'
            '<strong>1. Go to the Failures tab</strong> — '
            'select this run from the sidebar, then click '
            '"Analyze Failure Patterns" to cluster failures by root cause.'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="background:#fef9c3;border-left:4px solid #eab308;'
            'padding:12px 16px;border-radius:0 6px 6px 0;margin-bottom:10px">'
            '<strong>2. Click "Generate Improvement Hypotheses"</strong> — '
            'the LLM diagnoses each cluster: missing KB content, wrong prompt instruction, '
            'or retrieval parameter issue.'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="background:#fef9c3;border-left:4px solid #eab308;'
            'padding:12px 16px;border-radius:0 6px 6px 0;margin-bottom:10px">'
            '<strong>3. Generate your fix</strong> — '
            '"Generate prompt rewrite" for WRONG_PROMPT hypotheses (shows diff + expected improvement), '
            'or "Generate 20 training pairs" for Singlish/KB gaps (download JSONL/CSV).'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="background:#fef9c3;border-left:4px solid #eab308;'
            'padding:12px 16px;border-radius:0 6px 6px 0;margin-bottom:10px">'
            '<strong>4. Apply the fix and re-evaluate</strong> — '
            'come back to Run Eval, run a new evaluation, then compare scores in the Iterations tab.'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.success(
            "All metrics are within acceptable thresholds. "
            "Consider checking the **Failures tab** to see if any marginal cases exist, "
            "or explore the **Questions & Verdicts tab** for per-question detail."
        )

    st.info(
        "Results saved to the database. "
        "Select this run (`" + p.get("run_id", "") + "`) from the sidebar dropdown to view it in any tab."
    )

    if st.button("Run Another Evaluation", type="secondary"):
        del st.session_state["pipeline"]
        st.rerun()


def render_run_eval(db_path: str, api_key: str = "") -> None:
    """Run Eval page: 5-step pipeline wizard for evaluating any gov AI bot."""
    import os

    if "pipeline" not in st.session_state:
        st.session_state["pipeline"] = {
            "step": 1,
            "bot_name": "gov-bot",
            "bot_type": "mock",
            "bot_endpoint": "",
            "source_mode": "mock",
            "source_urls": "",
            "source_text": "",
            "source_name": "Knowledge Source",
            "scrape_depth": 0,
            "chunks": [],
            "questions": [],
            "run_id": None,
            "result": None,
            "llm_provider": "anthropic",
            "llm_model": "claude-sonnet-4-6",
            "llm_api_key": "",
        }

    p = st.session_state["pipeline"]
    _key = p.get("llm_api_key") or api_key or os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")

    # Show quick-start tip only on step 1 when no key is set yet
    if p["step"] == 1 and not _key:
        st.info(
            "**Quick start:** Use the mock bot + mock KB to see IterEval in action without a live chatbot URL.  \n"
            "An LLM API key is required for question generation and scoring. "
            "Groq (console.groq.com) or Anthropic (console.anthropic.com) — enter it in Step 1."
        )

    _pipeline_progress(p["step"])
    st.divider()

    step = p["step"]
    if step == 1:
        _step1_configure(p, _key)
    elif step == 2:
        _step2_sources(p)
    elif step == 3:
        _step3_questions(p, _key)
    elif step == 4:
        _step4_evaluate(p, _key, db_path)
    else:
        _step5_results(p)


# ── Entry point ───────────────────────────────────────────────────────────────

_GUIDE_CSS = """
<style>
.guide-step {
    background: #f0f9ff;
    border-left: 4px solid #0ea5e9;
    padding: 10px 16px;
    margin-bottom: 8px;
    border-radius: 0 6px 6px 0;
    font-size: 0.9rem;
}
.guide-step strong { color: #0369a1; }
.guide-arrow {
    text-align: center;
    color: #94a3b8;
    font-size: 1.2rem;
    margin: 4px 0;
}
</style>
"""


def _render_guide(db_exists: bool) -> None:
    """Full-flow guide — collapsed once there are results, expanded for first-time users."""
    st.markdown(_GUIDE_CSS, unsafe_allow_html=True)

    with st.expander(
        "How to use IterEval — full eval + fix flow  (click to expand)",
        expanded=not db_exists,
    ):
        st.markdown(
            "IterEval's core innovation is the **fix loop** — most eval tools stop at a score. "
            "This platform goes further: evaluate → diagnose → generate concrete fixes → re-evaluate.\n"
        )

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("#### Part 1 — Run the Evaluation")
            st.markdown(
                '<div class="guide-step">'
                '<strong>Step 1 — Configure Bot + LLM</strong><br>'
                'Choose the <em>mock bot</em> (no URL needed, 2 seeded hallucinations) '
                'or paste your own bot\'s API endpoint. '
                'Select your LLM judge: Groq (Llama) for high-throughput runs or when target bot is Claude; Anthropic (Claude) for highest accuracy on nuanced policy text.'
                '</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="guide-arrow">↓</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="guide-step">'
                '<strong>Step 2 — Knowledge Sources</strong><br>'
                'Use the built-in demo KB (CPF, HDB, Baby Bonus, CDC Voucher facts) '
                'or scrape your own URLs. IterEval uses this to generate questions '
                'and judge whether answers are grounded.'
                '</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="guide-arrow">↓</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="guide-step">'
                '<strong>Step 3 — Generate Questions</strong><br>'
                'The LLM reads KB chunks and generates 4 types of questions: '
                'formal English, Singlish variants, out-of-scope (should refuse), '
                'and adversarial (wrong premise to correct).'
                '</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="guide-arrow">↓</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="guide-step">'
                '<strong>Step 4 — Evaluate</strong><br>'
                'IterEval probes the bot with all questions and scores each response '
                'across 7 metrics. The LLM judge explains every verdict — not just a score.'
                '</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="guide-arrow">↓</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="guide-step">'
                '<strong>Step 5 — Results</strong><br>'
                'See the risk tier (RED/AMBER/GREEN) and all 7 metric scores. '
                'Results are saved to the database — select the run from the sidebar.'
                '</div>',
                unsafe_allow_html=True,
            )

        with col_right:
            st.markdown("#### Part 2 — Diagnose + Fix  *(Failures tab)*")
            st.markdown(
                '<div class="guide-step">'
                '<strong>Analyze Failure Patterns</strong><br>'
                'Clusters failing questions using sentence embeddings + KMeans. '
                'The LLM labels each cluster with a human-readable root cause. '
                'Requires an API key.'
                '</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="guide-arrow">↓</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="guide-step">'
                '<strong>Generate Improvement Hypotheses</strong><br>'
                'For each failure cluster the LLM diagnoses: is this a missing KB document, '
                'a wrong prompt instruction, or a retrieval parameter issue? '
                'Each hypothesis has an estimated impact and a specific proposed fix.'
                '</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="guide-arrow">↓</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="guide-step">'
                '<strong>Path A — Generate Prompt Rewrite</strong><br>'
                'For WRONG_PROMPT hypotheses: paste your current system prompt, '
                'click "Generate prompt rewrite." See the diff, expected metric improvements, '
                'and regression risk. Download the new prompt JSON.'
                '</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="guide-arrow">↓</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="guide-step">'
                '<strong>Path B — Generate Training Pairs</strong><br>'
                'Click "Generate 20 training pairs." Get (question, ideal_response) pairs '
                'grounded in your KB — Singlish variants, adversarial cases, edge conditions. '
                'Download as JSONL or CSV for few-shot injection or fine-tuning.'
                '</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="guide-arrow">↓</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="guide-step">'
                '<strong>Close the Loop — Re-evaluate</strong><br>'
                'Apply the prompt fix to your bot. '
                'Go back to Run Eval and run another evaluation. '
                'Compare before/after scores in the Iterations tab.'
                '</div>',
                unsafe_allow_html=True,
            )

        st.divider()
        st.caption(
            "Demo tip: start with **Run Eval → mock bot → mock KB → 5 chunks → Groq or Anthropic key**. "
            "The mock bot has 2 seeded hallucinations so the eval will show AMBER or RED immediately, "
            "giving you real failures to work with in the Failures tab."
        )


def render_judge_validation(db, run_id: str, api_key: str = "", model: str = "") -> None:
    """
    Judge Validation tab — human-in-the-loop Cohen's Kappa workflow.

    Step 1: Show N sample (question, response) pairs from the selected run.
    Step 2: Human labels each as hallucination (1) or clean (0).
    Step 3: "Compute Kappa" runs the LLM judge on the same pairs.
    Step 4: Display kappa, confusion matrix, reliability tier, recommendation.

    Blocks loop use if kappa < 0.6. Offers a JSON download of the audit report.
    """
    import json as _json

    _section("🔬", "Judge Reliability Validation")
    st.markdown(
        "Before trusting the automated eval loop, verify that the LLM judge agrees with "
        "a human domain expert. Label a sample of responses below, then click "
        "**Compute Kappa** to measure inter-rater reliability.  \n"
        "**Required threshold:** κ ≥ 0.60 (moderate) · **Recommended:** κ ≥ 0.80 (strong)"
    )

    if not api_key:
        st.info("Enter an API key in the sidebar to run judge validation.")
        return

    verdicts = _get_question_verdicts(db, run_id)
    if not verdicts:
        st.info("No verdict data found for this run.")
        return

    # Build sample — limit to 20 pairs for labeling tractability
    all_pairs = [
        {
            "question_id": v["question_id"],
            "question_text": v.get("question_text") or "",
            "response_text": v.get("response_text") or "",
            "chunks": [],
        }
        for v in verdicts
        if v.get("question_text") and v.get("response_text")
    ]

    sample_key = f"jv_sample_{run_id}"
    label_key  = f"jv_labels_{run_id}"
    result_key = f"jv_result_{run_id}"

    if sample_key not in st.session_state:
        import random
        # Stratified sample: include all flagged hallucinations first, fill rest with clean
        flagged = [
            v for v in verdicts
            if v.get("question_text") and v.get("response_text")
            and (v.get("detail") or {}).get("hallucination_rate", 0) > 0
        ]
        clean = [
            v for v in verdicts
            if v.get("question_text") and v.get("response_text")
            and (v.get("detail") or {}).get("hallucination_rate", 0) == 0
        ]
        def _to_pair(v):
            return {
                "question_id": v["question_id"],
                "question_text": v.get("question_text") or "",
                "response_text": v.get("response_text") or "",
                "chunks": [],
            }
        flagged_pairs = [_to_pair(v) for v in flagged]
        clean_pairs   = [_to_pair(v) for v in clean]
        random.shuffle(clean_pairs)
        sample = (flagged_pairs + clean_pairs)[:20]
        if not sample:
            sample = all_pairs[:20]
        st.session_state[sample_key] = sample
        st.session_state[label_key]  = {}

    sample = st.session_state[sample_key]
    labels: dict = st.session_state[label_key]

    st.divider()
    _section("🏷️", "Step 1 — Label Sample Responses")
    n_flagged = sum(1 for p in sample if any(
        v.get("detail", {}).get("hallucination_rate", 0) > 0
        for v in verdicts if v["question_id"] == p["question_id"]
    ))
    st.caption(
        f"Labeling {len(sample)} responses ({n_flagged} judge-flagged hallucinations, "
        f"{len(sample) - n_flagged} clean). "
        "For each, read the question and bot response "
        "and decide: does the response make any factual claim that is **not supported** "
        "by what you know of the policy?"
    )

    if st.button("Reset sample (pick new 20)", key="jv_reset"):
        del st.session_state[sample_key]
        if label_key in st.session_state:
            del st.session_state[label_key]
        if result_key in st.session_state:
            del st.session_state[result_key]
        st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    for i, pair in enumerate(sample):
        qid = pair["question_id"]
        current = labels.get(qid)
        icon = "🔴" if current == 1 else ("🟢" if current == 0 else "⚪")
        status_text = "Hallucination" if current == 1 else ("Clean" if current == 0 else "Not labeled")

        with st.expander(
            f"{icon} **{qid}** — {status_text} — {pair['question_text'][:70]}…",
            expanded=(current is None),
        ):
            col_q, col_r = st.columns(2)
            with col_q:
                st.markdown("**Question**")
                st.info(pair["question_text"])
            with col_r:
                st.markdown("**Bot Response**")
                st.success(pair["response_text"])

            col_h, col_c, col_skip = st.columns(3)
            with col_h:
                if st.button(
                    "🔴 Hallucination",
                    key=f"jv_hall_{qid}",
                    type="primary" if current == 1 else "secondary",
                ):
                    st.session_state[label_key][qid] = 1
                    if result_key in st.session_state:
                        del st.session_state[result_key]
                    st.rerun()
            with col_c:
                if st.button(
                    "🟢 Clean",
                    key=f"jv_clean_{qid}",
                    type="primary" if current == 0 else "secondary",
                ):
                    st.session_state[label_key][qid] = 0
                    if result_key in st.session_state:
                        del st.session_state[result_key]
                    st.rerun()
            with col_skip:
                if current is not None and st.button("Clear", key=f"jv_clr_{qid}"):
                    del st.session_state[label_key][qid]
                    if result_key in st.session_state:
                        del st.session_state[result_key]
                    st.rerun()

    labeled_count = len(labels)
    total = len(sample)
    st.progress(labeled_count / total if total else 0,
                text=f"{labeled_count} / {total} labeled")

    if labeled_count < total:
        st.caption(f"Label all {total} responses to enable kappa computation.")

    # Step 2: Compute Kappa
    st.divider()
    _section("📐", "Step 2 — Compute Cohen's Kappa")

    if result_key not in st.session_state:
        can_compute = (labeled_count == total)
        if st.button(
            "Compute Kappa",
            type="primary",
            disabled=not can_compute,
            key="jv_compute",
        ):
            with st.status("Running LLM judge on sample…", expanded=True) as status:
                try:
                    from goveval.eval.judge_validator import validate_judge
                    llm = _client_from_key(api_key, model)

                    ordered_sample = [p for p in sample if p["question_id"] in labels]
                    human_labels_list = [labels[p["question_id"]] for p in ordered_sample]

                    st.write(f"Running hallucination judge on {len(ordered_sample)} responses…")
                    report = validate_judge(ordered_sample, human_labels_list, llm)
                    st.session_state[result_key] = report
                    status.update(
                        label=f"Done — overall reliability: {report.overall_reliability} "
                              f"(κ = {report.per_metric[0].kappa:.3f})",
                        state="complete",
                    )
                except Exception as e:
                    status.update(label=f"Failed: {e}", state="error")
                    st.error(str(e))
            st.rerun()

    if result_key in st.session_state:
        report = st.session_state[result_key]
        kr = report.per_metric[0]  # hallucination is always first

        # Top result banner
        _KAPPA_STYLE = {
            "HIGH":     ("#f0fdf4", "#86efac", "#166534"),
            "MODERATE": ("#fffbeb", "#fcd34d", "#92400e"),
            "LOW":      ("#fef2f2", "#fca5a5", "#991b1b"),
        }
        bg, border, fg = _KAPPA_STYLE.get(kr.reliability, _KAPPA_STYLE["LOW"])
        st.markdown(
            f'<div style="background:{bg};border:1px solid {border};border-radius:8px;'
            f'padding:16px 20px;margin-bottom:12px">'
            f'<div style="font-size:1.5rem;font-weight:700;color:{fg}">'
            f'κ = {kr.kappa:.3f} — {kr.reliability} reliability</div>'
            f'<div style="color:{fg};margin-top:4px">{report.recommendation}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if not report.passed:
            st.error(
                "**Loop blocked.** Judge reliability does not meet the κ ≥ 0.60 threshold. "
                "Do not run the automated improvement loop until the judge prompt is revised "
                "and this check passes."
            )
        else:
            st.success("Judge reliability verified. The automated eval loop may proceed.")

        # Detail metrics
        col_k, col_a, col_n = st.columns(3)
        col_k.metric("Cohen's κ", f"{kr.kappa:.4f}", help="1.0 = perfect agreement; 0 = chance-level")
        col_a.metric("Agreement rate", f"{kr.agreement_rate:.1%}")
        col_n.metric("Sample size", kr.n_samples)

        # Confusion matrix
        st.divider()
        _section("📊", "Confusion Matrix")
        st.caption("Rows = human labels · Columns = LLM judge labels")
        import pandas as pd
        cm = kr.confusion_matrix
        cm_df = pd.DataFrame(
            cm,
            index=["Human: Clean (0)", "Human: Hallucination (1)"],
            columns=["Judge: Clean (0)", "Judge: Hallucination (1)"],
        )
        st.dataframe(cm_df, width="content")

        tn, fp = cm[0]
        fn, tp = cm[1]
        col_tp, col_tn, col_fp, col_fn = st.columns(4)
        col_tp.metric("True Positives", tp, help="Both say hallucination — agreement on failures")
        col_tn.metric("True Negatives", tn, help="Both say clean — agreement on passes")
        col_fp.metric("False Positives", fp, help="Judge says hallucination, human says clean — over-flagging")
        col_fn.metric("False Negatives", fn, help="Judge says clean, human says hallucination — missed failures")

        # Threshold reference
        st.divider()
        _section("📏", "Threshold Reference")
        tbl = {
            "Threshold": ["κ ≥ 0.80 (HIGH)", "κ ≥ 0.60 (MODERATE)", "κ < 0.60 (LOW)"],
            "Meaning": [
                "Strong agreement — judge is highly trustworthy",
                "Moderate agreement — loop may proceed, monitor results",
                "Poor agreement — loop must not run; revise judge prompt",
            ],
            "Status": [
                "PASS" if kr.kappa >= 0.8 else "—",
                "PASS" if kr.kappa >= 0.6 else "FAIL",
                "—"   if kr.kappa >= 0.6 else "TRIGGERED",
            ],
        }
        st.dataframe(pd.DataFrame(tbl), width="stretch", hide_index=True)

        # Download
        st.divider()
        from goveval.eval.judge_validator import save_validation_report
        import io, json as _json2

        def _to_native(obj):
            if hasattr(obj, "item"):
                return obj.item()
            if isinstance(obj, dict):
                return {k: _to_native(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_to_native(v) for v in obj]
            return obj

        report_data = _to_native({
            "overall_reliability": report.overall_reliability,
            "passed": report.passed,
            "recommendation": report.recommendation,
            "per_metric": [
                {
                    "metric": k.metric, "kappa": k.kappa,
                    "agreement_rate": k.agreement_rate, "n_samples": k.n_samples,
                    "confusion_matrix": k.confusion_matrix, "reliability": k.reliability,
                    "human_labels": k.human_labels, "judge_labels": k.judge_labels,
                }
                for k in report.per_metric
            ],
        })
        st.download_button(
            "Download validation report (JSON)",
            data=_json2.dumps(report_data, indent=2),
            file_name=f"judge_validation_{run_id}.json",
            mime="application/json",
            key="jv_dl",
        )


def run_dashboard(db_path: str = "goveval_test.db", report_path: Optional[str] = None, api_key: str = "", model: str = "") -> None:
    """
    Main dashboard entry point.
    Called by ui/app.py. Loads DB, renders sidebar run selector + 6 page tabs.
    """
    from goveval.eval.engine import compute_risk_tier

    try:
        db = _get_db(db_path)
        db_exists = True
    except Exception:
        db = None
        db_exists = False

    _render_guide(db_exists)

    # Always show Run Eval tab even if DB doesn't exist yet
    tab_overview, tab_metrics, tab_failures, tab_iterations, tab_questions, tab_validation, tab_run = st.tabs(
        ["Overview", "Metrics", "Failures", "Iterations", "Questions & Verdicts", "Judge Validation", "Run Eval"]
    )

    with tab_run:
        render_run_eval(db_path, api_key=api_key)

    if not db_exists:
        for tab in (tab_overview, tab_metrics, tab_failures, tab_iterations, tab_questions, tab_validation):
            with tab:
                st.info(
                    f"Could not connect to database `{db_path}`.  \n"
                    "Check that PostgreSQL is running and the DSN in the sidebar is correct."
                )
        return

    runs = db.get_runs()

    if not runs:
        for tab in (tab_overview, tab_metrics, tab_failures, tab_iterations, tab_questions, tab_validation):
            with tab:
                st.info("No eval runs yet. Go to the **Run Eval** tab to run your first evaluation.")
        return

    # Sidebar: run selector
    run_labels = {
        f"{r['run_id']}  •  {r['target_name']}  •  {r['created_at'][:10]}  [{r['status'].upper()}]": r
        for r in runs
    }
    selected_label = st.sidebar.selectbox("Select Run", list(run_labels.keys()))
    run_meta = run_labels[selected_label]
    run_id = run_meta["run_id"]

    # Sidebar: delete runs
    with st.sidebar.expander("🗑 Manage Runs"):
        to_delete = st.multiselect(
            "Select runs to delete",
            options=list(run_labels.keys()),
            format_func=lambda x: x,
            key="runs_to_delete",
        )
        if to_delete:
            if st.button("Delete Selected", type="primary", key="delete_runs_btn"):
                for label in to_delete:
                    rid = run_labels[label]["run_id"]
                    db.delete_run(rid)
                st.success(f"Deleted {len(to_delete)} run(s). Refreshing…")
                st.rerun()

    # Load metrics
    iterations = db.get_all_iteration_metrics(run_id)

    if not iterations:
        for tab in (tab_overview, tab_metrics, tab_failures, tab_iterations, tab_questions):
            with tab:
                st.warning(f"Run `{run_id}` has no saved metrics yet. The eval may still be running.")
        return

    latest_metrics = {k: v for k, v in iterations[-1].items() if k != "iteration"}
    tier, risk_reasons = compute_risk_tier(latest_metrics)
    verdicts = _get_question_verdicts(db, run_id)

    with tab_overview:
        render_overview(latest_metrics, tier, risk_reasons, run_meta, iterations=iterations)

    with tab_metrics:
        render_metrics(verdicts, latest_metrics)

    with tab_failures:
        render_failures(db, run_id, api_key=api_key, model=model)

    with tab_iterations:
        render_iterations(iterations, db=db, run_id=run_id, api_key=api_key, run_meta=run_meta, model=model)

    with tab_questions:
        render_questions(db, run_id)

    with tab_validation:
        render_judge_validation(db, run_id, api_key=api_key, model=model)
