import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict


class LLMUnavailableError(RuntimeError):
    pass


def call_ollama(prompt: str) -> str:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }
    req = urllib.request.Request(
        url=f"{base_url}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return str(data.get("response", "")).strip()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise LLMUnavailableError(f"Ollama unavailable: {exc}") from exc
