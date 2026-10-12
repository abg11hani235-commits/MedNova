"use client";

import Link from "next/link";

import { BriefSkeleton, ErrorState } from "../../../components/States";
import { usePatients } from "../../../lib/api/hooks";

export default function PatientsPage() {
  const q = usePatients();
  return (
    <>
      <div className="row">
        <h1>Patients</h1>
        <span className="chip">Demo data</span>
        <Link className="btn" style={{ marginInlineStart: "auto" }} href="/upload">
          Upload patient file
        </Link>
      </div>
      {q.isLoading && <BriefSkeleton />}
      {q.isError && <ErrorState onRetry={() => q.refetch()} />}
      {q.data && (
        <section className="card" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr>
                <th>Patient</th><th>Age</th><th>Diabetes</th><th>Last visit</th><th>Next visit</th><th>Open items</th>
              </tr>
            </thead>
            <tbody>
              {q.data.map((p) => (
                <tr key={p.id}>
                  <td><Link href={`/patients/${p.id}`} style={{ color: "#1F4E79", fontWeight: 600 }}>{p.display_name}</Link></td>
                  <td>{p.age}</td>
                  <td>{p.diabetes_type}</td>
                  <td>{p.last_visit}</td>
                  <td>{p.next_visit}</td>
                  <td>
                    <span className="row">
                      {p.open_items.urgent > 0 && <span className="sev urgent">{p.open_items.urgent} urgent</span>}
                      {p.open_items.review > 0 && <span className="sev review">{p.open_items.review} to review</span>}
                      {p.open_items.urgent + p.open_items.review === 0 && <span className="sev done">None</span>}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}
