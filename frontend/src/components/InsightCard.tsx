import type { Insight } from "../lib/api/types";
import { SeverityBadge } from "./SeverityBadge";
import { SourceChip } from "./SourceChip";

export function InsightRow({ patientId, insight }: { patientId: string; insight: Insight }) {
  return (
    <div className="item" data-testid="snapshot-item">
      <SeverityBadge severity={insight.severity} />
      <span>
        {insight.statement}{" "}
        {insight.review_state === "reviewed" && <span className="chip">Reviewed</span>}
      </span>
      {insight.source ? (
        <SourceChip patientId={patientId} source={insight.source} />
      ) : (
        <span className="chip">{insight.absence_note ?? "No source"}</span>
      )}
    </div>
  );
}
