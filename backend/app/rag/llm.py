"""LLM client using OpenAI SDK for Groq API (app/rag/llm.py).

Features:
- Configurable base_url and model.
- Exponential backoff on 429 and 5xx honoring Retry-After.
- Rate limiter respecting LLM_REQUESTS_PER_MINUTE.
- Disk cache keyed by hash(model, messages, params) in eval/.cache.
- Pydantic schema validation with single retry on invalid JSON.
- Token usage tracking.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

from app.config import ROOT, get_settings
from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError
from pydantic import BaseModel, Field, ValidationError


class ClaimModel(BaseModel):
    text: str = Field(description="The factual claim text")
    chunk_id: str = Field(description="The source chunk id")
    quote: str = Field(description="The exact verbatim quote copied from the chunk")


class RAGResponseModel(BaseModel):
    answerable: bool = Field(description="Whether the question can be answered from chunks")
    answer: str = Field(description="The final answer text or refusal text")
    claims: list[ClaimModel] = Field(default_factory=list, description="List of factual claims")


CACHE_DIR = ROOT / "eval" / ".cache"
_last_call_timestamp: float = 0.0


def check_credentials() -> tuple[bool, str]:
    """Check if GROQ_API_KEY and LLM_MODEL are configured."""
    settings = get_settings()
    if not settings.groq_api_key or not settings.groq_api_key.strip():
        return False, "GROQ_API_KEY is empty. Please set it in .env to run live LLM calls."
    if not settings.llm_model or not settings.llm_model.strip():
        return False, "LLM_MODEL is empty. Please set it in .env to run live LLM calls."
    return True, ""


def get_cache_path(key_data: dict[str, Any]) -> Path:
    """Generate deterministic cache file path."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(key_data, sort_keys=True)
    key_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{key_hash}.json"


def _throttle(rpm: int) -> None:
    """Enforce rate limit between requests."""
    global _last_call_timestamp
    if rpm <= 0:
        return
    min_interval = 60.0 / rpm
    now = time.time()
    elapsed = now - _last_call_timestamp
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_call_timestamp = time.time()


class GroqLLMClient:
    def __init__(self, client: OpenAI | None = None) -> None:
        self.settings = get_settings()
        self.client = client

    def _get_client(self) -> OpenAI:
        if self.client is None:
            ok, msg = check_credentials()
            if not ok:
                print(f"[FATAL] {msg}", file=sys.stderr)
                sys.exit(1)
            self.client = OpenAI(
                api_key=self.settings.groq_api_key,
                base_url=self.settings.llm_base_url,
            )
        return self.client

    def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        model: str | None = None,
        use_cache: bool = True,
    ) -> tuple[dict[str, Any], dict[str, int], int]:
        """Generate response with disk caching, rate limiting, and backoff.

        Returns: (parsed_json_dict, usage_dict, latency_ms)
        """
        chosen_model = model or self.settings.llm_model
        params = {"temperature": temperature, "model": chosen_model}
        cache_key = {"model": chosen_model, "messages": messages, "params": params}
        cache_file = get_cache_path(cache_key)

        if use_cache and cache_file.exists():
            try:
                with open(cache_file, encoding="utf-8") as f:
                    cached_data = json.load(f)
                return (
                    cached_data["response"],
                    cached_data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0}),
                    0,
                )
            except Exception:
                pass

        client = self._get_client()
        rpm = self.settings.llm_requests_per_minute

        max_retries = 5
        base_delay = 2.0
        response_json = None
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        start_time = time.time()

        for attempt in range(max_retries):
            _throttle(rpm)
            try:
                res = client.chat.completions.create(
                    model=chosen_model,
                    messages=messages,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                )

                content = res.choices[0].message.content or "{}"
                if res.usage:
                    usage = {
                        "prompt_tokens": res.usage.prompt_tokens,
                        "completion_tokens": res.usage.completion_tokens,
                    }

                # Validate with Pydantic
                try:
                    parsed = json.loads(content)
                    validated = RAGResponseModel.model_validate(parsed)
                    response_json = validated.model_dump()
                    break
                except (json.JSONDecodeError, ValidationError) as parse_err:
                    # Retry once on invalid JSON with correction prompt
                    if attempt == 0:
                        correction_messages = list(messages) + [
                            {"role": "assistant", "content": content},
                            {
                                "role": "user",
                                "content": (
                                    f"Your previous response had JSON/schema error: {parse_err}. "
                                    "Return ONLY valid JSON matching: "
                                    '{"answerable": bool, "answer": str, '
                                    '"claims": [{"text": str, "chunk_id": str, "quote": str}]}'
                                ),
                            },
                        ]
                        messages = correction_messages
                        continue
                    else:
                        response_json = {
                            "answerable": False,
                            "answer": "I couldn't find this in the patient's files.",
                            "claims": [],
                        }
                        break

            except RateLimitError as e:
                retry_after = getattr(e, "response", None)
                wait_time = base_delay * (2**attempt)
                if retry_after and hasattr(retry_after, "headers"):
                    h = retry_after.headers.get("retry-after")
                    if h and h.isdigit():
                        wait_time = float(h)
                print(
                    f"[WARN] 429 Rate limit encountered. Backing off for {wait_time:.1f}s...",
                    file=sys.stderr,
                )
                time.sleep(wait_time)
            except APIStatusError as e:
                if e.status_code >= 500:
                    wait_time = base_delay * (2**attempt)
                    print(
                        f"[WARN] {e.status_code} Server error. Backing off for {wait_time:.1f}s...",
                        file=sys.stderr,
                    )
                    time.sleep(wait_time)
                else:
                    raise
            except APIConnectionError:
                wait_time = base_delay * (2**attempt)
                print(f"[WARN] Connection error. Retrying in {wait_time:.1f}s...", file=sys.stderr)
                time.sleep(wait_time)

        if response_json is None:
            response_json = {
                "answerable": False,
                "answer": "I couldn't find this in the patient's files.",
                "claims": [],
            }

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Cache response
        if use_cache:
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(
                        {"response": response_json, "usage": usage, "latency_ms": elapsed_ms}, f
                    )
            except Exception:
                pass

        return response_json, usage, elapsed_ms
