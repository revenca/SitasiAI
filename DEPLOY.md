# Deploy SitasiAI ke Server Kampus (Internal) — Runbook

Target: server internal ITS (akses via IP jaringan kampus, tanpa domain/HTTPS).
Metode: **Docker Compose** — satu perintah menyalakan 3 kontainer:

```
web  (nginx + React build)  :80  ──►  api (FastAPI + SPECTER2) :8000  ──►  db (pgvector) :5432
        ▲ user akses di sini
```

Ganti placeholder berikut sesuai punyamu:
- `USER@SERVER_IP` → login SSH kamu (mis. `dwiyana@10.15.20.5`)
- `/opt/sitasi-ai` → folder tujuan di server (boleh diganti)

---

## FASE 0 — Cek kondisi server (WAJIB dulu)

Masuk server:
```bash
ssh USER@SERVER_IP
```

Cek 4 hal:
```bash
cat /etc/os-release | head -2      # OS apa (Ubuntu/Debian/RHEL?)
docker --version                   # Docker ada?
docker compose version             # Compose v2 ada?
nproc; free -h; df -h /            # CPU, RAM, disk kosong
```

**Syarat minimum:** RAM ≥ 4 GB (ideal 8 GB), disk kosong ≥ 8 GB, ada koneksi internet
(untuk unduh image + model SPECTER2 sekali di awal).

- Kalau `docker` & `docker compose` **muncul versinya** → lompat ke **FASE 2**.
- Kalau **"command not found"** → lanjut **FASE 1**.

---

## FASE 1 — Install Docker (hanya jika belum ada)

Butuh akses `sudo`. Pilih sesuai OS di FASE 0:

**Ubuntu / Debian:**
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER      # biar tak perlu sudo tiap docker
newgrp docker                      # aktifkan grup tanpa logout
docker run hello-world             # tes
```

**RHEL / CentOS / Rocky:**
```bash
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER; newgrp docker
docker run hello-world
```

> Tidak boleh install Docker (tanpa sudo)? Lihat **Lampiran B — deploy tanpa Docker**.

---

## FASE 2 — Ambil kode + data ke server

### 2a. Kode (via git)
```bash
sudo mkdir -p /opt/sitasi-ai && sudo chown $USER /opt/sitasi-ai
git clone https://github.com/revenca/sitasi-ai.git /opt/sitasi-ai
cd /opt/sitasi-ai
```
> Repo privat? Pakai Personal Access Token:
> `git clone https://<TOKEN>@github.com/revenca/sitasi-ai.git /opt/sitasi-ai`

### 2b. Data besar (TIDAK ikut git — transfer manual)
File ini gitignored, jalankan dari **komputer lokal (Windows)**, di folder `d:\TUGAS AKHIR\TA`:

```bash
# 4 file wajib (total ~640 MB) — jalankan di PowerShell/Git Bash lokal
scp external_index/faiss_index_external.bin  USER@SERVER_IP:/opt/sitasi-ai/external_index/
scp external_index/metadata_external.jsonl   USER@SERVER_IP:/opt/sitasi-ai/external_index/
scp backend/data/faiss_index.bin             USER@SERVER_IP:/opt/sitasi-ai/backend/data/
scp backend/data/metadata.json               USER@SERVER_IP:/opt/sitasi-ai/backend/data/
```
> Folder `external_index/vecs/` (shard .npy) TIDAK perlu — itu bahan mentah, bukan runtime.

