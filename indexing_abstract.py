"""
indexing_abstract.py — Arsitektur ALTERNATIF: index per-paper dari JUDUL + ABSTRAK
(format kanonik SPECTER2: "title [SEP] abstract" → 1 vektor/paper), BUKAN chunk body.

Output TERPISAH (tidak menimpa index lama):
  - faiss_index_abstract.bin     (≈100 vektor, 1 per paper)
  - metadata_abstract.json       (schema sama: paper_title + chunk_text)  ← chunk_text = abstrak
  - extracted_abstracts.csv      (QA: cek kualitas ekstraksi abstrak per paper)

Index lama (faiss_index.bin / metadata.json, 11.066 chunk) TIDAK disentuh.

Pakai di pipeline/evaluate (setelah path di-env-kan):
  $env:FAISS_INDEX_FILE="faiss_index_abstract.bin"; $env:METADATA_FILE="metadata_abstract.json"

Jalankan:
  & ".venv\\Scripts\\python.exe" indexing_abstract.py
"""
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import json
import re
import sys
import numpy as np
import pandas as pd
import faiss
import torch
from pathlib import Path
from transformers import AutoTokenizer
from adapters import AutoAdapterModel

# ── CONFIG ─────────────────────────────────────────────────────────────────────
OUTPUT_TEKS_DIR  = os.getenv("OUTPUT_TEKS_DIR", "output_teks")
FAISS_OUT        = os.getenv("FAISS_INDEX_FILE", "faiss_index_abstract.bin")
METADATA_OUT     = os.getenv("METADATA_FILE",   "metadata_abstract.json")
QA_CSV           = "extracted_abstracts.csv"

MODEL_NAME   = "allenai/specter2_base"   # sama dgn indexing.py / pipeline.py
ADAPTER_NAME = "allenai/specter2"        # proximity adapter (citation-aware) — WAJIB sama agar 1 ruang vektor
MAX_LEN      = 512
ABS_CAP      = 1800   # batas char abstrak bila penanda akhir tak ketemu (toh SPECTER truncate 512 token)
# ───────────────────────────────────────────────────────────────────────────────

# Penanda akhir abstrak (IEEE): Index Terms / Keywords / heading Introduction
END_MARKERS = r"(Index\s+Terms|Keywords?|I\.\s*Introduction|1\.?\s*Introduction|I\s+INTRODUCTION|1\s+INTRODUCTION)"


def extract_abstract(text: str):
    """Kembalikan (abstrak, metode). metode: 'regex' bila penanda 'Abstract' ketemu, else 'fallback'."""
    flat = re.sub(r"\s+", " ", text).strip()
    m = re.search(r"\bAbstract\b\s*[—\-–:.]*\s*", flat, re.IGNORECASE)
    if m:
        rest = flat[m.end():]
        em = re.search(END_MARKERS, rest, re.IGNORECASE)
        abs_txt = (rest[:em.start()] if em else rest[:ABS_CAP]).strip(" .—–-:")
        if len(abs_txt) >= 60:
            return abs_txt, "regex"
    # Fallback: ~1500 char pertama (umumnya mencakup judul+abstrak+awal intro)
    return flat[:1500].strip(), "fallback"


def load_encoder():
    print(f"Memuat encoder '{MODEL_NAME}' + adapter '{ADAPTER_NAME}'...")
    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    mdl = AutoAdapterModel.from_pretrained(MODEL_NAME)
    mdl.load_adapter(ADAPTER_NAME, source="hf", load_as="proximity", set_active=True)
    mdl.set_active_adapters("proximity")
    mdl.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    mdl.to(device)
    print(f"  Device: {device} | Adapter: proximity\n")
    return tok, mdl, device


def embed(text: str, tok, mdl, device) -> np.ndarray:
    inputs = tok(text, return_tensors="pt", truncation=True, max_length=MAX_LEN, padding=True)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        out = mdl(**inputs)
    emb = out.last_hidden_state[:, 0, :]                       # CLS token (sama dgn indexing.py)
    emb = torch.nn.functional.normalize(emb, dim=1)           # L2 → dot product = cosine
    return emb.squeeze().cpu().numpy()


def main():
    txt_dir = Path(OUTPUT_TEKS_DIR)
    if not txt_dir.exists():
        print(f"[ERROR] Folder '{OUTPUT_TEKS_DIR}' tidak ditemukan.", file=sys.stderr)
        sys.exit(1)
    txt_files = sorted(txt_dir.glob("*.txt"))
    if not txt_files:
        print(f"[ERROR] Tidak ada .txt di '{OUTPUT_TEKS_DIR}'.", file=sys.stderr)
        sys.exit(1)
    print(f"Ditemukan {len(txt_files)} paper.\n")

    tok, mdl, device = load_encoder()
    sep = tok.sep_token or "[SEP]"

    embeddings, metadata, qa_rows = [], [], []
    n_regex = n_fallback = 0
    for i, txt_path in enumerate(txt_files, 1):
        paper_title = txt_path.stem                            # SAMA dgn indexing.py → cocok ke ground truth
        try:
            text = txt_path.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception as e:
            print(f"  [SKIP] {txt_path.name}: {e}")
            continue
        if not text:
            print(f"  [SKIP] {txt_path.name}: kosong.")
            continue

        abstract, method = extract_abstract(text)
        n_regex    += (method == "regex")
        n_fallback += (method == "fallback")

        # Format kanonik SPECTER2: judul [SEP] abstrak  → 1 embedding/paper
        spec_input = f"{paper_title}{sep}{abstract}"
        emb = embed(spec_input, tok, mdl, device)
        embeddings.append(emb)
        metadata.append({"paper_title": paper_title, "chunk_text": abstract})  # chunk_text = abstrak (utk display + map paper)
        qa_rows.append({"paper_title": paper_title, "method": method,
                        "abstract_chars": len(abstract), "abstract_preview": abstract[:160]})
        flag = "" if method == "regex" else "  ⚠FALLBACK"
        print(f"  [{i:3d}/{len(txt_files)}] {paper_title[:60]:<60} abs={len(abstract):>4} char ({method}){flag}")

    if not embeddings:
        print("[ERROR] Tidak ada paper terembedding.", file=sys.stderr)
        sys.exit(1)

    arr = np.vstack(embeddings).astype(np.float32)
    dim = arr.shape[1]
    index = faiss.IndexFlatIP(dim)                              # cosine pada vektor L2-normal (sama dgn indexing.py)
    index.add(arr)
    faiss.write_index(index, FAISS_OUT)
    with open(METADATA_OUT, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    pd.DataFrame(qa_rows).to_csv(QA_CSV, index=False, encoding="utf-8")

    print("\n" + "=" * 64)
    print(f"  Paper terindeks   : {index.ntotal} vektor (1 per paper)")
    print(f"  Dimensi           : {dim}")
    print(f"  Ekstraksi abstrak : {n_regex} regex-OK | {n_fallback} fallback ⚠ (cek {QA_CSV})")
    print(f"  Index             → '{FAISS_OUT}'")
    print(f"  Metadata          → '{METADATA_OUT}'")
    print(f"  QA abstrak        → '{QA_CSV}'  (PERIKSA kualitas ekstraksi sebelum pakai!)")
    print("=" * 64)
    print(f"\n  Bandingkan: index lama (chunk) 11.066 vektor → index abstrak {index.ntotal} vektor.")
    print("  Pakai di pipeline/evaluate (perlu path di-env-kan dulu):")
    print(f"    $env:FAISS_INDEX_FILE='{FAISS_OUT}'; $env:METADATA_FILE='{METADATA_OUT}'")


if __name__ == "__main__":
    main()
