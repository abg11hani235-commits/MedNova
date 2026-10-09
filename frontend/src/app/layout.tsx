import type { Metadata } from "next";
import { Inter, IBM_Plex_Sans_Arabic } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const ibmPlexArabic = IBM_Plex_Sans_Arabic({
  subsets: ["arabic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-arabic",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Clinsight | Decision Support for Diabetes Care",
  description: "Clinical decision support web application for diabetes doctors.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${ibmPlexArabic.variable}`}>
      <body className="flex min-h-screen flex-col bg-clinsight-bg text-clinsight-text antialiased">
        <main className="flex-1">{children}</main>
        <footer className="border-t border-clinsight-border bg-white px-4 py-3 text-center text-xs text-clinsight-muted">
          Clinical decision support only. Verify findings against the patient record and current
          clinical guidance. Not a substitute for clinical judgment.
        </footer>
      </body>
    </html>
  );
}
