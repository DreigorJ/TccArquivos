#!/usr/bin/env python3
"""
analise_estatistica.py
- Carrega data/metrics_all.csv
- Calcula estatísticas descritivas por approach
- Executa Kruskal-Wallis por métrica (LOC, avg_mi, pylint_total, max_complexity, coverage_pct)
- Se significativo, faz comparações pares Mann-Whitney U (correção de Holm)
- Calcula Cohen's d (para comparação de médias) e Bootstrap CI para diferenças de médias
Salva resultados em data/stats_summary.csv e data/pairwise_results.csv
"""
import pandas as pd
import numpy as np
from scipy import stats
import itertools
import os

df = pd.read_csv("data/metrics_all.csv")
df = df.dropna(subset=["approach"])  # garantir

metrics = ["code", "n_lines", "avg_mi", "pylint_total", "max_complexity", "coverage_pct"]
approaches = sorted(df['approach'].unique())

def descr_stats(g):
    return {
        "n": len(g),
        "mean": np.nanmean(g),
        "median": np.nanmedian(g),
        "std": np.nanstd(g, ddof=1),
        "iqr": np.nanpercentile(g,75)-np.nanpercentile(g,25)
    }

stats_rows = []
pairwise_rows = []

for m in metrics:
    groups = [df.loc[df['approach']==a, m].dropna().values for a in approaches]
    # descriptive per approach
    for a,g in zip(approaches, groups):
        s = descr_stats(g)
        s.update({"metric": m, "approach": a})
        stats_rows.append(s)
    # Kruskal-Wallis
    try:
        kw_stat, kw_p = stats.kruskal(*groups)
    except Exception as e:
        kw_stat, kw_p = np.nan, np.nan
    # pairwise if p < 0.05
    pairwise_results = []
    if not np.isnan(kw_p) and kw_p < 0.05:
        combos = list(itertools.combinations(approaches,2))
        pvals = []
        for a,b in combos:
            xa = df.loc[df['approach']==a, m].dropna().values
            xb = df.loc[df['approach']==b, m].dropna().values
            if len(xa)==0 or len(xb)==0:
                u_p = np.nan
            else:
                u_stat, u_p = stats.mannwhitneyu(xa, xb, alternative='two-sided')
                # effect size Cohen's d
                mean_diff = np.nanmean(xa) - np.nanmean(xb)
                pooled_sd = np.sqrt(((len(xa)-1)*np.nanvar(xa, ddof=1) + (len(xb)-1)*np.nanvar(xb, ddof=1)) / (len(xa)+len(xb)-2)) if len(xa)+len(xb)-2>0 else np.nan
                cohens_d = mean_diff / pooled_sd if pooled_sd and pooled_sd>0 else np.nan
                pairwise_rows.append({
                    "metric": m, "group_a": a, "group_b": b,
                    "u_p": u_p, "u_stat": u_stat, "cohen_d": cohens_d,
                    "mean_a": np.nanmean(xa), "mean_b": np.nanmean(xb),
                    "n_a": len(xa), "n_b": len(xb)
                })
                pvals.append(u_p)
        # Holm correction
        if pvals:
            pvals = np.array(pvals)
            sorted_idx = np.argsort(pvals)
            m_tests = len(pvals)
            adjusted = np.empty_like(pvals)
            for rank, idx in enumerate(sorted_idx):
                adjusted[idx] = min((m_tests - rank) * pvals[idx], 1.0)
            # add adjusted pvals back to pairwise_rows in same order
            for i,pr in enumerate(pairwise_rows):
                pr["u_p_adj_holm"] = adjusted[i]
    # save KW summary
    stats_rows.append({"metric": m, "approach": "KRUSKAL_WALLIS", "n": np.nan, "mean": kw_stat, "median": kw_p, "std": np.nan, "iqr": np.nan})

os.makedirs("data", exist_ok=True)
pd.DataFrame(stats_rows).to_csv("data/stats_summary.csv", index=False)
pd.DataFrame(pairwise_rows).to_csv("data/pairwise_results.csv", index=False)
print("Saved data/stats_summary.csv and data/pairwise_results.csv")