import asyncio
import base64
import io
import json
import wave

import pytest

from musegadget.voice_note import validate_voice_note
from musegadget.service import Service
from musegadget.identity import Identity
from musegadget.executor import Account, Executor
from musegadget.noise import ApplicationResponse, ServiceFrame
from test_link_client import make_session


def note(seconds=5):
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(bytes(seconds * 32000))
    return base64.b64encode(output.getvalue()).decode('ascii')


@pytest.mark.parametrize('encoded', ['', '%%%', base64.b64encode(b'not a WAV').decode(), note(6)])
def test_invalid_notes_are_rejected(encoded):
    with pytest.raises(ValueError):
        validate_voice_note(encoded)


def test_truncated_pcm_is_rejected():
    encoded = base64.b64encode(base64.b64decode(note())[:-10]).decode()
    with pytest.raises(ValueError):
        validate_voice_note(encoded)


@pytest.mark.parametrize('reply_on_display', [False,True])
def test_voice_attachment_crosses_the_real_encrypted_session(reply_on_display):
    async def scenario():
        session, vm = make_session(lambda *a: {'ok': True}, [])
        task = asyncio.ensure_future(session.run(asyncio.Event()))
        await vm.handshake()
        await vm.accept_control_stream()
        await vm.next_message()
        encoded = note()
        reply = asyncio.ensure_future(session.send_voice(encoded,reply_on_display=reply_on_display))
        frame = await vm.next_frame()
        assert frame.value.path == '/chat/stream'
        body = json.loads(frame.value.body)
        assert body['device_id'] == 'homelink-abcdef'
        assert body['output_modality'] == 'text'
        if reply_on_display:
            assert 'display.show' in body['message'] and 'homelink-abcdef' in body['message']
        else:
            assert body['message'] == ''
        assert body['items'] == [{'type': 'file', 'mime_type': 'audio/wav',
                                  'filename': 'voice_note.wav', 'data_base64': encoded}]
        await vm.send_frame(ServiceFrame.response(frame.stream_id,
                           ApplicationResponse(status=200, body=b'{"message_id":"test-note"}', end_body=True)))
        assert (await asyncio.wait_for(reply, 2))['response']['message_id'] == 'test-note'
        task.cancel()
    asyncio.run(scenario())


def test_local_voice_note_uses_the_live_session_and_no_root_file_path():
    async def scenario():
        service = Service(identity=Identity('02:00:00:00:00:01'), executor=Executor(Account.current()))
        class VoiceSession:
            registered_at = 1
            sent = []
            async def send_voice(self, encoded, session_id):
                self.sent.append((encoded, session_id))
                return {'ok': True}
        service._current = VoiceSession()
        encoded = note()
        assert (await service._local_request(json.dumps({'voice_wav_base64': encoded, 'session_id': 'test-1'}).encode()))['ok']
        assert service._current.sent == [(encoded, 'test-1')]
        assert not (await service._local_request(b'{"voice_path":"/var/lib/musegadget/sdk_token"}'))['ok']
    asyncio.run(scenario())
