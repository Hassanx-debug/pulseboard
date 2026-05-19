import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PulseBoard — AI Trend Intelligence",
  description: "Real-time signal detection across Reddit, HackerNews & GitHub",
};

export const viewport: Viewport = {
  themeColor: "#080A0F",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="noise">
      <body className="min-h-screen bg-bg font-mono antialiased">
        {children}
      </body>
    </html>
  );
}