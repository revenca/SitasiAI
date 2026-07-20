import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Aplikasi disajikan di bawah PATH, bukan domain sendiri:
//   https://senopati.its.ac.id/sitasi-ai/
// Maka `base` harus diset agar aset dirujuk sebagai /sitasi-ai/assets/... (bukan /assets/...),
// kalau tidak browser meminta path tanpa prefix → 404 → halaman blank.
export default defineConfig({
  base: "/sitasi-ai/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // dev disamakan dgn produksi supaya yang diuji lokal = yang jalan di server
      "/sitasi-ai/api": {
        target: "http://localhost:8003", changeOrigin: true,
        timeout: 120000, proxyTimeout: 120000,
        rewrite: (p) => p.replace(/^\/sitasi-ai\/api/, ""),
      },
    },
  },
});
