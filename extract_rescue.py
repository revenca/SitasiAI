"""
extract_rescue.py — Ekstrak teks lengkap kueri yang HyDE rescue KONSISTEN (3/3 run):
CoT gagal (Hit=0) tapi Proposed berhasil di ketiga run. Sertakan gold + retrieval bukti.
"""
import json, re, textwrap
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
import evaluate as _ev
categorize = getattr(_ev, "_categorize", lambda t: "Lain")
src_paper = valid.groupby("page_content_sumber")["title_paper_sumber"].first().to_dict()


def papers_and_hit(pred_csv):
    df = pd.read_csv(pred_csv); res = {}
    for _, row in df.iterrows():
        para = str(row["source_paragraph"]); golds = gold_ref.get(para, [])
        if not golds: continue
        try: ctxs = json.loads(row["retrieved_contexts"]) if pd.notna(row.get("retrieved_contexts")) else []
        except Exception: ctxs = []
        rp = []
        for c in ctxs:
            p = paper_of(c)
            if p and p not in rp: rp.append(p)
        hit = any(any(tmatch(r, g) for r in rp) for g in golds)
        res[para] = (rp, hit)
    return res


cot = papers_and_hit(RES / "hasil_prediksi_cot_k5_cot_r1.csv")
prop = [papers_and_hit(RES / f"hasil_prediksi_proposed_k5_proposed_k5_r{r}.csv") for r in (1, 2, 3)]

paras = [p for p in cot if all(p in pr for pr in prop)]
consistent = [p for p in paras if cot[p][1] is False and all(pr[p][1] for pr in prop)]

print("=" * 100)
print(f"KUERI RESCUE KONSISTEN (CoT Hit=0, Proposed Hit=1 di 3/3 run): {len(consistent)} kueri")
print("=" * 100)
for i, p in enumerate(consistent, 1):
    golds = gold_ref[p]; nwords = len(p.split())
    print(f"\n{'#'*100}\nKUERI {i}  | topik={categorize(src_paper.get(p,''))} | panjang={nwords} kata")
    print("-" * 100)
    print("PARAGRAF MASUKAN (lengkap):")
    print(textwrap.fill(p, 98))
    print("\nGOLD (paper yang seharusnya disitasi):")
    for g in golds: print("  -", g)
    print("\nCoT (tanpa HyDE) menemukan paper:  [GOLD TIDAK ADA -> gagal]")
    for pp in cot[p][0]: print("  -", pp[:85])
    print("\nProposed (HyDE) run-1 menemukan paper:  [GOLD ADA -> berhasil]")
    for pp in prop[0][p][0]:
        mark = "  <-- GOLD" if any(tmatch(pp, g) for g in golds) else ""
        print(f"  - {pp[:85]}{mark}")
