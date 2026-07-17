"""
per_query_compare.py — Cari celah HyDE di level PER-KUERI.
Bandingkan Proposed (HyDE+CoT) vs CoT-only: Hit & Precision per kueri.
"Rescue" = CoT gagal (Hit=0) tapi Proposed berhasil (Hit=1).
Pakai data 3 run yang sudah ada (tanpa run baru).
"""
import json, re
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
RES = ROOT / "hasil_eksperimen"

def norm(s):
    s = str(s).strip(); s = re.sub(r"\.p?d?f?$", "", s); return s.strip().lower()
def tmatch(a, b):
    a, b = norm(a), norm(b); return bool(a and b and (a.startswith(b) or b.startswith(a)))

chunk2paper = {m["chunk_text"][:80]: m["paper_title"] for m in json.load(open("metadata.json", encoding="utf-8"))}
def paper_of(c): return chunk2paper.get(str(c)[:80], "")

gt = pd.read_csv("ground_truth_human.csv")
gt["lbl"] = gt["ground_truth"].map({True:1,False:0,1:1,0:0,"TRUE":1,"FALSE":0}).fillna(0).astype(int)
valid = gt[gt["lbl"] == 1]
gold_ref = valid.groupby("page_content_sumber")["title_paper_referensi"].apply(list).to_dict()
src_paper = valid.groupby("page_content_sumber")["title_paper_sumber"].first().to_dict()

import importlib.util
spec = importlib.util.spec_from_file_location("ev", ROOT / "evaluate.py")
# pakai _categorize dari evaluate tanpa run main
import evaluate as _ev  # evaluate.py: hanya definisi + __main__ guard? cek
categorize = getattr(_ev, "_categorize", lambda t: "Lain")


def per_query_hit_prec(pred_csv):
    df = pd.read_csv(pred_csv)
    out = {}
    for _, row in df.iterrows():
        para = str(row["source_paragraph"]); golds = gold_ref.get(para, [])
        if not golds: continue
        try: ctxs = json.loads(row["retrieved_contexts"]) if pd.notna(row.get("retrieved_contexts")) else []
        except Exception: ctxs = []
        rp = set(p for c in ctxs if (p := paper_of(c)))
        gu = []
        for g in golds:
            if not any(tmatch(g, x) for x in gu): gu.append(g)
        hits = sum(1 for g in gu if any(tmatch(r, g) for r in rp))
        out[para] = (1.0 if hits > 0 else 0.0, hits / max(len(rp), 1))
    return out


cot = per_query_hit_prec(RES / "hasil_prediksi_cot_k5_cot_r1.csv")  # deterministik
prop_runs = [per_query_hit_prec(RES / f"hasil_prediksi_proposed_k5_proposed_k5_r{r}.csv") for r in (1, 2, 3)]

paras = [p for p in cot if all(p in pr for pr in prop_runs)]
rescued, lost, prec_win = [], [], 0
for p in paras:
    cot_hit = cot[p][0]
    prop_hit_rate = sum(pr[p][0] for pr in prop_runs) / 3
    prop_prec = sum(pr[p][1] for pr in prop_runs) / 3
    if cot_hit == 0 and prop_hit_rate > 0:
        rescued.append((p, prop_hit_rate, categorize(src_paper.get(p, ""))))
    if cot_hit == 1 and prop_hit_rate < 1:
        lost.append((p, prop_hit_rate, categorize(src_paper.get(p, ""))))
    if prop_prec > cot[p][1] + 1e-9:
        prec_win += 1

print("=" * 90)
print(f"ANALISIS PER-KUERI — {len(paras)} kueri  (Proposed/HyDE vs CoT-only)")
print("=" * 90)
print(f"\nHIT@5:")
print(f"  HyDE 'rescue' (CoT gagal -> Proposed berhasil di >=1 run) : {len(rescued)} kueri")
print(f"  HyDE 'lost'   (CoT berhasil -> Proposed gagal di >=1 run) : {len(lost)} kueri")
print(f"  Net Hit (rescue - lost)                                   : {len(rescued) - len(lost):+d}")
print(f"\nPRECISION@5:")
print(f"  Kueri dgn Precision Proposed > CoT : {prec_win} / {len(paras)}")

print(f"\n--- Detail RESCUE (HyDE menemukan paper yang CoT lewatkan) ---")
for p, hr, cat in sorted(rescued, key=lambda x: -x[1]):
    cons = "konsisten 3/3" if hr == 1 else f"{int(hr*3)}/3 run"
    print(f"  [{cat:16}] ({cons})  {p[:70]}...")

print(f"\n--- Detail LOST (CoT berhasil, HyDE kadang gagal) ---")
from collections import Counter
lost_cat = Counter(c for _, _, c in lost)
print("  per kategori:", dict(lost_cat))
