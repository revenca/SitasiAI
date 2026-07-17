"""
export_sensitivity.py — Tabel + grafik untuk 3 eksperimen sensitivitas.
Jalankan SETELAH run_sensitivity.ps1 selesai.

  & ".venv\\Scripts\\python.exe" export_sensitivity.py
"""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
RES = ROOT / "hasil_eksperimen"
OUT = ROOT / "results_sensitivity"
OUT.mkdir(exist_ok=True)
CLR = {"Precision@K": "#4c72b0", "Recall@K": "#dd8452", "Hit@K": "#55a868",
       "Faithfulness": "#c44e52", "Answer_Relevancy": "#8172b3"}
plt.rcParams.update({"font.size": 10, "axes.grid": True, "grid.alpha": 0.3, "axes.axisbelow": True})


def has(tag):
    return (RES / f"hasil_ragas_{tag}_citation.csv").exists() and (RES / f"hasil_ragas_{tag}.csv").exists()


def row(tag):
    c = pd.read_csv(RES / f"hasil_ragas_{tag}_citation.csv").iloc[0]
    r = pd.read_csv(RES / f"hasil_ragas_{tag}.csv")
    return {"Precision@K": round(float(c["citation_precision"]), 4),
            "Recall@K": round(float(c["citation_recall"]), 4),
            "Hit@K": round(float(c["hit_at_k"]), 4),
            "Faithfulness": round(float(r["faithfulness"].fillna(0).mean()), 4),
            "Answer_Relevancy": round(float(r["answer_relevancy"].fillna(0).mean()), 4)}


def build(name, param, items, focus, fname_csv, fname_png, title):
    """items = list of (label_value, tag). focus = list metrik untuk grafik."""
    rows, xs = [], []
    for val, tag in items:
        if not has(tag):
            print(f"  [skip] {tag} belum ada — jalankan run_sensitivity.ps1 dulu")
            continue
        d = row(tag); d2 = {param: val, **d}; rows.append(d2); xs.append(val)
    if not rows:
        print(f"  [{name}] tidak ada data."); return
    df = pd.DataFrame(rows)
    df.to_csv(OUT / fname_csv, index=False)
    print(f"\n=== {name} ===\n{df.to_string(index=False)}")

    fig, ax = plt.subplots(figsize=(8, 5))
    for i, m in enumerate(focus):
        ax.plot(range(len(xs)), df[m].values, marker="o", linewidth=2,
                color=CLR.get(m, "#4c72b0"), label=m)
        for j, v in enumerate(df[m].values):
            ax.text(j, v + 0.012, f"{v:.2f}", ha="center", fontsize=8)
    ax.set_xticks(range(len(xs))); ax.set_xticklabels([str(x) for x in xs])
    ax.set_xlabel(param); ax.set_ylabel("Skor"); ax.set_ylim(0, 1.05)
    ax.set_title(title, fontweight="bold"); ax.legend(fontsize=9)
    fig.tight_layout(); fig.savefig(OUT / fname_png, dpi=150); plt.close(fig)


# ── A. CoT temperature (retrieval identik → fokus Faithfulness/AnsRel) ────────
build("Eksp A — CoT Temperature", "CoT_Temp",
      [(0.2, "cot_t02"), (0.5, "cot_t05"), (0.7, "cot_t07")],
      ["Faithfulness", "Answer_Relevancy"],
      "A_cot_temp.csv", "A_cot_temp.png",
      "Efek CoT Temperature terhadap Faithfulness & Answer Relevancy\n(single-run; selisih pada level noise)")

# ── B. HyDE temperature (fokus retrieval) ────────────────────────────────────
build("Eksp B — HyDE Temperature", "HyDE_Temp",
      [(0.2, "hyde_t02"), (0.4, "proposed_k5"), (0.7, "hyde_t07")],
      ["Precision@K", "Recall@K", "Hit@K"],
      "B_hyde_temp.csv", "B_hyde_temp.png",
      "Efek HyDE Temperature terhadap Retrieval (Proposed, K=5)")

# ── C. Panjang abstrak HyDE (fokus retrieval) ────────────────────────────────
build("Eksp C — Panjang HyDE", "HyDE_Words",
      [("50-80", "w50_t07"), ("100-150", "hyde_t07"), ("200-250", "w200_t07")],
      ["Precision@K", "Recall@K", "Hit@K"],
      "C_hyde_words.csv", "C_hyde_words.png",
      "Efek Panjang Abstrak HyDE terhadap Retrieval (Proposed, K=5, HyDE 0,7)")

print(f"\nSelesai. Tabel + grafik di: {OUT}")
