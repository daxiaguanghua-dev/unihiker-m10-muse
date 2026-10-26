#!/usr/bin/env python3
"""Capture one explicitly requested five-second note and send it to paired Muse."""
import fcntl
import json
from pathlib import Path
import socket


def request(path, data, timeout):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(path)
        sock.sendall(json.dumps(data).encode() + b'\n')
        response = sock.makefile('rb').readline(256 * 1024)
        reply = json.loads(response)
    if not reply.get('ok'):
        raise RuntimeError(reply.get('error') or str(reply.get('status', 'Request failed')))
    return reply


def main():
    directory = Path.home() / '.local/share/muse-m10'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / 'voice.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        capture = request('/run/muse-m10/hardware.sock', {'op': 'audio.record', 'duration_s': 5}, 10)
        request('/run/muse-m10/hardware.sock', {'op': 'led.set', 'on': False}, 5)
        from m10_agent import show_screen, WORK_TITLE, MODE_FILE
        if Path(MODE_FILE).read_text().strip() == 'work':
            show_screen(WORK_TITLE, 'Recording finished\nSending to Muse...\n\nReply will appear here', 'sending')
        reply = request('/run/musegadget/musegadget.sock',
                        {'voice_wav_base64': capture['payload']['wav_base64'], 'reply_on_display': True}, 90)
        # The ack confirms upload, not transcription or reply completion.
        result = {'ok': True, 'duration_s': 5, 'status': reply['status'],
                  'response': reply.get('response'), 'note': 'Voice note accepted; check the Muse chat for the transcript and reply.'}
        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
