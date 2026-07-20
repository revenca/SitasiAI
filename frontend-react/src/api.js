import axios from "axios";

// Disajikan di bawah path /sitasi-ai/ (reverse-proxy senopati.its.ac.id/sitasi-ai/)
// timeout 120s: HyDE proper (N=5) butuh ~10-30 dtk per rekomendasi
const api = axios.create({ baseURL: "/sitasi-ai/api", timeout: 120000 });

// Sisipkan token JWT ke tiap request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default api;
