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

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError
from pydantic import BaseModel, Field, ValidationError

from app.config import ROOT, get_settings


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


_printed_first_call_info = False


def check_credentials() -> tuple[bool, str]:
    """Check if LLM_API_KEY (or GROQ_API_KEY), LLM_MODEL, and LLM_BASE_URL are configured."""
    settings = get_settings()
    missing = []
    if not settings.effective_api_key:
        missing.append("Neither LLM_API_KEY nor GROQ_API_KEY is set in .env")
    if not settings.llm_model or not settings.llm_model.strip():
        missing.append("LLM_MODEL is not set in .env")
    if not settings.llm_base_url or not settings.llm_base_url.strip():
        missing.append("LLM_BASE_URL is not set in .env")
    if missing:
        return False, "; ".join(missing)
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
            default_headers: dict[str, str] = {}
            if self.settings.llm_http_referer:
                default_headers["HTTP-Referer"] = self.settings.llm_http_referer
            if self.settings.llm_title:
                default_headers["X-Title"] = self.settings.llm_title

            self.client = OpenAI(
                api_key=self.settings.effective_api_key,
                base_url=self.settings.llm_base_url,
                default_headers=default_headers or None,
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
        global _printed_first_call_info
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

        if not _printed_first_call_info:
            from urllib.parse import urlparse

            host = urlparse(self.settings.llm_base_url).netloc or self.settings.llm_base_url
            print(f"[LLM Info] Host: {host} | Model: {chosen_model}")
            if chosen_model.endswith(":free"):
                print(
                    "[LLM Warning] Free endpoints (:free) may have strict daily request limits and "
                    "weaker data policies. Only synthetic, de-identified dataset may be used."
                )
            mode_desc = (
                "structured mode (json_object response_format)"
                if self.settings.llm_structured_output
                else "plain JSON instructions + Pydantic validation"
            )
            print(f"[LLM Info] Output Mode: {mode_desc}")
            _printed_first_call_info = True

        client = self._get_client()
        rpm = self.settings.llm_requests_per_minute
        if chosen_model.endswith(":free") and rpm > 10:
            rpm = 10

        max_retries = 3
        base_delay = 2.0
        response_json = None
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        start_time = time.time()

        for attempt in range(max_retries):
            _throttle(rpm)
            try:
                kwargs: dict[str, Any] = {
                    "model": chosen_model,
                    "messages": messages,
                    "temperature": temperature,
                }
                if self.settings.llm_structured_output:
                    kwargs["response_format"] = {"type": "json_object"}

                res = client.chat.completions.create(**kwargs)

                content = ""
                if res.choices and res.choices[0].message and res.choices[0].message.content:
                    content = res.choices[0].message.content
                else:
                    print("[WARN] Received empty or null message content from LLM", file=sys.stderr)

                if res.usage is not None:
                    usage = {
                        "prompt_tokens": getattr(res.usage, "prompt_tokens", 0) or 0,
                        "completion_tokens": getattr(res.usage, "completion_tokens", 0) or 0,
                    }
                else:
                    print("[WARN] LLM response missing usage field", file=sys.stderr)
                    usage = {"prompt_tokens": 0, "completion_tokens": 0}

                # Validate with Pydantic
                try:
                    # Strip any potential markdown fences in plain mode
                    cleaned_content = content.strip()
                    if cleaned_content.startswith("```"):
                        lines = cleaned_content.splitlines()
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].startswith("```"):
                            lines = lines[:-1]
                        cleaned_content = "\n".join(lines).strip()

                    parsed = json.loads(cleaned_content) if cleaned_content else {}
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
                headers = {}
                retry_after_val = None
                res_obj = getattr(e, "response", None)
                if res_obj is not None and hasattr(res_obj, "headers"):
                    raw_headers = dict(res_obj.headers)
                    headers = {
                        k: v
                        for k, v in raw_headers.items()
                        if any(term in k.lower() for term in ["rate", "limit", "retry"])
                        and not any(
                            secret in k.lower()
                            for secret in ["key", "auth", "token", "secret", "cookie", "set-cookie"]
                        )
                    }
                    retry_after_val = raw_headers.get("retry-after")
                print(
                    "[ERROR] 429 Rate limit encountered on LLM call. "
                    "Stopping execution immediately.",
                    file=sys.stderr,
                )
                print(f"[ERROR] Rate-limit headers: {headers}", file=sys.stderr)
                if retry_after_val:
                    print(f"[ERROR] Retry-After header: {retry_after_val}", file=sys.stderr)
                raise
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
