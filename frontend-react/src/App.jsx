import { Routes, Route, Navigate } from "react-router-dom";
import Home from "./pages/Home.jsx";
import Papers from "./pages/Papers.jsx";
import Layout from "./components/Layout.jsx";

// Mode tools internal (deploy senopati.its): tanpa landing, tanpa login —
// root langsung membuka halaman chat.
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout><Home /></Layout>} />
      <Route path="/app" element={<Navigate to="/" replace />} />
      <Route path="/papers" element={<Layout><Papers /></Layout>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
