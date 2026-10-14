"""Single source of truth for strings shared across the API."""

REFUSAL_TEXT = "المعلومة دي مش موجودة في ملف المريض."
CROSS_PATIENT_TEXT = "I cannot access records for another patient."
DECLINE_POLICY_TEXT = (
    "أداة مساعدة لمتابعة التغذية، القرار النهائي للأخصائي. "
    "مش هقدر أكتب علاج، أحدد جرعات، أو أقدم تشخيص."
)
PATIENT_CHAT_DECLINE_TEXT = (
    "أنا مش بقدم نصايح علاجية أو غذائية. اسأل الأخصائي بتاعك، وأنا هسجل أكلك وأوصله ليه."
)
EMERGENCY_SYMPTOM_TEXT = (
    "دي أعراض طارئة تستدعي تدخل فوري. برجاء التوجه لأقرب طوارئ أو الاتصال بالإسعاف (123) فوراً."
)
