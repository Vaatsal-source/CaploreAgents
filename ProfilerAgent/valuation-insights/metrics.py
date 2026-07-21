"""
Stage 2 - Fundamental Analysis / Metrics Computation
Takes the flat structure from extractor.py and computes every number the
LLM is later allowed to cite. This is the anti-hallucination backbone:
if a metric isn't computed here, the LLM has no basis to mention it, and
the validator (validator.py) will strip it out if it tries.

All output values are stored in `computed_metrics` as {label: value_string}
pairs, already formatted the way you want them to appear in prose
(e.g. "160%", "₹ 6,904 Cr", "40.7x") so both the LLM prompt and the
validator work off the exact same formatted strings.

NOTE: Your source JSON's `quarterly` block only exposes Mar-quarter figures
(fiscal year-end) among other quarters. This script pulls March-ending
values as annual proxies. If your JSON has a separate "annual" /
"balance_sheet" / "cash_flow" top-level section (common in full
screener.in exports but not visible in the truncated view I inspected),
extend `extract_all()` in extractor.py with matching extractors and wire
their outputs into `compute_metrics()` below - the structure is designed
to make that a small addition, not a rewrite.
"""

from extractor import extract_all


def _find_row(quarterly: list, label: str):
    for row in quarterly:
        if row["label"] == label:
            return row["values"]
    return None


def _mar_years(values: dict):
    """Returns {year: value} restricted to March (fiscal year-end) columns,
    sorted chronologically."""
    mar = {k: v for k, v in values.items() if k.startswith("Mar") and v is not None}
    return dict(sorted(mar.items(), key=lambda kv: kv[0]))


def _fmt_pct(v):
    return None if v is None else f"{v:.2f}%"


def _fmt_cr(v):
    return None if v is None else f"₹ {v:,.0f} Cr"


def _fmt_x(v):
    return None if v is None else f"{v:.1f}x"


def _last_n(d: dict, n: int = 4) -> dict:
    """Keep only the most recent n March/year columns."""
    return dict(list(d.items())[-n:])


def compute_metrics(extracted: dict) -> dict:
    km = extracted["key_metrics"]
    pl = extracted["profit_loss"]       # annual P&L
    cf = extracted["cash_flows"]        # CFO, CFI, CFF
    bs = extracted["balance_sheet"]     # Balance Sheet
    ratios = extracted["ratios"]        # ROCE etc.

    metrics = {}

    # --- 1. Key Metrics & Ratios (from key_metrics) ---
    for label in ("Stock P/E", "Book Value", "ROCE", "ROE", "Dividend Yield",
                  "Market Cap", "Current Price"):
        if label in km and km[label] is not None:
            metrics[label.replace(" ", "_").replace("/", "_")] = km[label]

    if "Current Price" in km and "Book Value" in km and km["Book Value"]:
        metrics["P_B_ratio"] = _fmt_x(km["Current Price"] / km["Book Value"])

    # --- 2. Income Statement Trends ---
    sales = _last_n(_mar_years(_find_row(pl, "Sales") or {}))
    expenses = _last_n(_mar_years(_find_row(pl, "Expenses") or {}))
    op_profit = _last_n(_mar_years(_find_row(pl, "Operating Profit") or {}))
    opm = _last_n(_mar_years(_find_row(pl, "OPM %") or {}))
    net_profit = _last_n(_mar_years(_find_row(pl, "Net Profit") or {}))
    eps = _last_n(_mar_years(_find_row(pl, "EPS in Rs") or {}))

    metrics["sales_by_year"] = {y: _fmt_cr(v) for y, v in sales.items()}
    metrics["expenses_by_year"] = {y: _fmt_cr(v) for y, v in expenses.items()}
    metrics["operating_profit_by_year"] = {y: _fmt_cr(v) for y, v in op_profit.items()}
    metrics["opm_by_year"] = {y: _fmt_pct(v) for y, v in opm.items()}
    metrics["net_profit_by_year"] = {y: _fmt_cr(v) for y, v in net_profit.items()}
    metrics["eps_by_year"] = {y: f"₹ {v:.2f}" if isinstance(v, (int, float)) else str(v) for y, v in eps.items()}

    # --- 3. Balance Sheet Snapshot/Trends ---
    total_assets = _last_n(_mar_years(_find_row(bs, "Total Assets") or {}))
    borrowings = _last_n(_mar_years(_find_row(bs, "Borrowings") or {}))
    equity_cap = _last_n(_mar_years(_find_row(bs, "Equity Capital") or {}))
    reserves = _last_n(_mar_years(_find_row(bs, "Reserves") or {}))

    metrics["total_assets_by_year"] = {y: _fmt_cr(v) for y, v in total_assets.items()}
    metrics["borrowings_by_year"] = {y: _fmt_cr(v) for y, v in borrowings.items()}
    
    # Calculate Shareholders' Equity = Equity Capital + Reserves
    sh_equity = {}
    de_ratio = {}
    for y in total_assets.keys():
        eq_val = equity_cap.get(y)
        res_val = reserves.get(y)
        borrow_val = borrowings.get(y)
        if eq_val is not None and res_val is not None:
            equity_sum = eq_val + res_val
            sh_equity[y] = equity_sum
            if borrow_val is not None and equity_sum > 0:
                de_ratio[y] = borrow_val / equity_sum

    metrics["shareholders_equity_by_year"] = {y: _fmt_cr(v) for y, v in sh_equity.items()}
    metrics["debt_to_equity_by_year"] = {y: f"{v:.2f}" for y, v in de_ratio.items()}

    # --- 4. Cash Flow Statement Trends ---
    cfo = _last_n(_mar_years(_find_row(cf, "Cash from Operating Activity") or {}))
    cfi = _last_n(_mar_years(_find_row(cf, "Cash from Investing Activity") or {}))
    cff = _last_n(_mar_years(_find_row(cf, "Cash from Financing Activity") or {}))
    
    metrics["operating_cash_flow_by_year"] = {y: _fmt_cr(v) for y, v in cfo.items()}
    metrics["investing_cash_flow_by_year"] = {y: _fmt_cr(v) for y, v in cfi.items()}
    metrics["financing_cash_flow_by_year"] = {y: _fmt_cr(v) for y, v in cff.items()}

    # CapEx & FCF calculation
    capex_row = _find_row(cf, "Cash from Investing Activity > Fixed assets purchased") or {}
    capex = _last_n(_mar_years(capex_row))
    metrics["capex_by_year"] = {y: _fmt_cr(abs(v)) for y, v in capex.items()}

    fcf = {}
    for y in cfo.keys():
        cfo_val = cfo.get(y)
        capex_val = capex.get(y)  # usually negative in screener
        if cfo_val is not None:
            capex_abs = abs(capex_val) if capex_val is not None else 0.0
            fcf[y] = cfo_val - capex_abs

    metrics["free_cash_flow_by_year"] = {y: _fmt_cr(v) for y, v in fcf.items()}

    # flatten out None/empty values so the LLM never sees "null" or "{}"
    def _prune(d):
        if isinstance(d, dict):
            return {k: _prune(v) for k, v in d.items() if v not in (None, {}, [])}
        return d

    return _prune(metrics)


def run(json_path: str) -> dict:
    extracted = extract_all(json_path)
    return {
        "ticker": extracted["ticker"],
        "company_name": extracted["company_name"],
        "computed_metrics": compute_metrics(extracted),
    }


if __name__ == "__main__":
    import sys
    import json as _json
    result = run(sys.argv[1] if len(sys.argv) > 1 else "data/company_data.json")
    print(_json.dumps(result, indent=2))