"""
aggregate_multirun.py — Agregasi 3 run independen → mean ± std.
Membaca file hasil_ragas_{tag}_r{1,2,3}.csv di hasil_eksperimen/.
Output ke results_multirun/: raw long-format, ringkasan mean±std, per-topik, cek determinisme.

  & ".venv\\Scripts\\python.exe" aggregate_multirun.py
"""
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent
RES = ROOT / "hasil_eksperimen"
OUT = ROOT / "results_multirun"
OUT.mkdir(exist_ok=True)

# (eksperimen, konfigurasi, K, file_tag) — "words100" & "HyDE 0.7" pakai proposed_k5
ROWS = [
    ("Ablasi (K=5)", "Baseline", 5, "baseline"),
    ("Ablasi (K=5)", "HyDE", 5, "hyde"),
    ("Ablasi (K=5)", "CoT", 5, "cot"),
    ("Ablasi (K=5)", "Proposed", 5, "proposed_k5"),
    ("Variasi K", "K=3", 3, "proposed_k3"),
    ("Variasi K", "K=5", 5, "proposed_k5"),
    ("Variasi K", "K=10", 10, "proposed_k10"),
    ("Sensitivitas HyDE temp", "0.2", 5, "hydetemp02"),
    ("Sensitivitas HyDE temp", "0.4", 5, "hydetemp04"),
    ("Sensitivitas HyDE temp", "0.7", 5, "proposed_k5"),
    ("Sensitivitas CoT temp", "0.2", 5, "cottemp02"),
    ("Sensitivitas CoT temp", "0.5", 5, "cottemp05"),
    ("Sensitivitas CoT temp", "0.7", 5, "cottemp07"),
    ("Sensitivitas panjang HyDE", "50-80", 5, "words50"),
    ("Sensitivitas panjang HyDE", "100-150", 5, "proposed_k5"),
    ("Sensitivitas panjang HyDE", "200-250", 5, "words200"),
]
MET = ["Precision", "Recall", "Hit", "Faithfulness", "Answer_Relevancy"]


def run_metrics(tag, run):
    cf = RES / f"hasil_ragas_{tag}_r{run}_citation.csv"
    rf = RES / f"hasil_ragas_{tag}_r{run}.csv"
    if not (cf.exists() and rf.exists()):
        return None
    c = pd.read_csv(cf).iloc[0]; r = pd.read_csv(rf)
    # Opsi B: response kosong (reject) → faithfulness 0 (NaN dari RAGAS diisi 0) demi konsistensi
    return {"Precision": float(c["citation_precision"]), "Recall": float(c["citation_recall"]),
            "Hit": float(c["hit_at_k"]), "Faithfulness": float(r["faithfulness"].fillna(0).mean()),
            "Answer_Relevancy": float(r["answer_relevancy"].fillna(0).mean())}


# ── Raw long-format + ringkasan mean±std ─────────────────────────────────────
raw_rows, summ_rows = [], []
for eksp, konf, k, tag in ROWS:
    vals = {m: [] for m in MET}
    for run in (1, 2, 3):
        rm = run_metrics(tag, run)
        if rm is None:
            continue
        raw_rows.append({"run": run, "eksperimen": eksp, "konfigurasi": konf, "K": k,
                         **{m: round(rm[m], 4) for m in MET}})
        for m in MET:
            vals[m].append(rm[m])
    n_run = len(vals["Precision"])
    row = {"eksperimen": eksp, "konfigurasi": konf, "K": k, "n_run": n_run}
    for m in MET:
        arr = np.array(vals[m])
        if n_run == 0:
            row[m] = "-"
        else:
            mean = arr.mean(); std = arr.std(ddof=1) if n_run >= 2 else 0.0
            row[m] = f"{mean:.4f} ± {std:.4f}"
    summ_rows.append(row)

