"""
ui/app.py — IterEval Streamlit entry point.

Launch:
    streamlit run ui/app.py

Env vars:
    GOVEVAL_PG_DSN, ANTHROPIC_API_KEY, GROQ_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

st.set_page_config(
    page_title="IterEval",
    page_icon="🔁",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* ── Base & typography ────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI",
                 Roboto, sans-serif;
}
.block-container {
    padding-top: 1.25rem;
    padding-bottom: 3rem;
    max-width: 1280px;
}
h1 { font-size: 1.6rem !important; font-weight: 700; letter-spacing: -0.03em; }
h2 { font-size: 1.3rem !important; font-weight: 600; letter-spacing: -0.02em; }
h3 { font-size: 1.1rem !important; font-weight: 600; }
h4 { font-size: 0.9rem !important; font-weight: 600;
     text-transform: uppercase; letter-spacing: 0.06em; color: #64748b; }
hr  { border-color: #f1f5f9 !important; margin: 0.75rem 0 !important; }

/* ── Tabs ─────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    background: #f8fafc;
    border-radius: 10px;
    padding: 4px;
    border: 1px solid #e2e8f0;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 7px;
    padding: 7px 18px;
    font-weight: 500;
    font-size: 0.84rem;
    color: #64748b;
    background: transparent;
    border: none;
    white-space: nowrap;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #1e293b;
    background: rgba(255,255,255,0.7);
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    background: #ffffff;
    color: #1e293b;
    font-weight: 600;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
}
/* hide the underline bar Streamlit adds */
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }
.stTabs [data-baseweb="tab-border"]    { display: none !important; }

/* ── Sidebar ──────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #f8fafc;
    border-right: 1px solid #e2e8f0;
}
[data-testid="stSidebar"] .block-container {
    padding-top: 1.5rem;
}

/* ── Metric cards ─────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 14px 16px !important;
    transition: box-shadow 0.15s;
}
[data-testid="stMetric"]:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
[data-testid="stMetricValue"] {
    font-size: 1.55rem !important;
    font-weight: 700 !important;
    color: #1e293b;
    letter-spacing: -0.02em;
}
[data-testid="stMetricLabel"] {
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ── Buttons ──────────────────────────────────────────────────── */
.stButton > button {
    border-radius: 8px;
    font-weight: 500;
    font-size: 0.88rem;
    padding: 7px 18px;
    transition: all 0.15s;
    border: 1px solid #e2e8f0;
    color: #374151;
    background: white;
}
.stButton > button:hover {
    border-color: #cbd5e1;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    color: #1e293b;
}
.stButton > button[kind="primary"],
.stButton > button[data-testid$="primary"] {
    background: #2563eb;
    border-color: #2563eb;
    color: white;
    font-weight: 600;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid$="primary"]:hover {
    background: #1d4ed8;
    border-color: #1d4ed8;
}

/* ── Expanders ────────────────────────────────────────────────── */
div[data-testid="stExpander"] {
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
    margin-bottom: 8px;
    overflow: hidden;
    box-shadow: none !important;
}
div[data-testid="stExpander"] > details > summary {
    padding: 10px 16px;
    font-weight: 500;
    color: #374151;
    font-size: 0.9rem;
    background: #fafafa;
}
div[data-testid="stExpander"] > details > summary:hover {
    background: #f1f5f9;
}
div[data-testid="stExpander"] > details[open] > summary {
    border-bottom: 1px solid #f1f5f9;
}

/* ── Alerts (info / success / warning / error) ────────────────── */
[data-testid="stAlert"] {
    border-radius: 8px !important;
    border-left-width: 4px !important;
    font-size: 0.875rem;
}

/* ── DataFrames ───────────────────────────────────────────────── */
[data-testid="stDataFrame"] > div {
    border-radius: 8px;
    border: 1px solid #e2e8f0;
    overflow: hidden;
}

/* ── Code blocks ──────────────────────────────────────────────── */
.stCode > div, [data-testid="stCode"] > div {
    border-radius: 8px !important;
    font-size: 0.82rem;
}

/* ── Status widget ────────────────────────────────────────────── */
[data-testid="stStatusWidget"] {
    border-radius: 8px;
    border: 1px solid #e2e8f0;
}

/* ── Input fields ─────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    border-radius: 7px;
    font-size: 0.875rem;
}
[data-testid="stSelectbox"] > div > div {
    border-radius: 7px;
    font-size: 0.875rem;
}

/* ── Captions ─────────────────────────────────────────────────── */
[data-testid="stCaptionContainer"] {
    font-size: 0.8rem;
    color: #94a3b8;
}

/* ── Download button ──────────────────────────────────────────── */
.stDownloadButton > button {
    border-radius: 7px;
    font-size: 0.82rem;
    padding: 5px 14px;
    border: 1px solid #e2e8f0;
    background: white;
    color: #374151;
}
.stDownloadButton > button:hover {
    background: #f8fafc;
    border-color: #2563eb;
    color: #2563eb;
}

/* ── Custom component classes ─────────────────────────────────── */

/* Pipeline stepper */
.goveval-stepper {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 12px 0 8px;
    gap: 0;
    width: 100%;
}
.goveval-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    flex: 0 0 auto;
    min-width: 0;
}
.step-circle {
    width: 32px; height: 32px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.82rem; font-weight: 700;
    flex-shrink: 0;
}
.step-circle-done    { background: #dcfce7; color: #166534; border: 2px solid #86efac; }
.step-circle-active  { background: #2563eb; color: white;   border: 2px solid #2563eb;
                        box-shadow: 0 0 0 3px rgba(37,99,235,0.15); }
.step-circle-future  { background: #f1f5f9; color: #94a3b8; border: 2px solid #e2e8f0; }
.step-label {
    text-align: center;
    max-width: 80px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.step-title-done   { font-size: 0.75rem; font-weight: 500; color: #166534; }
.step-title-active { font-size: 0.75rem; font-weight: 700; color: #1e40af; }
.step-title-future { font-size: 0.75rem; font-weight: 400; color: #94a3b8; }
.step-sub { font-size: 0.68rem; color: #94a3b8; }
.step-connector {
    flex: 1;
    height: 2px;
    min-width: 16px;
    max-width: 60px;
    margin-bottom: 20px;
    border-radius: 1px;
}
.connector-done   { background: #86efac; }
.connector-active { background: linear-gradient(to right, #86efac, #e2e8f0); }
.connector-future { background: #e2e8f0; }

/* Risk badge */
.risk-badge {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 12px 20px;
    border-radius: 10px;
    border-width: 2px;
    border-style: solid;
    margin-bottom: 4px;
}
.risk-badge-label {
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: 0.02em;
}
.risk-badge-sub {
    font-size: 0.78rem;
    font-weight: 400;
    opacity: 0.8;
}

/* Section headers */
.goveval-section-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0.5rem 0 0.75rem;
    padding-bottom: 6px;
    border-bottom: 2px solid #f1f5f9;
}
.goveval-section-header .icon { font-size: 1rem; }
.goveval-section-header .title {
    font-size: 0.88rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: #475569;
}

/* Metric card (custom HTML) */
.ge-metric-card {
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 0;
    border-width: 1px;
    border-style: solid;
    height: 100%;
}
.ge-metric-label {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 4px;
}
.ge-metric-value {
    font-size: 1.55rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1.1;
    margin-bottom: 4px;
}
.ge-metric-note {
    font-size: 0.72rem;
    opacity: 0.75;
}

/* Failure/hypothesis cards */
.ge-cluster-card {
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 10px;
    border-left-width: 4px;
    border-left-style: solid;
    border-top: 1px solid #e2e8f0;
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #e2e8f0;
    background: white;
}
.ge-hyp-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    margin-bottom: 6px;
}
.ge-fix-diff {
    background: #0f172a;
    color: #e2e8f0;
    border-radius: 8px;
    padding: 14px 16px;
    font-family: "SF Mono", "Fira Code", monospace;
    font-size: 0.8rem;
    line-height: 1.6;
    white-space: pre-wrap;
    overflow-x: auto;
}
.ge-fix-diff .diff-add { color: #86efac; }
.ge-fix-diff .diff-rem { color: #fca5a5; }
.ge-fix-diff .diff-same { color: #94a3b8; }

/* Guide steps */
.guide-step {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #2563eb;
    padding: 10px 16px;
    margin-bottom: 8px;
    border-radius: 0 8px 8px 0;
    font-size: 0.875rem;
    line-height: 1.5;
}
.guide-step strong { color: #1e40af; display: block; margin-bottom: 3px; }
.guide-arrow { text-align: center; color: #cbd5e1; margin: 2px 0; font-size: 1rem; }

/* What's Next callouts */
.ge-next-step {
    background: #fffbeb;
    border-left: 4px solid #f59e0b;
    border-top: 1px solid #fde68a;
    border-right: 1px solid #fde68a;
    border-bottom: 1px solid #fde68a;
    padding: 12px 16px;
    border-radius: 0 8px 8px 0;
    margin-bottom: 10px;
    font-size: 0.875rem;
    line-height: 1.5;
}
.ge-next-step strong { color: #92400e; display: block; margin-bottom: 3px; }
.ge-next-step-green {
    background: #f0fdf4;
    border-left-color: #22c55e;
    border-top-color: #bbf7d0;
    border-right-color: #bbf7d0;
    border-bottom-color: #bbf7d0;
}
.ge-next-step-green strong { color: #166534; }

/* Failures flow banner */
.ge-flow-banner {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 8px;
    padding: 12px 18px;
    margin-bottom: 16px;
    font-size: 0.875rem;
}
.ge-flow-banner .flow-title { font-weight: 700; color: #1e40af; margin-bottom: 4px; }
.ge-flow-banner .flow-steps { color: #1d4ed8; font-weight: 500; }
.ge-flow-banner .flow-note  { font-size: 0.8rem; color: #64748b; margin-top: 6px; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.markdown("## IterEval")
st.sidebar.caption("Evaluate · Diagnose · Fix · Re-evaluate")
st.sidebar.divider()

db_path = st.sidebar.text_input(
    "PostgreSQL DSN",
    value=os.environ.get("GOVEVAL_PG_DSN", "postgresql://localhost/goveval"),
    help="PostgreSQL connection string, e.g. postgresql://user:pass@host/dbname",
)

st.sidebar.divider()
st.sidebar.markdown("**LLM API Key**")
st.sidebar.caption(
    "Groq (`gsk_...`): Llama — [console.groq.com](https://console.groq.com)  \n"
    "Anthropic (`sk-ant-...`): Claude — [console.anthropic.com](https://console.anthropic.com)  \n"
    "Gemini (`AIza...`): Gemini Flash/Pro — [aistudio.google.com](https://aistudio.google.com)  \n"
    "OpenAI (`sk-...`): GPT-4o — [platform.openai.com](https://platform.openai.com)"
)

_raw_key = (
    os.environ.get("ANTHROPIC_API_KEY", "")
    or os.environ.get("GROQ_API_KEY", "")
    or os.environ.get("GEMINI_API_KEY", "")
    or os.environ.get("OPENAI_API_KEY", "")
)
_api_key = st.sidebar.text_input(
    "API key",
    value=_raw_key,
    type="password",
    key="sidebar_api_key",
)

_BADGE = (
    '<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:6px;'
    'padding:6px 12px;font-size:0.8rem;color:#166534">{}</div>'
)
if _api_key:
    if _api_key.startswith("gsk_"):
        st.sidebar.markdown(_BADGE.format("✓ Groq — llama-3.3-70b-versatile"), unsafe_allow_html=True)
    elif _api_key.startswith("sk-ant-"):
        st.sidebar.markdown(_BADGE.format("✓ Anthropic — claude-sonnet-4-6"), unsafe_allow_html=True)
    elif _api_key.startswith("AIza"):
        st.sidebar.markdown(_BADGE.format("✓ Gemini — gemini-2.0-flash"), unsafe_allow_html=True)
    elif _api_key.startswith("sk-"):
        st.sidebar.markdown(_BADGE.format("✓ OpenAI — gpt-4o-mini"), unsafe_allow_html=True)
    else:
        st.sidebar.warning("Key prefix not recognised", icon="⚠")

st.sidebar.divider()
st.sidebar.markdown(
    '<div style="font-size:0.8rem;color:#64748b;line-height:1.7">'
    '<strong>Eval → Fix loop</strong><br>'
    '① Run Eval (5-step wizard)<br>'
    '② Failures → Analyze Patterns<br>'
    '③ Generate Hypotheses<br>'
    '④ Prompt Rewrite or Training Pairs<br>'
    '⑤ Re-evaluate → Iterations tab<br>'
    '⑥ Judge Validation → verify κ ≥ 0.6'
    '</div>',
    unsafe_allow_html=True,
)

# ── Main ──────────────────────────────────────────────────────────────────────

st.markdown(
    '<h1 style="margin-bottom:2px">IterEval</h1>'
    '<p style="color:#64748b;font-size:0.95rem;margin-top:0">'
    'Evaluate · Diagnose · Fix — closed-loop LLM evaluation for Singapore government chatbots'
    '</p>',
    unsafe_allow_html=True,
)

from goveval.report.dashboard import run_dashboard
run_dashboard(db_path=db_path, api_key=_api_key)
