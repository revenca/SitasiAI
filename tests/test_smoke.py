"""
tests/test_smoke.py — Smoke test API (tanpa panggilan LLM berbayar).

Menguji endpoint dasar: /health, register/login/me, /papers, proteksi auth, dan
rate limiter. rag_engine.init() di-monkeypatch jadi no-op supaya test tidak memuat
model SPECTER2 (berat) — endpoint LLM tidak dipanggil di sini.

Jalankan:  python -m pytest tests/test_smoke.py -q
"""
import os
import uuid

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ["AUTH_DISABLED"] = "0"   # test selalu dgn auth ON (cegah endpoint LLM tereksekusi)

import pytest
from fastapi.testclient import TestClient

import backend.rag_engine as rag_engine


@pytest.fixture(scope="module")
def client():
    rag_engine.init = lambda: None          # jangan load model saat startup test
    from backend.api import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def token(client):
    email = f"smoke-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/auth/register", json={"name": "Smoke", "email": email,
                                            "password": "smoke1234"})
    assert r.status_code == 200, r.text
    r = client.post("/auth/login", json={"email": email, "password": "smoke1234"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_register_duplicate_rejected(client):
    email = f"dup-{uuid.uuid4().hex[:8]}@example.com"
    body = {"name": "Dup", "email": email, "password": "x12345678"}
    assert client.post("/auth/register", json=body).status_code == 200
    assert client.post("/auth/register", json=body).status_code == 400


def test_login_wrong_password(client, token):
    r = client.post("/auth/login", json={"email": "nouser@example.com", "password": "salah"})
    assert r.status_code == 401


def test_me_requires_auth(client, token):
    assert client.get("/auth/me").status_code in (401, 403)
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and "email" in r.json()


def test_papers_listing(client):
    r = client.get("/papers")
    assert r.status_code == 200
    d = r.json()
    assert isinstance(d, dict) and "papers" in d and "total" in d
    assert isinstance(d["papers"], list)


def test_llm_endpoints_require_auth(client):
    for path, body in [("/recommend", {"paragraph": "x"}),
                       ("/recommend-external", {"paragraph": "x"}),
                       ("/cite-abstract", {"paragraph": "x"}),
                       ("/ask", {"question": "x"}),
                       ("/ask-external", {"question": "x"})]:
        assert client.post(path, json=body).status_code in (401, 403), path


def test_rate_limiter_blocks_after_n():
    from backend.api import check_rate_limit, RATE_LIMIT_N
    from fastapi import HTTPException
    uid = 999_999
    for _ in range(RATE_LIMIT_N):
        check_rate_limit(uid)
    with pytest.raises(HTTPException) as e:
        check_rate_limit(uid)
    assert e.value.status_code == 429
