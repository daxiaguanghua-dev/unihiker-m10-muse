"""Unprivileged text requests consumed by the M10 screen process."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path


def apply_request(request):
    op = request.get("op")
    if op not in ("show", "clear"):
        return {"ok": False, "error": "unsupported display operation"}
    text = request.get("text", "")
    title = request.get("title", "Muse")
    if not isinstance(text, str) or len(text) > 2000 or (op == "show" and not text.strip()):
        return {"ok": False, "error": "text must contain 1 to 2000 characters"}
    if not isinstance(title, str) or len(title) > 40:
        return {"ok": False, "error": "title must be a string of up to 40 characters"}
    directory = Path(os.environ["HOME"]) / ".local/share/muse-m10"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".display-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump({"text": text if op == "show" else "", "title": title,
                       "updated_at": time.time(), "source": "Muse device tool"},
                      output, ensure_ascii=False)
        os.replace(name, directory / "display.json")
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return {"ok": True, "payload": {"accepted": True, "operation": op,
            "characters": len(text) if op == "show" else 0,
            "note": "Screen updates within one second while the Muse screen app is running."}}


if __name__ == "__main__":
    try:
        result = apply_request(json.load(sys.stdin))
    except (ValueError, OSError, KeyError) as exc:
        result = {"ok": False, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False))
