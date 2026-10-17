"""Small hardware broker: fixed board operations, no shell execution."""
import array
import base64
from concurrent.futures import ThreadPoolExecutor
import grp
import fcntl
import json
import math
import io
import os
from pathlib import Path
import socket
import struct
import subprocess
import time
import threading
import wave

SOCKET = '/run/muse-m10/hardware.sock'
AUDIO_LOCK = threading.Lock()


def bounded_integer(value, default, low, high):
    if value is None:
        value = default
    if type(value) is not int or not low <= value <= high:
        raise ValueError('value must be an integer between %s and %s' % (low, high))
    return value


def audio_level():
    result = subprocess.run(['arecord', '-q', '-D', 'hw:1,0', '-f', 'S16_LE',
                             '-r', '16000', '-c', '2', '-d', '1', '-t', 'raw', '-'],
                            capture_output=True, timeout=4)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-500:])
    samples = array.array('h')
    samples.frombytes(result.stdout)
    if not samples:
        raise RuntimeError('Microphone returned no samples')
    rms = math.sqrt(sum(value * value for value in samples) / len(samples))
    return {'duration_s': 1, 'rms': round(rms, 2),
            'peak': max(map(abs, samples)),
            'level_dbfs': round(20 * math.log10(rms / 32768), 2) if rms else None,
            'note': 'Relative digital level in dBFS, not calibrated environmental dBA. No recording file is saved.'}


def audio_record(duration_s):
    duration = bounded_integer(duration_s, 5, 1, 5)
    result = subprocess.run(['arecord', '-q', '-D', 'hw:1,0', '-f', 'S16_LE',
                             '-r', '16000', '-c', '2', '-d', str(duration), '-t', 'raw', '-'],
                            capture_output=True, timeout=duration + 3)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-500:])
    # The ALSA device requires stereo. Mix to the official mono PCM16 format.
    if len(result.stdout) != duration * 16000 * 4:
        raise RuntimeError('Incomplete microphone recording')
    samples = array.array('h')
    samples.frombytes(result.stdout)
    mono = array.array('h', (int((samples[i] + samples[i+1]) / 2) for i in range(0, len(samples), 2)))
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(mono.tobytes())
    return {'duration_s': duration, 'wav_base64': base64.b64encode(output.getvalue()).decode('ascii')}


def decode_imu(packet):
    # The supplied test-image driver sometimes returns an incomplete reply.
    # Accept the observed ICM20689 packet only; never treat malformed bytes as
    # a different chip or combine axes from separate transactions.
    if len(packet) != 15 or packet[0] != 2:
        raise ValueError('Incomplete or unsupported IMU packet')
    ax, ay, az, temperature, gx, gy, gz = struct.unpack('>7h', packet[1:])
    acceleration = {'x': round(-ax / 2048, 4), 'y': round(-ay / 2048, 4),
                    'z': round(-az / 2048, 4), 'unit': 'g'}
    scale = 2000 / 32768 * math.pi / 180
    rotation = {'x': round(gx * scale, 5), 'y': round(gy * scale, 5),
                'z': round(gz * scale, 5), 'unit': 'rad/s'}
    return acceleration, rotation


