#!/usr/bin/env python3
"""
compila_resultados.py
Lê todos os arquivos JSON do diretório current (padrão "sumario_final - vX - cY.json"),
extrai métricas-chave e produz data/metrics_all.csv
"""
import json
import glob
import re
import os
import pandas as pd

def parse_filename(fname):
    # espera padrão "sumario_final - v1 - c1.json" (pode ajustar)
    base = os.path.basename(fname)
    m = re.search(r'v(\d+)\s*-\s*c(\d+)', base, re.IGNORECASE)
    if m:
        return f"v{m.group(1)}", f"c{m.group(2)}"
    # fallback: separar por -
    parts = base.split('-')
    return parts[1].strip() if len(parts) > 1 else "", parts[2].split('.')[0].strip() if len(parts) > 2 else ""

def safe_get(d, path, default=None):
    cur = d
    for key in path.split('/'):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur

rows = []
for f in glob.glob("*.json"):
    try:
        j = json.load(open(f, encoding='utf-8'))
    except Exception as e:
        print("ignoring", f, e)
        continue
    approach, checkpoint = parse_filename(f)
    generated_at = j.get("generated_at")
    cloc = j.get("cloc", {})
    pylint = j.get("pylint", {})
    radon_mi = j.get("radon_mi", {})
    radon_cc = j.get("radon_cc", {})
    pytest_j = j.get("pytest", {})
    coverage = j.get("coverage", {})
    # compute some aggregated fields
    n_files = cloc.get("n_files")
    n_lines = cloc.get("n_lines")
    code = cloc.get("code")
    blank = cloc.get("blank")
    comment = cloc.get("comment")
    python_code = None
    by_language = cloc.get("by_language", {})
    if isinstance(by_language, dict):
        python_code = by_language.get("Python", {}).get("code") or by_language.get("python", {}).get("code")
    pylint_total = pylint.get("total_issues")
    pylint_conv = safe_get(pylint, "by_type/convention")
    pylint_refactor = safe_get(pylint, "by_type/refactor")
    pylint_error = safe_get(pylint, "by_type/error")
    pylint_warning = safe_get(pylint, "by_type/warning")
    avg_mi = radon_mi.get("average_mi")
    radon_total_measured = radon_cc.get("total_measured")
    max_complexity = None
    if radon_cc.get("top_complex"):
        try:
            max_complexity = max([i.get("complexity", 0) for i in radon_cc.get("top_complex")])
        except Exception:
            max_complexity = None
    pytest_total = pytest_j.get("total")
    coverage_pct = coverage.get("line_rate_percent") or coverage.get("attribs", {}).get("line-rate")
    rows.append({
        "file": f,
        "approach": approach,
        "checkpoint": checkpoint,
        "generated_at": generated_at,
        "n_files": n_files,
        "n_lines": n_lines,
        "code": code,
        "python_code": python_code,
        "blank": blank,
        "comment": comment,
        "pylint_total": pylint_total,
        "pylint_convention": pylint_conv,
        "pylint_refactor": pylint_refactor,
        "pylint_error": pylint_error,
        "pylint_warning": pylint_warning,
        "avg_mi": avg_mi,
        "radon_total_measured": radon_total_measured,
        "max_complexity": max_complexity,
        "pytest_total": pytest_total,
        "coverage_pct": coverage_pct
    })

df = pd.DataFrame(rows)
os.makedirs("data", exist_ok=True)
df.to_csv("data/metrics_all.csv", index=False)
print("Saved data/metrics_all.csv with", len(df), "rows")