### 2c. File `.env` (rahasia — buat manual di server)
`.env` gitignored dan berisi API key. **Jangan** commit. Buat di server:
```bash
cd /opt/sitasi-ai
nano .env
```
Isi (ganti nilai `xxx` dengan key aslimu — ambil dari `.env` lokalmu):
```env
AUTH_DISABLED=1
CORS_ORIGINS=*
POSTGRES_PASSWORD=ubah-password-kuat-ini

OPENROUTER_API_KEY=sk-or-xxx
GROQ_API_KEY=gsk_xxx
DEEPSEEK_API_KEY=sk-xxx
S2_API_KEY=xxx

GEN_MODEL=openai/gpt-4o-mini
GROQ_MODEL=llama-3.3-70b-versatile
JWT_SECRET=string-acak-panjang-apa-saja

MIN_SIM=0.62
REL_WIN=0.12
VERIFY_CITATION=1
VERIFY_STRICT=0
```
> `DATABASE_URL` TIDAK perlu diisi di sini — compose meng-set otomatis ke Postgres kontainer.

---

## FASE 3 — Build & jalankan

```bash
cd /opt/sitasi-ai
docker compose up -d --build
```

Build pertama makan ~5-10 menit (unduh torch CPU + node build). Pantau:
```bash
docker compose ps                 # ke-3 service harus "running"
docker compose logs -f api        # tunggu "Uvicorn running" + model SPECTER2 selesai unduh
```
> Start pertama, `api` mengunduh model SPECTER2 (~440 MB) → butuh 1-2 menit.
> Selama itu web bisa balas 502; normal. Tunggu log `api` siap.

---

## FASE 4 — Verifikasi

```bash
curl http://localhost/api/health          # {"status":"ok"}
curl -s -X POST http://localhost/api/recommend \
  -H "Content-Type: application/json" \
  -d '{"paragraph":"U-Net is a standard architecture for medical image segmentation.","top_k":10}' \
  | head -c 300
```

Lalu dari browser di jaringan kampus: **`http://SERVER_IP/`** → SitasiAI muncul.

---

## OPERASIONAL sehari-hari

```bash
docker compose logs -f api        # lihat log backend
docker compose restart api        # restart 1 service
docker compose down               # matikan semua (data DB & model aman di volume)
docker compose up -d              # nyalakan lagi
```

**Update setelah ada perubahan kode:**
```bash
cd /opt/sitasi-ai && git pull
docker compose up -d --build      # rebuild image yang berubah
```

**Auto-nyala saat server reboot:** sudah otomatis (`restart: unless-stopped` di compose).

---

## Troubleshooting

| Gejala | Sebab & solusi |
|---|---|
| `web` 502 Bad Gateway | `api` belum siap (masih unduh model). `docker compose logs -f api`, tunggu. |
| `api` exit / OOM | RAM kurang. Cek `free -h`. SPECTER2+FAISS butuh ~3 GB. Tambah RAM/swap. |
| Rekomendasi lama (>60s) | Normal untuk HyDE N=5 di CPU. Kalau kena limit Groq → otomatis fallback OpenRouter→DeepSeek. |
| Port 80 dipakai | Ada nginx/apache lain. Ganti mapping `web` ke `"8080:80"` di compose, akses `http://SERVER_IP:8080/`. |
| Search jatuh ke 100-paper | File 163k belum ter-scp. Cek `ls -lh external_index/faiss_index_external.bin` di server. |

---

## (Opsional) pgvector untuk skala

Default sudah pakai FAISS 163k (cukup untuk internal). Kalau nanti mau pindah ke
pgvector (query paralel lebih tahan banyak user), sekali saja:
```bash
docker compose exec api python -m backend.migrate_to_pgvector
```

---

## Lampiran B — deploy TANPA Docker (bare-metal)

Hanya jika Docker tak bisa dipasang. Butuh Python 3.11 + Node 20 + Postgres (opsional).
```bash
# Backend
cd /opt/sitasi-ai
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# .env seperti FASE 2c, tapi kosongkan DATABASE_URL (pakai SQLite fallback)
nohup .venv/bin/uvicorn backend.api:app --host 0.0.0.0 --port 8000 &

# Frontend
cd frontend-react && npm ci && npm run build
# sajikan dist/ via nginx sistem; proxy /api → localhost:8000 (pakai frontend-react/nginx.conf sbg acuan)
```
Untuk produksi sebaiknya bungkus uvicorn sebagai `systemd` service (bukan `nohup`).