class Hardware:
    def __init__(self):
        self.count_fd = os.open('/dev/pinpong_count', os.O_RDWR)
        flag = os.read(self.count_fd, 4)
        if len(flag) == 4 and flag[3] == 0:
            os.write(self.count_fd, bytes([0, 0, 0, 1]))
            config = os.open('/dev/pinpong_config', os.O_RDWR)
            try:
                fcntl.ioctl(config, 16642, bytearray(struct.pack('ii', 0x1f, 1)), True)
            finally:
                os.close(config)
        self.a = Button(219)
        self.b = Button(200)
        self.led = GPIO(215, 'out')
        self.buzzer = Buzzer()
        self.light = Light()
        self.imu_fd = os.open('/dev/icm20689', os.O_RDWR)

    def read_imu(self):
        last_error = None
        for attempt in range(8):
            try:
                return decode_imu(os.read(self.imu_fd, 15))
            except (OSError, ValueError) as exc:
                last_error = exc
                time.sleep(0.05)
        raise RuntimeError(
            'IMU driver returned no valid packet after 8 attempts; last error: '
            '%s: %s' % (type(last_error).__name__, last_error)
        )

    def handle(self, request):
        op = request.get('op')
        if op == 'buttons.read':
            return {'a_pressed': bool(self.a.is_pressed()), 'b_pressed': bool(self.b.is_pressed())}
        if op == 'sensors.read':
            result = {'sampled_at': time.time(), 'ambient_temperature': {
                'available': False, 'reason': 'No ambient temperature sensor connected; CPU temperature is separate.'}}
            operations = {
                'light': lambda: {'raw': self.light.read(), 'range': [0, 4095], 'unit': 'relative ADC, not lux'},
                'buttons': lambda: {'a_pressed': bool(self.a.is_pressed()), 'b_pressed': bool(self.b.is_pressed())},
            }
            for name, read in operations.items():
                try:
                    result[name] = {'available': True, **read()}
                except Exception as exc:
                    result[name] = {'available': False, 'error': '%s: %s' % (type(exc).__name__, exc)}
            try:
                acceleration, rotation = self.read_imu()
                result['accelerometer'] = {'available': True, **acceleration}
                result['gyroscope'] = {'available': True, **rotation}
            except Exception as exc:
                failure = {'available': False, 'error': str(exc)}
                result['accelerometer'] = failure
                result['gyroscope'] = failure.copy()
            return result
        if op in ('audio.level', 'audio.record'):
            if not AUDIO_LOCK.acquire(blocking=False):
                raise RuntimeError('Microphone is busy')
            try:
                return audio_level() if op == 'audio.level' else audio_record(request.get('duration_s'))
            finally:
                AUDIO_LOCK.release()
        if op == 'led.set':
            state = request.get('on')
            if type(state) is not bool:
                raise ValueError('on must be true or false')
            self.led.write_digital(int(state))
            return {'on': state}
        if op == 'buzzer.beep':
            frequency = bounded_integer(request.get('frequency_hz'), 880, 100, 5000)
            duration = bounded_integer(request.get('duration_ms'), 200, 50, 2000)
            try:
                self.buzzer.pitch(frequency)
                time.sleep(duration / 1000)
            finally:
                self.buzzer.stop()
            return {'frequency_hz': frequency, 'duration_ms': duration}
        raise ValueError('unsupported hardware operation')


class GPIO:
    def __init__(self, number, direction):
        self.directory = Path('/sys/class/gpio/gpio' + str(number))
        if not self.directory.exists():
            Path('/sys/class/gpio/export').write_text(str(number))
        path = self.directory / 'direction'
        if path.read_text().strip() != direction:
            path.write_text(direction + '\n')

    def write_digital(self, state):
        (self.directory / 'value').write_text(str(state))


class Button(GPIO):
    def __init__(self, number):
        super().__init__(number, 'in')

    def is_pressed(self):
        return int((self.directory / 'value').read_text().strip()) == 0


class Light:
    def __init__(self):
        self.path = None
        for device in Path('/sys/bus/iio/devices').glob('iio:device*'):
            if (device / 'name').read_text().strip() == 'pinpong-adc-1':
                self.path = device / 'in_voltage0_raw'
                break
        if self.path is None:
            raise RuntimeError('PinPong light ADC is missing')

    def read(self):
        values = sorted(int(self.path.read_text().strip()) for _ in range(5))
        value = sum(values[1:-1]) // 3
        if not 0 <= value <= 4095:
            raise ValueError('Invalid light ADC value')
        return 4095 if value < 150 else 0 if value > 4080 else 4095 - value


class Buzzer:
    def __init__(self):
        self.fd = os.open('/dev/buzzer', os.O_RDWR)

    def pitch(self, frequency):
        os.write(self.fd, bytes([2, frequency >> 8, frequency & 255, 0, 4, 4]))

    def stop(self):
        os.write(self.fd, bytes([5]))


def serve_client(client, hardware, hardware_lock):
    with client:
        client.settimeout(8)
        try:
            data = bytearray()
            while b'\n' not in data and len(data) < 4096:
                part = client.recv(1024)
                if not part:
                    break
                data.extend(part)
            if len(data) >= 4096:
                raise ValueError('request too large')
            request = json.loads(data)
            if not isinstance(request, dict):
                raise ValueError('request must be an object')
            if request.get('op') in ('audio.level', 'audio.record'):
                payload = hardware.handle(request)
            else:
                with hardware_lock:
                    payload = hardware.handle(request)
            response = {'ok': True, 'payload': payload}
        except Exception as exc:
            response = {'ok': False, 'error': '%s: %s' % (type(exc).__name__, exc)}
        try:
            client.sendall(json.dumps(response, ensure_ascii=False).encode() + b'\n')
        except OSError:
            pass


def main():
    hardware = Hardware()
    directory = Path(SOCKET).parent
    directory.mkdir(exist_ok=True)
    group = grp.getgrnam('muse').gr_gid
    os.chown(directory, 0, group)
    os.chmod(directory, 0o750)
    Path(SOCKET).unlink(missing_ok=True)
    hardware_lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=4) as workers, socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(SOCKET)
        os.chown(SOCKET, 0, group)
        os.chmod(SOCKET, 0o660)
        server.listen(8)
        print('M10 hardware broker ready', flush=True)
        while True:
            client, _ = server.accept()
            workers.submit(serve_client, client, hardware, hardware_lock)


if __name__ == '__main__':
    main()
