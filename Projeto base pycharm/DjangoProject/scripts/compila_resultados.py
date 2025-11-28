#!/usr/bin/env python3
"""
Build a final summary.json merging cloc, pylint, radon, pytest, coverage.

This version is more tolerant: it will not fail if a tool produced plain text
instead of JSON (it will keep a "_raw" preview), and it prioritizes junit XML
pytest_results.xml when present. These changes address cases where the
collector/script produced outputs that compila_resultados couldn't parse.
Usage:
  python scripts/compila_resultados.py --dir resultados
"""
from pathlib import Path
import json
import xml.etree.ElementTree as ET
import argparse
import re
import sys
from collections import Counter
from datetime import datetime, timezone

# --- helpers ---------------------------------------------------------------
def load_json_flexible(p: Path):
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1", "cp1252"):
        try:
            s = raw.decode(enc)
        except Exception:
            continue
        try:
            return json.loads(s)
        except Exception:
            continue
    raise ValueError(f"Unable to decode/load JSON: {p}")

def read_text_safe(p: Path, maxlen=20000):
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
        if maxlen and len(txt) > maxlen:
            return txt[:maxlen] + "\n... (truncated)"
        return txt
    except Exception as e:
        return f"(failed to read text: {e})"

def find_any(base: Path, substrs):
    """Return first file under base whose name contains any of the substrs (case-insensitive)."""
    for p in base.rglob("*"):
        if p.is_file() and any(s.lower() in p.name.lower() for s in substrs):
            return p
    return None

def find_all_cloc_patterns(base: Path):
    """Return all files matching cloc_inventario_*.json under base."""
    return sorted([p for p in base.rglob("cloc_inventario_*.json") if p.is_file()])

def find_file_by_names(base: Path, names):
    """Search for files whose name matches exactly any of the names (case-insensitive).
    Returns the first match or None.
    """
    lower_names = {n.lower() for n in names}
    for p in base.rglob("*"):
        if p.is_file() and p.name.lower() in lower_names:
            return p
    return None

def find_cloc_pattern(base: Path):
    """Return the first cloc_inventario_*.json under base (or None)."""
    lst = find_all_cloc_patterns(base)
    return lst[0] if lst else None

# --- parsers ---------------------------------------------------------------
def parse_cloc(p: Path):
    try:
        data = load_json_flexible(p)
    except Exception as e:
        return {"error": f"load error: {e}", "raw": read_text_safe(p)}
    sum_block = data.get("SUM", {})
    header = data.get("header", {})
    return {
        "n_files": header.get("n_files", sum_block.get("nFiles")),
        "n_lines": header.get("n_lines"),
        "code": sum_block.get("code"),
        "blank": sum_block.get("blank"),
        "comment": sum_block.get("comment"),
        "by_language": {k: {"files": v.get("nFiles"), "code": v.get("code")} for k, v in data.items() if k not in ("header", "SUM")}
    }

def parse_pylint(p: Path):
    try:
        arr = load_json_flexible(p)
    except Exception as e:
        # keep raw output to help debugging (pylint sometimes prints plain text)
        return {"error": f"load error: {e}", "raw": read_text_safe(p)}
    counts = Counter()
    files = Counter()
    msgs = Counter()
    errors = []
    for e in arr:
        t = e.get("type", "unknown")
        counts[t] += 1
        files[e.get("path", "unknown")] += 1
        msgs[e.get("message-id") or e.get("symbol")] += 1
        if t in ("error", "fatal"):
            errors.append({"path": e.get("path"), "line": e.get("line"), "msg": e.get("message")})
    return {
        "total_issues": sum(counts.values()),
        "by_type": dict(counts),
        "top_files": files.most_common(10),
        "top_messages": msgs.most_common(10),
        "sample_errors": errors[:20]
    }

def parse_radon_cc(p: Path):
    try:
        data = load_json_flexible(p)
    except Exception as e:
        return {"error": f"load error: {e}", "raw": read_text_safe(p)}
    items = []
    for fname, lst in data.items():
        if isinstance(lst, list):
            for it in lst:
                if isinstance(it, dict) and "complexity" in it:
                    items.append({"file": fname, "name": it.get("name"), "complexity": it.get("complexity"), "rank": it.get("rank")})
    items_sorted = sorted(items, key=lambda x: (x.get("complexity") or 0), reverse=True)
    return {"total_measured": len(items), "top_complex": items_sorted[:30]}

