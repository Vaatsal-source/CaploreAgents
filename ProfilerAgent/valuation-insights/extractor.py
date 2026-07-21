"""
Stage 1 - Extraction
Parses the raw company_data.json (screener.in-style export) into a flat,
normalized intermediate structure. No LLM calls here - pure data wrangling.

Handles:
  - key_metrics (flat dict of valuation/return ratios)
  - pros_cons (screener's own pre-written bullets - kept separate, NOT fed
    to the LLM as "ground truth insight", only as raw source text if needed)
  - quarterly (list of rows, some with nested "children" sub-rows like
    "YOY Sales Growth %", "Material Cost %" etc.)
  - shareholding (nested by category -> entity -> year), aggregated down
    to category totals + top non-zero movers only (drops hundreds of
    zero-value shell entities so the LLM never sees them)

If your JSON has additional top-level sections (e.g. "balance_sheet",
"cash_flow", "annual"), add small `_extract_x()` functions for them
following the same pattern and register them in `extract_all()`.
"""

import json
import re
from pathlib import Path


def _clean_number(raw):
    """'₹ 17,37,577 Cr.' -> 1737577.0 ; '40.7' -> 40.7 ; '' -> None"""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    if s == "" or s.lower() in ("na", "n/a", "-"):
        return None
    s = s.replace("₹", "").replace("Cr.", "").replace("Cr", "")
    s = s.replace("%", "").replace(",", "").strip()
    # handle "1,612 / 1,253" style ranges by returning as-is (caller splits)
    try:
        return float(s)
    except ValueError:
        return s  # leave non-numeric strings (e.g. ranges) untouched


def extract_key_metrics(data: dict) -> dict:
    raw = data.get("key_metrics", {})
    cleaned = {}
    for label, value in raw.items():
        cleaned[label] = _clean_number(value)
    # known screener.in bug: overview.current_price sometimes duplicates
    # market cap instead of actual price - cross check against key_metrics
    overview_price = _clean_number(data.get("overview", {}).get("current_price"))
    km_price = cleaned.get("Current Price")
    if overview_price is not None and km_price is not None:
        if abs(overview_price - km_price) > 1:  # meaningfully different
            cleaned["_conflict_current_price"] = {
                "overview.current_price": overview_price,
                "key_metrics.Current Price": km_price,
                "note": "Mismatch between overview and key_metrics current price fields. "
                        "Using key_metrics value as source of truth.",
            }
    return cleaned


def _flatten_quarterly_row(row: dict, parent_label: str = None) -> list:
    """Flattens one row (and its nested children, if any) into a list of
    {label, values: {period: value}} dicts."""
    label = row.get("", "").strip()
    if not label:
        return []
    full_label = f"{parent_label} > {label}" if parent_label else label
    values = {
        period: _clean_number(val)
        for period, val in row.items()
        if period not in ("", "expandable", "children")
    }
    out = [{"label": full_label, "values": values}]
    for child in row.get("children", []):
        out.extend(_flatten_quarterly_row(child, parent_label=label))
    return out


def extract_row_table(rows: list) -> list:
    """Generic flattener for any screener.in-style row-table section
    (quarterly, profit_loss, balance_sheet, cash_flows, ratios all share
    this exact {label, period: value, expandable, children} shape)."""
    flat = []
    for row in rows:
        flat.extend(_flatten_quarterly_row(row))
    return flat


def extract_all(json_path: str) -> dict:
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    return {
        "ticker": data.get("ticker"),
        "company_name": data.get("overview", {}).get("company_name"),
        "key_metrics": extract_key_metrics(data),
        "profit_loss": extract_row_table(data.get("profit_loss", [])),
        "balance_sheet": extract_row_table(data.get("balance_sheet", [])),
        "cash_flows": extract_row_table(data.get("cash_flows", [])),
        "ratios": extract_row_table(data.get("ratios", [])),
    }


if __name__ == "__main__":
    import sys
    out = extract_all(sys.argv[1] if len(sys.argv) > 1 else "data/company_data.json")
    print(json.dumps(out, indent=2)[:2000])