"""
Stage 3a - Single LLM Call
Exactly ONE call to Gemini per run. Takes the computed_metrics dict from
metrics.py (already-verified, pre-formatted numbers) and asks the model
to write ONLY the "Qualitative Synthesis" (Pros/Cons) section.
"""

import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

HALLUCINATION_RULES = """
### Hallucination Resistance Rules:
- Use only the information present in the provided JSON or values that can be directly and unambiguously calculated from it.
- Never invent missing metrics, years, shareholding values, labels, or company-specific details.
- If a value is absent, unclear, or inconsistent, explicitly state "Not available in the provided data" rather than guessing.
- If a calculation cannot be made reliably from the available fields, state that the calculation is not possible from the provided data.
- Do not use outside knowledge, prior memory, market assumptions, or generic company commentary to fill gaps.
- When multiple interpretations are possible, choose the most conservative one and note the ambiguity.
- Separate facts from inference clearly. Any inference must be directly supported by the supplied data and phrased as a cautious observation, not a certainty.
- Do not fabricate trends across years if the dataset does not contain enough time points to support them.
- If the dataset contains conflicting values, surface the conflict instead of resolving it silently.
"""

PROMPT_TEMPLATE = """You are a financial analyst writing a "Fundamental Analysis Report"
of a due-diligence report for {company_name} ({ticker}).

Below is a JSON object of PRE-COMPUTED, VERIFIED metrics. Every number in
your output MUST come directly from this JSON - do not compute new ratios,
do not round differently, and do not introduce any number not present here.

```json
{metrics_json}
```

{rules}

Write your output in exactly this markdown structure, nothing else:

## Executive Summary
Provide a brief summary of the company's financial health based on the data. (1 paragraph)

## Quantitative Analysis
### Income Statement Analysis
Discuss the trends in sales, expenses, operating profit, OPM, net profit, and EPS, citing specific numbers from the JSON. (1-2 paragraphs)

### Balance Sheet Analysis
Discuss the trends in total assets, borrowings, and shareholders' equity, citing specific numbers from the JSON. (1-2 paragraphs)

### Cash Flow Statement Analysis
Discuss the trends in operating cash flow, investing cash flow, financing cash flow, and capital expenditures (CapEx), citing specific numbers from the JSON. (1-2 paragraphs)

## Key Financial Ratios & Metrics
Provide bullet points for the following key ratios, explaining their values:
* **Price-to-Earnings (P/E) Ratio:** <description citing specific P/E value from the JSON>
* **Debt-to-Equity (D/E) Ratio:** <description citing specific D/E values over the years from the JSON>
* **Return on Equity (ROE) & ROCE:** <description citing specific ROE and ROCE values from the JSON>
* **Free Cash Flow (FCF):** <description citing specific FCF values over the years from the JSON>

## Valuation Models
### Relative Valuation
Analyze the stock's valuation using the P/E and P/B multiples from the JSON. (1 paragraph)

### Absolute Valuation (Discounted Cash Flow - DCF)
Provide a qualitative discussion of the company's absolute valuation model based on historical Cash Flows, CapEx, and growth trends. (1 paragraph)
"""


def generate_qualitative_synthesis(computed: dict, model_name: str = "gemini-3.5-flash") -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set (check your .env file)")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    prompt = PROMPT_TEMPLATE.format(
        company_name=computed.get("company_name", "the company"),
        ticker=computed.get("ticker", ""),
        metrics_json=json.dumps(computed["computed_metrics"], indent=2),
        rules=HALLUCINATION_RULES,
    )

    # single call - no retries, no follow-ups, per project constraint
    response = model.generate_content(prompt)
    return response.text