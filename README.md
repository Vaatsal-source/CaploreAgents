# SAFEAgentic

SAFEAgentic is a small Python project that runs an agentic financial analysis workflow through `ProfilerAgent/AgenticProfiler.py`.

The script reads a company financial dataset in JSON format, sends it to Gemini, and produces a structured markdown report.

## Features

- Reads corporate financial data from a JSON file
- Uses Gemini via the `google-genai` SDK
- Loads secrets from a local `.env` file
- Prints the report to the terminal or saves it to a markdown file

## Requirements

- Python 3.10 or newer
- A valid Gemini API key

## Setup

1. Clone the repository.
2. Change into the project directory.
3. Create and activate a virtual environment.
4. Install dependencies.
5. Add your API key to `ProfilerAgent/.env`.

Example setup on Windows PowerShell:

```powershell
cd C:\path\to\SAFEAgentic
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r ProfilerAgent\requirement.txt
```

## Environment Variables

Create `ProfilerAgent/.env` with your Gemini API key:

```env
GEMINI_API_KEY=your_api_key_here
```

## Input File

The agent expects a JSON file containing the company dataset. A sample file is included at:

- `ProfilerAgent/company_data.json`

You can replace that file with your own data or point the script to another JSON file.

## Run the Agent

Run the script from the project root:

```powershell
python ProfilerAgent\AgenticProfiler.py ProfilerAgent\company_data.json
```

To save the generated report to a file:

```powershell
python ProfilerAgent\AgenticProfiler.py ProfilerAgent\company_data.json ProfilerAgent\report.md
```

If no output path is provided, the report is printed to the console.

## Output

The generated report is formatted in markdown and includes:

- Quantitative screening
- Qualitative synthesis
- Shareholding architecture and trajectory

## Notes

- The script uses `ProfilerAgent/.env` automatically through `python-dotenv`.
- Make sure `GEMINI_API_KEY` is set before running the agent.
- Large or malformed JSON input may cause API or parsing errors.

## Project Structure

```text
SAFEAgentic/
├── ProfilerAgent/
│   ├── AgenticProfiler.py
│   ├── company_data.json
│   ├── report.md
│   ├── requirement.txt
│   └── .env
├── .gitignore
└── README.md
```

## Troubleshooting

- If you see `File not found`, confirm the JSON path you passed to the script exists.
- If Gemini authentication fails, verify that `GEMINI_API_KEY` is correct in `ProfilerAgent/.env`.
- If a package import fails, reinstall dependencies with `pip install -r ProfilerAgent\requirement.txt`.
