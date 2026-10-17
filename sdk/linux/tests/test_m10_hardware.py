import importlib.util
import json
import os
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

from musegadget import m10_hardware

source = Path(os.environ.get('M10_HARDWARE_SERVICE_SOURCE', str(Path(__file__).resolve().parents[4] / 'm10_hardware_service.py')))
spec = importlib.util.spec_from_file_location('m10_hardware_service', source)
broker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(broker)


def test_client_rejects_unknown_operation():
    assert not m10_hardware.request('system.run', {'command': 'id'})['ok']


def test_client_reports_missing_hardware_service(monkeypatch, tmp_path):
    monkeypatch.setattr(m10_hardware, 'SOCKET_PATH', str(tmp_path / 'missing.sock'))
    assert not m10_hardware.request('sensors.read', {})['ok']


@pytest.mark.parametrize('value', [True, '200', 0, 2001])
def test_buzzer_rejects_invalid_duration(value):
    with pytest.raises(ValueError):
        broker.bounded_integer(value, 200, 50, 2000)


def test_zero_audio_is_json_safe(monkeypatch):
    monkeypatch.setattr(broker.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=bytes(100), stderr=b''))
    result = broker.audio_level()
    assert result['level_dbfs'] is None
    assert result['peak'] == 0
    json.dumps(result, allow_nan=False)


def test_sensor_failure_does_not_hide_working_light():
    hardware = broker.Hardware.__new__(broker.Hardware)
    def failure():
        raise OSError('IMU unavailable')
    hardware.light = SimpleNamespace(read=lambda: 123)
    hardware.acc = SimpleNamespace(get_x=failure)
    hardware.gyro = SimpleNamespace(get_x=failure)
    hardware.read_imu = failure
    hardware.a = SimpleNamespace(is_pressed=lambda: 1)
    hardware.b = SimpleNamespace(is_pressed=lambda: 0)
    result = hardware.handle({'op': 'sensors.read'})
    assert result['light']['raw'] == 123
    assert result['buttons']['a_pressed'] is True
    assert not result['accelerometer']['available']
    assert not result['ambient_temperature']['available']


def test_broker_rejects_arbitrary_command_and_non_boolean_led():
    hardware = broker.Hardware.__new__(broker.Hardware)
    with pytest.raises(ValueError):
        hardware.handle({'op': 'system.run', 'command': 'id'})
    with pytest.raises(ValueError):
        hardware.handle({'op': 'led.set', 'on': 1})


def test_imu_signed_conversion_and_packet_validation():
    acceleration, rotation = broker.decode_imu(bytes([2]) + struct.pack('>7h', -2048, 0, 2048, 0, 0, 0, 0))
    assert acceleration['x'] == 1 and acceleration['z'] == -1
    assert rotation['z'] == 0
    for packet in (b'', bytes(15), bytes([2]) + bytes(10)):
        with pytest.raises(ValueError):
            broker.decode_imu(packet)


def test_recording_mixes_stereo_to_bounded_mono_wav(monkeypatch):
    import base64
    import io
    import wave
    stereo = struct.pack('<hh', 1000, 3000) * 16000
    monkeypatch.setattr(broker.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=stereo, stderr=b''))
    result = broker.audio_record(1)
    with wave.open(io.BytesIO(base64.b64decode(result['wav_base64'])), 'rb') as wav:
        assert wav.getnchannels() == 1 and wav.getframerate() == 16000
        assert wav.getnframes() == 16000 and struct.unpack('<h', wav.readframes(1)) == (2000,)
    for duration in (True, 0, 6, '5'):
        with pytest.raises(ValueError):
            broker.audio_record(duration)


def test_microphone_cannot_be_recorded_twice_concurrently():
    hardware = broker.Hardware.__new__(broker.Hardware)
    with broker.AUDIO_LOCK:
        with pytest.raises(RuntimeError, match='busy'):
            hardware.handle({'op': 'audio.record', 'duration_s': 5})
