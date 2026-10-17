import asyncio
import json
from musegadget.executor import Account, Executor
from musegadget.identity import Identity
from musegadget.service import Service


def test_live_status_without_registration_logs_or_chat():
    async def check():
        service = Service(identity=Identity('02:00:00:00:00:01'), executor=Executor(Account.current()))
        request = b'{"action":"connection.status"}'
        assert not (await service._local_request(request))['connected']
        class Session:
            registered_at = 1.0
            _requests = {}
            _tasks = set()
            secret = 'MUST_NOT_APPEAR'
        service._current = Session()
        reply = await service._local_request(request)
        assert reply['connected'] and not reply['busy']
        assert Session.secret not in json.dumps(reply)
        service._current._requests = {1: object()}
        assert (await service._local_request(request))['busy']
        service._current = None
        service._connection_reason = 'api_unreachable'
        assert (await service._local_request(request))['reason'] == 'api_unreachable'
    asyncio.run(check())


def test_status_reports_retry_countdown():
    async def check():
        service = Service(identity=Identity('02:00:00:00:00:01'), executor=Executor(Account.current()))
        sleeper = asyncio.create_task(service._sleep(60))
        await asyncio.sleep(0)
        reply = await service._local_request(b'{"action":"connection.status"}')
        assert 59 <= reply['retry_in_s'] <= 60
        service.stop()
        await sleeper
        assert (await service._local_request(b'{"action":"connection.status"}'))['retry_in_s'] == 0
    asyncio.run(check())
