import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import BookLogo from "./BookLogo.jsx";

// Navbar publik (landing + tentang)
export default function SiteNav() {
  return (
    <motion.nav
      className="landing-nav"
      initial={{ y: -24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: [0.22, 0.61, 0.36, 1] }}
    >
      <Link to="/" className="landing-brand">
        <BookLogo size={30} />
        <span><b>Sitasi</b>AI</span>
      </Link>
      <div className="landing-links">
        <a href="#tentang">Tentang</a>
      </div>
      <div className="landing-auth">
        <Link to="/login" className="link-muted">Masuk</Link>
        <motion.div whileTap={{ scale: 0.95 }}>
          <Link to="/register" className="btn-primary">Daftar</Link>
        </motion.div>
      </div>
    </motion.nav>
  );
}
