"""Read live SDK connection state and explain the current network dependency."""
import json
import socket
import subprocess
import urllib.error
import urllib.request

SDK_SOCKET = '/run/musegadget/musegadget.sock'


def sdk_status():
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(2)
        sock.connect(SDK_SOCKET)
        sock.sendall(b'{"action":"connection.status"}\n')
        result = json.loads(sock.makefile('rb').readline(4096))
    if not result.get('ok'):
        raise RuntimeError('SDK status unavailable')
    return result


def classify(active, live, wifi, proxy_port, api_reachable):
    """Keep observed facts separate: TCP listener does not prove Internet access."""
    if live and live.get('connected'):
        return 'online', 'Muse connected', 'Secure session established; ready for requests.'
    if not active:
        return 'offline', 'Muse service stopped', 'Tap Retry to start the device service.'
    if not proxy_port and not wifi:
        return 'offline', 'Wi-Fi disconnected', 'No Wi-Fi address. Connect the board in system settings.'
    if not api_reachable:
        return 'connecting', 'Muse API unreachable', 'Check Wi-Fi, DNS and HTTPS access, then tap Retry.'
    if live is None:
        return 'checking', 'Device status unavailable', 'Network responds, but SDK status is unavailable. Tap Retry.'
    reason = live.get('reason', '')
    reasons = {
        'unpaired': ('Pairing required', 'Pair this device in the Muse app.'),
        'no_vm': ('No Muse session', 'The API responded, but no Muse session is available. Check the app.'),
        'api_http_401': ('Authorization refresh needed', 'Muse rejected device credentials; SDK is refreshing them.'),
        'api_http_403': ('Muse access denied', 'Check the Muse account and paired device in the app.'),
        'refresh_failed': ('Authorization refresh failed', 'Network is reachable; SDK will retry credential refresh.'),
        'auth_rejected': ('Session authorization denied', 'SDK will request new session credentials.'),
        'forbidden': ('Session refused', 'Check the Muse account and paired device in the app.'),
        'TimeoutError': ('Muse session timed out', 'Network works; session handshake is still pending.'),
        'api_unreachable': ('Muse API request failed', 'Network recovered; waiting for the next SDK retry.'),
    }
    return ('connecting', *reasons.get(reason, ('Connecting to Muse', 'Opening a session. Tap Retry if this persists.')))


def diagnose():
    active = subprocess.run(['systemctl','is-active','musegadget'], capture_output=True,text=True,timeout=3).stdout.strip() == 'active'
    try:
        live = sdk_status()
    except (OSError,ValueError,RuntimeError):
        live = None
    if live and live.get('connected'):
        status,title,detail = classify(active,live,True,True,True)
        return dict(connection=status,reason=title,detail=detail,retry=0)
    wifi = bool(subprocess.run(['ip','-4','-o','addr','show','dev','wlan0'], capture_output=True,text=True,timeout=3).stdout.strip())
    try:
        with socket.create_connection(('127.0.0.1',17890),timeout=1):
            proxy_port=True
    except OSError:
        proxy_port=False
    api=False
    if proxy_port or wifi:
        # The original M10 used a local proxy. Overseas setups often use
        # direct Wi-Fi; neither path should be declared broken by default.
        proxies={'https':'http://127.0.0.1:17890'} if proxy_port else {}
        opener=urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
        try:
            with opener.open('https://api.muse.ai/',timeout=3) as response:
                api=True
        except urllib.error.HTTPError as exc:
            api=exc.code in (401,403,404,405)  # Root route may not exist; TLS still succeeded.
        except (OSError,urllib.error.URLError):
            pass
    status,title,detail=classify(active,live,wifi,proxy_port,api)
    return dict(connection=status,reason=title,detail=detail,retry=(live or {}).get('retry_in_s',0))
