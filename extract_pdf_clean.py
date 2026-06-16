"""
extract_pdf_clean.py — Re-ekstrak PDF dengan deteksi kolom (pdfplumber, LOKAL).
Memperbaiki 2 artefak di output_teks lama:
  1. Kolom ganda ke-interleaving  → deteksi 2-kolom per halaman, baca kolom KIRI penuh lalu KANAN.
  2. Spasi hilang (kata nempel)    → pdfplumber extract berbasis kata (sisip spasi dari posisi).

Input : Data (paper)/*.pdf  (100 PDF asli)
Output: output_teks_clean/<judul>.txt   (output_teks/ LAMA tidak disentuh)
PDF tidak dikirim ke layanan eksternal mana pun.

  & ".venv\\Scripts\\python.exe" extract_pdf_clean.py
"""
import sys
from pathlib import Path
import pdfplumber

ROOT    = Path(__file__).resolve().parent
PDF_DIR = ROOT / "Data (paper)"
OUT_DIR = ROOT / "output_teks_clean"
OUT_DIR.mkdir(exist_ok=True)

X_TOL, Y_TOL = 1.5, 3   # toleransi spasi/baris untuk extract_words


def _render_column(ws) -> str:
    """Bentuk baris dari kata-kata SATU kolom (sudah dipisah): urut atas→bawah, kiri→kanan."""
    lines, cur, ct = [], [], None
    for w in sorted(ws, key=lambda w: (w["top"], w["x0"])):
        if ct is None or abs(w["top"] - ct) <= Y_TOL:
            cur.append(w); ct = w["top"] if ct is None else ct
        else:
            lines.append(cur); cur = [w]; ct = w["top"]
    if cur:
        lines.append(cur)
    return "\n".join(" ".join(x["text"] for x in sorted(l, key=lambda w: w["x0"])) for l in lines)


def page_text(page) -> str:
    """Deteksi gutter sempit (strip vertikal paling jarang dilintasi kata) → assign tiap kata
    ke kolom KIRI/KANAN, bentuk baris DI DALAM tiap kolom, baca kiri penuh lalu kanan.
    Bila tak ada gutter jelas → 1 kolom (ekstraksi normal)."""
    try:
        words = page.extract_words(x_tolerance=X_TOL, y_tolerance=Y_TOL)
    except Exception:
        words = []
    N = len(words)
    if N < 20:                                   # halaman jarang (judul/gambar) → normal
        return page.extract_text(x_tolerance=X_TOL, y_tolerance=Y_TOL) or ""

    W = float(page.width)
    # Gutter = strip vertikal tersempit (lebar 6px) yang PALING SEDIKIT dilintasi kata, di area tengah
    best_x, best_cross, x = W / 2.0, 10 ** 9, 0.40 * W
    while x <= 0.60 * W:
        cross = sum(1 for w in words if w["x0"] < x - 3 and w["x1"] > x + 3)
        if cross < best_cross:
            best_cross, best_x = cross, x
        x += 4
    if best_cross > 0.08 * N:                     # tak ada gutter jelas → anggap 1 kolom
        return page.extract_text(x_tolerance=X_TOL, y_tolerance=Y_TOL) or ""

    g = best_x
    left  = [w for w in words if (w["x0"] + w["x1"]) / 2 <  g]
    right = [w for w in words if (w["x0"] + w["x1"]) / 2 >= g]
    return (_render_column(left) + "\n" + _render_column(right)).strip()


def extract_pdf(pdf_path: Path) -> str:
    parts, ncol = [], 0
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page_text(page)
            if t.strip():
                parts.append(t)
    return "\n".join(parts).strip()


def main():
    if not PDF_DIR.exists():
        print(f"[ERROR] Folder '{PDF_DIR}' tidak ada.", file=sys.stderr); sys.exit(1)
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"[ERROR] Tidak ada PDF di '{PDF_DIR}'.", file=sys.stderr); sys.exit(1)
    print(f"Ditemukan {len(pdfs)} PDF. Re-ekstrak dengan deteksi kolom...\n")

    ok = fail = 0
    for i, p in enumerate(pdfs, 1):
        out_path = OUT_DIR / (p.stem + ".txt")
        try:
            text = extract_pdf(p)
            if not text:
                print(f"  [{i:3d}/{len(pdfs)}] {p.stem[:60]:<60}  ⚠ KOSONG"); fail += 1; continue
            out_path.write_text(text, encoding="utf-8")
            print(f"  [{i:3d}/{len(pdfs)}] {p.stem[:60]:<60}  {len(text):>6} char"); ok += 1
        except Exception as e:
            print(f"  [{i:3d}/{len(pdfs)}] {p.stem[:55]:<55}  ✗ ERROR: {str(e)[:40]}"); fail += 1

    print("\n" + "=" * 64)
    print(f"  Selesai: {ok} OK, {fail} gagal → '{OUT_DIR}'")
    print("=" * 64)

    # Demo before/after utk paper yang tadi ke-interleaving (3D Patch)
    demo = OUT_DIR / "3D Patch Spatially Localized Network Tiles Enables for 3D Brain Segmentation.txt"
    if demo.exists():
        print("\nCONTOH HASIL BERSIH (3D Patch, ~400 char pertama):")
        print("-" * 64)
        print(demo.read_text(encoding="utf-8")[:400])
        print("-" * 64)


if __name__ == "__main__":
    main()
