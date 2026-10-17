"""Unprivileged client for the M10's fixed hardware operations."""
import json
import socket
import sys

SOCKET_PATH = '/run/muse-m10/hardware.sock'
OPERATIONS = {'sensors.read', 'audio.level', 'led.set', 'buzzer.beep'}


def request(operation, params):
    if operation not in OPERATIONS:
        return {'ok': False, 'error': 'unsupported hardware operation'}
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(6)
            client.connect(SOCKET_PATH)
            client.sendall(json.dumps({**params, 'op': operation}).encode() + b'\n')
            data = bytearray()
            while b'\n' not in data and len(data) < 16384:
                part = client.recv(2048)
                if not part:
                    break
                data.extend(part)
            return json.loads(data)
    except (OSError, ValueError) as exc:
        return {'ok': False, 'error': 'M10 hardware service: %s' % exc}


if __name__ == '__main__':
    payload = json.load(sys.stdin)
    print(json.dumps(request(payload.pop('op'), payload), ensure_ascii=False))
