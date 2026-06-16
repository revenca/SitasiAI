"""
visualize_results.py — Grafik hasil eksperimen SitasiAI.
Membaca CSV hasil (citation + RAGAS + per-topik) → simpan PNG ke results_viz/.

Jalankan:  & ".venv\\Scripts\\python.exe" visualize_results.py
"""
import os
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
RES = ROOT / "hasil_eksperimen"
OUT = ROOT / "results_viz"
OUT.mkdir(exist_ok=True)

# Palet biru ITS
COLORS = ["#1e3a8a", "#1d4ed8", "#2563eb", "#60a5fa", "#93c5fd"]
plt.rcParams.update({"font.size": 10, "axes.grid": True,
                     "grid.alpha": 0.3, "axes.axisbelow": True})


def load_citation(tag):
    df = pd.read_csv(RES / f"hasil_ragas_{tag}_citation.csv")
    r = df.iloc[0]
    return {"Precision": float(r["citation_precision"]),
            "Recall": float(r["citation_recall"]),
            "Hit": float(r["hit_at_k"])}


def load_ragas(tag):
    df = pd.read_csv(RES / f"hasil_ragas_{tag}.csv")
    return {"Faithfulness": float(df["faithfulness"].mean()),
            "Answer Rel.": float(df["answer_relevancy"].mean())}


def metrics(tag):
    return {**load_citation(tag), **load_ragas(tag)}


def bars(ax, groups, series, values, title, ylabel="Skor"):
    x = np.arange(len(groups)); w = 0.8 / len(series)
    for i, s in enumerate(series):
        vals = [values[g][s] for g in groups]
        b = ax.bar(x + i * w - 0.4 + w / 2, vals, w, label=s, color=COLORS[i % len(COLORS)])
        for rect, v in zip(b, vals):
            ax.text(rect.get_x() + rect.get_width() / 2, v + 0.01, f"{v:.2f}",
                    ha="center", va="bottom", fontsize=7)
    ax.set_xticks(x); ax.set_xticklabels(groups)
    ax.set_ylim(0, 1.05); ax.set_ylabel(ylabel); ax.set_title(title, fontweight="bold")
    ax.legend(fontsize=8, ncol=len(series))


# ── 1. Studi Ablasi (K=5) ────────────────────────────────────────────────────
modes = {"Baseline": "baseline_k5", "HyDE": "hyde_k5", "CoT": "cot_k5", "Proposed": "proposed_k5"}
abl = {name: metrics(tag) for name, tag in modes.items()}
METR = ["Precision", "Recall", "Hit", "Faithfulness", "Answer Rel."]

fig, ax = plt.subplots(figsize=(10, 5.5))
bars(ax, list(modes.keys()), METR, abl, "Studi Ablasi (K=5, 144 paragraf — Ground Truth Human)")
fig.tight_layout(); fig.savefig(OUT / "01_ablasi.png", dpi=150); plt.close(fig)

# ── 2. Variasi K (Proposed: K=3,5,10) ────────────────────────────────────────
ktags = {3: "proposed_k3", 5: "proposed_k5", 10: "proposed_k10"}
kdata = {k: metrics(t) for k, t in ktags.items()}
ks = list(ktags.keys())

fig, ax = plt.subplots(figsize=(9, 5.5))
for i, m in enumerate(METR):
    ax.plot(ks, [kdata[k][m] for k in ks], marker="o", linewidth=2,
            color=COLORS[i % len(COLORS)], label=m)
    for k in ks:
        ax.text(k, kdata[k][m] + 0.012, f"{kdata[k][m]:.2f}", ha="center", fontsize=7)
ax.set_xticks(ks); ax.set_xlabel("Top-K"); ax.set_ylabel("Skor")
ax.set_ylim(0, 1.05); ax.set_title("Variasi K — Metode Proposed (HyDE + CoT)", fontweight="bold")
ax.legend(fontsize=8, ncol=3)
fig.tight_layout(); fig.savefig(OUT / "02_variasi_k.png", dpi=150); plt.close(fig)

# ── 3. Trade-off Precision/Recall/Hit terhadap K ─────────────────────────────
fig, ax = plt.subplots(figsize=(8, 5))
for i, m in enumerate(["Precision", "Recall", "Hit"]):
    ax.plot(ks, [kdata[k][m] for k in ks], marker="s", linewidth=2.2,
            color=COLORS[i], label=m + "@K")
    for k in ks:
        ax.text(k, kdata[k][m] + 0.012, f"{kdata[k][m]:.2f}", ha="center", fontsize=8)
ax.set_xticks(ks); ax.set_xlabel("Top-K"); ax.set_ylabel("Skor")
ax.set_ylim(0, 1.05); ax.set_title("Trade-off Retrieval terhadap K (Proposed)", fontweight="bold")
ax.legend(fontsize=9)
fig.tight_layout(); fig.savefig(OUT / "03_tradeoff_k.png", dpi=150); plt.close(fig)

# ── 4. Per-topik (Proposed K=5) ──────────────────────────────────────────────
tp = pd.read_csv(RES / "hasil_ragas_proposed_k5_topic.csv").sort_values("n", ascending=False)
topics = tp["kategori"].tolist()
cols = {"Precision": "precision_at_k", "Recall": "recall_at_k", "Hit": "hit_at_k",
        "Faithfulness": "faithfulness", "Answer Rel.": "answer_relevancy"}

fig, ax = plt.subplots(figsize=(12, 6))
x = np.arange(len(topics)); w = 0.16
for i, (lbl, col) in enumerate(cols.items()):
    ax.bar(x + i * w - 0.32, tp[col].values, w, label=lbl, color=COLORS[i % len(COLORS)])
ax.set_xticks(x)
ax.set_xticklabels([f"{t}\n(n={n})" for t, n in zip(topics, tp["n"])], fontsize=8)
ax.set_ylim(0, 1.08); ax.set_ylabel("Skor")
ax.set_title("Performa per-Topik — Proposed (K=5)", fontweight="bold")
ax.legend(fontsize=8, ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.12))
fig.tight_layout(); fig.savefig(OUT / "04_per_topik.png", dpi=150); plt.close(fig)

# ── 5. Ringkasan tabel → PNG ─────────────────────────────────────────────────
rows = []
for name, tag in modes.items():
    m = abl[name]; rows.append([name, "5"] + [f"{m[k]:.4f}" for k in METR])
for k in ks:
    m = kdata[k]; rows.append([f"Proposed", str(k)] + [f"{m[mk]:.4f}" for mk in METR])
fig, ax = plt.subplots(figsize=(11, 3.4)); ax.axis("off")
tbl = ax.table(cellText=rows, colLabels=["Mode", "K"] + METR, loc="center", cellLoc="center")
tbl.auto_set_font_size(False); tbl.set_fontsize(9); tbl.scale(1, 1.5)
for j in range(len(METR) + 2):
    tbl[0, j].set_facecolor("#1e3a8a"); tbl[0, j].set_text_props(color="white", fontweight="bold")
ax.set_title("Rekap Metrik — Ablasi + Variasi K", fontweight="bold", pad=14)
fig.tight_layout(); fig.savefig(OUT / "05_tabel_rekap.png", dpi=150); plt.close(fig)

print("Selesai. 5 grafik tersimpan di:", OUT)
for f in sorted(OUT.glob("*.png")):
    print("  -", f.name)
