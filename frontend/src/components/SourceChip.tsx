import Link from "next/link";

import type { Source } from "../lib/api/types";

const NAMES: Record<string, string> = {
  Lab_Report: "Lab report",
  Visit_Note: "Visit note",
  Clinic_Note: "Clinic note",
  Nephrology_Note: "Nephrology note",
  Eye_Report: "Eye report",
};

export function sourceLabel(fileName: string): string {
  const stem = fileName.replace(/\.pdf$/i, "").replace(/_\d{4}-\d{2}-\d{2}$/, "");
  return NAMES[stem] ?? stem.replace(/_/g, " ");
}

export function SourceChip({ patientId, source }: { patientId: string; source: Source }) {
  return (
    <Link
      className="chip src"
      style={{ textDecoration: "none" }}
      href={`/patients/${patientId}/sources/${encodeURIComponent(source.chunk_id)}`}
    >
      {sourceLabel(source.file_name)} · p.{source.page}
    </Link>
  );
}
