"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { ChatBubble } from "../../../../../components/ChatBubble";
import { InsightRow } from "../../../../../components/InsightCard";
import { SourceChip } from "../../../../../components/SourceChip";
import { useBrief, useChat, useSuggestions } from "../../../../../lib/api/hooks";
import type { Source } from "../../../../../lib/api/types";

interface Msg {
  role: "user" | "assistant";
  text: string;
  answerable?: boolean;
  source?: Source | null;
}

export default function ChatPage() {
  const { id } = useParams<{ id: string }>();
  const brief = useBrief(id);
  const chat = useChat(id);
  const suggestions = useSuggestions(id);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");

  const ask = async (question: string) => {
    const q = question.trim();
    if (!q || chat.isPending) return;
    setMsgs((m) => [...m, { role: "user", text: q }]);
    setText("");
    try {
      const a = await chat.mutateAsync(q);
      setMsgs((m) => [...m, { role: "assistant", text: a.answer, answerable: a.answerable, source: a.source }]);
    } catch {
      setMsgs((m) => [...m, { role: "assistant", text: "The question could not be sent. Please try again.", answerable: false }]);
    }
  };
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void ask(text);
  };

  return (
    <>
      <div className="row">
        <h1>Ask Rafiq</h1>
        <span className="chip">Answers come only from this patient&apos;s files</span>
      </div>
      <div className="grid" style={{ gridTemplateColumns: "1fr 420px" }}>
        <section className="card">
          <h2>Patient Brief</h2>
          <div className="muted">{brief.data?.patient.display_name}</div>
          {brief.data?.snapshot.slice(0, 3).map((i) => <InsightRow key={i.id} patientId={id} insight={i} />)}
          <Link className="btn ghost" href={`/patients/${id}`}>Open full brief</Link>
        </section>
        <section className="card chat" aria-label="Chat">
          <div className="row">
            {(suggestions.data ?? []).map((s) => (
              <button key={s} className="chip" style={{ cursor: "pointer" }} onClick={() => void ask(s)}>{s}</button>
            ))}
          </div>
          <div role="log" aria-live="polite" style={{ display: "grid", gap: 12 }}>
            {msgs.map((m, i) =>
              m.role === "user" ? (
                <ChatBubble key={i} variant="user">{m.text}</ChatBubble>
              ) : (
                <ChatBubble
                  key={i}
                  variant={m.answerable ? "assistant" : "not-found"}
                  extra={m.source ? <SourceChip patientId={id} source={m.source} /> : m.answerable === false ? <span className="muted" dir="auto">Nothing was inferred or guessed.</span> : null}
                >
                  {m.text}
                </ChatBubble>
              ),
            )}
          </div>
          <form className="chat-input" onSubmit={onSubmit}>
            <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask Rafiq about this patient's files" aria-label="Question" dir="auto" />
            <button className="btn" type="submit" disabled={chat.isPending}>Ask</button>
          </form>

        </section>
      </div>
    </>
  );
}
