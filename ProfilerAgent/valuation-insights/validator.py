"""
Stage 3b - Post-Generation Numeric Validator
Pure Python, zero LLM calls. Extracts every number the LLM's output cites
and checks it against the computed_metrics dict. Per project decision:
unverifiable numbers are NOT stripped or blocked - they are simply
tagged inline so a human can spot them later. The report still gets
written either way.
"""

import re


NUMBER_PATTERN = re.compile(r"-?\d[\d,]*\.?\d*\s*%?x?")


def _normalize(token: str) -> str:
    """Strip formatting so '160%' == '160.0%' == '160' for comparison."""
    t = token.strip().replace(",", "")
    t = t.rstrip("x")
    is_pct = t.endswith("%")
    t = t.rstrip("%").strip()
    try:
        num = float(t)
    except ValueError:
        return token.strip()
    return f"{num}%" if is_pct else f"{num}"


def _collect_known_numbers(computed_metrics: dict) -> set:
    known = set()

    def _add_from_text(text):
        for match in NUMBER_PATTERN.findall(str(text)):
            if match.strip():
                known.add(_normalize(match))

    def _walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                _add_from_text(k)   # dict keys often ARE year labels ("Mar 2024")
                _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)
        elif isinstance(node, (str, int, float)):
            _add_from_text(node)

    _walk(computed_metrics)
    return known


def validate(llm_output: str, computed_metrics: dict) -> str:
    """
    Returns the llm_output with any unverifiable number annotated as
    ' [unverified: <token>]' right after it. Does not remove or block
    anything - just flags for visibility.
    """
    known_numbers = _collect_known_numbers(computed_metrics)

    def _check(match: re.Match) -> str:
        token = match.group(0)
        if not token.strip() or token.strip() in ("-",):
            return token
        norm = _normalize(token)
        if norm in known_numbers:
            return token
        return f"{token.rstrip()} [unverified]"

    return NUMBER_PATTERN.sub(_check, llm_output)


if __name__ == "__main__":
    sample_metrics = {"opm_by_year": {"Mar 2024": "14%", "Mar 2026": "11%"}}
    sample_text = "OPM fell from 14% in Mar 2024 to 11% in Mar 2026, while ROE was 99.9%."
    print(validate(sample_text, sample_metrics))