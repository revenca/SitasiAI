"""
visualize_multirun.py — Grafik mean ± std (error bar) dari 3 run independen.
Baca raw_long.csv (per-run) + file per-topik per-run. Output ke results_multirun/.

  & ".venv\\Scripts\\python.exe" visualize_multirun.py
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
RES = ROOT / "hasil_eksperimen"
OUT = ROOT / "results_multirun"
OUT.mkdir(exist_ok=True)
plt.rcParams.update({"font.size": 10, "axes.grid": True, "grid.alpha": 0.3, "axes.axisbelow": True})

CLR = {"Precision": "#4c72b0", "Recall": "#dd8452", "Hit": "#55a868",
       "Faithfulness": "#c44e52", "Answer Rel.": "#8172b3"}
MARK = {"Precision": "o", "Recall": "s", "Hit": "^", "Faithfulness": "D", "Answer Rel.": "v"}
COL = {"Precision": "Precision", "Recall": "Recall", "Hit": "Hit",
       "Faithfulness": "Faithfulness", "Answer Rel.": "Answer_Relevancy"}
METR = list(CLR.keys())

raw = pd.read_csv(OUT / "raw_long.csv")


def ms(df, konf, m):
    v = df[df["konfigurasi"] == konf][COL[m]].values
    return v.mean(), (v.std(ddof=1) if len(v) >= 2 else 0.0)


def bars_err(ax, order, sub, title):
    x = np.arange(len(order)); w = 0.8 / len(METR)
    for i, m in enumerate(METR):
        means = [ms(sub, k, m)[0] for k in order]
        stds = [ms(sub, k, m)[1] for k in order]
        ax.bar(x + i * w - 0.4 + w / 2, means, w, yerr=stds, capsize=3,
               label=m, color=CLR[m], edgecolor="white", linewidth=0.4,
               error_kw={"elinewidth": 0.9, "ecolor": "#444"})
    ax.set_xticks(x); ax.set_xticklabels(order); ax.set_ylim(0, 1.08); ax.set_ylabel("Skor")
    ax.set_title(title, fontweight="bold")
    ax.legend(fontsize=8, ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.08))


def line_2panel(sub, xs, xlabel, suptitle, fname):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.2))
    for ax, mlist, ttl in [(a1, ["Precision", "Recall", "Hit"], "Metrik Retrieval"),
                           (a2, ["Faithfulness", "Answer Rel."], "Metrik Generation")]:
        for m in mlist:
            means = [ms(sub, k, m)[0] for k in xs]
            stds = [ms(sub, k, m)[1] for k in xs]
            ax.errorbar(range(len(xs)), means, yerr=stds, marker=MARK[m], capsize=4,
                        linewidth=2, color=CLR[m], label=(m + "@K" if m in ("Precision", "Recall", "Hit") else m))
        ax.set_xticks(range(len(xs))); ax.set_xticklabels([str(x) for x in xs])
        ax.set_xlabel(xlabel); ax.set_ylabel("Skor"); ax.set_ylim(0, 1.05)
        ax.set_title(ttl, fontweight="bold"); ax.legend(fontsize=9, loc="lower left")
    fig.suptitle(suptitle, fontweight="bold", y=1.00)
    fig.tight_layout(); fig.savefig(OUT / fname, dpi=150, bbox_inches="tight"); plt.close(fig)


# ── 1. Ablasi ────────────────────────────────────────────────────────────────
sub = raw[raw["eksperimen"] == "Ablasi (K=5)"]
fig, ax = plt.subplots(figsize=(10, 5.8))
bars_err(ax, ["Baseline", "HyDE", "CoT", "Proposed"], sub, "Uji Kontribusi Komponen (K = 5, mean ± std, 3 run)")
fig.tight_layout(); fig.savefig(OUT / "G1_ablasi_errbar.png", dpi=150, bbox_inches="tight"); plt.close(fig)

# ── 2. Variasi K ─────────────────────────────────────────────────────────────
line_2panel(raw[raw["eksperimen"] == "Variasi K"], ["K=3", "K=5", "K=10"], "Top-K",
            "Variasi Nilai K (mean ± std, 3 run)", "G2_variasi_k_errbar.png")

# ── 3. Sensitivitas HyDE temp ────────────────────────────────────────────────
line_2panel(raw[raw["eksperimen"] == "Sensitivitas HyDE temp"], ["0.2", "0.4", "0.7"], "Temperature HyDE",
            "Sensitivitas Temperature HyDE (mean ± std, 3 run)", "G3_hyde_temp_errbar.png")

# ── 4. Sensitivitas CoT temp ─────────────────────────────────────────────────
line_2panel(raw[raw["eksperimen"] == "Sensitivitas CoT temp"], ["0.2", "0.5", "0.7"], "Temperature CoT",
            "Sensitivitas Temperature CoT (mean ± std, 3 run)", "G4_cot_temp_errbar.png")

# ── 5. Sensitivitas panjang HyDE ─────────────────────────────────────────────
line_2panel(raw[raw["eksperimen"] == "Sensitivitas panjang HyDE"], ["50-80", "100-150", "200-250"], "Panjang abstrak (kata)",
            "Sensitivitas Panjang Abstrak HyDE (mean ± std, 3 run)", "G5_panjang_errbar.png")

# ── 6. Per-topik (2 panel: memadai | n<=5 faded) ─────────────────────────────
tcols = {"Precision": "precision_at_k", "Recall": "recall_at_k", "Hit": "hit_at_k",
         "Faithfulness": "faithfulness", "Answer Rel.": "answer_relevancy"}
import evaluate as _ev
_gt = pd.read_csv(ROOT / "ground_truth_human.csv")
_gt["_lbl"] = _gt["ground_truth"].map({True: 1, False: 0, 1: 1, 0: 0, "TRUE": 1, "FALSE": 0}).fillna(0).astype(int)
_src = _gt[_gt["_lbl"] == 1].groupby("page_content_sumber")["title_paper_sumber"].first().to_dict()
runs = []
for r in (1, 2, 3):
    f = RES / f"hasil_ragas_proposed_k5_r{r}_topic.csv"
    if f.exists():
        d = pd.read_csv(f)
        rq = pd.read_csv(RES / f"hasil_ragas_proposed_k5_r{r}.csv")
        rq["_cat"] = rq["user_input"].astype(str).map(lambda p: _ev._categorize(_src.get(p, "")))
        fmap = rq.assign(_f=rq["faithfulness"].fillna(0)).groupby("_cat")["_f"].mean().to_dict()
        d["faithfulness"] = d["kategori"].map(fmap).fillna(d["faithfulness"])  # NaN→0 (Opsi B)
        runs.append(d)
allt = pd.concat(runs, ignore_index=True)
agg = {}
for kat, g in allt.groupby("kategori"):
    agg[kat] = {"n": int(g["n"].iloc[0]),
                **{m: (g[c].mean(), g[c].std(ddof=1) if len(g) >= 2 else 0.0) for m, c in tcols.items()}}
order = sorted(agg, key=lambda k: -agg[k]["n"])
large = [k for k in order if agg[k]["n"] >= 22]
small = [k for k in order if agg[k]["n"] <= 5]


def topic_panel(ax, names, title, faded=False):
    x = np.arange(len(names)); w = 0.16
    for i, m in enumerate(METR):
        means = [agg[k][m][0] for k in names]; stds = [agg[k][m][1] for k in names]
        ax.bar(x + i * w - 0.32, means, w, yerr=stds, capsize=2.5, label=m, color=CLR[m],
               edgecolor="white", linewidth=0.4, alpha=(0.55 if faded else 1.0),
               error_kw={"elinewidth": 0.8, "ecolor": "#555"})
    ax.set_xticks(x); ax.set_xticklabels([f"{k}\n(n={agg[k]['n']})" for k in names], fontsize=8)
    ax.set_ylim(0, 1.12); ax.set_ylabel("Skor"); ax.set_title(title, fontweight="bold")


fig, (axA, axB) = plt.subplots(1, 2, figsize=(13, 5.8), gridspec_kw={"width_ratios": [3, 4]})
topic_panel(axA, large, "Topik dengan Sampel Memadai (n ≥ 22)")
topic_panel(axB, small, "Topik Sampel Kecil (n ≤ 5) — interpretasi terbatas", faded=True)
h, l = axA.get_legend_handles_labels()
fig.legend(h, l, fontsize=8, ncol=5, loc="lower center", bbox_to_anchor=(0.5, -0.02))
fig.suptitle("Performa Sistem per Topik (Mode Proposed, K = 5, mean ± std)", fontweight="bold")
fig.tight_layout(rect=[0, 0.04, 1, 1]); fig.savefig(OUT / "G6_per_topik_errbar.png", dpi=150, bbox_inches="tight"); plt.close(fig)

print("Selesai. Grafik error-bar di:", OUT)
for f in sorted(OUT.glob("G*.png")):
    print("  -", f.name)
