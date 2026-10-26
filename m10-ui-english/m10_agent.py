#!/usr/bin/env python3
"""M10 local agent: touch controls modes and recording; A/B only turn pages."""
import fcntl
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import tempfile
import threading
import time

SOCK = '/run/muse-m10/hardware.sock'
DISPLAY_SOCKET = '/run/muse-m10/display.sock'
MODE_FILE = '/tmp/m10_ui_mode'
HEARTBEAT_FILE = '/tmp/m10_agent_heartbeat'
LOG_FILE = '/tmp/m10_agent.log'
DIRECTORY = Path.home() / '.local/share/muse-m10'
DISPLAY_JSON = DIRECTORY / 'display.json'
REPLY_JSON = DIRECTORY / 'last_reply.json'
AGENT_SOCKET = str(DIRECTORY / 'agent.sock')
WORK_TITLE = 'Muse Work Mode'
WORK_TEXT = 'Tap Record to capture 5 seconds\nMuse replies appear here\n\nA: previous · B: next'
VOICE_BUSY = threading.Lock()
ACTIONS = queue.Queue()
ALLOWED_ACTIONS = {'work', 'dashboard', 'record'}


def log(message):
    with open(LOG_FILE,'a',encoding='utf-8') as stream:
        stream.write(time.strftime('%Y-%m-%d %H:%M:%S')+' '+message+'\n')


def request(path,data,timeout=3):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(path)
        sock.sendall(json.dumps(data).encode()+b'\n')
        reply=json.loads(sock.makefile('rb').readline(16384))
    if not reply.get('ok'):
        raise RuntimeError(reply.get('error','operation rejected'))
    return reply.get('payload',reply)


def hw(op,**params):
    return request(SOCK,{'op':op,**params},5)


def show_screen(title,text,ui_state=None,source='m10_agent'):
    DIRECTORY.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,name=tempfile.mkstemp(prefix='.display-',dir=DIRECTORY)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            data={'title':title,'text':text,'updated_at':time.time(),'source':source}
            if ui_state:
                data['ui_state']=ui_state
            json.dump(data,stream,ensure_ascii=False)
        os.replace(name,DISPLAY_JSON)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def set_mode(mode):
    Path(MODE_FILE).write_text(mode)


def can_show_voice_result(started):
    try:
        current=json.loads(DISPLAY_JSON.read_text())
        return not (current.get('source')=='Muse device tool' and current.get('updated_at',0)>=started)
    except (OSError,ValueError,TypeError):
        return True


def saved_reply_stamp():
    try:
        info=REPLY_JSON.stat()
        return info.st_mtime_ns,info.st_size
    except OSError:
        return None


def show_new_saved_reply():
    try:
        if Path(MODE_FILE).read_text().strip()!='work':
            return True
        reply=json.loads(REPLY_JSON.read_text())
        title=reply.get('title') or 'Muse reply'
        message=reply.get('text')
        if not isinstance(title,str) or not isinstance(message,str) or not message.strip():
            return False
        try:
            current=json.loads(DISPLAY_JSON.read_text())
        except (OSError,ValueError):
            current={}
        if (current.get('source')=='Muse device tool'
                and current.get('title')==title and current.get('text')==message):
            return True
        show_screen(title,message,'message',source='Muse device tool')
        log('new Muse reply shown from last_reply.json')
        return True
    except (OSError,ValueError,TypeError) as exc:
        log('saved Muse reply unavailable: '+str(exc))
        return False


def record_voice():
    if not VOICE_BUSY.acquire(blocking=False):
        return
    def worker():
        started=time.time()
        try:
            hw('led.set',on=True)
            hw('buzzer.beep',duration_ms=80,frequency_hz=1000)
            show_screen(WORK_TITLE,'Recording for 5 seconds\nSpeak to the board','recording')
            result=subprocess.run(['/usr/bin/python3','/home/muse/m10_voice.py'],
                                   capture_output=True,text=True,timeout=100)
            successful=result.returncode==0
            log('voice note accepted by Muse' if successful else 'voice note failed: '+result.stdout[-300:])
            if Path(MODE_FILE).read_text().strip()=='work' and can_show_voice_result(started):
                show_screen(WORK_TITLE,
                    'Voice sent\nWaiting for Muse reply' if successful else 'Voice send failed\nCheck connection, then retry',
                    'sent' if successful else 'failed')
        except Exception as exc:
            log('voice error: '+str(exc))
            if Path(MODE_FILE).read_text().strip()=='work' and can_show_voice_result(started):
                show_screen(WORK_TITLE,'Voice send failed\nPlease try again','failed')
        finally:
            try:
                hw('led.set',on=False)
                hw('buzzer.beep',duration_ms=80,frequency_hz=1500)
            except Exception:
                pass
            VOICE_BUSY.release()
    threading.Thread(target=worker,daemon=True).start()


