"""
score_phyde_retrieval.py — Gate murah: PROPER HyDE (multi-gen + avg + query) vs SPECTER2, retrieval-only, clean-chunk.
Metrik Precision/Recall/Hit@{3,5,10}. Tanpa generasi/judge. Pakai metadata clean-chunk.

  & ".venv\\Scripts\\python.exe" score_phyde_retrieval.py
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import evaluate as ev

RES = Path("hasil_eksperimen")
KS = [3, 5, 10]; METR = ["Precision", "Recall", "Hit"]
MF = "metadata_chunk_clean.json"
gt = ev.load_ground_truth()

SPEC = RES / "hasil_prediksi_baseline_k10_specter_cleanchunk.csv"   # SPECTER2-only di clean-chunk (deterministik, sudah ada)
PHY  = sorted(RES.glob("hasil_prediksi_hyde_k10_phyde_ret_r*.csv"))  # proper HyDE


def slice_ctx(df, n):
    df = df.copy()
    def sl(s):
        try: l = json.loads(s) if pd.notna(s) else []
        except Exception: l = []
        return json.dumps(l[:n], ensure_ascii=False)
    df["retrieved_contexts"] = df["retrieved_contexts"].map(sl); return df


def at(df, k):
    m = ev.citation_metrics(slice_ctx(df, k), gt, meta_file=MF)
    return {"Precision": m["citation_precision"], "Recall": m["citation_recall"], "Hit": m["hit_at_k"]}


if not SPEC.exists() or not PHY:
    raise SystemExit("[ERROR] Prediksi belum lengkap. Jalankan run_phyde_retrieval.ps1 dulu.")

spec_df = pd.read_csv(SPEC)
phy_dfs = [pd.read_csv(f) for f in PHY]
fb = sum(int(d["hyde_fallback"].sum()) if "hyde_fallback" in d.columns else 0 for d in phy_dfs)

print("=" * 80)
print(f"PROPER HyDE (multi-gen+avg+query) vs SPECTER2 — retrieval-only, clean-chunk, n_HyDE={len(phy_dfs)} run")
print(f"HyDE fallback (semua generasi gagal): {fb}")
print("=" * 80)
print(f"{'K':>3} {'Metrik':<11}{'SPECTER2':>11}{'Proper HyDE (mean±std)':>26}{'Δ':>10}")
print("-" * 80)
rows = []
for k in KS:
    sm = at(spec_df, k)
    pm = {m: (float(np.mean([at(d, k)[m] for d in phy_dfs])),
              float(np.std([at(d, k)[m] for d in phy_dfs], ddof=1)) if len(phy_dfs) > 1 else 0.0) for m in METR}
    for m in METR:
        s = sm[m]; hm, hs = pm[m]; d = hm - s
        sig = abs(d) / hs if hs > 1e-9 else float("inf")
        flag = (f"  {sig:.1f}σ{'↑' if d>0 else '↓'}") if sig != float("inf") else ""
        print(f"{k:>3} {m:<11}{s:>11.4f}{hm:>17.4f} ±{hs:5.4f}{d:>+10.4f}{flag}")
        rows.append({"K": k, "Metrik": m, "SPECTER2": round(s,4), "ProperHyDE_mean": round(hm,4),
                     "ProperHyDE_std": round(hs,4), "delta": round(d,4)})
    print("-" * 80)
Path("results_retrieval").mkdir(exist_ok=True)
pd.DataFrame(rows).to_csv("results_retrieval/proper_hyde_vs_specter.csv", index=False)
print("Tabel → results_retrieval/proper_hyde_vs_specter.csv")
