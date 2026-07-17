"""
external_index/harvest_openalex.py — Panen abstrak dari OpenAlex (RESUMABLE).

Fetch works berbahasa Inggris ber-abstrak dari konsep yang relevan (default: Computer
Science), simpan per-shard JSONL + checkpoint cursor. Aman di-Ctrl+C kapan pun:
jalankan ulang → lanjut dari cursor terakhir (paling banyak rugi 1 halaman).

Jalankan:
    python external_index/harvest_openalex.py            # target default (lihat TARGET)
    TARGET=1000000 python external_index/harvest_openalex.py
"""
import os, json, time, glob
import requests

HERE      = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(HERE, "data")
CKPT      = os.path.join(HERE, "harvest_checkpoint.json")
MAILTO    = os.getenv("OPENALEX_MAILTO", "yudhaprawira209@gmail.com")
TARGET    = int(os.getenv("TARGET", "1000000"))       # jumlah abstrak yang mau dipanen
CONCEPT   = os.getenv("OA_CONCEPT", "C41008148")      # Computer Science (root concept)
PER_PAGE  = 200                                        # maksimum OpenAlex
SHARD_SZ  = 10000                                      # record per file shard
URL       = "https://api.openalex.org/works"
SELECT    = "id,title,publication_year,authorships,cited_by_count,abstract_inverted_index,doi"

os.makedirs(DATA_DIR, exist_ok=True)


def load_ckpt():
    if os.path.exists(CKPT):
        return json.load(open(CKPT, encoding="utf-8"))
    return {"cursor": "*", "harvested": 0, "shard": 0}


def save_ckpt(c):
    json.dump(c, open(CKPT, "w", encoding="utf-8"))


def deinvert(inv):
    if not inv:
        return ""
    pos = {i: w for w, idxs in inv.items() for i in idxs}
    return " ".join(pos[i] for i in sorted(pos))


def fetch_page(cursor):
    params = {"filter": f"concepts.id:{CONCEPT},has_abstract:true,language:en",
              "per-page": PER_PAGE, "cursor": cursor, "select": SELECT, "mailto": MAILTO}
    for attempt in range(12):                       # lebih sabar thd 429/putus sesaat
        try:
            r = requests.get(URL, params=params, timeout=60)
            if r.status_code == 200:
                d = r.json()
                return "ok", d.get("results", []), d.get("meta", {}).get("next_cursor")
            if r.status_code == 429:
                msg = r.text[:200]
                if "budget" in msg.lower() or "insufficient" in msg.lower():
                    return "budget", None, None     # kuota harian habis → berhenti bersih
                time.sleep(min(3 * (attempt + 1), 30)); continue
            print(f"  HTTP {r.status_code}: {r.text[:120]}"); time.sleep(min(3 * (attempt + 1), 30))
        except requests.RequestException as e:
            print(f"  net err: {e}"); time.sleep(min(3 * (attempt + 1), 30))
    return "fail", None, None


def main():
    c = load_ckpt()
    print(f"Mulai: harvested={c['harvested']} shard={c['shard']} target={TARGET}")
    buf = []
    t0 = time.time()
    fail_streak = 0
    while c["harvested"] < TARGET and c["cursor"]:
        status, results, nxt = fetch_page(c["cursor"])
        if status == "budget":
            print(f"Budget harian OpenAlex habis di {c['harvested']:,} — berhenti bersih "
                  "(reset tengah malam UTC; scheduled task akan resume otomatis).")
            break
        if status == "fail":
            # Kegagalan sesaat (jaringan): JANGAN keluar — cooldown lalu ulangi cursor sama.
            fail_streak += 1
            if fail_streak >= 20:
                print("Gagal 20x beruntun — berhenti (jalankan ulang untuk lanjut)."); break
            cooldown = min(30 * fail_streak, 300)
            print(f"  fetch gagal (streak {fail_streak}) — cooldown {cooldown}s lalu ulangi...")
            time.sleep(cooldown); continue
        fail_streak = 0
        if not results:
            print("Cursor habis — semua data terpanen."); c["cursor"] = None; break
        for w in results:
            abstract = deinvert(w.get("abstract_inverted_index"))
            if not abstract or not w.get("title"):
                continue
            buf.append({
                "id": w.get("id", ""), "title": w["title"], "abstract": abstract,
                "year": w.get("publication_year"),
                "authors": [a["author"]["display_name"] for a in (w.get("authorships") or [])[:6]],
                "cited_by": w.get("cited_by_count", 0), "doi": w.get("doi") or "",
            })
        c["cursor"] = nxt
        time.sleep(0.12)                            # jeda antar-halaman: hindari 429 burst
        # tulis shard bila penuh
        while len(buf) >= SHARD_SZ:
            path = os.path.join(DATA_DIR, f"shard_{c['shard']:05d}.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                for rec in buf[:SHARD_SZ]:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            c["harvested"] += SHARD_SZ; c["shard"] += 1; buf = buf[SHARD_SZ:]
            save_ckpt(c)
            rate = c["harvested"] / max(time.time() - t0, 1)
            print(f"  shard {c['shard']-1:05d} tersimpan | total {c['harvested']:,} | {rate:.0f}/s")
        if not nxt:
            c["cursor"] = None; break
    # flush sisa buffer sebagai shard terakhir
    if buf:
        path = os.path.join(DATA_DIR, f"shard_{c['shard']:05d}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for rec in buf:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        c["harvested"] += len(buf); c["shard"] += 1
        save_ckpt(c)
        print(f"  shard {c['shard']-1:05d} (sisa {len(buf)}) | total {c['harvested']:,}")
    print(f"\nSELESAI panen: {c['harvested']:,} abstrak dalam {c['shard']} shard "
          f"({time.time()-t0:.0f}s). File: external_index/data/shard_*.jsonl")


if __name__ == "__main__":
    main()
