"use client";

import { useAudit } from "../../../lib/api/hooks";

const CARDS = [
  ["De-identification", "Names, national IDs and phone numbers are removed before any AI analysis."],
  ["Encryption", "Files are encrypted in transit and at rest."],
  ["Patient isolation", "Each patient has a separate data space. A question never reads another patient."],
  ["No training", "Patient files are not used to train models."],
];

export default function PrivacyPage() {
  const audit = useAudit();
  return (
    <>
      <div className="row">
        <h1>Privacy &amp; Audit</h1>
        <span className="chip">Demo data</span>
      </div>
      <div className="muted">Design commitments for the MVP, aligned with Egypt Personal Data Protection Law No. 151 of 2020.</div>
      <div className="grid" style={{ gridTemplateColumns: "repeat(4,1fr)" }}>
        {CARDS.map(([t, d]) => (
          <div className="card" key={t}><b>{t}</b><p className="muted">{d}</p></div>
        ))}
      </div>
      <section className="card" style={{ padding: 0 }}>
        <div style={{ padding: "16px 16px 0" }}><h2>Access log</h2></div>
        <table>
          <thead><tr><th>Time</th><th>User</th><th>Action</th><th>Patient</th></tr></thead>
          <tbody>
            {audit.data?.map((a, i) => (
              <tr key={i}><td>{a.time}</td><td>{a.actor}</td><td>{a.action}</td><td>{a.patient_id ? `#${a.patient_id}` : ""}</td></tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
