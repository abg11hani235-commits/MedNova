"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { CareGapRow } from "../../../../components/CareGapRow";
import { InsightRow } from "../../../../components/InsightCard";
import { ReviewActions } from "../../../../components/ReviewActions";
import { SeverityBadge } from "../../../../components/SeverityBadge";
import { SourceChip } from "../../../../components/SourceChip";
import { BriefSkeleton, ErrorState } from "../../../../components/States";
import { TrendChart } from "../../../../components/TrendChart";
import { useBrief } from "../../../../lib/api/hooks";

export default function BriefPage() {
  const { id } = useParams<{ id: string }>();
  const q = useBrief(id);
  if (q.isLoading) return <BriefSkeleton />;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  const b = q.data;
  const state = (iid: string) => b.snapshot.find((i) => i.id === iid);

  return (
    <>
      <div className="row">
        <h1>{b.patient.display_name}</h1>
        <span className="chip">Demo data</span>
        <span className="row" style={{ marginInlineStart: "auto" }}>
          <button className="btn ghost" disabled title="Coming soon">Export one-page brief (PDF)</button>
          <Link className="btn" href={`/patients/${id}/chat`}>Ask the Chart</Link>
        </span>
      </div>
      <div className="row muted">
        <span className="chip">Age {b.patient.age}</span>
        <span className="chip">
          {b.patient.diabetes_type} diabetes{b.patient.duration_years ? ` · ${b.patient.duration_years} years` : ""}
        </span>
        {b.patient.medications.map((m) => (
          <span className="chip" key={m}>{m}</span>
        ))}
        {b.coverage.unreadable_files > 0 && <span className="sev review">Coverage</span>}
        <span>
          Based on {b.coverage.readable_files} of {b.coverage.total_files} files
          {b.coverage.unreadable_files > 0 ? ` · ${b.coverage.unreadable_files} could not be read` : ""}
        </span>
      </div>

      <section className="card" data-testid="snapshot">
        <h2>Clinical Snapshot</h2>
        {b.snapshot.map((i) => (
          <InsightRow key={i.id} patientId={id} insight={i} />
        ))}
      </section>

      <section className="card">
        <h2>Trend View</h2>
        <div className="grid g2">
          <TrendChart title="HbA1c (%)" trend={b.trends.hba1c} />
          <TrendChart title="eGFR (mL/min/1.73m²)" trend={b.trends.egfr} />
        </div>
      </section>

      <section className="card">
        <h2>Care Gap Checklist</h2>
        {b.care_gaps.map((g) => (
          <CareGapRow key={g.name} patientId={id} gap={g} />
        ))}
      </section>

      <section>
        <h2>Review Considerations</h2>
        <div className="grid g2">
          {b.considerations.map((c) => {
            const s = state(c.id);
            return (
              <div className="card grid" key={c.id}>
                <span style={{ justifySelf: "start" }}><SeverityBadge severity={c.severity} /></span>
                <b>{c.statement}</b>
                <span className="muted">Why: {c.why}</span>
                {c.source && <span style={{ justifySelf: "start" }}><SourceChip patientId={id} source={c.source} /></span>}
                <ReviewActions patientId={id} insightId={c.id} reviewState={s?.review_state ?? "none"} feedback={s?.feedback ?? "none"} />
              </div>
            );
          })}
        </div>
      </section>
    </>
  );
}
