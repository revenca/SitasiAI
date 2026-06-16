import { motion } from "framer-motion";

const EASE = [0.22, 0.61, 0.36, 1];

// Pembungkus transisi masuk/keluar halaman.
export default function PageTransition({ children, className = "" }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      transition={{ duration: 0.42, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}
