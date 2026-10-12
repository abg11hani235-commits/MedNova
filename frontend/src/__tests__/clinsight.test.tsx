import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatBubble } from "../components/ChatBubble";
import { SeverityBadge } from "../components/SeverityBadge";
import { SourceChip } from "../components/SourceChip";
import { REFUSAL_TEXT } from "../lib/constants";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "1042" }),
  usePathname: () => "/patients/1042",
}));

class RO {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(globalThis as unknown as { ResizeObserver: typeof RO }).ResizeObserver = RO;

import BriefPage from "../app/(app)/patients/[id]/page";

afterEach(cleanup);

describe("SeverityBadge", () => {
  it("shows a text label and a severity class (never color alone)", () => {
    render(<SeverityBadge severity="urgent_review" />);
    const badge = screen.getByText("Urgent Review");
    expect(badge).toHaveClass("sev", "urgent");
    expect(badge).toHaveAttribute("data-severity", "urgent_review");
  });
});

describe("SourceChip", () => {
  it("links to the Source Trace page with a readable label", () => {
    render(
      <SourceChip
        patientId="1042"
        source={{ chunk_id: "1042-Nephrology_Note_2026-06-18-p1", file_name: "Nephrology_Note_2026-06-18.pdf", page: 1, quote: "q", date: "2026-06-18" }}
      />,
    );
    const link = screen.getByRole("link", { name: /Nephrology note · p\.1/ });
    expect(link).toHaveAttribute("href", "/patients/1042/sources/1042-Nephrology_Note_2026-06-18-p1");
  });
});

describe("ChatBubble", () => {
  it("renders the refusal bubble in the not-found style", () => {
    render(<ChatBubble variant="not-found">{REFUSAL_TEXT}</ChatBubble>);
    expect(screen.getByText(REFUSAL_TEXT)).toHaveClass("nf");
  });
});

describe("Patient Brief", () => {
  it("renders insights sorted by severity with the disclaimer-safe wording", async () => {
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <BriefPage />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Synthetic Patient #1042")).toBeInTheDocument();
    const snapshot = screen.getByTestId("snapshot");
    const badges = within(snapshot).getAllByText(/^(Urgent Review|Review|Info)$/);
    expect(badges[0]).toHaveTextContent("Urgent Review");
    expect(within(snapshot).getAllByTestId("snapshot-item")).toHaveLength(5);
    expect(screen.getByText(/Based on 14 of 17 files/)).toBeInTheDocument();
  });
});
