"""
score_faithfulness.py — Baseline vs HyDE (batch fresh, 5 run): Faithfulness + Answer Relevancy + retrieval@5.
Opsi B: faithfulness NaN (response kosong/reject) → 0. mean±std antar 5 run + Welch-ish (selisih vs std).
Baca hasil_ragas_fresh_base_r{1..5}.csv & hasil_ragas_fresh_prop_r{1..5}.csv.

  & ".venv\\Scripts\\python.exe" score_faithfulness.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
RES  = ROOT / "hasil_eksperimen"
OUT  = ROOT / "results_fresh"
OUT.mkdir(exist_ok=True)

METR = ["Faithfulness", "Answer_Relevancy", "Precision@5", "Recall@5", "Hit@5"]

import sys
BASE_TAG = sys.argv[1] if len(sys.argv) > 1 else "fresh_base"   # tag Baseline (mode cot)
PROP_TAG = sys.argv[2] if len(sys.argv) > 2 else "fresh_prop"   # tag HyDE (mode proposed)


def metrics_of(tag_run):
    r = pd.read_csv(RES / f"hasil_ragas_{tag_run}.csv")
    c = pd.read_csv(RES / f"hasil_ragas_{tag_run}_citation.csv").iloc[0]
    return {"Faithfulness":     float(r["faithfulness"].fillna(0).mean()),       # Opsi B
            "Answer_Relevancy": float(r["answer_relevancy"].fillna(0).mean()),
            "Precision@5":      float(c["citation_precision"]),
            "Recall@5":         float(c["citation_recall"]),
            "Hit@5":            float(c["hit_at_k"])}


def collect(tag):
    runs = []
    for run in range(1, 6):
        if (RES / f"hasil_ragas_{tag}_r{run}_citation.csv").exists():
            runs.append(metrics_of(f"{tag}_r{run}"))
    return runs


base = collect(BASE_TAG)   # Baseline (mode cot, tanpa HyDE)
prop = collect(PROP_TAG)   # HyDE   (mode proposed)
if not base or not prop:
    raise SystemExit(f"[ERROR] Data fresh belum lengkap (base={len(base)} run, prop={len(prop)} run).")


def ms(runs, m):
    v = np.array([r[m] for r in runs])
    return v.mean(), (v.std(ddof=1) if len(v) > 1 else 0.0)


print("=" * 84)
print(f"FAITHFULNESS / GENERASI — Baseline '{BASE_TAG}' (n={len(base)}) vs HyDE '{PROP_TAG}' (n={len(prop)})  [K=5, HyDE 0.7, CoT 0.2]")
print("Opsi B: faithfulness NaN→0. CoT selalu aktif di kedua kondisi; yang berbeda hanya HyDE.")
print("=" * 84)
print(f"{'Metrik':<18} {'Baseline (mean±std)':>22} {'HyDE (mean±std)':>22} {'Δ':>10}")
print("-" * 84)
rows = []
for m in METR:
    bm, bs = ms(base, m); hm, hs = ms(prop, m); d = hm - bm
    pooled = np.sqrt(((len(base)-1)*bs**2 + (len(prop)-1)*hs**2) / (len(base)+len(prop)-2)) if (len(base)+len(prop)-2) > 0 else 0.0
    sig = abs(d) / pooled if pooled > 1e-9 else float("inf")
    flag = (f"  {sig:.1f}σ↓" if d < 0 else f"  {sig:.1f}σ↑") if sig != float("inf") else ""
    print(f"{m:<18} {bm:>13.4f} ±{bs:6.4f} {hm:>13.4f} ±{hs:6.4f} {d:>+10.4f}{flag}")
    rows.append({"Metrik": m, "Baseline_mean": round(bm, 4), "Baseline_std": round(bs, 4),
                 "HyDE_mean": round(hm, 4), "HyDE_std": round(hs, 4),
                 "delta_HyDE_minus_Baseline": round(d, 4), "pooled_sigma": round(sig, 2) if sig != float("inf") else ""})
print("=" * 84)
pd.DataFrame(rows).to_csv(OUT / f"faithfulness_{BASE_TAG}_vs_{PROP_TAG}.csv", index=False)
print(f"\nTabel disimpan → {OUT / f'faithfulness_{BASE_TAG}_vs_{PROP_TAG}.csv'}")
