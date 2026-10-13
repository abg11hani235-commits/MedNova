import type { Metadata } from "next";
import { IBM_Plex_Sans_Arabic, Inter } from "next/font/google";
import type { ReactNode } from "react";

import "./globals.css";
import "./rafiq.css";
import { DISCLAIMER } from "../lib/constants";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const arabic = IBM_Plex_Sans_Arabic({ subsets: ["arabic", "latin"], weight: ["400", "500", "600", "700"], variable: "--font-arabic" });

export const metadata: Metadata = {
  title: "Rafiq",
  description: "Every finding, traced to its source.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.variable} ${arabic.variable}`}>
        <Providers>
          <div className="page">
            <div className="grow">{children}</div>
            <footer className="foot" dir="auto">{DISCLAIMER}</footer>
          </div>
        </Providers>
      </body>
    </html>
  );
}

