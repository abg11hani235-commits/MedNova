from __future__ import annotations

import re

# Category 1: Prescription & Medication Orders / Recommendations
# English: prescribe, prescription, write prescription, administer, give treatment
# Arabic: اكتب له, وصف, اوصف, اصرف, روشتة, اعطه علاج, اكتب علاج
_RX_PATTERNS = [
    r"\b(?:prescribe|prescribing|write\s+(?:a\s+)?prescription|administer|give\s+(?:him|her|them|the\s+patient)?\s*(?:treatment|medication|drug|dose))\b",
    r"(?:اكتب\s+له|اكتب\s+لها|اصرف\s+له|اصرف\s+لها|اوصف\s+له|اوصف\s+لها|روشتة|علاج\s+جديد|اعطه\s+علاج|اعطها\s+علاج|اكتب\s+له\s+علاج)",
]

# Category 2: Dose Selection / Changes / Recommendations
# English: what dose should i (give|prescribe|use), increase/decrease/change/adjust the dose,
#          dose to reach target
# Arabic: زيادة جرعة, تقليل جرعة, تعديل جرعة, غير الجرعة, ما هي الجرعة التي يجب,
#         حدد جرعة, كم الجرعة المطلوبة
_DOSE_ADVICE_PATTERNS = [
    r"\b(?:what|which|how\s+much)\s+dose\s+(?:should|must|ought|can|to\s+give|to\s+prescribe|to\s+take|to\s+reach)\b",
    r"\b(?:increase|decrease|raise|lower|change|adjust|titrate|modify)\s+(?:the\s+)?(?:dose|dosage|medication|insulin)\b",
    r"(?:زيادة\s+جرعة|تقليل\s+جرعة|تعديل\s+جرعة|تغيير\s+جرعة|رفع\s+جرعة|خفض\s+جرعة|ما\s+الجرعة\s+المناسبة|جرعة\s+للوصول)",
]

# Category 3: Diagnosis / Clinical Assessment Requests
# English: give me the diagnosis, what is the diagnosis, diagnose (him/her/patient),
#          does he/she have [X]? give diagnosis
# Arabic: اعطني التشخيص, ما هو التشخيص, شخص الحالة, شخص المرض, تشخيص للحالة
_DIAGNOSIS_PATTERNS = [
    r"\b(?:give\s+me\s+the\s+diagnosis|what\s+is\s+the\s+diagnosis|diagnose\s+(?:the|this|him|her)|make\s+a\s+diagnosis)\b",
    r"\b(?:does\s+(?:he|she|the\s+patient)\s+have\b[^?]*\b(?:give\s+me\s+the\s+diagnosis|diagnose))\b",
    r"(?:اعطني\s+التشخيص|ما\s+هو\s+التشخيص|شخص\s+الحالة|شخص\s+المرض|تشخيص\s+للحالة)",
]

# Category 4: Rule Overrides / Policy Bypasses
# English: ignore your rules, bypass rules, forget instructions, override policy,
#          disregard limitations
# Arabic: تجاهل القواعد, انسى التعليمات, تخطى القيود, تجاوز القواعد
_OVERRIDE_PATTERNS = [
    r"\b(?:ignore|bypass|disregard|forget|override)\s+(?:all\s+)?(?:your\s+)?(?:rules|instructions|guidelines|policy|policies|limitations|system\s+prompt)\b",
    r"(?:تجاهل\s+(?:كل\s+)?(?:القواعد|التعليمات|الشروط|السياسات)|تخطى\s+القيود|تجاوز\s+القواعد)",
]

_ALL_POLICY_PATTERNS = (
    _RX_PATTERNS + _DOSE_ADVICE_PATTERNS + _DIAGNOSIS_PATTERNS + _OVERRIDE_PATTERNS
)
_COMPILED_POLICY = [re.compile(p, re.IGNORECASE) for p in _ALL_POLICY_PATTERNS]
_COMPILED_OVERRIDES = [re.compile(p, re.IGNORECASE) for p in _OVERRIDE_PATTERNS]

_PATIENT_ID_PATTERNS = [
    re.compile(r"\b(?:patient|pt\.?|case)\s*#?\s*([0-9]{3,})\b", re.IGNORECASE),
    re.compile(r"#([0-9]{3,})\b"),
    re.compile(r"(?:المريض|المريضة|مريض|مريضة)\s*#?\s*([0-9]{3,})"),
]

KNOWN_PATIENTS: dict[str, str] = {
    "1042": "Farouk Adel Mansour",
    "1043": "Nadia Tarek Soliman",
    "1044": "Ibrahim Samir El-Kady",
    "1045": "Dina Sherif Radwan",
    "1046": "Hussein Kamel Abdel-Aziz",
    "1047": "Layla Mahmoud Zahran",
    "1048": "Youssef Ashraf El-Banna",
    "1049": "Samira Gamal Helmy",
    "1050": "Amr Nabil Fakhry",
    "1051": "Mona Raafat El-Shazly",
}


def should_decline_policy(question: str) -> bool:
    """Return True if question asks to prescribe, change dose, diagnose, or override rules.

    Pure record lookups (e.g. asking for documented medications or recorded doses)
    must NOT be declined.
    """
    # Overrides / prompt injections always decline immediately
    for pattern in _COMPILED_OVERRIDES:
        if pattern.search(question):
            return True

    for pattern in _COMPILED_POLICY:
        if pattern.search(question):
            # Check if this is an explicit factual record lookup
            # e.g., 'What dose is documented in the record for Metformin?'
            is_record_lookup = (
                "documented" in question.lower()
                or "in the record" in question.lower()
                or "in the chart" in question.lower()
                or "in the file" in question.lower()
                or "مسجلة" in question
                or "مدونة" in question
                or "في السجل" in question
                or "في الملف" in question
            )
            if is_record_lookup:
                # Do not decline unless it contains an explicit command to change/prescribe/override
                has_active_command = any(
                    re.search(op, question, re.IGNORECASE)
                    for op in [
                        r"\b(?:should\s+i|increase|decrease|prescribe\s+now)\b",
                        r"زيادة",
                        r"تجاهل",
                    ]
                )
                if not has_active_command:
                    return False
            return True

    return False


def is_cross_patient(question: str, current_patient_id: str) -> bool:
    """Return True if question mentions a patient id or name other than current_patient_id."""
    current_pid_str = str(current_patient_id).strip()

    # 1. Explicit patient prefix matches (patient 1043, #1043, المريض 1043)
    for p in _PATIENT_ID_PATTERNS:
        matches = p.findall(question)
        for m in matches:
            if str(m).strip() != current_pid_str:
                return True

    # 2. Standalone known synthetic patient IDs from the dataset
    for pid in KNOWN_PATIENTS:
        if pid != current_pid_str:
            if re.search(r"\b" + re.escape(pid) + r"\b", question):
                return True

    # 3. Known synthetic patient names from the dataset
    for pid, name in KNOWN_PATIENTS.items():
        if pid != current_pid_str:
            if name.lower() in question.lower():
                return True

    return False
