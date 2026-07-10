"""Benchmark audit findings against the CUAD dataset — 510 expert-annotated
real-world contracts (Hendrycks et al., NeurIPS 2021). Stats in cuad_stats.json
are computed directly from the official dataset."""
import json
import os

_STATS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cuad_stats.json")

# Our audit clauses -> CUAD category names (only where a true equivalent exists)
CUAD_MAPPING = {
    "Non-Compete": "Non-Compete",
    "Intellectual Property (IP) Assignment": "Ip Ownership Assignment",
    "Limitation of Liability": "Cap On Liability",
    "Termination / Exit Clause": "Termination For Convenience",
    "Governing Law / Jurisdiction": "Governing Law",
}

try:
    with open(_STATS_PATH, encoding="utf-8") as f:
        _DATA = json.load(f)
    _TOTAL = _DATA["total_contracts"]
    _CATS = _DATA["categories"]
except Exception:
    _DATA, _TOTAL, _CATS = None, 0, {}


def benchmark_for(clause: str, status: str) -> str | None:
    """One-line comparison against real-world contract practice, or None
    when CUAD has no equivalent category for this clause."""
    cat = CUAD_MAPPING.get(clause)
    if not cat or cat not in _CATS:
        return None
    pct = _CATS[cat]["pct"]
    line = f"CUAD benchmark: appears in {pct:.0f}% of {_TOTAL} real contracts"
    if status == "ABSENT" and pct >= 60:
        line += "  — unusual omission: most real contracts include this"
    elif status == "PRESENT" and pct <= 25:
        line += "  — notable: relatively rare in practice"
    return line


def available() -> bool:
    return bool(_CATS)