def parse_radon_mi(p: Path):
    try:
        data = load_json_flexible(p)
    except Exception as e:
        return {"error": f"load error: {e}", "raw": read_text_safe(p)}
    rows = []
    for fname, v in data.items():
        if isinstance(v, dict):
            rows.append({"file": fname, "mi": v.get("mi"), "rank": v.get("rank")})
    vals = [r["mi"] for r in rows if r.get("mi") is not None]
    avg = round(sum(vals) / len(vals), 2) if vals else None
    return {"average_mi": avg, "files": rows}

def parse_pytest_output(p: Path):
    txt = read_text_safe(p, maxlen=20000)
    out = {}
    # try to detect passed/failed/skipped from textual pytest output
    m = re.search(r"(?P<passed>\d+)\s+passed", txt)
    if m:
        out["passed"] = int(m.group("passed"))
    m = re.search(r"(?P<failed>\d+)\s+failed", txt)
    if m:
        out["failed"] = int(m.group("failed"))
    m = re.search(r"(?P<skipped>\d+)\s+skipped", txt)
    if m:
        out["skipped"] = int(m.group("skipped"))
    # detect coverage report line if present
    m = re.search(r"Coverage XML written to file\s+(.+)", txt)
    if m:
        out["coverage_xml"] = m.group(1).strip()
    # try to detect junit xml generation line
    m = re.search(r"generated xml file:\s*(.+)", txt)
    if m:
        out["junit_xml"] = m.group(1).strip()
    return out

def parse_coverage(p: Path):
    try:
        tree = ET.parse(p)
        root = tree.getroot()
    except Exception as e:
        return {"error": f"parse error: {e}", "raw": read_text_safe(p)}
    lr = root.attrib.get("line-rate")
    pct = None
    try:
        pct = round(float(lr) * 100, 2) if lr else None
    except Exception:
        pct = None
    # include some useful numeric attrs
    attribs = dict(root.attrib)
    return {"line_rate_percent": pct, "attribs": attribs}

# --- summary builder ------------------------------------------------------
def build_summary_for_dir(target_dir: Path, cloc_file: Path = None):
    """
    Build a summary for a directory. If cloc_file is provided use it
    (useful when multiple cloc files are found in the base dir).
    """
    summary = {}
    # cloc: prefer provided cloc_file, else look for cloc_inventario_*.json
    if cloc_file:
        summary["cloc"] = parse_cloc(cloc_file)
        print(f"  - found cloc file: {cloc_file.name}")
    else:
        cloc_p = find_cloc_pattern(target_dir)
        if cloc_p:
            summary["cloc"] = parse_cloc(cloc_p)
            print(f"  - found cloc file: {cloc_p.name}")

    # pylint
    pylint_p = find_any(target_dir, ["pylint.json", "pylint_output.json"])
    if pylint_p:
        try:
            parsed = parse_pylint(pylint_p)
            summary["pylint"] = parsed
            print(f"  - found pylint: {pylint_p.name}")
        except Exception as e:
            summary["pylint_error"] = str(e)

    # radon cc
    radon_cc_p = find_any(target_dir, ["radon_cc.json", "radon-cc.json", "radon_cc"])
    if radon_cc_p:
        try:
            summary["radon_cc"] = parse_radon_cc(radon_cc_p)
            print(f"  - found radon cc: {radon_cc_p.name}")
        except Exception as e:
            summary["radon_cc_error"] = str(e)

    # radon mi
    radon_mi_p = find_any(target_dir, ["radon_mi.json", "radon-mi.json", "radon_mi"])
    if radon_mi_p:
        try:
            summary["radon_mi"] = parse_radon_mi(radon_mi_p)
            print(f"  - found radon mi: {radon_mi_p.name}")
        except Exception as e:
            summary["radon_mi_error"] = str(e)

    # pytest: prefer junit xml if present, else fall back to txt outputs
    junit = find_file_by_names(target_dir, ["pytest_results.xml", "pytest-results.xml", "junit.xml", "pytest.xml"])
    if junit:
        try:
            tree = ET.parse(junit)
            total = failed = errors = skipped = 0
            for suite in tree.findall(".//testsuite"):
                total += int(suite.attrib.get("tests", 0))
                failed += int(suite.attrib.get("failures", 0))
                errors += int(suite.attrib.get("errors", 0))
                skipped += int(suite.attrib.get("skipped", 0))
            summary["pytest"] = {"total": total, "failed": failed, "errors": errors, "skipped": skipped, "junit_xml": str(junit)}
            print(f"  - found pytest junit xml: {junit.name}")
        except Exception as e:
            summary["pytest_error"] = f"junit parse error: {e}"
    else:
        # fallback to textual outputs
        pytest_p = find_any(target_dir, ["pytest_cov.txt", "pytest_output.txt", "pytest_stdout.txt", "pytest_results.xml", "junitxml", "pytest_output"])
        if pytest_p:
            try:
                parsed = parse_pytest_output(pytest_p)
                summary["pytest"] = parsed
                print(f"  - found pytest text output: {pytest_p.name}")
                # if the text output references junit xml or coverage xml, try to pick them up
                if parsed.get("junit_xml"):
                    j = Path(parsed["junit_xml"])
                    if j.exists():
                        try:
                            tree = ET.parse(j)
                            total = failed = errors = skipped = 0
                            for suite in tree.findall(".//testsuite"):
                                total += int(suite.attrib.get("tests", 0))
                                failed += int(suite.attrib.get("failures", 0))
                                errors += int(suite.attrib.get("errors", 0))
                                skipped += int(suite.attrib.get("skipped", 0))
                            summary["pytest"].update({"total": total, "failed": failed, "errors": errors, "skipped": skipped})
                            print(f"  - parsed referenced junit xml: {j}")
                        except Exception as e:
                            summary.setdefault("pytest_meta", {})["junit_parse_error"] = str(e)
            except Exception as e:
                summary["pytest_error"] = str(e)

    # coverage: prefer coverage.xml inside target_dir
    cov = find_any(target_dir, ["coverage.xml"])
    if cov:
        try:
            summary["coverage"] = parse_coverage(cov)
            print(f"  - found coverage xml: {cov.name}")
        except Exception as e:
            summary["coverage_error"] = str(e)
    else:
        # sometimes coverage info may be referenced inside pytest text output -> try parse field
        if "pytest" in summary and isinstance(summary["pytest"], dict) and summary["pytest"].get("coverage_xml"):
            cov_path = Path(summary["pytest"]["coverage_xml"])
            if cov_path.exists():
                try:
                    summary["coverage"] = parse_coverage(cov_path)
                    print(f"  - found coverage xml referenced by pytest output: {cov_path}")
                except Exception as e:
                    summary["coverage_error"] = str(e)

    return summary

