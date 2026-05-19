"use client";
import { motion } from "framer-motion";

interface LiveDotProps {
  color?: "signal" | "amber" | "red";
}

const colorMap = {
  signal: "#00FFD1",
  amber: "#FF9500",
  red: "#FF4444",
};

export function LiveDot({ color = "signal" }: LiveDotProps) {
  const hex = colorMap[color];

  return (
    <span className="relative inline-flex items-center justify-center w-2 h-2">
      <motion.span
        className="absolute inline-flex rounded-full"
        style={{ backgroundColor: hex, width: 8, height: 8 }}
        animate={{ scale: [1, 1.8, 1], opacity: [1, 0, 1] }}
        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
      />
      <span
        className="relative inline-flex rounded-full w-2 h-2"
        style={{ backgroundColor: hex }}
      />
    </span>
  );
}