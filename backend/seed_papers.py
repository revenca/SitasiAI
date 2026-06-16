"""backend/seed_papers.py — Isi tabel papers dari korpus (100 paper).
Jalankan sekali: python -m backend.seed_papers
"""
import os
import re
import json
from pathlib import Path
from backend.database import Base, engine, SessionLocal
from backend import models

ROOT = Path(__file__).resolve().parent.parent


def categorize(t: str) -> str:
    t = t.lower()
    if any(k in t for k in ["segmentation","detection","yolo","cnn","image","vision","carving","batik","convnext","mobilenet","lesion","endoscopy","u-net","printing"]): return "Computer Vision"
    if any(k in t for k in ["sign language","javanese","sarcasm","entailment","named entity","transliteration"]): return "NLP"
    if any(k in t for k in ["mimo","radar","ofdm","lora","hevc","positioning","reconfigurable"]): return "Telecom/Radar"
    if any(k in t for k in ["power","photovoltaic","battery","wind","energy","grid","generator","transmission","scooter","ultracapacitor","charge"]): return "Power/Energy"
    if any(k in t for k in ["eeg","brain","emotion","epileptic"]): return "Biosignal/EEG"
    if any(k in t for k in ["drone","uav","flight log","aircraft"]): return "Drone/UAV"
    if any(k in t for k in ["electronic nose","e-nose","sensor","isfet","cookies","tea"]): return "E-Nose/Sensor"
    if any(k in t for k in ["cobit","process mining","microservice","api","code smell","conformance","governance"]): return "Software Eng/IT"
    if any(k in t for k in ["forecasting","stock","credit","prediction","classification","intrusion","diabetes"]): return "ML/Forecasting"
    if any(k in t for k in ["timetabling","optimization","colony","nearest neighbor"]): return "Optimization"
    return "Lainnya"


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Hitung chunk per paper dari metadata.json
    chunk_count = {}
    meta_file = ROOT / "metadata.json"
    if meta_file.exists():
        for m in json.load(open(meta_file, encoding="utf-8")):
            chunk_count[m["paper_title"]] = chunk_count.get(m["paper_title"], 0) + 1

    txt_dir = ROOT / "output_teks"
    titles = [os.path.splitext(f)[0] for f in os.listdir(txt_dir)] if txt_dir.exists() else []

    db.query(models.Paper).delete()
    for title in sorted(titles):
        db.add(models.Paper(title=title, category=categorize(title),
                            n_chunks=chunk_count.get(title, 0)))
    db.commit()
    n = db.query(models.Paper).count()
    print(f"Seed selesai: {n} paper dimasukkan ke database.")
    db.close()


if __name__ == "__main__":
    main()
