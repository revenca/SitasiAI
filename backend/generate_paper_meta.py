"""
backend/generate_paper_meta.py
Ekstrak metadata (penulis + tahun) tiap paper dari output_teks/*.txt
→ simpan ke paper_meta.json  { title: { authors: [...], year: "YYYY" } }

Penulis di-parse dari blok header "1st Nama 2nd Nama ...".
Tahun best-effort dari footer copyright IEEE (©20XX IEEE / ISBN /XX/$).
Jika tidak ketemu, dibiarkan kosong.
"""
import glob
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEKS_DIR = ROOT / "evaluasi" / "output_teks_clean"
OUT = Path(__file__).resolve().parent / "data" / "paper_meta.json"

MARKERS = [
    "Department", "Departemen", "Faculty", "Fakultas", "Institut", "Universit",
    "School", "Program Studi", "Abstract", "Received", "Digital Object", "e-mail",
    "@", "Engineering", "Informatics", "Computer Science", "Indonesia", "Corresponding",
    "Jurusan", "Telkom", "Surabaya", "Jakarta", "Bandung",
]
ORD = re.compile(r"\d+\s*(?:st|nd|rd|th)\s+")
CRED = re.compile(
    r",?\s*(?:Life\s+)?(?:Senior\s+|Graduate\s+Student\s+|Student\s+)?"
    r"(?:Member|Fellow),?\s*IEEE", re.I)


def parse_authors(text: str, title: str) -> list:
    head = re.sub(r"\s+", " ", text[:1500])

    # hapus judul (penuh) di mana pun ia muncul di awal
    t_norm = re.sub(r"\s+", " ", title).strip()
    pos = head.lower().find(t_norm.lower())
    region = head[pos + len(t_norm):] if pos >= 0 else head

    # potong di penanda afiliasi/bagian paling awal
    cut = len(region)
    for mk in MARKERS:
        p = region.find(mk)
        if 0 <= p < cut:
            cut = p
    region = region[:cut]

    region = CRED.sub(",", region)                         # buang gelar IEEE
    region = ORD.sub(",", region)                          # "1st/2nd" → pemisah
    region = re.sub(r"\b[Aa][Nn][Dd]\b|&", ",", region)    # "and"/& → pemisah

    authors = []
    for raw in region.split(","):
        name = raw.strip(" .,-")
        if not (4 <= len(name) <= 36):
            continue
        # wajib dua kata (Nama Belakang) atau ada inisial bertitik
        if " " not in name and "." not in name:
            continue
        if not re.match(r"^[A-Z][A-Za-z.\-' ]+$", name):
            continue
        if re.search(r"\b(?:the|for|with|using|based|model|methods?|analysis|approach|"
                     r"system|seminar|conference|vol|university|institut)\b", name, re.I):
            continue
        authors.append(name)

    seen, uniq = set(), []
    for a in authors:
        key = a.lower()
        if key not in seen:
            seen.add(key); uniq.append(a)
    return uniq[:8]


def parse_year(text: str) -> str:
    # 1. Copyright footer IEEE (normal)
    for pat in (r"©\s*(20[12]\d)\s*IEEE", r"(20[12]\d)\s*IEEE",
                r"©\s*(20[12]\d)", r"Copyright\D{0,8}(20[12]\d)"):
        m = re.search(pat, text)
        if m:
            return m.group(1)
    # 2. DOI IEEE: 10.1109/JOURNAL.YYYY.xxxxx  (paling andal utk IEEE Access/journal)
    m = re.search(r"10\.1109/[A-Za-z]+\.(20[12]\d)\.", text)
    if m:
        return m.group(1)
    # 3. Tahun TERBALIK dekat © (footer terotasi): "3202©" / "©3202" → 2023
    m = re.search(r"([0-5]202)\s*©|©\s*([0-5]202)\b", text)
    if m:
        return (m.group(1) or m.group(2))[::-1]
    # 4. ISBN footer: ...-5635-5/24/$31.00
    m = re.search(r"/(\d{2})/\s*\$", text)
    if m:
        return "20" + m.group(1)
    return ""


def main():
    files = sorted(glob.glob(str(TEKS_DIR / "*.txt")))
    meta = {}
    n_auth = n_year = 0
    for f in files:
        title = os.path.splitext(os.path.basename(f))[0]
        t = open(f, encoding="utf-8", errors="ignore").read()
        authors = parse_authors(t, title)
        year = parse_year(t)
        if authors:
            n_auth += 1
        if year:
            n_year += 1
        meta[title] = {"authors": authors, "year": year}
    json.dump(meta, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{len(files)} paper → {OUT.name}")
    print(f"  penulis terisi : {n_auth}/{len(files)}")
    print(f"  tahun terisi   : {n_year}/{len(files)}")


if __name__ == "__main__":
    main()
