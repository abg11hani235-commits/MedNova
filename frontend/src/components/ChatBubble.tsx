import type { ReactNode } from "react";

type Variant = "user" | "assistant" | "not-found";
const CLS: Record<Variant, string> = { user: "u", assistant: "a", "not-found": "nf" };

export function ChatBubble({ variant, children, extra }: { variant: Variant; children: ReactNode; extra?: ReactNode }) {
  return (
    <div className={`bub ${CLS[variant]}`} data-variant={variant}>
      {children}
      {extra && <div style={{ marginTop: 6 }}>{extra}</div>}
    </div>
  );
}
