"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import type { ReactNode } from "react";

export function AppShell({ children }: { children: ReactNode }) {
  const params = useParams<{ id?: string }>();
  const pathname = usePathname() ?? "";
  const id = params?.id;
  const item = (href: string, label: string, exact = false) => {
    const active = exact ? pathname === href : pathname.startsWith(href);
    return (
      <Link href={href} aria-current={active ? "page" : undefined}>
        {label}
      </Link>
    );
  };
  return (
    <div className="app-shell">
      <header className="top">
        <Link href="/patients" aria-label="Rafiq home">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo/rafiq-logo.svg" alt="Rafiq" height={26} style={{ height: 26, width: "auto" }} />
        </Link>
        <input className="search" placeholder="Search patients" aria-label="Search patients" />
        <span className="av" aria-label="Signed in as nutrition specialist">NS</span>
      </header>
      <nav className="side" aria-label="Main">
        {item("/patients", "Patients", true)}
        {id ? item(`/patients/${id}`, "Patient Brief", true) : <span className="disabled">Patient Brief</span>}
        {id ? item(`/patients/${id}/chat`, "Ask Rafiq") : <span className="disabled">Ask Rafiq</span>}
        {item("/upload", "Upload")}
        {item("/privacy", "Privacy & Audit")}
      </nav>

      <main className="main">{children}</main>
    </div>
  );
}
