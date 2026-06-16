import { motion } from "framer-motion";
import BookLogo from "./BookLogo.jsx";

// Transisi reveal: satu lembar biru menahan sebentar lalu meluncur
// ke atas dengan mulus (tanpa panel/kotak) mengungkap aplikasi.
export default function RevealTransition() {
  return (
    <motion.div
      className="reveal-cover"
      aria-hidden="true"
      initial={{ y: "0%" }}
      animate={{ y: "-105%", borderBottomLeftRadius: ["0px", "40%"], borderBottomRightRadius: ["0px", "40%"] }}
      transition={{ duration: 0.8, ease: [0.76, 0, 0.24, 1], delay: 0.5 }}
    >
      <motion.div
        className="reveal-logo"
        initial={{ opacity: 0, scale: 0.9, y: 8 }}
        animate={{ opacity: [0, 1, 1, 0], scale: [0.9, 1, 1, 1.04], y: [8, 0, 0, -4] }}
        transition={{ duration: 1.05, ease: "easeInOut", times: [0, 0.25, 0.65, 1] }}
      >
        <BookLogo size={56} /> <span><b>Sitasi</b>AI</span>
      </motion.div>
    </motion.div>
  );
}
