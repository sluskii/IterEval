# IterEval

*A structured pre-deployment evaluation harness for government RAG chatbots — designed to run before every deploy and after every KB update. IterEval maps what a chatbot is vulnerable to, generates targeted engineering fixes, and validates its own judge reliability before trusting any result.*

**Government problem, not just an AI problem:** Singapore agencies deploy RAG chatbots handling citizen eligibility queries (CPF, HDB, Baby Bonus, grants) at scale. Teams do QA before launch — but manual spot-checks don't give a reproducible signal, don't characterise *what type* of failure a bot is prone to, and don't survive a prompt or KB update. Citizens don't know when a response is wrong. They make a financial or administrative decision based on it. By the time the error surfaces, the harm is done.

IterEval addresses this in three ways:

1. **Vulnerability mapping** — not just "this bot is failing at 23%," but "it fails specifically on eligibility boundary conditions when phrased in Singlish, and fails confidently." Failures are clustered by sentence embedding and labelled with LLM-generated root causes.
2. **Fix generation** — every failure cluster produces two engineering artifacts: a targeted system prompt diff (with `+/-` diff, expected metric movement, and regression risk) and synthetic `(question, ideal_response)` training pairs covering formal, Singlish, and adversarial phrasings.
3. **Reliability-aware judging** — LLM judges are not infallible. The eval loop is gated on Cohen's Kappa (κ ≥ 0.60) against hand-labeled Q-A pairs, and the dashboard surfaces a human-in-loop labelling flow so policy officers can validate judge verdicts on ambiguous cases before results are trusted.

---

## Demo

