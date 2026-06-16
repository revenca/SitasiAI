import axios from "axios";

// Lewat proxy Vite (/api → http://localhost:8000)
const api = axios.create({ baseURL: "/api" });

// Sisipkan token JWT ke tiap request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default api;