raw_df = pd.DataFrame(raw_rows)
raw_df.to_csv(OUT / "raw_long.csv", index=False)
summ_df = pd.DataFrame(summ_rows)
summ_df.to_csv(OUT / "summary_mean_std.csv", index=False)

# ── Per-topik (Proposed K=5, mean±std antar 3 run) ───────────────────────────
topic_runs = []
# Opsi B: recompute faithfulness per-topik dengan NaN→0 dari raw ragas (file _topic.csv skip-NaN)
import evaluate as _ev
_gt = pd.read_csv("ground_truth_human.csv")
_gt["_lbl"] = _gt["ground_truth"].map({True: 1, False: 0, 1: 1, 0: 0, "TRUE": 1, "FALSE": 0}).fillna(0).astype(int)
_src = _gt[_gt["_lbl"] == 1].groupby("page_content_sumber")["title_paper_sumber"].first().to_dict()
for run in (1, 2, 3):
    f = RES / f"hasil_ragas_proposed_k5_r{run}_topic.csv"
    if f.exists():
        d = pd.read_csv(f); d["run"] = run
        rq = pd.read_csv(RES / f"hasil_ragas_proposed_k5_r{run}.csv")
        rq["_cat"] = rq["user_input"].astype(str).map(lambda p: _ev._categorize(_src.get(p, "")))
        fmap = rq.assign(_f=rq["faithfulness"].fillna(0)).groupby("_cat")["_f"].mean().to_dict()
        d["faithfulness"] = d["kategori"].map(fmap).fillna(d["faithfulness"])
        topic_runs.append(d)
per_topik = None
if topic_runs:
    allt = pd.concat(topic_runs, ignore_index=True)
    tmap = {"precision_at_k": "Precision", "recall_at_k": "Recall", "hit_at_k": "Hit",
            "faithfulness": "Faithfulness", "answer_relevancy": "Answer_Relevancy"}
    rows = []
    for kat, g in allt.groupby("kategori"):
        row = {"Topik": kat, "n": int(g["n"].iloc[0]), "n_run": len(g)}
        for col, lbl in tmap.items():
            mean = g[col].mean(); std = g[col].std(ddof=1) if len(g) >= 2 else 0.0
            row[lbl] = f"{mean:.4f} ± {std:.4f}"
        rows.append(row)
    per_topik = pd.DataFrame(rows).sort_values("n", ascending=False)
    per_topik.to_csv(OUT / "per_topik_mean_std.csv", index=False)

# ── Cek determinisme (Baseline & CoT retrieval harus identik antar-run) ──────
det_lines = []
for tag in ("baseline", "cot"):
    ps = [run_metrics(tag, r) for r in (1, 2, 3)]
    ps = [x for x in ps if x]
    if len(ps) >= 2:
        for m in ("Precision", "Recall", "Hit"):
            arr = np.array([x[m] for x in ps])
            ok = arr.std() < 1e-9
            det_lines.append(f"  {tag:9} {m:10}: {'IDENTIK ✓' if ok else 'BERBEDA ✗ -> ANOMALI'}  ({', '.join(f'{v:.4f}' for v in arr)})")

# ── Cetak ringkasan ──────────────────────────────────────────────────────────
print("=" * 80)
print("RINGKASAN mean ± std  (n_run per konfigurasi):")
print(summ_df.to_string(index=False))
if per_topik is not None:
    print("\n" + "=" * 80)
    print("PER-TOPIK (Proposed K=5) mean ± std:")
    print(per_topik.to_string(index=False))
print("\n" + "=" * 80)
print("VERIFIKASI DETERMINISME (retrieval Baseline & CoT harus identik antar-run):")
print("\n".join(det_lines) if det_lines else "  (belum cukup run untuk dicek)")
n_done = raw_df.groupby(["eksperimen", "konfigurasi"]).size() if len(raw_df) else []
print("\n" + "=" * 80)
print(f"Total baris raw: {len(raw_df)} (target 16 konfigurasi x 3 = 48 baris).")
print("File:", OUT)
