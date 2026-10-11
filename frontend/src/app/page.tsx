import Link from "next/link";

export default function Home() {
  return (
    <main style={{ padding: 48, display: "grid", gap: 16, justifyItems: "start" }}>
      <h1>Clinsight</h1>
      <p className="muted">Every finding, traced to its source.</p>
      <Link className="btn" href="/patients">
        Open patients
      </Link>
    </main>
  );
}