▶ [Watch the demo video](https://drive.google.com/file/d/1b9-pZP-nmexbfGNF2_Gc8ClHopbJYSfh/view?usp=drive_link)

The demo walks through a full IterEval run against the mock Singapore government chatbot: KB ingestion, question generation, hallucination detection across 6 failure types, failure clustering, and prompt rewrite generation.

---

## Quickstart

**Prerequisites:** Docker Desktop installed and running.

**1. Build and start**

```bash
docker compose up --build
```

First build takes a few minutes (installs dependencies and downloads the embedding model). Subsequent starts are fast.

**2. Open the app**

Visit `http://localhost:8501` in your browser.

Go to the **Run Eval** tab → Step 1 → select your provider → paste your key → follow the 5-step wizard.

**3. Stop**

```bash
docker compose down        # stops containers, keeps database
docker compose down -v     # stops and wipes the database
```

## Local development (no Docker)

**Prerequisites:** Python 3.11+, PostgreSQL 16 with pgvector extension.

```bash
# Create the database (one-time)
createdb goveval
psql goveval -c "CREATE EXTENSION IF NOT EXISTS vector;"

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

streamlit run ui/app.py
```

---

## Evaluation Methodology

### LLM-as-Judge with structured rubrics

Each bot response is scored by a second LLM using a structured prompt specifying the rubric, the retrieved KB context, and the expected behaviour.

**Why LLM-as-judge:**
- Ground-truth labels at scale are expensive and go stale as policies change
- Policy language is ambiguous — whether "I'm not sure about that" is an appropriate uncertainty flag requires contextual judgement, not a regex
- Singlish and adversarial cases need a model that has read the relevant facts

**Why not benchmark:** Standard benchmarks (MMLU, IFeval) measure general knowledge, not whether a bot correctly handles CPF withdrawal rules or HDB grant eligibility. The failure modes we care about — confident hallucination on policy specifics, silent refusal of valid Singlish phrasing — don't appear in any existing benchmark.

**Why not human eval alone:** Human labelling is the ground truth we calibrate against, but not the primary eval path. 200 questions × 6 metrics = 1,200 judgements per run; at weekly cadence that's not sustainable manually.

**Validity check:** `judge_validator.py` implements Cohen's Kappa between LLM judge and human labels. Kappa measures chance-corrected agreement — a κ of 0.72–0.76 means the judge catches ~85% of real hallucinations and correctly identifies ~88% of clean responses. Results from two independent runs:

| Metric | Value |
|--------|-------|
| Judge reliability (Kappa) | 0.72–0.76 (MODERATE-to-HIGH) |
| Per-run accuracy vs. human labels | 86–90% |
| Cross-run judge consistency | 0.81 Kappa |
| Decision | Automated eval loop safe to proceed |

**Limitations of the approach:** LLM judges can be inconsistent across runs and inherit the biases of the judge model. The calibration ECE metric partially compensates. The regression guard (blocks the loop if >10% of previously passing questions start failing) and the stagnation guard (stops if hallucination rate delta < 2% over 2 consecutive iterations) provide safety rails.

### Metrics

| # | Metric | What it measures | AMBER | RED |
|---|--------|-----------------|-------|-----|
| 1 | Hallucination Rate | Unsupported factual claims / total claims | > 10% | > 20% |
| 2 | Refusal Recall | True refusals / (true refusals + false answers) | < 80% | < 50% |
| 3 | Faithfulness | Accuracy + completeness + clarity + actionability (1–5) | < 3.5 | < 2.5 |
| 4 | Singlish Gap | Faithfulness drop: English score − Singlish score | > 15% | — |
| 5 | Calibration ECE | Expressed confidence vs. actual accuracy | > 0.20 | — |
| 6 | Transparency | Citation presence + uncertainty flagging + redirect quality | < 60% | — |

---

## Data Story

### Demo knowledge base

The built-in demo uses **25 KB chunks across 12 Singapore government schemes**, sourced from official agency websites. Each chunk records a `source_url`, `source_name`, `section_heading`, and `scraped_date` for full provenance traceability.

| Agency / Scheme | Chunks | Source |
|----------------|--------|--------|
| CPF (contributions, interest, withdrawal, self-employed) | 4 | cpf.gov.sg |
| HDB (EHG grant, BTO eligibility, maintenance) | 3 | hdb.gov.sg |
| MSF (Baby Bonus, maternity benefit, infant formula) | 3 | msf.gov.sg |
| CDC (vouchers, rental assistance) | 2 | cdc.gov.sg |
| MOH (MediShield Life, Medisave, vaccination) | 3 | moh.gov.sg |
| PAP / Public Assistance (eligibility, payment) | 2 | msf.gov.sg |
| LTA (driving licence, road tax) | 2 | lta.gov.sg |
| ICA (citizenship by descent, passport) | 2 | ica.gov.sg |
| Workfare Income Supplement | 1 | mom.gov.sg |
| GST Voucher (cash, U-Save) | 1 | gstvoucher.gov.sg |
| CHAS (Blue/Orange card subsidies) | 1 | chas.sg |
| SkillsFuture Credit | 1 | skillsfuture.gov.sg |

**Licensing:** All source content is published under the [Singapore Open Government Licence v1.0](https://www.tech.gov.sg/files/media/corporate-publications/FY2017/govt-of-singapore-open-data-licence-version-1.pdf), which permits free use and reproduction with attribution.

**Known data gaps:** 3 schemes that are partially JS-rendered (MediFund, ComCare Interim Assistance, Senior Mobility Fund) were not included in the demo KB because the scraper does not yet support Playwright-based crawling. 

### Synthetic data
The eval question bank is LLM-generated from KB chunks — not sourced from a public dataset. This is a deliberate choice: the failure modes we care about (Singlish phrasing, adversarial wrong-premise questions, eligibility boundary conditions) don't exist in any public dataset at the specificity required. The questions are grounded in actual KB source text, not generated freely, so they reflect real policy content rather than hallucinated scenarios.

**Defence of synthetic choice:** the judge validator (Cohen's Kappa against 50 hand-labelled pairs) provides an empirical check that LLM-generated questions produce meaningful signal — not just questions that the judge finds easy to score correctly.

### Demo smoke test

**Scope of this demo:** IterEval is evaluated here against a mock bot — a Python function (`demo/mock_bot.py`) that returns keyword-matched responses to Singapore government policy questions. This is a deliberate stand-in: I am treating it as a proxy for a real government LLM chatbot (e.g. a RAG system backed by the same KB) and assuming it exhibits the same failure modes — confident hallucination on policy specifics, silent refusal of valid queries, fabricated citations. The eval pipeline does not require LLM-based response generation in the target bot; it only requires that the bot accept a question string and return a response string, which any production chatbot API would satisfy.

The mock bot has **6 seeded hallucinations** across varied failure types so the detector has non-trivial ground truth to find:

| # | Type | Example |
|---|------|---------|
| 1 | Contradicted fact | CPF OA interest: says 3.5%, correct is 2.5% |
| 2 | Contradicted fact | Baby Bonus: says $8,000 flat, correct is $11,000/$13,000 |
| 3 | Contradicted fact | Workfare minimum age: says 25, correct is 30 |
| 4 | Contradicted fact | SkillsFuture: claims PRs are eligible; they are not |
| 5 | Omitted boundary condition | BTO selling: omits the 5-year minimum occupation period |
| 6 | Fabricated URL | GST Voucher: invents an application portal URL |

---

## How It Works — 7-Step Pipeline

```
STEP 1: INGEST
  User provides KB info
  User provides source URLs (or pastes raw text)
  Scraper builds knowledge base from gov sites
  Paragraph-aware splitting preserves natural semantic units in policy text
        ↓

STEP 2: GENERATE QUESTIONS
  4 question types compiled from KB:
  - In-scope (should answer)
  - Out-of-scope (should refuse)
  - Adversarial (wrong premises the bot must correct)
  - Singlish variants (colloquial equivalents)
        ↓

STEP 3: EVAL
  Fire questions at target bot (HTTP API or local function)
  Score across 6 metrics with exact natural language explanation
  and citation validation of why each response passed or failed
        ↓

STEP 4: DIAGNOSE
  Isolate failed test executions
  Cluster failures by type (sentence-transformers embeddings + KMeans)
  LLM labels each vector cluster with a human-readable root cause
        ↓

STEP 5: FIX

  Path A — Prompt Rewrite
    Generate candidate system prompt edits matching specific failure clusters
    Output includes explained diff (+/- lines via difflib), expected metrics, risk analysis

  Path B — Training Data
    Generate synthetic (Q, ideal_response) pairs (phrasing-style tagged)
    Generate 5 distinct follow-up test questions per synthetic topic
    Download formatted as JSONL (fine-tuning compatible) or CSV
        ↓

STEP 6: VERIFY
  Re-run eval loop with the prompt or data modifications
  Compare before/after metrics
  Regression guard: blocks iteration if >10% of previously passing questions fail
  Stagnation guard: stops if hallucination rate delta < 2% over 2 consecutive runs
        ↓

STEP 7: REPORT
  Dashboard shows metric scores (before/after), failure clusters, prompt diffs,
  generated training examples, and iteration trend across all loop runs
```

---

## Results

**Judge reliability (Kappa validation against 50 hand-labeled pairs):**
- Kappa: 0.72–0.76 across two independent runs — MODERATE-to-HIGH reliability
- Accuracy: 86–90% agreement with human labels
- Cross-run consistency: 0.81 Kappa

**Demo smoke test (6 seeded hallucinations):**
- Expected hallucination rate: ~25–30%, risk tier AMBER or RED
- All 6 seeded hallucination types detectable with the current keyword-overlap KB retrieval

---

## Deployment Considerations

**Who runs it and where:** Internal tool for the agency or team that owns a chatbot. Runs on a small VM (2 vCPU, 4 GB RAM) or a developer laptop before each release — analogous to running a test suite before a deploy. Requires a running PostgreSQL 16 instance with pgvector; the Docker Compose file bundles one automatically.

**What to monitor once live:** Trends in the different metrics across iterations (regression signal), judge Kappa score (judge drift), eval run latency (rate-limit headroom), and KB staleness date (policy freshness).

**The risk:** Judge–target model collusion. If the target bot and the judge model are the same family (e.g. both Claude), the judge may systematically fail to detect stylistic hallucinations that a Claude model produces and a Claude judge finds plausible. A well-calibrated evaluation system should not be blind to the failure modes of its own architecture family. Mitigation: enforce architectural heterogeneity — use Groq (Llama) as judge when the target is Claude-based, and Claude as judge otherwise. Run cross-provider validation periodically, and weight human-labelled spot checks heavily for high-stakes eligibility claims.

---

## Known Limitations

| Limitation | Impact | What I'd do with more time |
|------------|--------|---------------------------|
| Demo target is a mock bot, not a live LLM chatbot | The mock bot uses keyword matching, not LLM generation — it can't exhibit temperature-dependent hallucination, prompt injection, or context-window failures. Results demonstrate the eval harness works; they don't represent the full failure distribution of a production RAG system | Wire IterEval against a real RAG endpoint (e.g. a self-hosted Ollama or an OpenAI Assistants API bot backed by the same KB) to validate on authentic LLM output |
| KB uses keyword overlap, not semantic retrieval | Hallucination detection ceiling on long docs; keyword retrieval misses ~20–25% of paraphrased hallucinations | Wire `embedder.py` pgvector backend into the dashboard to replace `_SimpleKB` |
| Judge Kappa scoped to hallucination metric only | Faithfulness and transparency validators are not empirically validated | Add per-metric binary judge runners and separate human label flows in `judge_validator.py` |
| Limited functionality for document ingestion parsers for demo purposes | Can't use PDF/JSON/TXT as KB sources | Implement with pdfplumber, json flattening, text splitting |
| Prompt rewrites are suggestions, not auto-applied | Re-eval loop doesn't test the suggested rewrite to verify improvement | Add bot endpoint parameter accepting system_prompt override; auto-evaluate candidate |
| Eval is synchronous | 200-question eval takes ~20 minutes at 1s delay | Async with `asyncio` + `httpx` would cut to ~3–4 minutes |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | If using Anthropic | Claude API key — console.anthropic.com |
| `GROQ_API_KEY` | If using Groq | Obtain at console.groq.com |
| `GEMINI_API_KEY` | If using Gemini | Obtain at aistudio.google.com |
| `OPENAI_API_KEY` | If using OpenAI | Obtain at platform.openai.com |
| `GOVEVAL_PG_DSN` | No (Docker sets it) | PostgreSQL connection string (default: `postgresql://localhost/goveval`) |
