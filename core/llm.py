"""Talks to Ollama, the local language model program, on this computer only.

The model and the address are set here and nowhere else.
"""
import json
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434"
MODEL = "llama3.2:3b"        # check the licence of any model before company use
TIMEOUT_SECONDS = 120


class LLMError(Exception):
    """Ollama or the model could not be used."""


def status():
    """(True, message) if Ollama answers and the model is present, otherwise (False, message)."""
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=3) as response:
            models = [m.get("name", "") for m in json.load(response).get("models", [])]
    except (urllib.error.URLError, OSError, ValueError):
        return False, "The instruction reader is not available (Ollama is not running). All settings below still work by hand."
    if MODEL not in models:
        return False, f"Ollama is running but the model {MODEL} is not installed. All settings below still work by hand."
    return True, f"Instruction reader ready ({MODEL}, on this computer)."


def chat(system, user, schema):
    """Send one order to the model and return its answer text (expected to be JSON)."""
    body = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "format": schema,
        "stream": False,
        "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 600},   # 600 tokens: enough for ~6 actions
        "keep_alive": "2m",
    }
    request = urllib.request.Request(OLLAMA_URL + "/api/chat", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.load(response)["message"]["content"]
    except (urllib.error.URLError, OSError, ValueError, KeyError) as error:
        raise LLMError(f"The instruction reader did not answer ({error}).")
