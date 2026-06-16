"""
visualize_hyde07.py — Grafik + CSV metrik untuk konfigurasi HyDE 0.7 (Gao et al., 2023).
Baseline & CoT pakai angka lama (tak pakai HyDE); HyDE & Proposed pakai hasil _hyde07.
Warna distinct per metrik + hatch (aman cetak hitam-putih). Output ke results_hyde07/.

  & ".venv\\Scripts\\python.exe" visualize_hyde07.py
"""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
RES = ROOT / "hasil_eksperimen"
OUT = ROOT / "results_hyde07"
OUT.mkdir(exist_ok=True)
plt.rcParams.update({"font.size": 10, "axes.grid": True, "grid.alpha": 0.3, "axes.axisbelow": True})

METR = ["Precision", "Recall", "Hit", "Faithfulness", "Answer Rel."]
# Palet muted/profesional (seaborn-deep) — distinct tapi kalem
CLR = {"Precision": "#4c72b0", "Recall": "#dd8452", "Hit": "#55a868",
       "Faithfulness": "#c44e52", "Answer Rel.": "#8172b3"}
HATCH = {"Precision": "", "Recall": "", "Hit": "", "Faithfulness": "", "Answer Rel.": ""}
MARK = {"Precision": "o", "Recall": "s", "Hit": "^", "Faithfulness": "D", "Answer Rel.": "v"}
LS = {"Precision": "-", "Recall": "--", "Hit": "-.", "Faithfulness": "-", "Answer Rel.": ":"}


def metrics(tag):
    c = pd.read_csv(RES / f"hasil_ragas_{tag}_citation.csv").iloc[0]
    r = pd.read_csv(RES / f"hasil_ragas_{tag}.csv")
    return {"Precision": float(c["citation_precision"]), "Recall": float(c["citation_recall"]),
            "Hit": float(c["hit_at_k"]), "Faithfulness": float(r["faithfulness"].fillna(0).mean()),
            "Answer Rel.": float(r["answer_relevancy"].mean())}


def grouped_bars(ax, groups, data, title):
    x = np.arange(len(groups)); w = 0.8 / len(METR)
    for i, m in enumerate(METR):
        vals = [data[g][m] for g in groups]
        b = ax.bar(x + i * w - 0.4 + w / 2, vals, w, label=m, color=CLR[m],
                   hatch=HATCH[m], edgecolor="white", linewidth=0.4)
        for rect, v in zip(b, vals):
            ax.text(rect.get_x() + rect.get_width() / 2, v + 0.012, f"{v:.2f}",
                    ha="center", va="bottom", fontsize=7)
    ax.set_xticks(x); ax.set_xticklabels(groups)
    ax.set_ylim(0, 1.08); ax.set_ylabel("Skor"); ax.set_title(title, fontweight="bold")
    ax.legend(fontsize=8, ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.08))


# ── 1. Ablasi (K=5) ──────────────────────────────────────────────────────────
modes = {"Baseline": "baseline_k5", "HyDE": "hyde_k5_hyde07", "CoT": "cot_k5", "Proposed": "hyde_t07"}
abl = {n: metrics(t) for n, t in modes.items()}
fig, ax = plt.subplots(figsize=(10, 5.8))
grouped_bars(ax, list(modes.keys()), abl, "Uji Kontribusi Komponen (K = 5, 144 kueri)")
fig.tight_layout(); fig.savefig(OUT / "01_ablasi_hyde07.png", dpi=150, bbox_inches="tight"); plt.close(fig)

# ── 2. Variasi K (2 panel: retrieval | generation) ───────────────────────────
ktags = {3: "proposed_k3_hyde07", 5: "hyde_t07", 10: "proposed_k10_hyde07"}
kdata = {k: metrics(t) for k, t in ktags.items()}
ks = list(ktags.keys())
# (dy, va) untuk hindari label numpuk
OFF = {"Precision": (0.018, "bottom"), "Recall": (-0.024, "top"), "Hit": (0.020, "bottom"),
       "Faithfulness": (-0.024, "top"), "Answer Rel.": (0.018, "bottom")}


def kline(ax, mlist, title):
    for m in mlist:
        ax.plot(ks, [kdata[k][m] for k in ks], marker=MARK[m], linestyle=LS[m],
                linewidth=2.3, color=CLR[m], label=(m + "@K" if m in ("Precision", "Recall", "Hit") else m))
        dy, va = OFF[m]
        for k in ks:
            ax.text(k, kdata[k][m] + dy, f"{kdata[k][m]:.2f}", ha="center", va=va, fontsize=8.5, color=CLR[m])
    ax.set_xticks(ks); ax.set_xlabel("Top-K"); ax.set_ylabel("Skor"); ax.set_ylim(0, 1.05)
    ax.set_title(title, fontweight="bold"); ax.legend(fontsize=9, loc="lower left")


fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.4))
kline(ax1, ["Precision", "Recall", "Hit"], "Metrik Retrieval")
kline(ax2, ["Faithfulness", "Answer Rel."], "Metrik Generation")
fig.suptitle("Variasi Nilai K (Mode Proposed)", fontweight="bold", y=1.00)
fig.tight_layout(); fig.savefig(OUT / "02_variasi_k_hyde07.png", dpi=150, bbox_inches="tight"); plt.close(fig)

# ── 3. Per-topik (2 panel: sampel memadai n>=22 | sampel kecil n<=5) ──────────
tp = pd.read_csv(RES / "hasil_ragas_hyde_t07_topic.csv").sort_values("n", ascending=False)
# Faithfulness per-topik NaN→0 dari raw ragas hyde_t07
import evaluate as _ev
_gt = pd.read_csv(ROOT / "ground_truth_human.csv")
_gt["_l"] = _gt["ground_truth"].map({True: 1, False: 0, 1: 1, 0: 0, "TRUE": 1, "FALSE": 0}).fillna(0).astype(int)
_src = _gt[_gt["_l"] == 1].groupby("page_content_sumber")["title_paper_sumber"].first().to_dict()
_rq = pd.read_csv(RES / "hasil_ragas_hyde_t07.csv")
_rq["_cat"] = _rq["user_input"].astype(str).map(lambda p: _ev._categorize(_src.get(p, "")))
_fmap = _rq.assign(_f=_rq["faithfulness"].fillna(0)).groupby("_cat")["_f"].mean().to_dict()
tp["faithfulness"] = tp["kategori"].map(_fmap).fillna(tp["faithfulness"])
cols = {"Precision": "precision_at_k", "Recall": "recall_at_k", "Hit": "hit_at_k",
        "Faithfulness": "faithfulness", "Answer Rel.": "answer_relevancy"}


def topic_bars(ax, df, title, faded=False):
    topics = df["kategori"].tolist(); x = np.arange(len(topics)); w = 0.16
    for i, m in enumerate(METR):
        vals = df[cols[m]].values
        ax.bar(x + i * w - 0.32, vals, w, label=m, color=CLR[m], hatch=HATCH[m],
               edgecolor="white", linewidth=0.4, alpha=(0.55 if faded else 1.0))
    ax.set_xticks(x); ax.set_xticklabels([f"{t}\n(n={n})" for t, n in zip(topics, df["n"])], fontsize=8)
    ax.set_ylim(0, 1.08); ax.set_ylabel("Skor"); ax.set_title(title, fontweight="bold")


large = tp[tp["n"] >= 22]; small = tp[tp["n"] <= 5]
fig, (axA, axB) = plt.subplots(1, 2, figsize=(13, 5.6), gridspec_kw={"width_ratios": [3, 4]})
topic_bars(axA, large, "Topik dengan Sampel Memadai (n ≥ 22)")
topic_bars(axB, small, "Topik Sampel Kecil (n ≤ 5) — interpretasi terbatas", faded=True)
handles, labels = axA.get_legend_handles_labels()
fig.legend(handles, labels, fontsize=8, ncol=5, loc="lower center", bbox_to_anchor=(0.5, -0.02))
fig.suptitle("Performa Sistem per Topik (Mode Proposed, K = 5)", fontweight="bold")
fig.tight_layout(rect=[0, 0.04, 1, 1])
fig.savefig(OUT / "04_per_topik_hyde07.png", dpi=150, bbox_inches="tight"); plt.close(fig)

# ── CSV tabel (4 desimal) ────────────────────────────────────────────────────
def crow(d): return {m: round(d[m], 4) for m in METR}
pd.DataFrame([{"Mode": n, **crow(abl[n])} for n in modes]).to_csv(OUT / "Tabel_4.3_ablasi_hyde07.csv", index=False)
pd.DataFrame([{"K": k, **crow(kdata[k])} for k in ks]).to_csv(OUT / "Tabel_4.4_variasi_k_hyde07.csv", index=False)
tp.rename(columns={"kategori": "Topik", "n": "Jumlah_Paragraf", **{v: k for k, v in cols.items()}}).round(4) \
  .to_csv(OUT / "Tabel_4.5_per_topik_hyde07.csv", index=False)

print("Selesai. Output di:", OUT)
for f in sorted(OUT.glob("*")):
    print("  -", f.name)
