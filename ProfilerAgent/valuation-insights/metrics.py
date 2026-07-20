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
    pl = extracted["profit_loss"]       # annual P&L (Sales, OPM, Net Profit, etc.)
    cf = extracted["cash_flows"]        # CFO, FCF, CFO/OP
    ratios = extracted["ratios"]        # Debtor/Inventory/Payable/WC days
    bs = extracted["balance_sheet"]     # Borrowings
    sh_cat = extracted["shareholding_categories"]
    sh_movers = extracted["shareholding_top_movers"]

    metrics = {}

    # --- valuation & returns (flat from key_metrics) ---
    for label in ("Stock P/E", "Book Value", "ROCE", "ROE", "Dividend Yield",
                  "Market Cap", "Current Price"):
        if label in km and km[label] is not None:
            metrics[label.replace(" ", "_").replace("/", "_")] = km[label]

    if "Current Price" in km and "Book Value" in km and km["Book Value"]:
        metrics["P_B_ratio"] = _fmt_x(km["Current Price"] / km["Book Value"])

    # --- trailing financial trends (annual, from profit_loss) ---
    sales = _last_n(_mar_years(_find_row(pl, "Sales") or {}))
    opm = _last_n(_mar_years(_find_row(pl, "OPM %") or {}))
    net_profit = _last_n(_mar_years(_find_row(pl, "Net Profit") or {}))
    other_income = _last_n(_mar_years(_find_row(pl, "Other Income") or {}))
    pbt = _last_n(_mar_years(_find_row(pl, "Profit before tax") or {}))
    interest = _last_n(_mar_years(_find_row(pl, "Interest") or {}))
    material_cost_pct = _last_n(
        _mar_years(_find_row(pl, "Expenses > Material Cost %") or {})
    )
    dividend_payout = _last_n(_mar_years(_find_row(pl, "Dividend Payout %") or {}))

    metrics["sales_by_year"] = {y: _fmt_cr(v) for y, v in sales.items()}
    metrics["opm_by_year"] = {y: _fmt_pct(v) for y, v in opm.items()}
    metrics["net_profit_by_year"] = {y: _fmt_cr(v) for y, v in net_profit.items()}
    metrics["interest_by_year"] = {y: _fmt_cr(v) for y, v in interest.items()}
    metrics["material_cost_pct_by_year"] = {y: _fmt_pct(v) for y, v in material_cost_pct.items()}
    metrics["dividend_payout_pct_by_year"] = {y: _fmt_pct(v) for y, v in dividend_payout.items()}

    years = list(sales.keys())
    sales_growth = {}
    for i in range(1, len(years)):
        prev, cur = sales[years[i - 1]], sales[years[i]]
        if prev:
            sales_growth[years[i]] = round((cur - prev) / prev * 100, 2)
    metrics["sales_growth_pct_by_year"] = {y: _fmt_pct(v) for y, v in sales_growth.items()}

    if pbt and other_income:
        last_year = list(pbt.keys())[-1]
        if last_year in other_income and pbt[last_year]:
            pct = round(other_income[last_year] / pbt[last_year] * 100, 1)
            key = last_year.replace(" ", "_")
            metrics[f"other_income_pct_of_pbt_{key}"] = _fmt_pct(pct)
            metrics[f"other_income_{key}"] = _fmt_cr(other_income[last_year])

    # --- cash flow efficiency (CFO/OP ratio, FCF) ---
    cfo_op = _last_n(_mar_years(_find_row(cf, "CFO/OP") or {}))
    cfo = _last_n(_mar_years(_find_row(cf, "Cash from Operating Activity") or {}))
    fcf = _last_n(_mar_years(_find_row(cf, "Free Cash Flow") or {}))
    metrics["cfo_op_ratio_by_year"] = {y: _fmt_pct(v) for y, v in cfo_op.items()}
    metrics["cfo_by_year"] = {y: _fmt_cr(v) for y, v in cfo.items()}
    metrics["free_cash_flow_by_year"] = {y: _fmt_cr(v) for y, v in fcf.items()}

    # --- efficiency & capital structure (ratios + balance sheet) ---
    wc_days = _last_n(_mar_years(_find_row(ratios, "Working Capital Days") or {}))
    debtor_days = _last_n(_mar_years(_find_row(ratios, "Debtor Days") or {}))
    inventory_days = _last_n(_mar_years(_find_row(ratios, "Inventory Days") or {}))
    payable_days = _last_n(_mar_years(_find_row(ratios, "Days Payable") or {}))
    borrowings = _last_n(_mar_years(_find_row(bs, "Borrowings") or {}))

    metrics["working_capital_days_by_year"] = {y: str(v) for y, v in wc_days.items()}
    metrics["debtor_days_by_year"] = {y: str(v) for y, v in debtor_days.items()}
    metrics["inventory_days_by_year"] = {y: str(v) for y, v in inventory_days.items()}
    metrics["payable_days_by_year"] = {y: str(v) for y, v in payable_days.items()}
    metrics["borrowings_by_year"] = {y: _fmt_cr(v) for y, v in borrowings.items()}

    # --- shareholding trends ---
    metrics["shareholding_category_totals_pct"] = {
        label: {
            y: (str(int(v)) if "No. of Shareholders" in label else _fmt_pct(v))
            for y, v in _last_n(values, 7).items()
        }
        for label, values in sh_cat.items()
    }
    metrics["shareholding_top_movers"] = sh_movers

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