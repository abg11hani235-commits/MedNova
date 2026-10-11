import type { Severity } from "../lib/api/types";

const LABEL: Record<Severity, string> = { info: "Info", review: "Review", urgent_review: "Urgent Review" };
const CLS: Record<Severity, string> = { info: "info", review: "review", urgent_review: "urgent" };

/** Severity is conveyed by a shape icon (CSS), a text label and a color, never color alone. */
export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`sev ${CLS[severity]}`} data-severity={severity}>
      {LABEL[severity]}
    </span>
  );
}
