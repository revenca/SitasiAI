"""
score_ablation.py — Ablation 3 kondisi di index clean-chunk (mean±std antar run):
  SPECTER2 (tanpa CoT)  → SPECTER2 + CoT  → HyDE + CoT
Opsi B: faithfulness NaN→0. Baca hasil_ragas_{tag}_r{n}.csv + _citation.csv.

  & ".venv\\Scripts\\python.exe" score_ablation.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

RES = Path("hasil_eksperimen")
OUT = Path("results_fresh"); OUT.mkdir(exist_ok=True)

COND = [
    ("SPECTER2 (tanpa CoT)", "clean_specter"),
    ("SPECTER2 + CoT",       "clean_base"),
    ("HyDE + CoT",           "clean_hyde"),
]
METR = ["Faithfulness", "Answer_Relevancy", "Precision@5", "Recall@5", "Hit@5"]


def metrics_of(tag_run):
    r = pd.read_csv(RES / f"hasil_ragas_{tag_run}.csv")
    c = pd.read_csv(RES / f"hasil_ragas_{tag_run}_citation.csv").iloc[0]
    return {"Faithfulness":     float(r["faithfulness"].fillna(0).mean()),
            "Answer_Relevancy": float(r["answer_relevancy"].fillna(0).mean()),
            "Precision@5":      float(c["citation_precision"]),
            "Recall@5":         float(c["citation_recall"]),
            "Hit@5":            float(c["hit_at_k"])}


def collect(tag):
    return [metrics_of(f"{tag}_r{run}") for run in range(1, 6)
            if (RES / f"hasil_ragas_{tag}_r{run}_citation.csv").exists()]


data = {lbl: collect(tag) for lbl, tag in COND}
missing = [lbl for lbl in data if not data[lbl]]
if missing:
    print(f"[WARN] Belum ada data utk: {missing}")

def ms(runs, m):
    v = np.array([r[m] for r in runs]); return v.mean(), (v.std(ddof=1) if len(v) > 1 else 0.0)

print("=" * 92)
print("ABLATION — index clean-chunk, K=5 (mean±std). CoT & HyDE di-toggle bertahap.")
print("=" * 92)
print(f"{'Kondisi':<24}" + "".join(f"{m:>17}" for m in ["Faithful.", "AnsRel", "Prec@5", "Recall@5", "Hit@5"]))
print("-" * 92)
rows = []
for lbl, tag in COND:
    runs = data[lbl]
    if not runs:
        print(f"{lbl:<24}  (data belum ada)"); continue
    cells, row = [], {"Kondisi": lbl, "n_run": len(runs)}
    for m in METR:
        mean, sd = ms(runs, m); cells.append(f"{mean:.4f}±{sd:.3f}"); row[m] = round(mean, 4); row[m + "_std"] = round(sd, 4)
    print(f"{lbl:<24}" + "".join(f"{c:>17}" for c in cells))
    rows.append(row)
print("=" * 92)

# Delta antar tahap (efek menambah CoT, lalu menambah HyDE)
if all(data[l] for l, _ in COND):
    f = {lbl: ms(data[lbl], "Faithfulness")[0] for lbl, _ in COND}
    print("\nEfek bertahap pada Faithfulness:")
    print(f"  + CoT  (SPECTER2 → SPECTER2+CoT)     : {f['SPECTER2 + CoT'] - f['SPECTER2 (tanpa CoT)']:+.4f}")
    print(f"  + HyDE (SPECTER2+CoT → HyDE+CoT)     : {f['HyDE + CoT'] - f['SPECTER2 + CoT']:+.4f}")
    print("  Catatan: Precision@5 chunk = paper-level (hits/paper unik); Recall & Hit apple-to-apple.")

pd.DataFrame(rows).to_csv(OUT / "ablation_cleanchunk.csv", index=False)
print(f"\nTabel → {OUT / 'ablation_cleanchunk.csv'}")
