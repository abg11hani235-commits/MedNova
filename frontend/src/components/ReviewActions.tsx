"use client";

import { useReview } from "../lib/api/hooks";
import type { Feedback, ReviewState } from "../lib/api/types";

export function ReviewActions({
  patientId,
  insightId,
  reviewState,
  feedback,
}: {
  patientId: string;
  insightId: string;
  reviewState: ReviewState;
  feedback: Feedback;
}) {
  const review = useReview(patientId);
  const send = (action: "reviewed" | "helpful" | "not_helpful") => review.mutate({ insightId, action });
  return (
    <div className="row">
      <button className="btn ghost sm" disabled={reviewState === "reviewed"} onClick={() => send("reviewed")}>
        {reviewState === "reviewed" ? "Reviewed" : "Mark as reviewed"}
      </button>
      <button className="btn ghost sm" aria-pressed={feedback === "helpful"} onClick={() => send("helpful")}>
        Helpful
      </button>
      <button className="btn ghost sm" aria-pressed={feedback === "not_helpful"} onClick={() => send("not_helpful")}>
        Not helpful
      </button>
    </div>
  );
}
