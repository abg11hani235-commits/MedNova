"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { getApi } from "../../../lib/api/client";
import type { MealLog, PatientChatResponse } from "../../../lib/api/types";

interface ChatMessageView {
  id: string;
  role: "patient" | "assistant";
  text: string;
  time: string;
  status?: string;
  mealLog?: MealLog | null;
  clarificationOptions?: Array<Record<string, unknown>> | null;
  safetyFlag?: string | null;
}

export default function PatientMealChatPage() {
  const params = useParams<{ id: string }>();
  const patientId = params?.id || "1042";
  const api = getApi();

  const [messages, setMessages] = useState<ChatMessageView[]>([
    {
      id: "welcome",
      role: "assistant",
      text: "أهلاً بيك! أنا رفيق، مساعدك لتسجيل الوجبات. تقدر تكتبلي أكلت إيه بلهجتك المصرية (مثلاً: «أكلت رغيف عيش بلدي وبيضتين مسلوقين») وأنا هحسب السعرات وأوصلها لأخصائي التغذية بتاعك.",
      time: new Date().toLocaleTimeString("ar-EG", { hour: "2-digit", minute: "2-digit" }),
    },
  ]);
  const [inputText, setInputText] = useState("");
  const [mealType, setMealType] = useState("snack");
  const [isLoading, setIsLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const text = inputText.trim();
    if (!text || isLoading) return;

    const userMsg: ChatMessageView = {
      id: `user-${Date.now()}`,
      role: "patient",
      text,
      time: new Date().toLocaleTimeString("ar-EG", { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText("");
    setIsLoading(true);

    try {
      const res: PatientChatResponse = await api.postPatientMealChat(
        patientId,
        text,
        mealType,
        `PT ${patientId}`
      );

      const assistantMsg: ChatMessageView = {
        id: `asst-${Date.now()}`,
        role: "assistant",
        text: res.reply,
        time: new Date().toLocaleTimeString("ar-EG", { hour: "2-digit", minute: "2-digit" }),
        status: res.status,
        mealLog: res.meal_log,
        clarificationOptions: res.clarification_options,
        safetyFlag: res.safety_flag,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          text: "حصل خطأ في الاتصال بالخدمة. برجاء المحاولة مرة أخرى.",
          time: new Date().toLocaleTimeString("ar-EG", { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectOption = async (option: Record<string, unknown>, mealLogId: string) => {
    if (isLoading) return;
    setIsLoading(true);

    const userConfirmMsg: ChatMessageView = {
      id: `user-confirm-${Date.now()}`,
      role: "patient",
      text: `اخترت: ${String(option.label || option.unit || "الحصة")}`,
      time: new Date().toLocaleTimeString("ar-EG", { hour: "2-digit", minute: "2-digit" }),
    };
    setMessages((prev) => [...prev, userConfirmMsg]);

    try {
      const updatedLog = await api.clarifyMeal(
        patientId,
        mealLogId,
        option,
        `PT ${patientId}`
      );

      const itemsSummary = updatedLog.items
        .map((it) => `${it.food_name_ar} (${it.quantity} ${it.unit})`)
        .join("، ");

      const reply = `تمام، سجلتلك: ${itemsSummary}. إجمالي السعرات: ${Math.round(
        updatedLog.total_kcal
      )} سعر حراري (تقديري). ألف صحة وهنا!`;

      setMessages((prev) => [
        ...prev,
        {
          id: `asst-clarified-${Date.now()}`,
          role: "assistant",
          text: reply,
          time: new Date().toLocaleTimeString("ar-EG", { hour: "2-digit", minute: "2-digit" }),
          status: "parsed",
          mealLog: updatedLog,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          text: "مش قادر أحدث السجل دلوقتي. برجاء المحاولة مرة أخرى.",
          time: new Date().toLocaleTimeString("ar-EG", { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      dir="rtl"
      lang="ar"
      style={{
        display: "flex",
        flexDirection: "column",
        minHeight: "100vh",
        background: "#F7FAFB",
        color: "#1A2B3C",
      }}
    >
      {/* Minimal Header without specialist navigation */}
      <header
        style={{
          background: "#fff",
          borderBottom: "1px solid #DDE5EA",
          padding: "12px 20px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo/rafiq-logo.svg" alt="Rafiq" height={26} style={{ height: 26, width: "auto" }} />
          <div>
            <b style={{ color: "#1F4E79", fontSize: "16px" }}>تسجيل وجبات المريض</b>
            <span className="chip" style={{ marginInlineStart: "8px", fontSize: "11px" }}>
              ملف المريض #{patientId}
            </span>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span className="chip" style={{ background: "#E6F2F3", color: "#0B5F67" }}>
            محادثة مريض
          </span>
          <Link href="/patients" className="btn ghost sm" style={{ fontSize: "12px" }}>
            لوحة الأخصائي
          </Link>
        </div>
      </header>

      {/* Main Chat Area */}
      <main
        style={{
          flex: 1,
          maxWidth: "800px",
          width: "100%",
          margin: "0 auto",
          padding: "16px",
          display: "flex",
          flexDirection: "column",
          gap: "14px",
        }}
      >
        {/* Chat message list */}
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            gap: "12px",
            overflowY: "auto",
            minHeight: "480px",
          }}
        >
          {messages.map((m) => {
            const isUser = m.role === "patient";
            return (
              <div
                key={m.id}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: isUser ? "flex-start" : "flex-end", // In RTL: flex-start is right, flex-end is left
                  maxWidth: "85%",
                  alignSelf: isUser ? "flex-start" : "flex-end",
                }}
              >
                <div
                  className={`bub ${isUser ? "u" : "a"}`}
                  dir="auto"
                  style={{
                    background: isUser ? "#1F4E79" : m.safetyFlag === "emergency_symptom" ? "#FEE2E2" : "#fff",
                    color: isUser ? "#fff" : m.safetyFlag === "emergency_symptom" ? "#991B1B" : "#1A2B3C",
                    border: m.safetyFlag === "emergency_symptom" ? "1px solid #F87171" : undefined,
                    boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
                    fontSize: "14px",
                    lineHeight: "1.5",
                  }}
                >
                  {m.text}

                  {/* Clarification Options as tappable buttons */}
                  {m.clarificationOptions && m.clarificationOptions.length > 0 && m.mealLog && (
                    <div
                      style={{
                        marginTop: "10px",
                        display: "flex",
                        flexWrap: "wrap",
                        gap: "6px",
                      }}
                    >
                      {m.clarificationOptions.map((opt, idx) => (
                        <button
                          key={idx}
                          type="button"
                          className="btn ghost sm"
                          style={{
                            background: "#fff",
                            borderColor: "#0E7C86",
                            color: "#0B5F67",
                            fontWeight: 600,
                          }}
                          onClick={() => handleSelectOption(opt, m.mealLog!.id)}
                          disabled={isLoading}
                        >
                          {String(opt.label || opt.unit)}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Parsed Meal Summary Badge */}
                  {m.mealLog && m.mealLog.items.length > 0 && (
                    <div
                      style={{
                        marginTop: "8px",
                        padding: "6px 10px",
                        background: isUser ? "rgba(255,255,255,0.15)" : "#F0FDF4",
                        border: isUser ? "none" : "1px solid #BBF7D0",
                        borderRadius: "6px",
                        fontSize: "12px",
                      }}
                    >
                      <div className="row" style={{ justifyContent: "space-between" }}>
                        <span>
                          السعرات: <b>{Math.round(m.mealLog.total_kcal)}</b> kcal
                        </span>
                        <span className="chip" style={{ fontSize: "10px", padding: "1px 6px" }}>
                          تقديري
                        </span>
                      </div>
                    </div>
                  )}
                </div>

                <span
                  style={{
                    fontSize: "11px",
                    color: "#8896A3",
                    margin: "2px 4px 0 4px",
                  }}
                >
                  {m.time}
                </span>
              </div>
            );
          })}

          {isLoading && (
            <div
              style={{
                alignSelf: "flex-end",
                background: "#fff",
                border: "1px solid #DDE5EA",
                borderRadius: "14px",
                padding: "8px 14px",
                fontSize: "13px",
                color: "#5B6B7A",
              }}
            >
              جاري حساب السعرات والتحقق...
            </div>
          )}

          <div ref={endRef} />
        </div>

        {/* Input Bar */}
        <form
          onSubmit={handleSend}
          className="card"
          style={{
            padding: "10px 14px",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}
        >
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <select
              value={mealType}
              onChange={(e) => setMealType(e.target.value)}
              aria-label="نوع الوجبة"
              style={{
                border: "1px solid #DDE5EA",
                borderRadius: "8px",
                padding: "8px 10px",
                background: "#fff",
                fontFamily: "inherit",
                fontSize: "13px",
                color: "#1F4E79",
                cursor: "pointer",
              }}
            >
              <option value="breakfast">إفطار</option>
              <option value="lunch">غداء</option>
              <option value="dinner">عشاء</option>
              <option value="snack">سناك</option>
            </select>

            <input
              type="text"
              dir="auto"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="اكتب أكلت إيه... (مثال: رغيف عيش بلدي مع بيضتين مسلوقين)"
              aria-label="رسالة الوجبة"
              disabled={isLoading}
              style={{
                flex: 1,
                border: "1px solid #DDE5EA",
                borderRadius: "8px",
                padding: "9px 12px",
                fontFamily: "inherit",
                fontSize: "14px",
              }}
            />

            <button
              type="submit"
              className="btn"
              disabled={!inputText.trim() || isLoading}
              style={{ padding: "9px 20px" }}
            >
              إرسال
            </button>
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              fontSize: "11px",
              color: "#788B9B",
              paddingInlineStart: "4px",
            }}
          >
            <span>الحسابات تقديرية وتعتمد على الوصف المدخل.</span>
            <span style={{ fontStyle: "italic" }}>القرار النهائي لأخصائي التغذية</span>
          </div>
        </form>
      </main>
    </div>
  );
}
