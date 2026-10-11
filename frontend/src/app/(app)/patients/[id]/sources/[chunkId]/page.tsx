"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { SeverityBadge } from "../../../../../../components/SeverityBadge";
import { sourceLabel } from "../../../../../../components/SourceChip";
import { BriefSkeleton, ErrorState } from "../../../../../../components/States";
import { useBrief, useSource } from "../../../../../../lib/api/hooks";

export default function SourceTracePage() {
  const { id, chunkId } = useParams<{ id: string; chunkId: string }>();
  const q = useSource(id, chunkId);
  const brief = useBrief(id);
  if (q.isLoading) return <BriefSkeleton />;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  const s = q.data;
  const insight = brief.data?.snapshot.find((i) => i.source?.chunk_id === chunkId);
  const h = s.highlight;

  return (
    <>
      <div className="row">
        <h1>Source Trace</h1>
        <Link className="btn ghost" style={{ marginInlineStart: "auto" }} href={`/patients/${id}`}>Back to brief</Link>
      </div>
      <div className="grid" style={{ gridTemplateColumns: "1fr 360px" }}>
        <section className="card">
          <div className="row">
            <b>{sourceLabel(s.file_name)}</b>
            <span className="muted">{s.date} · page {s.page}</span>
          </div>
          <div className="paper" data-testid="paper">
            {h ? (
              <>
                {s.page_text.slice(0, h.start)}
                <mark>{s.page_text.slice(h.start, h.end)}</mark>
                {s.page_text.slice(h.end)}
              </>
            ) : (
              s.page_text
            )}
          </div>
        </section>
        <aside className="card grid" style={{ alignContent: "start" }}>
          <div className="row">
            {insight && <SeverityBadge severity={insight.severity} />}
            <span className="chip src">Evidence</span>
          </div>
          {insight && <b>{insight.statement}</b>}
          {s.quote ? (
            <>
              <div className="muted">Quoted source</div>
              <div style={{ borderInlineStart: "3px solid #F59E0B", paddingInlineStart: 12 }}>{s.quote}</div>
            </>
          ) : (
            <div className="muted">No quoted sentence is attached to this page.</div>
          )}
          <span className="muted">{sourceLabel(s.file_name)} · page {s.page} · {s.date}</span>
          {s.quote && <span className="sev done" style={{ justifySelf: "start" }}>Supported by source</span>}
        </aside>
      </div>
    </>
  );
}