def select_action(action):
    if action not in ALLOWED_ACTIONS:
        raise ValueError('unsupported touch action')
    if action=='work':
        try:
            mode=Path(MODE_FILE).read_text().strip()
            current=json.loads(DISPLAY_JSON.read_text())
        except (OSError,ValueError):
            mode,current='',{}
        if mode=='work' and current.get('source')=='Muse device tool' and current.get('text'):
            log('duplicate work action ignored while showing Muse reply')
            return
        set_mode('work')
        # Entering Work Mode starts with its instructions. A new display.show
        # call from Muse can replace this screen when an actual reply arrives.
        show_screen(WORK_TITLE,WORK_TEXT,'ready')
    elif action=='dashboard':
        set_mode('dashboard')
        show_screen('M10 Dashboard','', 'dashboard')
    else:
        set_mode('work')
        record_voice()


def listen_touch():
    Path(AGENT_SOCKET).unlink(missing_ok=True)
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as server:
        server.bind(AGENT_SOCKET)
        os.chmod(AGENT_SOCKET,0o600)
        server.listen(8)
        while True:
            client,_=server.accept()
            with client:
                client.settimeout(2)
                try:
                    data=json.loads(client.makefile('rb').readline(1024))
                    action=data.get('action')
                    if action not in ALLOWED_ACTIONS:
                        raise ValueError('unsupported touch action')
                    ACTIONS.put(action)
                    reply={'ok':True}
                except (OSError,ValueError,AttributeError) as exc:
                    reply={'ok':False,'error':str(exc)}
                try:
                    client.sendall(json.dumps(reply).encode()+b'\n')
                except OSError:
                    pass


def main():
    DIRECTORY.mkdir(parents=True,exist_ok=True,mode=0o700)
    instance_lock=(DIRECTORY/'agent.lock').open('w')
    try:
        fcntl.flock(instance_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        return
    # Keep the selected mode across a UI update or daemon restart.
    try:
        mode=Path(MODE_FILE).read_text().strip()
    except OSError:
        mode='dashboard'
    if mode not in ('work','dashboard'):
        mode='dashboard'
    set_mode(mode)
    # Remove stale instructions that still assigned recording to A/B.
    try:
        data=json.loads(DISPLAY_JSON.read_text())
    except (OSError,ValueError):
        data={}
    if data.get('source')=='m10_agent' or not data.get('text'):
        select_action('work' if mode=='work' else 'dashboard')
    threading.Thread(target=listen_touch,daemon=True).start()
    log('m10_agent started: touch modes; A previous / B next')
    previous_a=previous_b=False
    last_beat=0
    last_reply_stamp=saved_reply_stamp()
    while True:
        try:
            while True:
                try:
                    select_action(ACTIONS.get_nowait())
                except queue.Empty:
                    break
            reply_stamp=saved_reply_stamp()
            if reply_stamp != last_reply_stamp:
                if reply_stamp is None or show_new_saved_reply():
                    last_reply_stamp=reply_stamp
            buttons=hw('buttons.read')
            a,b=bool(buttons.get('a_pressed')),bool(buttons.get('b_pressed'))
            if a and not previous_a:
                request(DISPLAY_SOCKET,{'action':'page_up'})
                log('A pressed -> previous page')
            if b and not previous_b:
                request(DISPLAY_SOCKET,{'action':'page_down'})
                log('B pressed -> next page')
            previous_a,previous_b=a,b
            now=time.monotonic()
            if now-last_beat>=10:
                Path(HEARTBEAT_FILE).write_text(str(int(time.time())))
                last_beat=now
        except Exception as exc:
            log('agent loop error: '+str(exc))
        time.sleep(0.1)


if __name__=='__main__':
    main()
