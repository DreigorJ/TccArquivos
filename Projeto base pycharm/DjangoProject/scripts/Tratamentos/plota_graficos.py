#!/usr/bin/env python3
"""
plota_graficos.py
Gera gráficos principais e salva em figures/
- boxplots por métrica e approach
- séries temporais por checkpoint (por approach)
- matriz de correlação (intensidade_IA se disponível)
"""
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os

df = pd.read_csv("data/metrics_all.csv")
metrics = {"code":"Lines of code","avg_mi":"Maintainability (MI)","pylint_total":"Pylint issues","max_complexity":"Max complexity","coverage_pct":"Coverage (%)"}
os.makedirs("figures", exist_ok=True)
for col,label in metrics.items():
    plt.figure(figsize=(8,5))
    sns.boxplot(x="approach", y=col, data=df)
    sns.stripplot(x="approach", y=col, data=df, color="0.2", jitter=True, size=4)
    plt.title(f"{label} por abordagem")
    plt.savefig(f"figures/box_{col}.png", bbox_inches='tight', dpi=150)
    plt.close()

# series by checkpoint (assume checkpoint sortable as c1,c2,...)
df['checkpoint_order'] = df['checkpoint'].str.extract(r'c(\d+)').astype(float)
for col,label in metrics.items():
    plt.figure(figsize=(9,4))
    sns.lineplot(x="checkpoint_order", y=col, hue="approach", marker="o", data=df, estimator='mean')
    plt.title(f"Evolução média de {label} por checkpoint")
    plt.xlabel("Checkpoint (c1..)")
    plt.ylabel(label)
    plt.savefig(f"figures/series_{col}.png", bbox_inches='tight', dpi=150)
    plt.close()

print("Saved figures/*.png")