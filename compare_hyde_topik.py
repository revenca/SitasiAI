"""
compare_hyde_topik.py — Bandingkan Proposed (HyDE+CoT) vs CoT-only PER TOPIK,
untuk menemukan di mana HyDE menang. Pakai data 3 run yang sudah ada.

  & ".venv\\Scripts\\python.exe" compare_hyde_topik.py
"""
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent
RES = ROOT / "hasil_eksperimen"
OUT = ROOT / "results_multirun"
OUT.mkdir(exist_ok=True)

COLS = {"Precision": "precision_at_k", "Recall": "recall_at_k", "Hit": "hit_at_k",
        "Faithfulness": "faithfulness", "Answer_Relevancy": "answer_relevancy"}
MET = list(COLS.keys())


def load_mean(prefix):
    runs = []
    for r in (1, 2, 3):
        f = RES / f"hasil_ragas_{prefix}_r{r}_topic.csv"
        if f.exists():
            runs.append(pd.read_csv(f))
    allt = pd.concat(runs, ignore_index=True)
    out = {}
    for kat, g in allt.groupby("kategori"):
        out[kat] = {"n": int(g["n"].iloc[0]), **{m: float(g[COLS[m]].mean()) for m in MET}}
    return out


cot = load_mean("cot")
prop = load_mean("proposed_k5")
topics = sorted(set(cot) & set(prop), key=lambda k: -cot[k]["n"])

rows = []
for k in topics:
    row = {"Topik": k, "n": cot[k]["n"]}
    for m in MET:
        d = prop[k][m] - cot[k][m]
        row[f"{m}_CoT"] = round(cot[k][m], 4)
        row[f"{m}_Prop"] = round(prop[k][m], 4)
        row[f"{m}_Δ"] = round(d, 4)
    rows.append(row)
df = pd.DataFrame(rows)
df.to_csv(OUT / "compare_hyde_vs_cot_per_topik.csv", index=False)

# ── Cetak ringkas: fokus retrieval (tempat HyDE bekerja) + Faithfulness ──────
print("=" * 100)
print("PROPOSED (HyDE+CoT) vs CoT-only per TOPIK — Δ = Proposed − CoT  (positif = HyDE MENANG)")
print("=" * 100)
for m in MET:
    print(f"\n--- {m} ---")
    print(f"{'Topik':18} {'n':>3}  {'CoT':>8}  {'Proposed':>9}  {'Δ (HyDE)':>9}")
    for k in topics:
        d = prop[k][m] - cot[k][m]
        flag = "  <== HyDE menang" if d > 0.0005 else ("  (kalah)" if d < -0.0005 else "  (seri)")
        print(f"{k:18} {cot[k]['n']:>3}  {cot[k][m]:>8.4f}  {prop[k][m]:>9.4f}  {d:>+9.4f}{flag}")

# ── Ringkasan: di mana HyDE menang (Δ>0) untuk metrik retrieval ──────────────
print("\n" + "=" * 100)
print("RINGKASAN — Topik di mana HyDE MENANG (Δ>0), per metrik retrieval:")
for m in ["Precision", "Recall", "Hit"]:
    wins = [(k, prop[k][m] - cot[k][m]) for k in topics if prop[k][m] - cot[k][m] > 0.0005]
    wins.sort(key=lambda x: -x[1])
    if wins:
        s = ", ".join(f"{k}(+{d:.3f}, n={cot[k]['n']})" for k, d in wins)
        print(f"  {m:10}: {s}")
    else:
        print(f"  {m:10}: (tidak ada topik di mana HyDE menang)")
print("\nFile:", OUT / "compare_hyde_vs_cot_per_topik.csv")
