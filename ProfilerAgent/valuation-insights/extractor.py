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


def extract_pros_cons_raw(data: dict) -> dict:
    """Screener's own pre-written pros/cons - kept as separate raw source
    text. NOT used as the LLM's output; useful only as cross-reference."""
    return data.get("pros_cons", {"pros": [], "cons": []})


def _num(v):
    try:
        return float(str(v).replace(",", "").replace("%", "").strip())
    except (ValueError, TypeError):
        return None


def extract_shareholding_categories(data: dict) -> dict:
    """
    data["shareholding"]["table_1"] / ["table_2"] are simple row-tables
    (Promoters / FIIs / DIIs / Government / Public rows, one column per
    period) - table_1 is quarterly-granularity, table_2 is annual/yearly.
    We use table_2 for the year-over-year category totals actually cited
    in the report.
    """
    sh = data.get("shareholding", {})
    table = sh.get("table_2") or sh.get("table_1") or []
    flat = extract_row_table(table)
    return {row["label"]: row["values"] for row in flat}


def extract_top_investors(data: dict, top_n: int = 5) -> dict:
    """
    data["investors"]["yearly"] holds individual-holder detail (LIC, SBI MF,
    foreign funds, promoter-linked entities, etc.), keyed by category then
    entity name then year - this is where the hundreds of 0.00% shell/LLP
    entities live. We drop anything that's zero across every year it
    appears, then keep only the top N movers per category by
    (max - min) over the years each entity actually reports.
    """
    investors = data.get("investors", {}).get("yearly", {})
    top_movers = {}
    for category, entities in investors.items():
        movers = []
        for name, yearly in entities.items():
            vals = [_num(v) for v in yearly.values() if _num(v) is not None]
            if not vals or max(vals) == 0:
                continue
            movement = max(vals) - min(vals)
            movers.append((name, yearly, movement))
        movers.sort(key=lambda x: x[2], reverse=True)
        if movers:
            top_movers[category] = [
                {"name": name, "values": yearly} for name, yearly, _ in movers[:top_n]
            ]
    return top_movers


def extract_all(json_path: str) -> dict:
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    return {
        "ticker": data.get("ticker"),
        "company_name": data.get("overview", {}).get("company_name"),
        "key_metrics": extract_key_metrics(data),
        "quarterly": extract_row_table(data.get("quarterly", [])),
        "profit_loss": extract_row_table(data.get("profit_loss", [])),
        "balance_sheet": extract_row_table(data.get("balance_sheet", [])),
        "cash_flows": extract_row_table(data.get("cash_flows", [])),
        "ratios": extract_row_table(data.get("ratios", [])),
        "pros_cons_raw": extract_pros_cons_raw(data),
        "shareholding_categories": extract_shareholding_categories(data),
        "shareholding_top_movers": extract_top_investors(data),
    }


if __name__ == "__main__":
    import sys
    out = extract_all(sys.argv[1] if len(sys.argv) > 1 else "data/company_data.json")
    print(json.dumps(out, indent=2)[:2000])