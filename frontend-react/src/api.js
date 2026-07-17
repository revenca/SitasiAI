import axios from "axios";

// Lewat proxy Vite (/api → http://localhost:8000)
// timeout 120s: HyDE proper (N=5) butuh ~10-30 dtk per rekomendasi
const api = axios.create({ baseURL: "/api", timeout: 120000 });

// Sisipkan token JWT ke tiap request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default api;
