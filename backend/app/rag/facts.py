"""Deterministic facts extractor and rule-based clinical router (app/rag/facts.py).

Builds a per-patient facts table (concept, value, unit, date, chunk_id, quote)
from readable chunks using regex and dictionary matching.

NOTE ON DATASET FORMAT DEPENDENCY:
This extractor is calibrated against the synthetic dataset's specific layout:
- Lab reports have structured lines of the format 'Test Name: value unit'
- File identifiers/headers contain ISO dates 'YYYY-MM-DD'
- Visit notes and eye/clinic reports follow consistent phrase structures
Any significant change in raw text formats requires updating these extraction rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.constants import REFUSAL_TEXT
from app.terms.terms import CONCEPTS, detect_concepts, normalize_arabic


@dataclass
class Fact:
    concept: str
    value: Any
    unit: str
    date: str
    chunk_id: str
    quote: str


MONTH_MAP = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}


def _extract_date_from_header_or_chunk(chunk_id: str, text: str) -> str:
    """Extract ISO date YYYY-MM-DD from chunk ID or chunk header."""
    # Check chunk_id (e.g. 1042-Lab_Report_2025-03-12-p1)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", chunk_id)
    if m:
        return m.group(1)

    # Check text for YYYY-MM-DD
    m_text = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m_text:
        return m_text.group(1)

    # Check text for 'DD Mon YYYY' (e.g. '12 Mar 2025', '18 Jun 2026')
    m_text_mon = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\b", text)
    if m_text_mon:
        day = m_text_mon.group(1).zfill(2)
        mon = MONTH_MAP.get(m_text_mon.group(2).lower()[:3], "01")
        year = m_text_mon.group(3)
        return f"{year}-{mon}-{day}"

    return "2025-01-01"


def extract_patient_facts(chunks: list[Any]) -> list[Fact]:
    """Extract structured clinical facts from a patient's readable chunks.

    Supported concepts:
    - hba1c, egfr, creatinine, fasting_glucose, total_cholesterol, ldl, hdl,
      triglycerides, uacr
    - medications
    - retinal_exam, foot_exam
    - hypoglycemia_symptoms
    """
    facts: list[Fact] = []

    for chunk in chunks:
        chunk_id = chunk.id
        text = chunk.text
        file_date = _extract_date_from_header_or_chunk(chunk_id, text)

        for line in text.splitlines():
            line_clean = line.strip()
            if not line_clean:
                continue

            # 1. HbA1c
            # Format: 'Glycated Hemoglobin (HbA1c): 7.4% (Reference: <5.7%)' or 'HbA1c: 8.9%'
            m_hba1c = re.search(
                r"(?:Glycated Hemoglobin\s*(?:\(HbA1c\))?|HbA1c)\s*:\s*([\d\.]+)\s*(%?)",
                line_clean,
                re.IGNORECASE,
            )
            if m_hba1c:
                val = float(m_hba1c.group(1))
                if not any(f.concept == "hba1c" and f.date == file_date for f in facts):
                    facts.append(
                        Fact(
                            concept="hba1c",
                            value=val,
                            unit="%",
                            date=file_date,
                            chunk_id=chunk_id,
                            quote=line_clean,
                        )
                    )
                continue

            # 2. eGFR
            # Lab: 'Estimated GFR: 78 mL/min/1.73m² (CKD-EPI 2021)'
            m_egfr_lab = re.search(
                r"(?:Estimated GFR|eGFR)\s*:\s*(\d+)\s*(mL/min/1\.73m[²2]?)?",
                line_clean,
                re.IGNORECASE,
            )
            if m_egfr_lab:
                val = int(m_egfr_lab.group(1))
                if not any(f.concept == "egfr" and f.date == file_date for f in facts):
                    facts.append(
                        Fact(
                            concept="egfr",
                            value=val,
                            unit="mL/min/1.73m²",
                            date=file_date,
                            chunk_id=chunk_id,
                            quote=line_clean,
                        )
                    )
                continue

            # Note: 'Estimated GFR today is 59 mL/min/1.73m², down from 78...'
            m_egfr_note = re.search(
                r"Estimated GFR today is (\d+)\s*(mL/min/1\.73m[²2]?)?",
                line_clean,
                re.IGNORECASE,
            )
            if m_egfr_note:
                val = int(m_egfr_note.group(1))
                if not any(f.concept == "egfr" and f.date == file_date for f in facts):
                    facts.append(
                        Fact(
                            concept="egfr",
                            value=val,
                            unit="mL/min/1.73m²",
                            date=file_date,
                            chunk_id=chunk_id,
                            quote=line_clean,
                        )
                    )
                continue

            # 3. Serum Creatinine
            m_cr = re.search(
                r"(?:Serum Creatinine|Creatinine)\s*:\s*([\d\.]+)\s*(mg/dL)?",
                line_clean,
                re.IGNORECASE,
            )
            if m_cr:
                val = float(m_cr.group(1))
                facts.append(
                    Fact(
                        concept="creatinine",
                        value=val,
                        unit="mg/dL",
                        date=file_date,
                        chunk_id=chunk_id,
                        quote=line_clean,
                    )
                )
                continue

            # 4. Fasting Blood Glucose
            m_fbg = re.search(
                r"(?:Fasting Blood Glucose|Fasting Glucose|FBG)\s*:\s*([\d\.]+)\s*(mg/dL)?",
                line_clean,
                re.IGNORECASE,
            )
            if m_fbg:
                val = float(m_fbg.group(1))
                facts.append(
                    Fact(
                        concept="fasting_glucose",
                        value=val,
                        unit="mg/dL",
                        date=file_date,
                        chunk_id=chunk_id,
                        quote=line_clean,
                    )
                )
                continue

            # 5. Total Cholesterol
            m_tc = re.search(
                r"Total Cholesterol\s*:\s*([\d\.]+)\s*(mg/dL)?",
                line_clean,
                re.IGNORECASE,
            )
            if m_tc:
                val = float(m_tc.group(1))
                facts.append(
                    Fact(
                        concept="total_cholesterol",
                        value=val,
                        unit="mg/dL",
                        date=file_date,
                        chunk_id=chunk_id,
                        quote=line_clean,
                    )
                )
                continue

            # 6. LDL Cholesterol
            m_ldl = re.search(
                r"LDL Cholesterol\s*:\s*([\d\.]+)\s*(mg/dL)?",
                line_clean,
                re.IGNORECASE,
            )
            if m_ldl:
                val = float(m_ldl.group(1))
                facts.append(
                    Fact(
                        concept="ldl",
                        value=val,
                        unit="mg/dL",
                        date=file_date,
                        chunk_id=chunk_id,
                        quote=line_clean,
                    )
                )
                continue

            # 7. HDL Cholesterol
            m_hdl = re.search(
                r"HDL Cholesterol\s*:\s*([\d\.]+)\s*(mg/dL)?",
                line_clean,
                re.IGNORECASE,
            )
            if m_hdl:
                val = float(m_hdl.group(1))
                facts.append(
                    Fact(
                        concept="hdl",
                        value=val,
                        unit="mg/dL",
                        date=file_date,
                        chunk_id=chunk_id,
                        quote=line_clean,
                    )
                )
                continue

            # 8. Triglycerides
            m_tg = re.search(
                r"Triglycerides\s*:\s*([\d\.]+)\s*(mg/dL)?",
                line_clean,
                re.IGNORECASE,
            )
            if m_tg:
                val = float(m_tg.group(1))
                facts.append(
                    Fact(
                        concept="triglycerides",
                        value=val,
                        unit="mg/dL",
                        date=file_date,
                        chunk_id=chunk_id,
                        quote=line_clean,
                    )
                )
                continue

            # 9. UACR
            m_uacr = re.search(
                r"(?:Urine Albumin-to-Creatinine Ratio|UACR|ACR)\s*:\s*([\d\.]+)\s*(mg/g)?",
                line_clean,
                re.IGNORECASE,
            )
            if m_uacr:
                val = float(m_uacr.group(1))
                facts.append(
                    Fact(
                        concept="uacr",
                        value=val,
                        unit="mg/g",
                        date=file_date,
                        chunk_id=chunk_id,
                        quote=line_clean,
                    )
                )
                continue

            # 10. Retinal Exam
            if re.search(
                r"(?:dilated retinal examination|retinal exam|funduscopy)", line_clean, re.I
            ):
                m_ret_date = re.search(r"completed(?:\s+on\s+([^\.]+))?", line_clean, re.I)
                exam_date = file_date
                if m_ret_date and m_ret_date.group(1):
                    # parse date string if present
                    parsed_d = _extract_date_from_header_or_chunk("", m_ret_date.group(1))
                    if parsed_d != "2025-01-01":
                        exam_date = parsed_d
                facts.append(
                    Fact(
                        concept="retinal_exam",
                        value=exam_date,
                        unit="",
                        date=exam_date,
                        chunk_id=chunk_id,
                        quote=line_clean,
                    )
                )

            # 11. Foot Exam
            if re.search(r"(?:foot examination|preventive foot screening)", line_clean, re.I):
                facts.append(
                    Fact(
                        concept="foot_exam",
                        value=file_date,
                        unit="",
                        date=file_date,
                        chunk_id=chunk_id,
                        quote=line_clean,
                    )
                )

            # 12. Hypoglycemia symptoms
            if re.search(
                r"(?:night-time sweating|hypoglycemia|low glucose symptoms|lightheadedness)",
                line_clean,
                re.I,
            ):
                facts.append(
                    Fact(
                        concept="hypoglycemia_symptoms",
                        value="present",
                        unit="",
                        date=file_date,
                        chunk_id=chunk_id,
                        quote=line_clean,
                    )
                )

            # 13. Medications
            for concept_def in CONCEPTS:
                if concept_def.get("class") in (
                    "biguanide",
                    "sulfonylurea",
                    "DPP-4 inhibitor",
                    "SGLT2 inhibitor",
                    "GLP-1 receptor agonist",
                    "thiazolidinedione",
                    "statin",
                    "insulin",
                ):
                    med_name = concept_def["canonical_name"]
                    if re.search(rf"\b{re.escape(med_name)}\b", line_clean, re.I):
                        facts.append(
                            Fact(
                                concept="medication",
                                value=med_name,
                                unit="",
                                date=file_date,
                                chunk_id=chunk_id,
                                quote=line_clean,
                            )
                        )

    return facts


def classify_question_intent(question: str) -> tuple[str | None, str | None]:
    """Classify factual query intent strictly from the raw question text.

    CRITICAL RULE (User Requirement 5):
    The facts router must decide ONLY from the question text, never from any
    external metadata or 'type' field of questions.jsonl.

    NOTE ON DATASET FORMAT DEPENDENCY:
    This extractor and router are calibrated against the synthetic dataset's specific layout:
    - Lab reports have structured lines of the format 'Test Name: value unit'
    - File identifiers/headers contain ISO dates 'YYYY-MM-DD'
    - Visit notes and eye/clinic reports follow consistent phrase structures
    Any significant change in raw text formats requires updating these extraction rules.
    """
    detected = detect_concepts(question)
    concept_id = detected[0]["id"] if detected else None

    q_lower = question.lower()
    q_norm = normalize_arabic(question)

    # 1. Absence queries (checks if asking for concepts known to be absent from patient records)
    if re.search(
        r"\b(uacr|urine albumin|microalbumin|c-peptide|islet cell|gad antibody)\b", q_lower
    ) or re.search(r"(زلال|ألبومين|سي ببتيد)", q_norm):
        return "absence", (concept_id or "uacr")

    # 2. First vs Last
    if (
        (
            re.search(r"\b(first|earliest|initial)\b", q_lower)
            and re.search(r"\b(last|latest|most recent)\b", q_lower)
        )
        or (
            re.search(r"\b(change|differ|evolv\w*)\b", q_lower)
            and re.search(r"\bfrom (the )?(first|initial|earliest)\b", q_lower)
        )
        or (re.search(r"(أول|بداية)", q_norm) and re.search(r"(آخر|أحدث)", q_norm))
    ):
        return "first_vs_last", concept_id

    # 3. Trend
    trend_pat = (
        r"\b(trend|trending|over time|trajectory|progress\w*|"
        r"rising or falling|increas\w* or decreas\w*)\b"
    )
    if re.search(trend_pat, q_lower) or re.search(
        r"(تطور|مسار|اتجاه|تغير عبر الوقت|ارتفع.*أم.*انخفض)", q_norm
    ):
        return "trend", concept_id

    # 4. Exam date queries (retinal/foot)
    if (
        (
            re.search(r"\b(eye|retin\w*|fundus|foot|feet|podiatr\w*)\b", q_lower)
            and re.search(r"\b(exam\w*|screen\w*|date|when)\b", q_lower)
        )
        or re.search(r"\bwhen was.*(eye|retin\w*|foot|feet)\b", q_lower)
        or re.search(r"(فحص.*(عين|شبكية|قدم)|متى.*(فحص|عين|قدم))", q_norm)
    ):
        return "exam_date", concept_id

    # 5. Value at date (has specific date YYYY-MM-DD or Month YYYY)
    has_date = bool(
        re.search(r"\b\d{4}-\d{2}-\d{2}\b", question)
        or re.search(
            r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}\b",
            q_lower,
        )
        or re.search(
            r"في\s+(يناير|فبراير|مارس|أبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر)\s+\d{4}",
            q_norm,
        )
    )
    if has_date:
        return "value_at_date", concept_id

    # 6. Last value
    if re.search(r"\b(last|latest|most recent|recent)\b", q_lower) or re.search(
        r"(آخر|أحدث)", q_norm
    ):
        if concept_id:
            return "last_value", concept_id

    # 7. Medication queries
    if re.search(r"\b(medicat\w*|drugs?|prescrib\w*|taking|rx)\b", q_lower) or re.search(
        r"(أدوية|دواء|علاج|يتناول|عقاقير)", q_norm
    ):
        return "medication", concept_id

    # 8. Symptoms (hypoglycemia)
    if re.search(
        r"\b(hypoglycem\w*|low glucose|low (blood )?sugar|sweating|tremors?|shakin\w*)\b",
        q_lower,
    ) or re.search(r"(هبوط.*سكر|انخفاض.*سكر|أعراض.*(سكر|نقص))", q_norm):
        return "symptom", concept_id

    # 9. Specific lab concept without extra qualifiers -> last_value
    if concept_id and concept_id in (
        "hba1c",
        "egfr",
        "creatinine",
        "glucose",
        "bp",
        "cholesterol",
        "ldl",
        "hdl",
    ):
        return "last_value", concept_id

    return None, None


def answer_from_facts(
    patient_id: str,
    question: str,
    facts: list[Fact],
    all_chunks: list[Any],
) -> dict[str, Any] | None:
    """Answer factual queries deterministically from the extracted facts table.

    Decides purely from question text (never from question_type).
    Returns dict matching pipeline interface or None to fall back to hybrid search.
    """
    intent, concept_id = classify_question_intent(question)
    if intent is None:
        return None

    # Helper: filter facts by concept
    def get_concept_facts(cid: str) -> list[Fact]:
        return sorted([f for f in facts if f.concept == cid], key=lambda x: x.date)

    if intent == "last_value" and concept_id:
        cfacts = get_concept_facts(concept_id)
        if cfacts:
            last = cfacts[-1]
            unit_str = f" {last.unit}" if last.unit else ""
            cname = last.concept.upper()
            answer = (
                f"The last {cname} value was {last.value}{unit_str} on {last.date}. "
                "Worth reviewing."
            )
            return {
                "answer": answer,
                "answerable": True,
                "citations": [{"chunk_id": last.chunk_id, "quote": last.quote}],
                "retrieved_chunk_ids": [last.chunk_id],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            }

    elif intent == "value_at_date" and concept_id:
        # Extract target date from question
        m_date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", question)
        target_date = m_date.group(1) if m_date else None
        if not target_date:
            m_mon = re.search(r"\b([A-Za-z]{3,9})\s+(\d{4})\b", question)
            if m_mon:
                mon = MONTH_MAP.get(m_mon.group(1).lower()[:3], "")
                year = m_mon.group(2)
                target_date = f"{year}-{mon}"

        cfacts = get_concept_facts(concept_id)
        matched = [f for f in cfacts if target_date and f.date.startswith(target_date)]
        if matched:
            fact = matched[-1]
            unit_str = f" {fact.unit}" if fact.unit else ""
            cname = fact.concept.upper()
            answer = (
                f"The {cname} value on {fact.date} was {fact.value}{unit_str}. Worth reviewing."
            )
            return {
                "answer": answer,
                "answerable": True,
                "citations": [{"chunk_id": fact.chunk_id, "quote": fact.quote}],
                "retrieved_chunk_ids": [fact.chunk_id],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            }

    elif intent == "first_vs_last" and concept_id:
        cfacts = get_concept_facts(concept_id)
        if len(cfacts) >= 2:
            first = cfacts[0]
            last = cfacts[-1]
            unit_str = f" {last.unit}" if last.unit else ""
            answer = (
                f"{last.concept.upper()} changed from {first.value}{unit_str} on {first.date} "
                f"to {last.value}{unit_str} on {last.date}. Worth reviewing."
            )
            citations = [
                {"chunk_id": first.chunk_id, "quote": first.quote},
                {"chunk_id": last.chunk_id, "quote": last.quote},
            ]
            return {
                "answer": answer,
                "answerable": True,
                "citations": citations,
                "retrieved_chunk_ids": [first.chunk_id, last.chunk_id],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            }

    elif intent == "trend" and concept_id:
        cfacts = get_concept_facts(concept_id)
        if len(cfacts) >= 2:
            first = cfacts[0]
            last = cfacts[-1]
            try:
                v_first = float(first.value)
                v_last = float(last.value)
                if v_last > v_first:
                    direction = "rising"
                elif v_last < v_first:
                    direction = "falling"
                else:
                    direction = "stable"
            except (ValueError, TypeError):
                direction = "changing"

            unit_str = f" {last.unit}" if last.unit else ""
            cname = last.concept.upper()
            answer = (
                f"{cname} showed a {direction} trend from {first.value}{unit_str} on {first.date} "
                f"to {last.value}{unit_str} on {last.date}. Worth reviewing."
            )
            citations = [
                {"chunk_id": first.chunk_id, "quote": first.quote},
                {"chunk_id": last.chunk_id, "quote": last.quote},
            ]
            return {
                "answer": answer,
                "answerable": True,
                "citations": citations,
                "retrieved_chunk_ids": [first.chunk_id, last.chunk_id],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            }

    elif intent == "medication":
        med_facts = [f for f in facts if f.concept == "medication"]
        if med_facts:
            unique_meds = list(dict.fromkeys([f.value for f in med_facts]))
            citations = [{"chunk_id": f.chunk_id, "quote": f.quote} for f in med_facts[:3]]
            meds_str = ", ".join(unique_meds)
            answer = (
                f"The documented medications in the record include: {meds_str}. Worth reviewing."
            )
            return {
                "answer": answer,
                "answerable": True,
                "citations": citations,
                "retrieved_chunk_ids": [c["chunk_id"] for c in citations],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            }

    elif intent == "exam_date":
        exam_id = concept_id if concept_id in ("retinal_exam", "foot_exam") else "retinal_exam"
        exam_facts = get_concept_facts(exam_id)
        if exam_facts:
            last = exam_facts[-1]
            ename = last.concept.replace("_", " ")
            answer = f"The {ename} was documented on {last.date}. Worth reviewing."
            return {
                "answer": answer,
                "answerable": True,
                "citations": [{"chunk_id": last.chunk_id, "quote": last.quote}],
                "retrieved_chunk_ids": [last.chunk_id],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            }

    elif intent == "symptom":
        sym_facts = [f for f in facts if f.concept == "hypoglycemia_symptoms"]
        if sym_facts:
            last = sym_facts[-1]
            answer = (
                f"Low glucose / hypoglycemia symptoms were documented on {last.date}. "
                "Worth reviewing."
            )
            return {
                "answer": answer,
                "answerable": True,
                "citations": [{"chunk_id": last.chunk_id, "quote": last.quote}],
                "retrieved_chunk_ids": [last.chunk_id],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            }

    elif intent == "absence":
        # Check if concept is absent
        target_concept = concept_id or "uacr"
        cfacts = get_concept_facts(target_concept)
        if len(cfacts) == 0:
            num_files = len(all_chunks)
            dates = [
                _extract_date_from_header_or_chunk(c.id, c.text)
                for c in all_chunks
                if _extract_date_from_header_or_chunk(c.id, c.text) != "2025-01-01"
            ]
            min_date = min(dates) if dates else "2025-01-01"
            max_date = max(dates) if dates else "2026-06-30"
            answer = (
                f"{REFUSAL_TEXT} "
                f"Searched for {target_concept.upper()} across {num_files} readable pages "
                f"spanning {min_date} to {max_date}."
            )
            return {
                "answer": answer,
                "answerable": False,
                "citations": [],
                "retrieved_chunk_ids": [],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            }

    return None
