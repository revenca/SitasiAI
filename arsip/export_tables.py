"""
export_tables.py — Ekspor Tabel 4.1 (ablasi), 4.2 (variasi K), 4.3 (per-topik)
ke CSV siap-skripsi di folder results_tables/.

Jalankan:  & ".venv\\Scripts\\python.exe" export_tables.py
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
RES = ROOT / "hasil_eksperimen"
OUT = ROOT / "results_tables"
OUT.mkdir(exist_ok=True)


def citation(tag):
    r = pd.read_csv(RES / f"hasil_ragas_{tag}_citation.csv").iloc[0]
    return float(r["citation_precision"]), float(r["citation_recall"]), float(r["hit_at_k"])


def ragas(tag):
    df = pd.read_csv(RES / f"hasil_ragas_{tag}.csv")
    return float(df["faithfulness"].mean()), float(df["answer_relevancy"].mean())


def row(mode, k, tag):
    p, rc, h = citation(tag)
    f, a = ragas(tag)
    return {"Mode": mode, "K": k, "Precision@K": round(p, 4), "Recall@K": round(rc, 4),
            "Hit@K": round(h, 4), "Faithfulness": round(f, 4), "Answer_Relevancy": round(a, 4)}


# ── Tabel 4.1 — Studi Ablasi (K=5) ───────────────────────────────────────────
abl = pd.DataFrame([
    row("Baseline", 5, "baseline_k5"),
    row("HyDE", 5, "hyde_k5"),
    row("CoT", 5, "cot_k5"),
    row("Proposed (HyDE+CoT)", 5, "proposed_k5"),
])
abl.to_csv(OUT / "Tabel_4.1_ablasi.csv", index=False)

# ── Tabel 4.2 — Variasi K (Proposed) ─────────────────────────────────────────
kvar = pd.DataFrame([
    row("Proposed", 3, "proposed_k3"),
    row("Proposed", 5, "proposed_k5"),
    row("Proposed", 10, "proposed_k10"),
])
kvar.to_csv(OUT / "Tabel_4.2_variasi_k.csv", index=False)

# ── Tabel 4.3 — Per-topik (Proposed K=5) ─────────────────────────────────────
tp = pd.read_csv(RES / "hasil_ragas_proposed_k5_topic.csv").sort_values("n", ascending=False)
tp = tp.rename(columns={
    "kategori": "Topik", "n": "Jumlah_Paragraf", "precision_at_k": "Precision@5",
    "recall_at_k": "Recall@5", "hit_at_k": "Hit@5",
    "faithfulness": "Faithfulness", "answer_relevancy": "Answer_Relevancy",
}).round(4)
tp.to_csv(OUT / "Tabel_4.3_per_topik.csv", index=False)

print("Tersimpan di:", OUT)
for name, df in [("Tabel 4.1 — Ablasi", abl), ("Tabel 4.2 — Variasi K", kvar), ("Tabel 4.3 — Per-topik", tp)]:
    print(f"\n=== {name} ===")
    print(df.to_string(index=False))
