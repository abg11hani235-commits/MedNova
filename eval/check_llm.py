from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings


def check_models() -> None:
    """Query {LLM_BASE_URL}/models and print available model IDs.

    Never prints or logs the API key or its length.
    Never selects or configures a model.
    """
    settings = get_settings()

    api_key = (
        settings.llm_api_key or os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY")
    )
    base_url = (
        settings.llm_base_url
        or os.getenv("LLM_BASE_URL")
        or "https://openrouter.ai/api/v1"
    ).rstrip("/")

    if not api_key:
        print(
            "[ERROR] No LLM API key configured in environment or settings.",
            file=sys.stderr,
        )
        print("Please set LLM_API_KEY in .env before running.", file=sys.stderr)
        sys.exit(1)

    url = f"{base_url}/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Rafiq-Evaluator/1.0",
    }
    if getattr(settings, "llm_http_referer", ""):
        headers["HTTP-Referer"] = settings.llm_http_referer
    if getattr(settings, "llm_title", ""):
        headers["X-Title"] = settings.llm_title

    print(f"[INFO] Querying models from endpoint: {url}")
    req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            data = json.loads(body)
    except urllib.error.HTTPError as he:
        print(f"[ERROR] HTTP {he.code}: {he.reason}", file=sys.stderr)
        try:
            err_body = he.read().decode("utf-8")
            print(f"[ERROR] Response body: {err_body}", file=sys.stderr)
        except OSError:
            print("[ERROR] Could not decode error response body.", file=sys.stderr)
        sys.exit(1)
    except (urllib.error.URLError, OSError) as exc:
        print(f"[ERROR] Connection error querying models: {exc}", file=sys.stderr)
        sys.exit(1)

    # Parse model ids from common formats (OpenAI / OpenRouter {data: [{id: ...}]})
    models: list[str] = []
    if isinstance(data, dict):
        if "data" in data and isinstance(data["data"], list):
            for m in data["data"]:
                if isinstance(m, dict) and "id" in m:
                    models.append(m["id"])
                elif isinstance(m, str):
                    models.append(m)
        elif "models" in data and isinstance(data["models"], list):
            for m in data["models"]:
                if isinstance(m, dict) and "id" in m:
                    models.append(m["id"])
                elif isinstance(m, str):
                    models.append(m)
    elif isinstance(data, list):
        for m in data:
            if isinstance(m, dict) and "id" in m:
                models.append(m["id"])
            elif isinstance(m, str):
                models.append(m)

    models.sort()
    print(f"\n[SUCCESS] Retrieved {len(models)} available model IDs (status {status}):")
    print("-" * 60)
    for mid in models:
        print(f"  - {mid}")
    print("-" * 60)
    print("\n[NOTE] Model selection is not automated. Please set LLM_MODEL in .env.")


if __name__ == "__main__":
    check_models()
