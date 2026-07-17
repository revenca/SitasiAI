"""
Analisis: (1) variasi K (3,5,10), (2) perbandingan per kategori topik.
Retrieval = SOURCE embedding (baseline) + SPECTER2. Gratis, tanpa API.
"""
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import re, json, faiss, torch
import pandas as pd
from transformers import AutoTokenizer
from adapters import AutoAdapterModel

DEV = "cuda" if torch.cuda.is_available() else "cpu"
tok = AutoTokenizer.from_pretrained("allenai/specter2_base")
mdl = AutoAdapterModel.from_pretrained("allenai/specter2_base")
mdl.load_adapter("allenai/specter2", source="hf", load_as="proximity", set_active=True)
mdl.set_active_adapters("proximity")
mdl.eval(); mdl.to(DEV)

def embed(text):
    x = tok(str(text), return_tensors="pt", truncation=True, max_length=512, padding=True)
    x = {k: v.to(DEV) for k, v in x.items()}
    with torch.no_grad():
        o = mdl(**x)
    e = torch.nn.functional.normalize(o.last_hidden_state[:, 0, :], dim=1)
    return e.cpu().numpy()

def norm(s):
    s = str(s).strip(); s = re.sub(r"\.p?d?f?$", "", s); return s.strip().lower()
def tmatch(a, b):
    a, b = norm(a), norm(b)
    return bool(a and b and (a.startswith(b) or b.startswith(a)))

idx = faiss.read_index("faiss_index.bin")
meta = json.load(open("metadata.json", encoding="utf-8"))
papers = [m["paper_title"] for m in meta]

g = pd.read_csv("ground_truth_human.csv")
g["lbl"] = g["ground_truth"].astype(int)
gold = g[g["lbl"] == 1].groupby("page_content_sumber").agg(
    {"title_paper_referensi": list, "title_paper_sumber": "first"}).to_dict("index")

# Kategori topik (keyword pada judul paper sumber)
def categorize(title):
    t = title.lower()
    if any(k in t for k in ["segmentation","detection","yolo","cnn","image","vision","carving","batik","convnext","mobilenet","lesion","endoscopy","u-net","printing"]): return "Computer Vision"
    if any(k in t for k in ["sign language","javanese","sarcasm","entailment","named entity","transliteration","word segmentation"]): return "NLP"
    if any(k in t for k in ["mimo","radar","ofdm","lora","hevc","positioning","reconfigurable"]): return "Telecom/Radar"
    if any(k in t for k in ["power","photovoltaic","battery","wind","energy","grid","generator","transmission","scooter","ultracapacitor","charge"]): return "Power/Energy"
    if any(k in t for k in ["eeg","brain","emotion","epileptic"]): return "Biosignal/EEG"
    if any(k in t for k in ["drone","uav","flight log","aircraft"]): return "Drone/UAV"
    if any(k in t for k in ["electronic nose","e-nose","sensor","isfet","cookies","tea"]): return "E-Nose/Sensor"
    if any(k in t for k in ["cobit","process mining","microservice","api","code smell","conformance","governance"]): return "Software Eng/IT"
    if any(k in t for k in ["forecasting","stock","credit","prediction","classification","detection","intrusion","diabetes","imputation"]): return "ML/Forecasting"
    if any(k in t for k in ["timetabling","optimization","colony","nearest neighbor"]): return "Optimization"
    return "Lainnya"

def metrics_at_k(retrieved_papers_ranked, golds, K):
    topk = retrieved_papers_ranked[:K]
    uniq = []
    for p in topk:
        if not any(tmatch(p, u) for u in uniq): uniq.append(p)
    gold_u = []
    for gg in golds:
        if not any(tmatch(gg, u) for u in gold_u): gold_u.append(gg)
    hits = sum(1 for gg in gold_u if any(tmatch(p, gg) for p in uniq))
    prec = hits / max(len(uniq), 1)
    rec  = hits / max(len(gold_u), 1)
    hit  = 1.0 if hits > 0 else 0.0
    return prec, rec, hit

# Hitung sekali: retrieve top-20 per paragraf
records = []
for src, d in gold.items():
    golds = d["title_paper_referensi"]; spaper = d["title_paper_sumber"]
    q = embed(src).reshape(1, -1).astype("float32")
    _, ids = idx.search(q, 30)
    ranked = []
    for i in ids[0]:
        if 0 <= i < len(papers) and not tmatch(papers[i], spaper):
            ranked.append(papers[i])
    records.append({"category": categorize(str(spaper)), "ranked": ranked, "golds": golds})

# ─── (1) VARIASI K ──────────────────────────────────────────────
print("="*60)
print("  ANALISIS 1 — VARIASI NILAI K (retrieval source/baseline)")
print("="*60)
print(f"  {'K':<5}{'Precision@K':>14}{'Recall@K':>12}{'Hit@K':>10}")
print("  " + "-"*40)
for K in [3, 5, 10]:
    ps, rs, hs = [], [], []
    for r in records:
        p, rc, h = metrics_at_k(r["ranked"], r["golds"], K)
        ps.append(p); rs.append(rc); hs.append(h)
    n = len(records)
    print(f"  {K:<5}{sum(ps)/n:>14.4f}{sum(rs)/n:>12.4f}{sum(hs)/n:>10.4f}")

# ─── (2) PER KATEGORI TOPIK (K=5) ───────────────────────────────
print("\n" + "="*60)
print("  ANALISIS 2 — PER KATEGORI TOPIK (K=5)")
print("="*60)
print(f"  {'Kategori':<20}{'N':>4}{'Prec@5':>9}{'Rec@5':>8}{'Hit@5':>8}")
print("  " + "-"*49)
cats = {}
for r in records:
    cats.setdefault(r["category"], []).append(r)
for cat in sorted(cats, key=lambda c: -len(cats[c])):
    rs_ = cats[cat]
    ps, rcs, hs = [], [], []
    for r in rs_:
        p, rc, h = metrics_at_k(r["ranked"], r["golds"], 5)
        ps.append(p); rcs.append(rc); hs.append(h)
    n = len(rs_)
    print(f"  {cat:<20}{n:>4}{sum(ps)/n:>9.3f}{sum(rcs)/n:>8.3f}{sum(hs)/n:>8.3f}")
