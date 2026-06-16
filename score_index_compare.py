"""
score_index_compare.py — SPECTER2-only retrieval di 3 index berbeda (perbandingan REPRESENTASI DOKUMEN).
Query = paragraf mentah (deterministik, tanpa HyDE, tanpa generasi/judge). Metrik @3/@5/@10.
Tiap index dipetakan ke metadata-nya sendiri (chunk_text→paper_title).

  & ".venv\\Scripts\\python.exe" score_index_compare.py
"""
import json
from pathlib import Path
import pandas as pd
import evaluate as ev

ROOT = Path(__file__).resolve().parent
RES  = ROOT / "hasil_eksperimen"
OUT  = ROOT / "results_index_compare"
OUT.mkdir(exist_ok=True)
KS = [3, 5, 10]
gt = ev.load_ground_truth()

# (label, pred_file, metadata_file)
INDEXES = [
    ("Dirty-Chunk (11066 vek)",  "hasil_prediksi_baseline_k10_specter_dirty.csv",      "metadata.json"),
    ("Clean-Chunk (9473 vek)",   "hasil_prediksi_baseline_k10_specter_cleanchunk.csv", "metadata_chunk_clean.json"),
    ("Clean-Abstract (100 vek)", "hasil_prediksi_baseline_k10_specter_cleanabs.csv",   "metadata_abstract_clean.json"),
]


def slice_ctx(df, n):
    df = df.copy()
    def sl(s):
        try:
            l = json.loads(s) if pd.notna(s) else []
        except Exception:
            l = []
        return json.dumps(l[:n], ensure_ascii=False)
    df["retrieved_contexts"] = df["retrieved_contexts"].map(sl)
    return df


rows = []
for label, pf, mf in INDEXES:
    p = RES / pf
    if not p.exists():
        print(f"[SKIP] {label}: {pf} belum ada"); continue
    df = pd.read_csv(p)
    for k in KS:
        m = ev.citation_metrics(slice_ctx(df, k), gt, meta_file=mf)
        rows.append({"Index": label, "K": k,
                     "Precision": round(m["citation_precision"], 4),
                     "Recall": round(m["citation_recall"], 4),
                     "Hit": round(m["hit_at_k"], 4)})

if not rows:
    raise SystemExit("[ERROR] Tidak ada prediksi. Jalankan run_compare_indexes_specter.ps1 dulu.")

df = pd.DataFrame(rows)
df.to_csv(OUT / "specter_index_compare.csv", index=False)

print("=" * 78)
print("SPECTER2-only (paragraf mentah) — PERBANDINGAN REPRESENTASI DOKUMEN")
print("144 kueri | deterministik | tanpa HyDE | tanpa generasi/judge")
print("=" * 78)
for k in KS:
    print(f"\n── K = {k} " + "─" * 60)
    print(f"  {'Index':<26}{'Precision':>11}{'Recall':>10}{'Hit':>9}")
    sub = df[df["K"] == k]
    for _, r in sub.iterrows():
        print(f"  {r['Index']:<26}{r['Precision']:>11.4f}{r['Recall']:>10.4f}{r['Hit']:>9.4f}")
print("\n" + "=" * 78)
print("Catatan: Precision = hits / jumlah PAPER unik yang ter-retrieve (paper-level).")
print("  Abstrak (1 vektor/paper) → top-K = K paper berbeda; chunk → K chunk bisa < K paper.")
print("  Recall & Hit paling apple-to-apple antar arsitektur.")
print(f"\nTabel → {OUT / 'specter_index_compare.csv'}")
