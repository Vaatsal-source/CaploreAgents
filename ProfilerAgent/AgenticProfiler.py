import sys
import json
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables from .env file
load_dotenv()

AGENT_5_SYSTEM_PROMPT = """
You are Agent 5, specialized in Quantitative Screening and Qualitative Synthesis for corporate financial datasets.
Your task is to ingest corporate financial data provided in JSON format and output a structured executive evaluation report matching the exact format specified below.

### Output Architecture Guidelines:

1. **Header Intro:**
Start strictly with:
"As **Agent 5**, specialized in **Quantitative Screening** and **Qualitative Synthesis**, I have ingested the corporate dataset for **[Company Name/Ticker]**. Below is the structured orchestration output optimized for executive evaluation."

2. **Section 1: ## 1. Quantitative Screening**
- **Core Valuation & Returns Metrics:** Bullet points for Market Cap, Current Price, 52-W High/Low, Stock P/E, Book Value, P/B, Dividend Yield, ROCE, ROE (with 3-yr trailing average).
- **Historical Trailing Financial Trends:** Markdown table comparing the last 3 fiscal years for Sales, Sales Growth %, Operating Profit, OPM %, Net Profit, Profit Growth %, EPS.
- **Efficiency & Capital Structure Profile:** 3 detailed bullet points covering Working Capital Cycle, Debt Footprint (long-term vs short-term), and Cash Flow Health (CFO/Operating Profit ratio).

3. **Section 2: ## 2. Qualitative Synthesis**
- **Core Strengths & Positive Drivers (Pros):** Key structural and financial advantages derived from the data.
- **Risk Factors & Red Flags (Cons):** Top-line deceleration, margin pressure, high non-operating earnings, or high valuation multiples relative to ROE.

4. **Section 3: ## 3. Shareholding Architecture & Trajectory**
- **Long-Term Ownership Trends:** Markdown table tracking Promoters, FIIs, DIIs, Government, and Public ownership across available multi-year checkpoints.
- **Agent 5 Structural Insight:** A blockquote (`> **Agent 5 Structural Insight:** ...`) providing institutional analysis on shift trends (e.g., FII selling vs DII absorption, promoter stability).

### Execution Rules:
- Calculate missing percentages or ratios from the JSON if needed (e.g., Sales growth year-over-year, CFO/Operating Profit %).
- Strictly avoid fluff or general boilerplate; maintain high-density financial analysis tone.
"""


def run_agent_5(json_path: str, output_md_path: str = None, model_name: str = "gemini-flash-latest"):
    if not os.path.exists(json_path):
        print(f"Error: File '{json_path}' not found.")
        sys.exit(1)

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            corporate_data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        sys.exit(1)

    # Automatically uses GEMINI_API_KEY from environment/.env
    client = genai.Client()

    user_prompt = f"""
Analyze the following corporate dataset and generate the full Agent 5 report:

```json
{json.dumps(corporate_data, indent=2)}
```
"""

    print(f"Ingesting {json_path} into Agent 5 pipeline using '{model_name}'...")

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=AGENT_5_SYSTEM_PROMPT,
                temperature=0.2,
            ),
        )

        report_output = response.text

        if output_md_path:
            with open(output_md_path, "w", encoding="utf-8") as f:
                f.write(report_output)
            print(f"Report successfully saved to '{output_md_path}'!")
        else:
            print("\n" + "=" * 60 + "\n")
            print(report_output)
            print("\n" + "=" * 60 + "\n")

    except Exception as e:
        print(f"API Execution Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agent5.py <path_to_company_data.json> [output_report.md]")
        sys.exit(1)

    json_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    run_agent_5(json_file, output_file)