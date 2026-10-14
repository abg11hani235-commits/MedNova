"""Test synthetic meal seeding and brief integration."""

from sqlalchemy.orm import sessionmaker

from app.config import ROOT
from app.db import make_engine
from app.models import Base, MealItem, MealLog, PatientChatMessage
from app.seed import seed_meals


def test_seed_meals_loads_and_is_idempotent():
    seed_file = ROOT / "data" / "seed_meals.json"
    assert seed_file.exists(), "data/seed_meals.json must exist"

    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    # Seed meals first time
    count1 = seed_meals(session, seed_file)
    assert count1 == 9  # 6 meals for 1042, 3 meals for 1043

    logs_1042 = session.query(MealLog).filter(MealLog.patient_id == "1042").all()
    assert len(logs_1042) == 6
    statuses_1042 = {log.status for log in logs_1042}
    assert "needs_clarification" in statuses_1042
    assert "rejected" in statuses_1042
    assert "emergency" in statuses_1042
    assert "parsed" in statuses_1042

    logs_1043 = session.query(MealLog).filter(MealLog.patient_id == "1043").all()
    assert len(logs_1043) == 3
    statuses_1043 = {log.status for log in logs_1043}
    assert "unknown_food" in statuses_1043
    assert "parsed" in statuses_1043

    # Items exist
    items = session.query(MealItem).all()
    assert len(items) > 0

    # Chat messages exist
    chat_msgs = session.query(PatientChatMessage).all()
    assert len(chat_msgs) == 9

    # Re-seed to verify idempotency (no duplicate rows)
    count2 = seed_meals(session, seed_file)
    assert count2 == 9
    assert session.query(MealLog).filter(MealLog.patient_id == "1042").count() == 6
    assert session.query(MealLog).filter(MealLog.patient_id == "1043").count() == 3

    session.close()
    engine.dispose()
