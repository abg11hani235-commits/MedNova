"use client";

import { useState } from "react";

import type { MealItem, MealLog, MealSection as MealSectionType } from "../lib/api/types";

interface Props {
  patientId: string;
  meals: MealSectionType;
}

export function MealsSection({ patientId, meals }: Props) {
  const [selectedTrace, setSelectedTrace] = useState<{
    item: MealItem;
    meal: MealLog;
  } | null>(null);

  if (!meals.has_logs || meals.recent_days.length === 0) {
    return null;
  }

  const mealTypeLabel: Record<string, string> = {
    breakfast: "إفطار (Breakfast)",
    lunch: "غداء (Lunch)",
    dinner: "عشاء (Dinner)",
    snack: "سناك (Snack)",
    unspecified: "وجبة (Meal)",
  };

  return (
    <section className="card" data-testid="meals-section" style={{ marginTop: "16px" }}>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h2>سجل التغذية والوجبات (Patient Meal Logs)</h2>
        <span className="chip" style={{ background: "#FEF3C7", color: "#92400E", fontWeight: 600 }}>
          تقديري · Unverified Estimates
        </span>
      </div>
      <p className="muted" style={{ margin: "4px 0 16px 0", fontSize: "13px" }}>
        الوجبات المسجلة بواسطة المريض عبر المحادثة اليومية. جميع الحسابات مستخرجة بقواعد برمجية حتمية بناءً على جدول الأطعمة المصرية التجريبي.
      </p>

      <div className="grid" style={{ gap: "16px" }}>
        {meals.recent_days.map((day) => (
          <div
            key={day.date}
            style={{
              border: "1px solid #DDE5EA",
              borderRadius: "10px",
              padding: "14px",
              background: "#FAFDFD",
            }}
          >
            {/* Day Header with Deterministic Totals */}
            <div className="row" style={{ justifyContent: "space-between", borderBottom: "1px solid #E6EFF3", paddingBottom: "8px" }}>
              <div>
                <b style={{ fontSize: "15px", color: "#1F4E79" }}>{day.date}</b>
                <span className="muted" style={{ marginInlineStart: "8px", fontSize: "13px" }}>
                  ({day.meal_count} {day.meal_count === 1 ? "وجبة" : "وجبات"})
                </span>
              </div>
              <div className="row" style={{ gap: "6px" }}>
                <span className="chip" title="إجمالي السعرات">
                  <b>{Math.round(day.total_kcal)}</b> kcal
                </span>
                <span className="chip" title="كربوهيدرات">
                  كارب <b>{Math.round(day.total_carbs_g)}</b>g
                </span>
                <span className="chip" title="بروتين">
                  بروتين <b>{Math.round(day.total_protein_g)}</b>g
                </span>
                <span className="chip" title="دهون">
                  دهون <b>{Math.round(day.total_fat_g)}</b>g
                </span>
                <span className="chip" style={{ fontSize: "11px", color: "#788B9B" }}>
                  تقديري
                </span>
              </div>
            </div>

            {/* List of meals for this day */}
            <div style={{ marginTop: "12px", display: "grid", gap: "12px" }}>
              {day.meals.map((meal) => (
                <div
                  key={meal.id}
                  style={{
                    background: "#fff",
                    border: "1px solid #E2EBF0",
                    borderRadius: "8px",
                    padding: "10px 14px",
                  }}
                >
                  <div className="row" style={{ justifyContent: "space-between", marginBottom: "6px" }}>
                    <div className="row">
                      <span className="chip" style={{ fontWeight: 600 }}>
                        {mealTypeLabel[meal.meal_type] || meal.meal_type}
                      </span>
                      {meal.logged_at && (
                        <span className="muted" style={{ fontSize: "12px" }}>
                          {meal.logged_at.slice(11, 16)}
                        </span>
                      )}
                      {meal.safety_flag === "emergency_symptom" && (
                        <span className="sev urgent" style={{ fontSize: "11px" }}>
                          طوارئ (123)
                        </span>
                      )}
                    </div>
                    <span className="muted" style={{ fontSize: "12px" }}>
                      المجموع: <b>{Math.round(meal.total_kcal)}</b> kcal
                    </span>
                  </div>

                  <div style={{ fontSize: "13px", color: "#3F4E5C", fontStyle: "italic", marginBottom: "8px" }}>
                    &ldquo;{meal.raw_text}&rdquo;
                  </div>

                  {meal.items.length > 0 && (
                    <div style={{ borderTop: "1px dashed #E2EBF0", paddingTop: "8px", display: "grid", gap: "6px" }}>
                      {meal.items.map((it) => (
                        <div
                          key={it.id}
                          className="row"
                          style={{ justifyContent: "space-between", fontSize: "13px" }}
                        >
                          <div>
                            <b>{it.food_name_ar}</b> ({it.food_name_en}) &mdash;{" "}
                            <span className="muted">
                              {it.quantity} {it.unit} ({it.grams} جم)
                            </span>
                          </div>
                          <div className="row" style={{ gap: "8px" }}>
                            <span>
                              <b>{Math.round(it.kcal)}</b> kcal
                            </span>
                            <button
                              type="button"
                              className="btn ghost sm"
                              style={{ padding: "2px 8px", fontSize: "11px" }}
                              onClick={() => setSelectedTrace({ item: it, meal })}
                              aria-label={`Source trace for ${it.food_name_ar}`}
                            >
                              Source Trace
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Source Trace Modal / Drawer */}
      {selectedTrace && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="trace-title"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15, 23, 42, 0.45)",
            backdropFilter: "blur(2px)",
            display: "grid",
            placeItems: "center",
            zIndex: 1000,
            padding: "16px",
          }}
          onClick={() => setSelectedTrace(null)}
        >
          <div
            className="card"
            style={{
              maxWidth: "560px",
              width: "100%",
              boxShadow: "0 10px 25px -5px rgba(0,0,0,0.2)",
              direction: "ltr",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="row" style={{ justifyContent: "space-between", borderBottom: "1px solid #DDE5EA", paddingBottom: "10px" }}>
              <div className="row">
                <span className="chip src">Source Trace</span>
                <b id="trace-title" style={{ fontSize: "15px" }}>{selectedTrace.item.food_name_ar} ({selectedTrace.item.food_name_en})</b>
              </div>
              <button
                type="button"
                className="btn ghost sm"
                onClick={() => setSelectedTrace(null)}
                aria-label="Close trace"
              >
                ✕
              </button>
            </div>

            <div style={{ marginTop: "14px", display: "grid", gap: "12px", fontSize: "13px" }}>
              {/* 1. Patient Raw Message */}
              <div>
                <b style={{ color: "#1F4E79" }}>1. Raw Patient Chat Input</b>
                <div
                  style={{
                    background: "#F7FAFB",
                    border: "1px solid #DDE5EA",
                    borderRadius: "6px",
                    padding: "10px 12px",
                    marginTop: "4px",
                    fontStyle: "italic",
                    direction: "rtl",
                    textAlign: "right",
                  }}
                >
                  &ldquo;{selectedTrace.meal.raw_text}&rdquo;
                </div>
                <span className="muted" style={{ fontSize: "11px" }}>
                  Logged at: {selectedTrace.meal.logged_at} · Date (Cairo): {selectedTrace.meal.local_date}
                </span>
              </div>

              {/* 2. Extraction & Matching */}
              <div>
                <b style={{ color: "#1F4E79" }}>2. Match Method & Scoring</b>
                <div style={{ marginTop: "4px" }}>
                  Method: <code>{selectedTrace.item.match_method}</code> · Confidence score: <code>{selectedTrace.item.match_score}</code>
                </div>
              </div>

              {/* 3. Egyptian Food Table Entry */}
              <div>
                <b style={{ color: "#1F4E79" }}>3. Composition Table Record (data/foods_eg.json)</b>
                <div
                  style={{
                    background: "#F7FAFB",
                    border: "1px solid #DDE5EA",
                    borderRadius: "6px",
                    padding: "8px 12px",
                    marginTop: "4px",
                    fontFamily: "monospace",
                    fontSize: "12px",
                  }}
                >
                  <div>food_id: {selectedTrace.item.food_id}</div>
                  <div>grams: {selectedTrace.item.grams}g (portion: {selectedTrace.item.quantity} {selectedTrace.item.unit})</div>
                  <div>kcal: {selectedTrace.item.kcal} | carbs: {selectedTrace.item.carbs_g}g | protein: {selectedTrace.item.protein_g}g | fat: {selectedTrace.item.fat_g}g</div>
                  <div style={{ color: "#92400E", marginTop: "4px", fontWeight: "bold" }}>
                    source: &quot;author estimate, unverified&quot; · verified: false
                  </div>
                </div>
              </div>

              {/* Disclaimer Notice */}
              <div
                style={{
                  background: "#FEF3C7",
                  border: "1px solid #FCD34D",
                  borderRadius: "6px",
                  padding: "8px 12px",
                  color: "#92400E",
                  fontSize: "12px",
                }}
              >
                <b>تنبيه الأمان:</b> القيم الغذائية مستخرجة من جدول تقديري تجريبي مؤلف ولم تخضع للتحقق المعملي. الأرقام للاسترشاد فقط والقرار النهائي للأخصائي.
              </div>
            </div>

            <div style={{ marginTop: "16px", display: "flex", justifyContent: "flex-end" }}>
              <button
                type="button"
                className="btn"
                onClick={() => setSelectedTrace(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
