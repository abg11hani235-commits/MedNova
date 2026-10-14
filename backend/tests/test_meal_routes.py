"""Tests for Patient Meal Logging & Chat routes and auth role enforcement."""

from fastapi.testclient import TestClient

from app.constants import EMERGENCY_SYMPTOM_TEXT, PATIENT_CHAT_DECLINE_TEXT


def test_auth_default_deny_no_actor_header(client: TestClient):
    """Missing X-Actor header must be rejected with 403 on patient routes."""
    # POST meal chat
    res = client.post("/patients/9001/meals/chat", json={"message": "أكلت بيضة"})
    assert res.status_code == 403
    assert "X-Actor header required" in res.json()["detail"]

    # GET meal history
    res = client.get("/patients/9001/meals/history")
    assert res.status_code == 403

    # GET daily summary
    res = client.get("/patients/9001/meals/daily-summary")
    assert res.status_code == 403


def test_auth_patient_actor_cannot_access_specialist_routes(client: TestClient):
    """Patient actors ('PT <pid>') must get 403 on specialist EHR routes."""
    headers = {"X-Actor": "PT 9001"}

    # Specialist brief
    res = client.get("/patients/9001/brief", headers=headers)
    assert res.status_code == 403
    assert "Patient actors cannot access specialist EHR routes" in res.json()["detail"]

    # Audit log
    res = client.get("/audit", headers=headers)
    assert res.status_code == 403

    # Patients list
    res = client.get("/patients", headers=headers)
    assert res.status_code == 403

    # Specialist chat
    res = client.post("/patients/9001/chat", json={"question": "What is HbA1c?"}, headers=headers)
    assert res.status_code == 403


def test_auth_patient_actor_wrong_pid(client: TestClient):
    """Patient PT 9002 cannot access patient 9001's meal routes."""
    headers = {"X-Actor": "PT 9002"}
    res = client.post(
        "/patients/9001/meals/chat",
        json={"message": "أكلت بيضة مسلوقة"},
        headers=headers,
    )
    assert res.status_code == 403
    assert "Patient cannot access another patient's data" in res.json()["detail"]

    res = client.get("/patients/9001/meals/history", headers=headers)
    assert res.status_code == 403


def test_auth_specialist_can_read_meals(client: TestClient):
    """Nutrition specialist (NS) can view patient meal history and daily summary."""
    headers = {"X-Actor": "NS (Nutrition Specialist)"}

    res = client.get("/patients/9001/meals/history", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    res = client.get("/patients/9001/meals/daily-summary", headers=headers)
    assert res.status_code == 200
    assert "total_kcal" in res.json()


def test_chat_parsed_meal_flow(client: TestClient):
    """Patient logs a normal meal that gets parsed and saved."""
    headers = {"X-Actor": "PT 9001"}
    res = client.post(
        "/patients/9001/meals/chat",
        json={"message": "أكلت رغيف عيش بلدي وبيضتين مسلوقين", "meal_type": "breakfast"},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "parsed"
    assert "سجلتلك" in data["reply"]
    assert "تقديري" in data["reply"]
    assert data["meal_log"] is not None
    assert len(data["meal_log"]["items"]) == 2

    # Verify history
    h_res = client.get("/patients/9001/meals/history", headers=headers)
    assert h_res.status_code == 200
    logs = h_res.json()
    assert len(logs) >= 1
    assert logs[0]["raw_text"] == "أكلت رغيف عيش بلدي وبيضتين مسلوقين"


def test_chat_clarification_flow(client: TestClient):
    """Ambiguous portion prompts clarification options, then clarify confirms it."""
    headers = {"X-Actor": "PT 9001"}
    res = client.post(
        "/patients/9001/meals/chat",
        json={"message": "أكلت كشري", "meal_type": "lunch"},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "needs_clarification"
    assert data["clarification_options"] is not None
    assert len(data["clarification_options"]) > 0

    log_id = data["meal_log"]["id"]

    # Clarify
    selected = data["clarification_options"][0]
    c_res = client.post(
        f"/patients/9001/meals/{log_id}/clarify",
        json={"selected_option": selected},
        headers=headers,
    )
    assert c_res.status_code == 200
    c_data = c_res.json()
    assert c_data["status"] == "parsed"
    assert len(c_data["items"]) == 1
    assert c_data["items"][0]["confirmed"] is True


def test_chat_unknown_food_flow(client: TestClient):
    """Unknown food returns unknown_food status with no invented numbers."""
    headers = {"X-Actor": "PT 9001"}
    res = client.post(
        "/patients/9001/meals/chat",
        json={"message": "أكلت زعبلوطة مع تيكيتيكي"},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "unknown_food"
    assert "مش موجودة في قاعدة بيانات الأطعمة المصرية" in data["reply"]
    assert data["meal_log"]["status"] == "unknown_food"
    assert len(data["meal_log"]["items"]) == 0


def test_chat_policy_decline_flow(client: TestClient):
    """Diet prescription request is rejected with exact Egyptian decline text."""
    headers = {"X-Actor": "PT 9001"}
    res = client.post(
        "/patients/9001/meals/chat",
        json={"message": "اديني دايت بلان للتخسيس وكام كالوري في اليوم؟"},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "rejected"
    assert data["reply"] == PATIENT_CHAT_DECLINE_TEXT
    assert data["safety_flag"] == "policy_decline"


def test_chat_emergency_flow_and_brief_wiring(client: TestClient):
    """Emergency symptom returns immediate triage advice with 123 and wires to brief."""
    headers = {"X-Actor": "PT 9001"}
    res = client.post(
        "/patients/9001/meals/chat",
        json={"message": "حاسس بهبوط حاد ودوخة وعرق وسكري 45"},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "emergency"
    assert data["reply"] == EMERGENCY_SYMPTOM_TEXT
    assert "123" in data["reply"]
    assert data["safety_flag"] == "emergency_symptom"

    # Now verify that when a specialist opens the brief, this urgent symptom is in considerations
    spec_headers = {"X-Actor": "NS (Nutrition Specialist)"}
    b_res = client.get("/patients/9001/brief", headers=spec_headers)
    assert b_res.status_code == 200
    brief_data = b_res.json()

    # Must contain an urgent_review consideration citing this message
    urgent_cons = [
        c
        for c in brief_data["considerations"]
        if c["severity"] == "urgent_review" and "severe symptoms" in c["statement"].lower()
    ]
    assert len(urgent_cons) == 1
    assert "حاسس بهبوط حاد" in urgent_cons[0]["source"]["quote"]
    assert urgent_cons[0]["source"]["file_name"] == "Patient Meal Chat"


def test_chat_record_lookup_flow(client: TestClient):
    """Plain record lookup returns structured summary of today's meals without inventing."""
    headers = {"X-Actor": "PT 9001"}
    res = client.post(
        "/patients/9001/meals/chat",
        json={"message": "أكلت إيه النهاردة؟"},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "record_lookup"
    assert isinstance(data["reply"], str)