# --- main ---------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=str, default="resultados")
    args = ap.parse_args()
    base = Path(args.dir)
    if not base.exists():
        print("Directory not found:", base)
        sys.exit(2)

    full_summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "source_dir": str(base.resolve()), "entries": {}}

    # include base and each direct subdirectory
    candidate_dirs = [base]
    for p in sorted(base.iterdir()):
        if p.is_dir():
            candidate_dirs.append(p)

    for d in candidate_dirs:
        print("Scanning:", str(d))
        # Special handling: if scanning the base directory and there are multiple cloc_inventario_*.json files,
        # create one entry per cloc file (useful when you place results directly under resultados/).
        if d == base:
            cloc_files = find_all_cloc_patterns(d)
            if cloc_files:
                # if there's exactly one cloc file and other artifacts exist in base, create a "." entry (legacy)
                if len(cloc_files) == 1:
                    sub_summary = build_summary_for_dir(d, cloc_file=cloc_files[0])
                    if sub_summary:
                        key = "."
                        full_summary["entries"][key] = {"path": str(d.resolve()), "summary": sub_summary}
                else:
                    # multiple cloc files: create an entry per cloc file (key by filename without suffix)
                    for cf in cloc_files:
                        pkg_key = cf.stem
                        print(f"  - building entry for cloc file {cf.name} -> key '{pkg_key}'")
                        sub_summary = build_summary_for_dir(d, cloc_file=cf)
                        if sub_summary:
                            full_summary["entries"][pkg_key] = {"path": str(d.resolve()), "summary": sub_summary}
            else:
                # no cloc files in base: treat base as single results dir
                sub_summary = build_summary_for_dir(d)
                if sub_summary:
                    key = "."
                    full_summary["entries"][key] = {"path": str(d.resolve()), "summary": sub_summary}
        else:
            # normal subdirectory handling
            sub_summary = build_summary_for_dir(d)
            if sub_summary:
                key = str(d.relative_to(base))
                full_summary["entries"][key] = {"path": str(d.resolve()), "summary": sub_summary}

    if not full_summary["entries"]:
        print("No per-subdir results found; building a summary for the base folder (legacy fallback).")
        full_summary["entries"]["."] = {"path": str(base.resolve()), "summary": build_summary_for_dir(base)}

    outp = base / "sumario_final.json"
    outp.write_text(json.dumps(full_summary, indent=2, ensure_ascii=False), encoding='utf-8')
    print("\nWrote final summary to", outp)
    print("Summary entries:", list(full_summary["entries"].keys()))

if __name__ == "__main__":
    main()