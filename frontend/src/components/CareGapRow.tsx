import type { CareGap } from "../lib/api/types";
import { SourceChip } from "./SourceChip";

const STATUS = {
  done: { cls: "done", label: "Done" },
  overdue: { cls: "review", label: "Overdue" },
  missing: { cls: "review", label: "Missing" },
} as const;

export function CareGapRow({ patientId, gap }: { patientId: string; gap: CareGap }) {
  const s = STATUS[gap.status];
  return (
    <div className="item">
      <span className={`sev ${s.cls}`}>{s.label}</span>
      <span>
        <b>{gap.name}</b> <span className="muted">{gap.detail}</span>
      </span>
      {gap.source ? <SourceChip patientId={patientId} source={gap.source} /> : <span className="chip">No source link</span>}
    </div>
  );
}
