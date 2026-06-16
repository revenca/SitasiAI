"""
score_retrieval.py — Uji RETRIEVAL MURNI: SPECTER2 saja vs HyDE+SPECTER2 (batch fresh, 5 run tiap sisi).
Hanya metrik retrieval (Precision/Recall/Hit@K) dari paper hasil retrieve vs ground truth.
TANPA generasi, TANPA LLM judge. SPECTER2 dijalankan 5x utk MEMBUKTIKAN determinisme (std≈0), bukan diasumsikan.
Skor pakai fungsi tervalidasi evaluate.citation_metrics (retrieved_contexts di-slice utk @3/@5/@10).

  & ".venv\\Scripts\\python.exe" score_retrieval.py
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import evaluate as ev

ROOT = Path(__file__).resolve().parent
RES  = ROOT / "hasil_eksperimen"
OUT  = ROOT / "results_retrieval"
OUT.mkdir(exist_ok=True)

KS = [3, 5, 10]
METR = ["Precision", "Recall", "Hit"]
gt = ev.load_ground_truth()

SPECTER_FILES = sorted(RES.glob("hasil_prediksi_baseline_k10_fresh_specter_r*.csv"))
HYDE_FILES    = sorted(RES.glob("hasil_prediksi_hyde_k10_fresh_hyderet_r*.csv"))


def slice_ctx(df, n):
    df = df.copy()
    def sl(s):
        try:
            lst = json.loads(s) if pd.notna(s) else []
        except Exception:
            lst = []
        return json.dumps(lst[:n], ensure_ascii=False)
    df["retrieved_contexts"] = df["retrieved_contexts"].map(sl)
    return df


def metrics_at(df, k):
    m = ev.citation_metrics(slice_ctx(df, k), gt)
    return {"Precision": m["citation_precision"], "Recall": m["citation_recall"], "Hit": m["hit_at_k"]}


def agg(runs, k):
    per = [metrics_at(df, k) for df in runs]
    return {m: (float(np.mean([p[m] for p in per])),
                float(np.std([p[m] for p in per], ddof=1)) if len(per) > 1 else 0.0)
            for m in METR}


if not SPECTER_FILES:
    raise SystemExit("[ERROR] File SPECTER2 (hasil_prediksi_baseline_k10_fresh_specter_r*.csv) belum ada.")
if not HYDE_FILES:
    raise SystemExit("[ERROR] File HyDE (hasil_prediksi_hyde_k10_fresh_hyderet_r*.csv) belum ada.")

specter_runs = [pd.read_csv(f) for f in SPECTER_FILES]
hyde_runs    = [pd.read_csv(f) for f in HYDE_FILES]
fb_total = sum(int(df["hyde_fallback"].sum()) if "hyde_fallback" in df.columns else 0 for df in hyde_runs)

spec = {k: agg(specter_runs, k) for k in KS}
hyde = {k: agg(hyde_runs, k) for k in KS}

# Determinisme SPECTER2: std maksimum antar-run (harus ~0)
spec_max_std = max(spec[k][m][1] for k in KS for m in METR)

print("=" * 86)
print(f"UJI RETRIEVAL MURNI — SPECTER2 (n={len(specter_runs)} run) vs HyDE (n={len(hyde_runs)} run)")
print(f"144 kueri | tanpa generasi | tanpa LLM judge | HyDE temp 0.7")
print(f"HyDE fallback: {fb_total} baris " + ("(semua kueri pakai HyDE asli)" if fb_total == 0 else "⚠️ HyDE GAGAL di sebagian baris!"))
print(f"SPECTER2 std maks antar-run: {spec_max_std:.6f} " +
      ("→ DETERMINISTIK TERBUKTI (5 run identik)" if spec_max_std < 1e-6 else "→ ada variasi kecil"))
print("=" * 86)
print(f"{'K':>3} {'Metrik':<11} {'SPECTER2 (mean±std)':>22} {'HyDE (mean±std)':>20} {'Δ':>10}")
print("-" * 86)
rows = []
for k in KS:
    for m in METR:
        sm, ss = spec[k][m]; hm, hs = hyde[k][m]; d = hm - sm
        sig = abs(d) / hs if hs > 1e-9 else float("inf")
        flag = (f"  {sig:.1f}σ↓" if d < 0 else f"  {sig:.1f}σ↑") if sig != float("inf") else ""
        print(f"{k:>3} {m:<11} {sm:>13.4f} ±{ss:6.4f} {hm:>13.4f} ±{hs:5.4f} {d:>+10.4f}{flag}")
        rows.append({"K": k, "Metrik": m, "SPECTER2_mean": round(sm, 4), "SPECTER2_std": round(ss, 6),
                     "HyDE_mean": round(hm, 4), "HyDE_std": round(hs, 4),
                     "delta_HyDE_minus_SPECTER": round(d, 4), "sigma": round(sig, 2) if sig != float("inf") else ""})
    print("-" * 86)
print("=" * 86)

pd.DataFrame(rows).to_csv(OUT / "retrieval_specter_vs_hyde.csv", index=False)
print(f"\nTabel disimpan → {OUT / 'retrieval_specter_vs_hyde.csv'}")
