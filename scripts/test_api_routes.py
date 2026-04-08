"""Comprehensive API route smoke test for local FastAPI app.

Run:
  python scripts/test_api_routes.py
"""

from __future__ import annotations

from typing import Callable
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import app


def assert_status(label: str, actual: int, expected: int | tuple[int, ...]) -> None:
    if isinstance(expected, tuple):
        ok = actual in expected
        exp_txt = "/".join(str(v) for v in expected)
    else:
        ok = actual == expected
        exp_txt = str(expected)

    if not ok:
        raise AssertionError(f"{label}: expected {exp_txt}, got {actual}")
    print(f"[PASS] {label}: {actual}")


def run_check(label: str, fn: Callable[[], None]) -> None:
    try:
        fn()
    except Exception as exc:
        print(f"[FAIL] {label}: {exc}")
        raise


def main() -> None:
    client = TestClient(app)

    run_check("GET /", lambda: assert_status("GET /", client.get("/").status_code, 200))
    run_check("GET /api", lambda: assert_status("GET /api", client.get("/api").status_code, 200))
    run_check("GET /health", lambda: assert_status("GET /health", client.get("/health").status_code, 200))

    run_check(
        "POST /ask missing question",
        lambda: assert_status(
            "POST /ask missing question",
            client.post("/ask", json={"question": ""}).status_code,
            400,
        ),
    )

    run_check(
        "POST /ask no OPENAI key",
        lambda: assert_status(
            "POST /ask no OPENAI key",
            client.post("/ask", json={"question": "hello"}).status_code,
            503,
        ),
    )

    run_check(
        "POST /api/chat compatibility",
        lambda: assert_status(
            "POST /api/chat compatibility",
            client.post("/api/chat", json={"question": "hello"}).status_code,
            503,
        ),
    )

    run_check(
        "POST /voice/tts missing form",
        lambda: assert_status(
            "POST /voice/tts missing form",
            client.post("/voice/tts").status_code,
            422,
        ),
    )

    run_check(
        "POST /voice/tts no provider",
        lambda: assert_status(
            "POST /voice/tts no provider",
            client.post("/voice/tts", data={"text": "hello"}).status_code,
            503,
        ),
    )

    run_check(
        "POST /voice/stt missing file",
        lambda: assert_status(
            "POST /voice/stt missing file",
            client.post("/voice/stt").status_code,
            422,
        ),
    )

    run_check(
        "POST /voice/stt no provider",
        lambda: assert_status(
            "POST /voice/stt no provider",
            client.post("/voice/stt", files={"file": ("sample.wav", b"abc", "audio/wav")}).status_code,
            503,
        ),
    )

    run_check(
        "POST /storyboard/generate missing question",
        lambda: assert_status(
            "POST /storyboard/generate missing question",
            client.post("/storyboard/generate", json={"question": ""}).status_code,
            503,
        ),
    )

    run_check(
        "POST /storyboard/generate no OPENAI key",
        lambda: assert_status(
            "POST /storyboard/generate no OPENAI key",
            client.post("/storyboard/generate", json={"question": "topic"}).status_code,
            503,
        ),
    )

    run_check(
        "GET /storyboard/get missing id",
        lambda: assert_status(
            "GET /storyboard/get missing id",
            client.get("/storyboard/get").status_code,
            422,
        ),
    )

    run_check(
        "GET /storyboard/get unknown",
        lambda: assert_status(
            "GET /storyboard/get unknown",
            client.get("/storyboard/get?id=does-not-exist").status_code,
            404,
        ),
    )

    run_check(
        "GET /js/config.js static",
        lambda: assert_status(
            "GET /js/config.js static",
            client.get("/js/config.js").status_code,
            200,
        ),
    )

    print("\nAll route checks passed.")


if __name__ == "__main__":
    main()
