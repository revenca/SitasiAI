"""
extract_pdf.py — Ekstrak teks dari semua PDF di 'Data (paper)/' menjadi file .txt
di folder 'output_teks/'. Jalankan SEKALI sebelum indexing.py.
"""

import re
import sys
import pdfplumber
from pathlib import Path

# ── CONFIG ─────────────────────────────────────────────────────────────────────
PDF_DIR    = "Data (paper)"     # folder berisi PDF asli
OUTPUT_DIR = "output_teks"      # folder tujuan file .txt
OVERWRITE  = False              # True = timpa .txt yang sudah ada
# ───────────────────────────────────────────────────────────────────────────────


def clean_text(text: str) -> str:
    """Rapikan teks hasil ekstrak: gabung baris terpotong, normalisasi spasi."""
    # Gabung kata yang terpotong tanda hubung di akhir baris: "segmen-\ntasi" → "segmentasi"
    text = re.sub(r"-\n", "", text)
    # Ganti newline tunggal jadi spasi (paragraf tetap dipisah newline ganda)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    # Normalisasi spasi berlebih
    text = re.sub(r"[ \t]+", " ", text)
    # Normalisasi newline berlebih
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_one(pdf_path: Path) -> str:
    """Ekstrak seluruh teks dari satu PDF."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            if txt.strip():
                pages.append(txt)
    return "\n\n".join(pages)


def main():
    pdf_dir = Path(PDF_DIR)
    if not pdf_dir.exists():
        print(f"[ERROR] Folder '{PDF_DIR}' tidak ditemukan.", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(exist_ok=True)

    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"[ERROR] Tidak ada file .pdf di '{PDF_DIR}'.", file=sys.stderr)
        sys.exit(1)

    print(f"Ditemukan {len(pdf_files)} PDF. Mulai ekstraksi...\n")

    n_ok, n_skip, n_fail = 0, 0, 0

    for i, pdf_path in enumerate(pdf_files, 1):
        out_path = out_dir / f"{pdf_path.stem}.txt"

        if out_path.exists() and not OVERWRITE:
            print(f"  [{i:3d}/{len(pdf_files)}] SKIP (sudah ada): {pdf_path.stem[:60]}")
            n_skip += 1
            continue

        try:
            raw   = extract_one(pdf_path)
            clean = clean_text(raw)

            if len(clean.split()) < 50:
                print(f"  [{i:3d}/{len(pdf_files)}] WARN (teks sedikit, {len(clean.split())} kata): {pdf_path.stem[:50]}")

            out_path.write_text(clean, encoding="utf-8")
            n_words = len(clean.split())
            print(f"  [{i:3d}/{len(pdf_files)}] OK   ({n_words:5d} kata): {pdf_path.stem[:55]}")
            n_ok += 1

        except Exception as e:
            print(f"  [{i:3d}/{len(pdf_files)}] FAIL: {pdf_path.stem[:50]} → {e}", file=sys.stderr)
            n_fail += 1

    print(f"\nSelesai. Berhasil: {n_ok} | Dilewati: {n_skip} | Gagal: {n_fail}")
    print(f"Output di folder: '{OUTPUT_DIR}/'")
    if n_ok > 0:
        print("\nSiap lanjut: python indexing.py")


if __name__ == "__main__":
    main()
