# Dockerfile — backend SitasiAI (FastAPI + SPECTER2 CPU).
# Catatan: inferensi embedding di container ini berjalan di CPU (lebih lambat dari GPU
# tetapi cukup untuk serving). Index FAISS/metadata di-mount sebagai volume.
FROM python:3.11-slim

WORKDIR /app

# torch CPU-only (jauh lebih kecil dari build CUDA)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/

# Cache model HuggingFace di volume supaya tidak unduh ulang tiap start
ENV HF_HOME=/models \
    KMP_DUPLICATE_LIB_OK=TRUE \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
