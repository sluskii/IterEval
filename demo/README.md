# Demo Data

This folder contains static data used for demonstration and judge calibration only.
It is independent of the core IterEval platform.

| File | Purpose |
|---|---|
| `demo_dataset.py` | 25 hardcoded KB chunks (CPF, HDB, Baby Bonus, CDC, etc.) used as the knowledge base in demo runs |
| `validation_dataset.py` | 50 hand-labeled question-response pairs used to compute Cohen's Kappa for LLM judge calibration |

Neither file is imported by the core evaluation pipeline. They are loaded explicitly when running in demo mode or when validating the judge against human labels.
