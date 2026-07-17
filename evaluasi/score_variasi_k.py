"""
score_variasi_k.py — Tabel KOMPLET variasi K (3,5,10): Baseline vs Proper HyDE di clean-chunk.
Metrik: Faithfulness + Answer Relevancy (judge) + Precision/Recall/Hit@K (retrieval, sesuai K masing-masing).
Opsi B (NaN→0). 5 run tiap sel (HyDE stokastik → mean±std).

  & ".venv\\Scripts\\python.exe" score_variasi_k.py
"""
import pandas as pd
import numpy as np
from pathlib import Path

RES = Path("hasil_eksperimen")
OUT = Path("results_fresh"); OUT.mkdir(exist_ok=True)

COND = {
    3:  [("Baseline", "base_k3"),    ("HyDE", "phyde_k3")],
    5:  [("Baseline", "clean_base"), ("HyDE", "phyde")],
    10: [("Baseline", "base_k10"),   ("HyDE", "phyde_k10")],
}
LBL = ["Faithfulness", "AnsRel", "Prec@K", "Recall@K", "Hit@K"]


def metrics_of(tag_run):
    rg = pd.read_csv(RES / f"hasil_ragas_{tag_run}.csv")
    c = pd.read_csv(RES / f"hasil_ragas_{tag_run}_citation.csv").iloc[0]
    return [rg["faithfulness"].fillna(0).mean(), rg["answer_relevancy"].fillna(0).mean(),
            float(c["citation_precision"]), float(c["citation_recall"]), float(c["hit_at_k"])]


def collect(tag):
    rows = [metrics_of(f"{tag}_r{r}") for r in range(1, 6)
            if (RES / f"hasil_ragas_{tag}_r{r}_citation.csv").exists()]
    return np.array(rows) if rows else None


print("=" * 92)
print("VARIASI NILAI K — Baseline vs Proper HyDE (clean-chunk). mean±std. Opsi B (NaN→0).")
print("=" * 92)
print(f"{'K':>3} {'Kondisi':<10}{'Faithful.':>13}{'AnsRel':>11}{'Prec@K':>11}{'Recall@K':>11}{'Hit@K':>11}{'n':>4}")
print("-" * 92)
rows_csv = []
for K in [3, 5, 10]:
    for name, tag in COND[K]:
        A = collect(tag)
        if A is None:
            print(f"{K:>3} {name:<10}  (data belum ada — {tag})"); continue
        m = A.mean(0); s = A.std(0, ddof=1) if len(A) > 1 else np.zeros(5)
        cells = "".join(f"{m[i]:>8.4f}±{s[i]:4.3f}" for i in range(5))
        print(f"{K:>3} {name:<10}{cells}{len(A):>4}")
        rows_csv.append({"K": K, "Kondisi": name, "n_run": len(A),
                         **{LBL[i]: round(m[i], 4) for i in range(5)},
                         **{LBL[i] + "_std": round(s[i], 4) for i in range(5)}})
    print("-" * 92)
print("=" * 92)
pd.DataFrame(rows_csv).to_csv(OUT / "variasi_k_lengkap.csv", index=False)
print(f"Tabel → {OUT / 'variasi_k_lengkap.csv'}")
