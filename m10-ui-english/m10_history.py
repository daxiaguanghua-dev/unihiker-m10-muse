"""Small, local text-only history for M10 voice notes and Muse replies."""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import uuid

MAX_ITEMS = 50
_WRITE_LOCK = threading.Lock()


def load_history(path):
    try:
        items = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict) and
            item.get('kind') in ('voice', 'reply') and
            isinstance(item.get('title'), str) and
            isinstance(item.get('text'), str) and
            isinstance(item.get('timestamp'), (int, float)) and
            0 < item['timestamp'] < 4102444800][-MAX_ITEMS:]


def append_history(path, kind, title, text, timestamp=None, event_id=None,
                   origin=None):
    if kind not in ('voice', 'reply') or not isinstance(text, str) or not text.strip():
        raise ValueError('invalid history entry')
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = float(timestamp if timestamp is not None else time.time())
    entry = {'id': event_id or uuid.uuid4().hex, 'kind': kind,
             'title': str(title)[:80], 'text': text[:2000], 'timestamp': stamp}
    if origin == 'legacy_import':
        entry['origin'] = origin
    with _WRITE_LOCK:
        items = load_history(destination)
        if any(item.get('id') == entry['id'] for item in items):
            return False
        items.append(entry)
        fd, temporary = tempfile.mkstemp(prefix='.history-', dir=destination.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(items[-MAX_ITEMS:], stream, ensure_ascii=False)
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return True
