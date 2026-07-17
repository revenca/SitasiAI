"""
one_example.py — Jalankan 1 paragraf lewat pipeline (HyDE 0.7) dengan log lengkap:
paragraf → HyDE → embed → retrieve top-5 → CoT → APA.
  & ".venv\\Scripts\\python.exe" one_example.py
"""
import os
os.environ["HYDE_TEMP"] = "0.7"
os.environ["COT_TEMP"] = "0.2"
os.environ["HYDE_WORDS"] = "100-150"
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import json, textwrap, faiss
import pipeline  # memuat SPECTER2 saat import (ada guard __main__, aman)

index = faiss.read_index("faiss_index.bin")
metadata = json.load(open("metadata.json", encoding="utf-8"))
pmeta = json.load(open("paper_metadata.json", encoding="utf-8"))

para = ("Azimuth-scanning MIMO radar can steer its transmit beam without per-element phase "
        "shifters by circulating coded signals, where the time-delay difference between "
        "antenna elements produces an equivalent phase steering.")

hyde = pipeline.hyde_generate(para)
emb = pipeline.embed(hyde)
# retrieve lalu dedup ke 5 PAPER unik (level paper, seperti yang ditampilkan sistem)
raw = pipeline.retrieve(emb, index, metadata, source_paper="", top_k=25)
seen, cands = set(), []
for c in raw:
    if c["paper_title"] in seen:
        continue
    seen.add(c["paper_title"]); cands.append(c)
    if len(cands) == 5:
        break
gen = pipeline.cot_generate(para, cands)


def apa(title):
    v = pmeta.get(title, {}); fa = v.get("first_author", ""); yr = v.get("year", "") or "n.d."
    return f"{fa} et al., {yr}" if fa else title[:40]


W = 98
print(f"\n[debug] raw chunks={len(raw)}  kandidat unik={len(cands)}")
print("=" * W)
print("PARAGRAF MASUKAN (draf pengguna):")
print(textwrap.fill(para, W))
print("\n" + "-" * W)
print("ABSTRAK HIPOTETIS (HyDE, temp 0,7):")
print(textwrap.fill(hyde, W))
print("\n" + "-" * W)
print("LIMA KANDIDAT TERATAS (K = 5):")
for i, c in enumerate(cands, 1):
    print(f"  {i}. {c['paper_title'][:80]}  (skor {c['score']:.4f})")
print("\n" + "-" * W)
best = gen.get("best_reference_paper", "")
print("KALIMAT SITASI (keluaran CoT):")
print(textwrap.fill(gen.get("citation_text", ""), W))
print("\n" + "-" * W)
print("PAPER REFERENSI :", best)
print("SITASI APA      : (" + apa(best) + ")")
print("=" * W)
