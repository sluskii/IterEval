# PROCESS.md — How IterEval Was Built

---

## Where I started

Building AI products is fast becoming a solved problem — Pair, Claude APIs, wrapped UIs. The harder question is what comes *after* everyone has deployed one.

The pace of AI rollout creates pressure on the QA layer. As chatbots ship faster and update more frequently — prompt changes, KB refreshes, model swaps — the question is whether manual spot-checks can keep up. They tend not to produce a reproducible signal, struggle to characterise *what type* of failure a bot is prone to, and often don't survive an update cycle intact. The gap I kept coming back to: there's no automated equivalent of re-running a test suite.

Consider a chatbot that states the CPF OA interest rate as 3.5% instead of 2.5%, or describes a housing grant without mentioning the citizenship prerequisite — a citizen makes a financial or administrative decision on wrong information, and by the time the error surfaces the harm is done. That's the kind of case IterEval is designed to catch before it reaches anyone.

I could have built something with cleaner, more definitive metrics — a classifier, a retrieval benchmark, something where "correct" is unambiguous. I chose this instead because the LLM evaluation space is genuinely unsettled. There's no consensus on how to do it well; the methodology is still being figured out. That ambiguity is the point — it's where novel work happens, and where getting something right actually matters.

The specific gap I focused on: most tools tell you a bot is failing — fewer tell you *what to change*, and most don't account for whether the judge itself is reliable. I used an LLM to evaluate whether another LLM is hallucinating, then used Cohen's Kappa against human labels to check whether the judge LLM is itself reliable. The layers of validation are what make the system trustworthy enough to use as a deployment gate rather than a vanity metric.

---

## The core reframe

Early versions stopped at "here's your score." A score answers the wrong question. The questions a team actually needs before deploying a government chatbot are: *what is this bot specifically vulnerable to?* and *what do I change to fix it?*

This led to four design commitments:

1. **Generate the evaluation set, not just run it.** The question bank is synthesised from KB chunks — covering in-scope, out-of-scope, adversarial, and Singlish variants. Existing benchmarks tend not to cover Singapore policy specifics at this granularity, so the eval set has to be built alongside the harness.

2. **Cluster failures, don't just count them.** KMeans on `all-MiniLM-L6-v2` embeddings + LLM root-cause labels turns a hallucination rate into: "Cluster 2: 7 failures, bot omits citizenship prerequisite on housing grants when question uses indirect phrasing." That's actionable, while a metric alone isn't.

3. **Generate fix artifacts, not just diagnoses.** Every failure cluster produces a targeted prompt rewrite (as a `+/-` diff with expected metric movement and regression risk) and synthetic `(question, ideal_response)` training pairs covering formal, Singlish, and adversarial phrasings.

4. **Validate the judge before trusting it.** LLM judges can be inconsistent and inherit model family bias. Rather than assuming the judge is reliable, I compute a score (Cohen's Kappa) that measures how much to trust it — by comparing its verdicts against hand-labeled Q-A pairs. The eval loop only proceeds if that score clears a minimum threshold (κ ≥ 0.60).

---

## Decisions, trade-offs, and what I'd change

**PostgreSQL + pgvector for semantic retrieval.** The embedder (`embed_and_store()`, IVFFlat cosine index) is fully implemented — but the dashboard currently still uses `_SimpleKB`, an inline keyword-overlap class, as a stand-in. It's sufficient for the demo but misses ~20–25% of paraphrased hallucinations that semantic retrieval would catch. Replacing `_SimpleKB` with the pgvector backend is the highest-priority remaining item.

**Kappa validation scoped to hallucination only.** The human-in-the-loop workflow works end-to-end for hallucination: a human reviewer labels responses, the LLM judge runs the same check, and Cohen's Kappa measures agreement. Faithfulness and transparency don't have corresponding binary judge runners or human labelling flows — extending Kappa to all metrics would require per-metric runners and separate label collection in the dashboard.

**KB-grounded training data.** The generation prompt explicitly forbids the LLM from fabricating policy facts not present in the provided KB chunks. Unconstrained generation would produce plausible-sounding but wrong training examples.

**Chunking.** The current chunker splits on paragraph boundaries, which works for the demo but doesn't account for cross-paragraph dependencies or section hierarchy. With more time I'd look at recursive splitting, semantic boundary detection, or layout-aware parsing for PDFs.

**Multi-model data generation.** Questions, ideal responses, and fix suggestions are currently generated by whichever LLM the user configures. Using multiple models and sampling across them would produce more varied writing styles in the synthetic data — which matters for training data quality and for catching judge blind spots tied to a single model's output style.

**Local document ingestion.** The KB currently supports URL scraping and the built-in demo dataset. PDF/JSON/TXT ingestion doesn't exist — a gap for agencies whose KB sources are downloadable documents rather than public HTML.

**Automated eval loop.** Each step currently requires manual initiation through the dashboard. The longer-term goal is for the full workflow — ingest, generate, evaluate, diagnose, fix, re-evaluate — to run periodically and automatically, producing a report at the end of each cycle.

---

## Tools used and why

| Tool | Why |
|------|-----|
| Streamlit | Fast dashboard with native session state; no frontend boilerplate |
| PostgreSQL + pgvector | Semantic KB retrieval; persistent eval history across runs |
| BeautifulSoup + requests | Sufficient for static government sites; simpler than Playwright |
| sentence-transformers | Local embeddings for failure clustering — no API cost |
| scikit-learn KMeans | Failure clustering; natural pairing with sentence-transformers |
| difflib | Clean `+/-` diff for prompt rewrites without a heavy dependency |
| Claude Code | AI coding assistant used throughout development — for scaffolding, debugging, and iterating on the pipeline |
