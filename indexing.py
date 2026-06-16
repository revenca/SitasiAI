"""
indexing.py — Baca output_teks/, chunk, embed dengan SciBERT, simpan ke FAISS.
Jalankan SEKALI sebelum pipeline.py.
"""

import os
# Hindari konflik OpenMP (torch + faiss + numpy) di Windows — harus diset SEBELUM import lib
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import json
import sys
import numpy as np
import faiss
import torch
from pathlib import Path
from transformers import AutoTokenizer
from adapters import AutoAdapterModel

# ── CONFIG ─────────────────────────────────────────────────────────────────────
OUTPUT_TEKS_DIR  = os.getenv("OUTPUT_TEKS_DIR", "output_teks")        # folder .txt hasil ekstrak PDF
FAISS_INDEX_FILE = os.getenv("FAISS_INDEX_FILE", "faiss_index.bin")   # output: FAISS index
METADATA_FILE    = os.getenv("METADATA_FILE", "metadata.json")        # output: mapping index_id → paper_title + chunk

CHUNK_SIZE    = 512   # proposition-style (karakter)
CHUNK_OVERLAP = 50

MODEL_NAME   = "allenai/specter2_base"   # SPECTER2 base model
ADAPTER_NAME = "allenai/specter2"        # proximity adapter (citation-aware)
# ───────────────────────────────────────────────────────────────────────────────


def load_scibert():
    print(f"Memuat encoder embedding '{MODEL_NAME}' + adapter '{ADAPTER_NAME}'...")
    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    mdl = AutoAdapterModel.from_pretrained(MODEL_NAME)
    mdl.load_adapter(ADAPTER_NAME, source="hf", load_as="proximity", set_active=True)
    mdl.set_active_adapters("proximity")
    mdl.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    mdl.to(device)
    print(f"  Device: {device} | Adapter: proximity\n")
    return tok, mdl, device


def embed(text: str, tokenizer, model, device: str) -> np.ndarray:
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=True,
    )
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        output = model(**inputs)
    # CLS token sebagai representasi kalimat
    embedding = output.last_hidden_state[:, 0, :]
    # Normalisasi L2 agar dot-product == cosine similarity
    embedding = torch.nn.functional.normalize(embedding, dim=1)
    return embedding.squeeze().cpu().numpy()


_splitter = None

def chunk_text(text: str) -> list:
    """Proposition-style: chunk kecil berbasis karakter (RecursiveCharacterTextSplitter)."""
    global _splitter
    if _splitter is None:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        _splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
    return [c.strip() for c in _splitter.split_text(text) if c.strip()]


def main():
    txt_dir = Path(OUTPUT_TEKS_DIR)
    if not txt_dir.exists():
        print(
            f"[ERROR] Folder '{OUTPUT_TEKS_DIR}' tidak ditemukan.\n"
            "Buat folder tersebut dan isi dengan file .txt hasil ekstrak PDF paper.",
            file=sys.stderr,
        )
        sys.exit(1)

    txt_files = sorted(txt_dir.glob("*.txt"))
    if not txt_files:
        print(f"[ERROR] Tidak ada file .txt di dalam '{OUTPUT_TEKS_DIR}'.", file=sys.stderr)
        sys.exit(1)

    print(f"Ditemukan {len(txt_files)} file teks.\n")

    tokenizer, model, device = load_scibert()

    all_embeddings: list = []
    metadata: list       = []

    for i, txt_path in enumerate(txt_files, 1):
        paper_title = txt_path.stem
        try:
            text = txt_path.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception as e:
            print(f"  [SKIP] {txt_path.name}: {e}")
            continue

        if not text:
            print(f"  [SKIP] {txt_path.name}: file kosong.")
            continue

        chunks = chunk_text(text)
        print(f"  [{i:3d}/{len(txt_files)}] {paper_title[:65]:<65} → {len(chunks)} chunk(s)")

        for chunk in chunks:
            emb = embed(chunk, tokenizer, model, device)
            all_embeddings.append(emb)
            metadata.append({
                "paper_title": paper_title,
                "chunk_text":  chunk,
            })

    if not all_embeddings:
        print("[ERROR] Tidak ada chunk yang berhasil diembedding.", file=sys.stderr)
        sys.exit(1)

    embeddings_np = np.array(all_embeddings, dtype=np.float32)
    dim           = embeddings_np.shape[1]
    print(f"\nTotal chunks   : {len(all_embeddings)}")
    print(f"Dimensi vektor : {dim}")

    # IndexFlatIP: inner product pada vektor L2-normal = cosine similarity
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings_np)

    faiss.write_index(index, FAISS_INDEX_FILE)
    print(f"\nFAISS index disimpan → '{FAISS_INDEX_FILE}' ({index.ntotal} vektor)")

    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"Metadata disimpan  → '{METADATA_FILE}'")

    print("\nIndexing selesai. Siap jalankan pipeline.py.")


if __name__ == "__main__":
    main()
