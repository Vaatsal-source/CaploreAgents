# Valuation Insights Pipeline

Automated "Qualitative Synthesis" (Pros/Cons) report generator for company
financial data, built around a single LLM call per run and a deterministic,
auditable computation layer that keeps that call honest.

Given a raw financial data export (screener.in-style JSON), the pipeline
extracts and computes the underlying metrics in code, hands only those
verified numbers to an LLM to turn into prose, then runs a code-only check
over the output before writing the final `report.md`.

---

## Pipeline Overview

```
company_data.json
       │
       ▼
┌─────────────────┐
│  1. Extraction    │  extractor.py
│  (no LLM)         │  Parses raw JSON into a flat, normalized structure.
└─────────────────┘
       │
       ▼
┌─────────────────┐
│  2. Metrics        │  metrics.py
│  Computation       │  Computes every number the LLM is allowed to cite -
│  (no LLM)          │  ratios, YoY growth, trends - all in plain Python.
└─────────────────┘
       │
       ▼
┌─────────────────┐
│  3. LLM Call       │  llm_client.py
│  (ONE call)        │  Gemini turns the verified metrics into Pros/Cons
│                    │  prose, under strict hallucination-resistance rules.
└─────────────────┘
       │
       ▼
┌─────────────────┐
│  4. Validation     │  validator.py
│  (no LLM)          │  Regex-extracts every number in the LLM's output and
│                    │  checks it against the computed metrics. Unverifiable
│                    │  numbers are tagged inline, never blocked or retried.
└─────────────────┘
       │
       ▼
┌─────────────────┐
│  5. Report Writer  │  report_writer.py
│                    │  Writes output/report.md + output/computed_metrics.json
└─────────────────┘
```

Only step 3 costs an LLM call. Everything else is free, fast, and testable
in isolation.

---

## Project Structure

```
valuation-insights/
├── .env.example          Copy to .env and add your GEMINI_API_KEY
├── requirements.txt
├── extractor.py           Stage 1 - JSON parsing / normalization
├── metrics.py             Stage 2 - deterministic metric computation
├── llm_client.py          Stage 3 - the single Gemini call + prompt
├── validator.py           Stage 4 - post-generation numeric check
├── report_writer.py       Stage 5 - writes final report.md
├── main.py                Orchestrates all stages
├── data/company_data.json Your input file goes here
└── output/                report.md + computed_metrics.json land here
```

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env       # add your GEMINI_API_KEY
```

## Usage

```bash
python main.py data/company_data.json
```

Output:
- `output/report.md` - the final Qualitative Synthesis section
- `output/computed_metrics.json` - the full audit trail of every number
  used, kept for debugging and traceability (never shown to end users)

---

## Hallucination Prevention

The pipeline treats hallucination prevention as an architectural property,
not just a prompting technique. Four layers work together:

**1. The LLM never sees raw data, only pre-computed facts.**
Every ratio, growth rate, and trend cited in the final report (CFO/OP
ratio, YoY sales growth, working capital days, dividend payout, etc.) is
calculated in `metrics.py` using plain Python arithmetic - not by the LLM.
The model's job is narrowed to turning already-correct numbers into prose,
not doing math or recalling facts from memory.

**2. Source-data conflicts are caught before they reach the LLM.**
`extractor.py` cross-checks fields that should agree (e.g. current price
appearing in two places in the source JSON) and flags mismatches instead
of silently picking one. A bad number in the source can't quietly become
a bad number in the report.

**3. Explicit hallucination-resistance rules constrain the single LLM call.**
The prompt in `llm_client.py` instructs the model to:
- Use only the supplied JSON, never outside knowledge or assumptions
- Say "Not available in the provided data" rather than guess
- Flag rather than resolve conflicting values
- Distinguish stated facts from cautious inference
- Never fabricate trends the data doesn't support

**4. A post-generation validator checks every number in the output - in code.**
After the LLM responds, `validator.py` regex-extracts every number it
wrote and checks it against the computed metrics dict - a plain set
lookup, no LLM involved. Numbers that don't trace back to a verified
source are tagged `[unverified]` inline so a human reviewer can spot them
at a glance. This step is a quality signal, not a blocker: since the
project runs on exactly one LLM call, there's no second call to retry or
regenerate - flagged content still ships, but visibly marked.

This means hallucination resistance doesn't depend on the LLM "behaving" -
even if it slips, the numeric ground-truth check catches it after the
fact, for free.

---

## Scalability Features

**Deterministic stages are cacheable.**
Extraction and metrics computation are pure functions of the input JSON -
same input always produces the same output. In a multi-company or
scheduled-run setup, these results can be cached per company + filing
date, so re-runs only pay for the LLM call, not the whole pipeline.

**One LLM call per company, regardless of data volume.**
The architecture already compresses potentially thousands of raw JSON
fields down to a compact, pre-verified metrics object before the one
Gemini call - so token cost stays flat even as the source data grows
(more years of history, more shareholding detail, etc.).

**Noise reduction happens before the LLM, not after.**
Shareholding data in particular can contain hundreds of near-zero,
inactive entities. `extractor.py` aggregates category totals and keeps
only the top movers, so the LLM's context - and therefore cost and
latency - doesn't scale with irrelevant long-tail data.

**Model-agnostic LLM layer.**
`llm_client.py` isolates the entire Gemini interaction behind one
function. Swapping providers (e.g. to a different model or vendor) or
model versions - which Google has changed several times this year -
means editing one file, not the pipeline logic.

**Stable intermediate schema.**
`metrics.py` outputs a consistent, versionable metrics structure
regardless of quirks in the underlying source JSON (nested rows,
inconsistent field names, differently-shaped shareholding tables). This
isolates the rest of the pipeline from source-format changes.

**Full audit trail, not just the final report.**
Every run persists `computed_metrics.json` alongside `report.md` - so any
bullet in the final report can be traced back to its exact source number
without re-running extraction or calling the LLM again.

---

## Things to Adjust

- `metrics.py` currently reads from `profit_loss`, `balance_sheet`,
  `cash_flows`, `ratios`, and `shareholding` sections matching a
  screener.in-style export. If your JSON source changes shape, update the
  row-label lookups in `metrics.py` (e.g. `_find_row(pl, "Sales")`)
  accordingly.
