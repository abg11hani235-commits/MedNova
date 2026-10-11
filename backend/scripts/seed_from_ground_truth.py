"""Seed the database from /data (ground truth JSON + page-delimited .txt). Idempotent.

Run from the backend folder:  python -m scripts.seed_from_ground_truth
"""

from app.config import get_settings
from app.db import get_session_factory
from app.seed import seed_all


def main() -> None:
    data_dir = get_settings().data_path
    with get_session_factory()() as db:
        ids = seed_all(db, data_dir)
    print(f"Seeded {len(ids)} patients from {data_dir}: {', '.join(ids)}")


if __name__ == "__main__":
    main()
