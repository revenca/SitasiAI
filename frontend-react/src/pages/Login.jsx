import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useAuth } from "../auth.jsx";
import BookLogo from "../components/BookLogo.jsx";
import FloatingBooks from "../components/FloatingBooks.jsx";
import { IconPlane, IconArrowLeft } from "../components/Icons.jsx";

const EASE = [0.22, 0.61, 0.36, 1];
const card = { hidden: { opacity: 0, y: 26, scale: 0.98 }, show: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.5, ease: EASE, when: "beforeChildren", staggerChildren: 0.06, delayChildren: 0.12 } } };
const it = { hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: EASE } } };

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      await login(email, password);
      nav("/app", { state: { fromLogin: true } });
    } catch (err) {
      setError(err?.response?.data?.detail || "Login gagal.");
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <FloatingBooks />

      <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
        <Link to="/" className="auth-home"><IconArrowLeft size={16} /> Beranda</Link>
      </motion.div>

      <motion.div className="auth-card" variants={card} initial="hidden" animate="show">
        <motion.div variants={it}>
          <Link to="/" className="auth-brand"><BookLogo size={32} /> <span><b>Sitasi</b>AI</span></Link>
        </motion.div>
        <motion.h2 variants={it}>Selamat datang kembali</motion.h2>
        <motion.p className="auth-sub" variants={it}>Masuk untuk mulai membuat sitasi.</motion.p>
        <form onSubmit={submit}>
          <motion.div variants={it}>
            <label>Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
          </motion.div>
          <motion.div variants={it}>
            <label>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </motion.div>
          {error && <motion.div className="auth-error" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}>{error}</motion.div>}
          <motion.button type="submit" className="btn-send" disabled={loading} variants={it}
            whileHover={{ y: -2 }} whileTap={{ scale: 0.97 }}>
            <span>{loading ? "Memproses…" : "Masuk"}</span>
            <IconPlane size={17} />
          </motion.button>
        </form>
        <motion.p className="auth-switch" variants={it}>Belum punya akun? <Link to="/register">Daftar</Link></motion.p>
      </motion.div>
    </div>
  );
}
