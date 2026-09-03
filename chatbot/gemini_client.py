import threading
import time

from google import genai
from google.genai import types
from pydantic import BaseModel

from config.settings import settings


class _TokenBucketLimiter:
    """Simple client-side rate limiter to stay under the Gemini free-tier RPM ceiling.

    Free-tier RPM limits vary by model/tier and change over time -- confirm the
    current figure at ai.google.dev/pricing before raising max_per_minute.
    """

    def __init__(self, max_per_minute: int = 10):
        self._max = max_per_minute
        self._lock = threading.Lock()
        self._timestamps: list[float] = []

    def wait(self) -> None:
        with self._lock:
            now = time.time()
            self._timestamps = [t for t in self._timestamps if now - t < 60]
            if len(self._timestamps) >= self._max:
                sleep_for = 60 - (now - self._timestamps[0]) + 0.1
            else:
                sleep_for = 0
            self._timestamps.append(now + sleep_for)
        if sleep_for > 0:
            time.sleep(sleep_for)


_limiter = _TokenBucketLimiter()
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def generate_structured(prompt: str, schema: type[BaseModel], max_retries: int = 3) -> BaseModel:
    """One Gemini call constrained to a Pydantic response schema, with client-side
    rate limiting and exponential backoff on transient/429 errors."""
    client = _get_client()
    last_err: Exception | None = None
    for attempt in range(max_retries):
        _limiter.wait()
        try:
            resp = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
            return resp.parsed
        except Exception as e:  # noqa: BLE001 -- broad on purpose: SDK raises several transient error types
            last_err = e
            time.sleep(2**attempt)
    raise RuntimeError(f"Gemini structured call failed after {max_retries} attempts") from last_err


def generate_text(prompt: str, max_retries: int = 3) -> str:
    client = _get_client()
    last_err: Exception | None = None
    for attempt in range(max_retries):
        _limiter.wait()
        try:
            resp = client.models.generate_content(model=settings.gemini_model, contents=prompt)
            return resp.text
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2**attempt)
    raise RuntimeError(f"Gemini text call failed after {max_retries} attempts") from last_err
