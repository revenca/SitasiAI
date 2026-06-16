"""
score_sensitivity_hyde.py — Uji sensitivitas HyDE (5 run, mean±std): temperature & panjang abstrak.
Setup: clean-chunk, proper HyDE (N=5+query), K=5, CoT 0.2. Titik standar (0.7/100-150) = data 'phyde'.

  & ".venv\\Scripts\\python.exe" score_sensitivity_hyde.py
"""
import pandas as pd
import numpy as np
from pathlib import Path

RES = Path("hasil_eksperimen")
OUT = Path("results_fresh"); OUT.mkdir(exist_ok=True)


def collect(tag):
    rows = []
    for r in range(1, 6):
        rf = RES / f"hasil_ragas_{tag}_r{r}.csv"; cf = RES / f"hasil_ragas_{tag}_r{r}_citation.csv"
        if rf.exists() and cf.exists():
            rg = pd.read_csv(rf); c = pd.read_csv(cf).iloc[0]
            rows.append([rg["faithfulness"].fillna(0).mean(), rg["answer_relevancy"].fillna(0).mean(),
                         float(c["citation_precision"]), float(c["citation_recall"]), float(c["hit_at_k"])])
    return np.array(rows) if rows else None


def table(title, param, items):
    print(f"\n{'='*86}\n{title}\n{'='*86}")
    print(f"{param:<12}{'Faithful.':>15}{'AnsRel':>14}{'Prec@5':>14}{'Recall@5':>14}{'Hit@5':>14}{'n':>4}")
    print("-" * 86)
    rows = []
    for label, tag in items:
        A = collect(tag)
        if A is None:
            print(f"{label:<12}  (belum ada — {tag})"); continue
        m = A.mean(0); s = A.std(0, ddof=1) if len(A) > 1 else np.zeros(5)
        cells = "".join(f"{m[i]:>9.4f}±{s[i]:4.3f}" for i in range(5))
        print(f"{label:<12}{cells}{len(A):>4}")
        rows.append({"sweep": title, param: label, "n_run": len(A),
                     "Faithfulness": round(m[0], 4), "Faith_std": round(s[0], 4),
                     "AnsRel": round(m[1], 4), "Prec@5": round(m[2], 4),
                     "Recall@5": round(m[3], 4), "Hit@5": round(m[4], 4)})
    return rows


r1 = table("SENSITIVITAS HyDE TEMPERATURE (panjang 100-150)", "HyDE_temp",
           [("0.2", "sens_t02"), ("0.4", "sens_t04"), ("0.7", "phyde")])
r2 = table("SENSITIVITAS PANJANG ABSTRAK HyDE (temp 0.7)", "Panjang",
           [("50-80", "sens_w50"), ("100-150", "phyde"), ("200-250", "sens_w200")])

pd.DataFrame(r1 + r2).to_csv(OUT / "sensitivitas_hyde.csv", index=False)
print(f"\nTabel → {OUT / 'sensitivitas_hyde.csv'}")
print("Titik 0.7/100-150 = config standar (data phyde, 5 run).")
