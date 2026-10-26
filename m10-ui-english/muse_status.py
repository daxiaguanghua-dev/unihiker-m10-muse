"""Native touchscreen UI for Muse on UNIHIKER M10; compatible with display.json."""
import datetime
import fcntl
import grp
import json
import math
import os
import pwd
import shutil
from pathlib import Path
import queue
import socket
import subprocess
import threading
import time
import tkinter as tk
from tkinter import font as tkfont

from muse_ui_model import clean_text, paginate, shorten, screen_state, memory_available, chip_temperature
from muse_connection import diagnose, sdk_status
from m10_history import load_history

os.environ.setdefault('DISPLAY', ':0')
os.environ.setdefault('XAUTHORITY', '/root/.Xauthority')
DISPLAY_FILE = Path('/home/muse/.local/share/muse-m10/display.json')
MODE_FILE = Path('/tmp/m10_ui_mode')
UI_SOCKET = '/run/muse-m10/display.sock'
AGENT_SOCKET = '/home/muse/.local/share/muse-m10/agent.sock'
HISTORY_FILE = Path('/home/muse/.local/share/muse-m10/history.json')
DASHBOARD_PAGES = 4
COLORS = dict(bg='#f5f4ef', card='#fbfcf7', ink='#202d29', muted='#77837b',
              line='#e1e5dc', green='#23674d', soft='#eaf0e5', orange='#c46540')


def command(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=3).stdout.strip()


def hardware_request(operation, timeout=2):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect('/run/muse-m10/hardware.sock')
        sock.sendall(json.dumps({'op': operation}).encode() + b'\n')
        response = json.loads(sock.makefile('rb').readline(4096))
    if not response.get('ok'):
        raise RuntimeError(response.get('error', 'Hardware read failed'))
    return response.get('payload', {})


def axes_text(sensor):
    if not sensor:
        return 'Reading...'
    if not sensor.get('available'):
        return 'Unavailable: device read failed'
    try:
        return 'X {x:.2f}  Y {y:.2f}  Z {z:.2f}'.format(**sensor)
    except (KeyError, TypeError, ValueError):
        return 'Invalid data format'


def collect_status(include_audio=False, include_imu=False):
    state = {'connection': 'offline', 'temperature': None, 'memory': None, 'ip': ''}
    try:
        state['memory'] = memory_available()
    except (OSError, ValueError, KeyError):
        pass
    state['temperature'] = chip_temperature(Path('/sys/class/thermal'))
    try:
        disk=shutil.disk_usage('/')
        state['disk_free']=round(disk.free/1024**3,1)
        state['disk_total']=round(disk.total/1024**3,1)
        state['load']=' / '.join(f'{x:.2f}' for x in os.getloadavg())
        state['uptime_minutes']=int(float(Path('/proc/uptime').read_text().split()[0])//60)
        state['memory_total']=round(int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:')))/1024)
        state['wifi_ip']=command(['ip','-4','-o','addr','show','dev','wlan0']).split('inet ')[-1].split('/')[0]
        link=command(['wpa_cli','-i','wlan0','status'])
        state['ssid']=next((x.split('=',1)[1] for x in link.splitlines() if x.startswith('ssid=')),None)
        if not state['ssid']:
            state['ssid']=command(['nmcli','-g','GENERAL.CONNECTION','device','show','wlan0']) or 'Disconnected'
    except (OSError,ValueError,StopIteration,subprocess.TimeoutExpired):
        pass
    try:
        for device in Path('/sys/bus/iio/devices').glob('iio:device*'):
            if (device/'name').read_text().strip()=='pinpong-adc-1':
                raw=int((device/'in_voltage0_raw').read_text())
                state['light']=4095 if raw<150 else 0 if raw>4080 else 4095-raw
    except (OSError, ValueError):
        pass
    try:
        state['buttons'] = hardware_request('buttons.read', timeout=2)
    except (OSError, ValueError, RuntimeError):
        pass
    try:
        state['led_on'] = Path('/sys/class/gpio/gpio215/value').read_text().strip() == '1'
    except OSError:
        state['led_on'] = None
    state['buzzer_ready'] = (Path('/dev/buzzer').exists()
                             and Path('/run/muse-m10/hardware.sock').exists())
    if include_imu:
        try:
            sensors = hardware_request('sensors.read', timeout=5)
            state['accelerometer'] = sensors.get('accelerometer')
            state['gyroscope'] = sensors.get('gyroscope')
        except (OSError, ValueError, RuntimeError):
            state['accelerometer'] = {'available': False}
            state['gyroscope'] = {'available': False}
    if include_audio:
        try:
            state['audio_level'] = hardware_request('audio.level', timeout=5)
            state['audio_sampled_at'] = time.time()
        except (OSError, ValueError, RuntimeError) as exc:
            state['audio_level'] = {'error': 'Mic busy' if 'busy' in str(exc).lower() else 'Unavailable'}
            state['audio_sampled_at'] = time.time()
    try:
        state.update(diagnose())
        state['ip'] = ' / '.join(command(['hostname', '-I']).split())
    except (OSError, subprocess.TimeoutExpired):
        state['connection'] = 'checking'
    return state


class MuseScreen:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Muse · M10')
        self.root.geometry('240x320+0+0')
        self.root.overrideredirect(True)
        self.root.configure(bg=COLORS['bg'])
        self.root.attributes('-topmost', True)
        self.root.bind('<Escape>', lambda event: self.root.withdraw())
        self.root.bind('<Up>', lambda event: self.flip(-1))
        self.root.bind('<Down>', lambda event: self.flip(1))
        self.canvas = tk.Canvas(self.root, width=240, height=320, bg=COLORS['bg'],
                                highlightthickness=0, borderwidth=0)
        self.canvas.pack()
        self.fonts = {}
        self.data = {}
        self.mode = 'dashboard'
        self.last_value = None
        self.page = 0
        self.pages = [['']]
        self.history_cards = []
        self.history_stamp = None
        self.history_current = None
        self.status = {'connection': 'checking', 'temperature': None, 'memory': None}
        self.inbox = queue.Queue()
        self.last_tick = -1
        self.notice = ''
        self.notice_until = 0
        self.connection_panel = False
        self.connection_panel_auto = False
        self.reconnect_running = False
        self.connection_note = ''
        self.reconnect_after = 0
        self.last_connection_warning = ''
        self.last_imu_check = 0
        self.closed = threading.Event()
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        threading.Thread(target=self.monitor, daemon=True).start()
        threading.Thread(target=self.listen_pages, daemon=True).start()
        self.root.after(20, self.poll)

    def close(self):
        self.closed.set()
        self.root.destroy()

    def font(self, size, bold=False):
        key = size, bold
        if key not in self.fonts:
            self.fonts[key] = tkfont.Font(root=self.root, family='WenQuanYi Zen Hei', size=-size,
                                         weight='bold' if bold else 'normal')
        return self.fonts[key]

    def text(self, x, y, text, size=13, color='ink', bold=False, anchor='nw'):
        return self.canvas.create_text(x, y, text=text, font=self.font(size, bold),
                                       fill=COLORS.get(color, color), anchor=anchor)

    def rect(self, x, y, width, height, radius=12, fill='card', stroke='line', tag=None):
        right, bottom = x + width, y + height
        points = [x+radius,y, right-radius,y, right,y, right,y+radius, right,bottom-radius,
                  right,bottom, right-radius,bottom, x+radius,bottom, x,bottom,
                  x,bottom-radius, x,y+radius, x,y]
        return self.canvas.create_polygon(points, smooth=True, splinesteps=20,
            fill=COLORS.get(fill, fill), outline=COLORS.get(stroke, stroke) if stroke else '',
            width=1, tags=(tag,) if tag else ())

    def touch(self, tag, x, y, width, height, label, action, primary=False, disabled=False):
        fill = 'green' if primary else 'soft'
        if disabled:
            fill = '#e1e5dc'
        self.rect(x, y, width, height, 9, fill, 'green' if primary and not disabled else 'line', tag)
        item = self.text(x+width/2, y+height/2, label, 12,
                         '#ffffff' if primary and not disabled else 'muted' if disabled else 'ink', anchor='center')
        self.canvas.itemconfigure(item, tags=(tag,))
        if not disabled:
            self.canvas.tag_bind(tag, '<Button-1>', lambda event: action())

    def microphone(self, cx, cy, recording=False):
        color = COLORS['orange' if recording else 'green']
        self.canvas.create_oval(cx-25,cy-25,cx+25,cy+25,fill='#f1dccc' if recording else COLORS['soft'],outline='')
        self.rect(cx-5,cy-14,10,19,5, '#f1dccc' if recording else 'soft', color)
        self.canvas.create_arc(cx-10,cy-12,cx+10,cy+11,start=180,extent=180,style='arc',outline=color,width=2)
        self.canvas.create_line(cx-10,cy-3,cx-10,cy+1,fill=color,width=2)
        self.canvas.create_line(cx+10,cy-3,cx+10,cy+1,fill=color,width=2)
        self.canvas.create_line(cx,cy+11,cx,cy+17,fill=color,width=2)
        self.canvas.create_line(cx-5,cy+17,cx+5,cy+17,fill=color,width=2)

    def show(self):
        self.root.deiconify()
        self.root.update_idletasks()
        self.root.lift()

    def flip(self, direction):
        if self.connection_panel:
            return
        state = screen_state(self.data, self.mode)
        total = self.work_page_count(state) if self.mode == 'work' else DASHBOARD_PAGES
        target = max(0, min(total-1, self.page + direction))
        if target != self.page:
            self.page = target
            self.notice = ''
        else:
            self.notice = 'Only one page' if total == 1 else 'First page' if direction < 0 else 'Last page'
            self.notice_until = time.monotonic() + 2
        self.show()
        self.draw()
        print(f'Page {direction:+}: {state} {self.page+1}/{total}', flush=True)

    def work_page_count(self,state):
        current_pages=len(self.pages) if state == 'message' else 1
        return current_pages+len(self.history_cards) if state not in ('recording','sending') else 1

    def refresh_history(self):
        try:
            stamp=HISTORY_FILE.stat().st_mtime_ns
        except OSError:
            stamp=None
        current=(self.data.get('source'),self.data.get('title'),self.data.get('text'))
        if stamp == self.history_stamp and current == self.history_current:
            return False
        self.history_stamp,self.history_current=stamp,current
        items=sorted(load_history(HISTORY_FILE),key=lambda item:item['timestamp'],reverse=True)
        # The newest reply is already the live first page; show it only once.
        if current[0]=='Muse device tool' and current[2]:
            for index,item in enumerate(items):
                if item['kind']=='reply' and item['title']==current[1] and item['text']==current[2]:
                    items.pop(index)
                    break
        cards=[]
        for item in items:
            pages=paginate(clean_text(item['text']),self.font(13).measure,184,4)
            for number,lines in enumerate(pages,1):
                cards.append((item,number,len(pages),lines))
        self.history_cards=cards
        if self.mode == 'work':
            state=screen_state(self.data,self.mode)
            self.page=min(self.page,self.work_page_count(state)-1)
        return True

    def agent_action(self, action):
        if self.data.get('preview'):
            return
        def send():
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                    sock.settimeout(2)
                    sock.connect(AGENT_SOCKET)
                    sock.sendall(json.dumps({'action': action}).encode() + b'\n')
                    reply = json.loads(sock.makefile('rb').readline(1024))
                if not reply.get('ok'):
                    raise RuntimeError(reply.get('error', 'action rejected'))
            except (OSError, ValueError, RuntimeError) as exc:
                self.inbox.put(('error', str(exc)))
        threading.Thread(target=send, daemon=True).start()

    def monitor(self):
        while not self.closed.is_set():
            dashboard = self.mode == 'dashboard' and not self.data.get('preview')
            imu_due = dashboard and self.page == 2 and time.monotonic() - self.last_imu_check >= 60
            if imu_due:
                self.last_imu_check = time.monotonic()
            self.inbox.put(('status', collect_status(
                include_audio=dashboard and self.page == 3, include_imu=imu_due)))
            self.closed.wait(3)

    def toggle_connection(self):
        self.connection_panel = not self.connection_panel
        self.connection_panel_auto = False
        self.draw()

    def reconnect(self):
        if self.reconnect_running or time.monotonic() < self.reconnect_after:
            return
        self.reconnect_running = True
        self.connection_note = 'Requesting reconnect...'
        self.draw()
        def restart():
            try:
                # A network restart must not interrupt an active voice upload.
                with open('/home/muse/.local/share/muse-m10/voice.lock','r+') as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    try:
                        busy = sdk_status().get('busy')
                    except (OSError,ValueError,RuntimeError):
                        busy = False
                    if busy:
                        self.inbox.put(('reconnect_done','Device busy; try again'))
                        return
                    subprocess.run(['systemctl','restart','musegadget'],check=True,
                                   capture_output=True,timeout=20)
                self.inbox.put(('reconnect_done','Reconnecting; waiting for session'))
                self.inbox.put(('status',collect_status()))
            except BlockingIOError:
                self.inbox.put(('reconnect_done','Voice in progress; try again'))
            except (OSError,subprocess.SubprocessError):
                self.inbox.put(('reconnect_done','Reconnect failed; check service'))
        threading.Thread(target=restart,daemon=True).start()

    def listen_pages(self):
        path = Path(UI_SOCKET)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(UI_SOCKET)
            os.chown(UI_SOCKET, 0, grp.getgrnam('muse').gr_gid)
            os.chmod(UI_SOCKET, 0o660)
            server.listen(8)
            server.settimeout(1)
            while not self.closed.is_set():
                try:
                    client, _ = server.accept()
                except socket.timeout:
                    continue
                with client:
                    client.settimeout(2)
                    try:
                        request = json.loads(client.makefile('rb').readline(1024))
                        action = request.get('action')
                        if action not in ('page_up', 'page_down'):
                            raise ValueError('unsupported display action')
                        self.inbox.put(('page', -1 if action == 'page_up' else 1))
                        reply = {'ok': True}
                    except (OSError, ValueError, AttributeError) as exc:
                        reply = {'ok': False, 'error': str(exc)}
                    try:
                        client.sendall(json.dumps(reply).encode() + b'\n')
                    except OSError:
                        pass

    def poll(self):
        redraw = False
        try:
            data = json.loads(DISPLAY_FILE.read_text()) if DISPLAY_FILE.exists() else {}
            if not isinstance(data, dict) or not isinstance(data.get('text', ''), str):
                raise ValueError('invalid display message')
            mode = MODE_FILE.read_text().strip() if MODE_FILE.exists() else 'dashboard'
            value = (data.get('text'), data.get('title'), data.get('updated_at'), data.get('ui_state'), mode)
            if value != self.last_value:
                same_content = self.last_value is not None and value[:2] + value[3:] == self.last_value[:2] + self.last_value[3:]
                same_dashboard = self.last_value is not None and self.mode == mode == 'dashboard' and not data.get('preview')
                self.last_value, self.data, self.mode = value, data, mode
                if not same_content and not same_dashboard:
                    self.page = 0
                    self.notice = ''
                    self.pages = paginate(clean_text(data.get('text', '')), self.font(13).measure, 184, 4)
                if data.get('source') == 'Muse device tool' and data.get('text') and 'Dashboard' not in str(data.get('title','')) and not data.get('preview') and data.get('origin') != 'saved_reply':
                    target=DISPLAY_FILE.with_name('last_reply.json')
                    temporary=target.with_suffix('.tmp')
                    temporary.write_text(json.dumps(data,ensure_ascii=False))
                    account=pwd.getpwnam('muse')
                    os.chown(temporary,account.pw_uid,account.pw_gid)
                    os.chmod(temporary,0o600)
                    os.replace(temporary,target)
                redraw = True
                self.show()
                print('Muse UI rendered: ' + screen_state(data, mode), flush=True)
        except (OSError, ValueError, TypeError):
            pass
        if self.refresh_history():
            redraw=True
        try:
            while True:
                kind, value = self.inbox.get_nowait()
                if kind == 'status':
                    self.status.update(value)
                    reason=value.get('reason','')
                    if value['connection']=='online':
                        self.last_connection_warning=''
                        if self.connection_panel_auto:
                            self.connection_panel=False
                            self.connection_panel_auto=False
                        if self.connection_note == 'Reconnecting; waiting for session':
                            self.connection_note = 'Reconnected'
                    elif reason and reason not in ('Connecting to Muse','Checking connection') and reason != self.last_connection_warning:
                        visible_state = screen_state(self.data,self.mode)
                        if not self.data.get('preview') and visible_state in ('dashboard','ready','sent','failed'):
                            self.connection_panel=True
                            self.connection_panel_auto=True
                            self.last_connection_warning=reason
                    redraw = True
                elif kind == 'page':
                    self.flip(value)
                elif kind == 'reconnect_done':
                    self.reconnect_running = False
                    self.reconnect_after = time.monotonic() + 5
                    self.connection_note = value
                    redraw = True
                elif kind == 'error':
                    self.data = {'text': 'Touch unavailable\nPlease try again', 'title': 'Device notice', 'ui_state': 'message'}
                    self.pages = paginate(self.data['text'], self.font(13).measure, 184)
                    self.page = 0
                    redraw = True
        except queue.Empty:
            pass
        tick = int(time.time())
        if self.notice and time.monotonic() >= self.notice_until:
            self.notice = ''
            redraw = True
        if screen_state(self.data, self.mode) == 'recording' and tick != self.last_tick:
            redraw = True
        self.last_tick = tick
        if redraw:
            self.draw()
        self.root.after(200, self.poll)

    def draw(self):
        self.canvas.delete('all')
        self.text(13,13,'Muse',21,bold=True)
        self.rect(72,17,27,17,4,'bg','line')
        self.text(85.5,25.5,'M10',9,'muted',anchor='center')
        self.rect(136,14,29,22,7,'bg','line','menu')
        for x in (145,150,155):
            self.canvas.create_oval(x-1,24,x+1,26,fill=COLORS['muted'],outline='',tags=('menu',))
        self.canvas.tag_bind('menu','<Button-1>',lambda event:self.root.withdraw())
        conn = self.status['connection']
        label, color = {'online':('Online','green'), 'connecting':('Retrying','orange'),
                        'offline':('Offline','muted'), 'checking':('Checking','muted')}[conn]
        if self.data.get('preview'):
            label, color = 'Preview', 'muted'
        self.rect(175,16,53,21,10,'soft',None,'connection')
        self.canvas.create_oval(183,24,188,29,fill=COLORS[color],outline='',tags=('connection',))
        item=self.text(194,18,label,10,color)
        self.canvas.itemconfigure(item,tags=('connection',))
        self.canvas.tag_bind('connection','<Button-1>',lambda event:self.toggle_connection())
        self.canvas.create_line(12,49,228,49,fill=COLORS['line'])
        if self.connection_panel:
            self.draw_connection()
            return
        state = screen_state(self.data, self.mode)
        if state == 'dashboard':
            self.draw_dashboard()
        elif self.mode == 'work' and state not in ('recording','sending') and self.page >= (len(self.pages) if state == 'message' else 1):
            index=self.page-(len(self.pages) if state == 'message' else 1)
            self.draw_history_card(self.history_cards[index])
        elif state == 'message':
            self.draw_message()
        else:
            self.draw_voice(state)
        total = self.work_page_count(state) if self.mode == 'work' else DASHBOARD_PAGES
        hint = self.notice or f'A Prev   {self.page+1}/{total}   B Next'
        self.text(120,259,hint,10,'green' if self.notice else 'muted',anchor='center')
        busy = state in ('recording','sending')
        in_work = self.mode == 'work'
        self.touch('mode',12,273,102,35,'Dashboard' if in_work else 'Work mode',
                   lambda:self.agent_action('dashboard' if in_work else 'work'), disabled=busy)
        if in_work:
            self.touch('record',122,273,106,35,
                       'Recording' if state == 'recording' else 'Sending' if state == 'sending' else 'Record',
                       lambda:self.agent_action('record'),primary=True,disabled=busy)
        else:
            self.touch('network',122,273,106,35,'Details',self.toggle_connection,primary=True)
        try:
            path = Path('/run/muse-m10/view.json')
            temporary = path.with_suffix('.tmp')
            visible_state='history' if self.mode=='work' and state not in ('recording','sending') and self.page >= (len(self.pages) if state=='message' else 1) else state
            temporary.write_text(json.dumps({'state':visible_state,'page':self.page+1,'pages':total,
                                            'mode':self.mode,'notice':self.notice,
                                            'updated_at':self.data.get('updated_at')}))
            os.replace(temporary, path)
        except OSError:
            pass

    def draw_connection(self):
        self.rect(12,62,216,184,16)
        self.text(27,77,'Connection · auto-retry on',10,'muted')
        title=self.status.get('reason','Checking connection')
        self.text(27,101,shorten(title,self.font(18,True).measure,184),18,bold=True)
        detail=self.status.get('detail','Checking device session...')
        lines=paginate(detail,self.font(12).measure,184,4)[0]
        for index,line in enumerate(lines):
            self.text(27,137+19*index,line,12,'#48584e')
        retry=self.status.get('retry',0)
        message='Waiting for SDK retry' if not retry else f'Auto-retry in {retry}s'
        if self.status['connection']=='online':
            message='Session is online'
        self.text(27,224,message,10,'green')
        note=self.connection_note or 'Tap Retry to reconnect now'
        self.text(120,259,shorten(note,self.font(10).measure,214),10,'muted',anchor='center')
        self.touch('back',12,273,102,35,'Back',self.toggle_connection)
        self.touch('reconnect',122,273,106,35,'Connecting' if self.reconnect_running else 'Retry',
                   self.reconnect,primary=True,disabled=self.reconnect_running or time.monotonic()<self.reconnect_after)
        Path('/run/muse-m10/view.json').write_text(json.dumps({'state':'connection',
            'connection':self.status['connection'],'reason':title,'reconnecting':self.reconnect_running}))

    def draw_dashboard(self):
        titles=['System','Connection','Sensors','Sound & I/O']
        self.text(14,64,titles[self.page],19,bold=True)
        self.text(226,73,f'{self.page+1:02} / {DASHBOARD_PAGES:02}',9,'muted',anchor='e')
        if self.page == 0:
            self.rect(12,98,216,90,14,'#204b3a','#204b3a')
            self.text(26,109,'CPU TEMP',10,'#b9d7c3')
            temp=self.status.get('temperature')
            temp_text='—' if temp is None else str(temp)
            self.text(25,128,temp_text,32,'#ffffff',bold=True)
            self.text(31+self.font(32,True).measure(temp_text),145,'°C',13,'#ffffff')
            self.text(26,167,'CPU · not ambient',9,'#b9d7c3')
            uptime=self.status.get('uptime_minutes')
            self.text(213,167,'—' if uptime is None else f'Up {uptime}m',9,'#b9d7c3',anchor='e')
            for x,label,value,unit in (
                (12,'FREE RAM',self.status.get('memory'),'MB'),
                (124,'FREE DISK',self.status.get('disk_free'),'GB')):
                self.rect(x,196,104,50,10)
                self.text(x+10,203,label,9,'muted')
                self.text(x+10,216,'—' if value is None else str(value),19,bold=True)
                self.text(x+92,229,unit,9,'muted',anchor='e')
        elif self.page == 1:
            online=self.status.get('connection')=='online'
            self.rect(12,98,216,90,14,'#204b3a' if online else '#5c695f',None)
            self.canvas.create_oval(26,112,34,120,fill='#8ce0a8' if online else '#e4bd91',outline='')
            self.text(43,109,'MUSE SESSION',10,'#b9d7c3')
            self.text(25,129,'Connected' if online else 'Checking...' if self.status.get('connection')=='checking' else 'Disconnected',23,'#ffffff',bold=True)
            reason=self.status.get('reason','Checking')
            detail='Auto-retry on' if online and reason=='Muse connected' else reason
            self.text(26,167,shorten(detail,self.font(9).measure,125),9,'#b9d7c3')
            load=str(self.status.get('load','—')).split()[0]
            self.text(213,167,'Load '+load,9,'#b9d7c3',anchor='e')
            for x,label,value in ((12,'Wi-Fi',self.status.get('ssid') or 'Disconnected'),
                                  (124,'IP ADDRESS',self.status.get('wifi_ip') or 'No address')):
                self.rect(x,196,104,50,10)
                self.text(x+10,203,label,9,'muted')
                self.text(x+10,220,shorten(str(value),self.font(11).measure,84),11)
        elif self.page == 2:
            self.rect(12,98,216,72,14)
            self.text(26,108,'LIGHT · RAW ADC',10,'muted')
            light=self.status.get('light')
            self.text(25,123,'—' if light is None else str(light),28,bold=True)
            self.text(212,139,'/ 4095',11,'muted',anchor='e')
            self.canvas.create_rectangle(26,157,214,161,fill=COLORS['line'],outline='')
            if isinstance(light,int):
                self.canvas.create_rectangle(26,157,26+max(2,188*max(0,min(light,4095))/4095),161,
                                             fill=COLORS['green'],outline='')
            buttons=self.status.get('buttons') or {}
            for x,key,label in ((12,'a_pressed','A'),(124,'b_pressed','B')):
                pressed=buttons.get(key)
                self.rect(x,178,104,29,9,'soft' if pressed else 'card')
                self.text(x+10,192.5,label,11,'muted',bold=True,anchor='w')
                self.text(x+94,192.5,'Down' if pressed else 'Up' if buttons else 'Unavailable',11,
                          'green' if pressed else 'ink',bold=True,anchor='e')
            for x,label,sensor in ((12,'ACCEL · g',self.status.get('accelerometer')),
                                   (124,'GYRO · rad/s',self.status.get('gyroscope'))):
                self.rect(x,215,104,31,9)
                self.text(x+9,219,label,9,'muted')
                if sensor and sensor.get('available'):
                    value='{x:.1f}/{y:.1f}/{z:.1f}'.format(**sensor)
                else:
                    value='N/A' if sensor else 'Reading...'
                self.text(x+9,232,shorten(value,self.font(10,True).measure,87),10,
                          'orange' if sensor and not sensor.get('available') else 'ink',bold=True)
        else:
            self.rect(12,98,216,82,14,'#204b3a','#204b3a')
            self.text(26,108,'MIC · 1s sample',10,'#b9d7c3')
            audio=self.status.get('audio_level') or {}
            fresh=time.time()-self.status.get('audio_sampled_at',0)<=6
            level=audio.get('level_dbfs') if fresh else None
            if fresh and 'error' in audio:
                loudness=audio['error']
            elif level is None:
                loudness='Sampling' if not fresh else 'Quiet'
            else:
                loudness=f'{level:.1f}'
            self.text(25,128,loudness,26,'#ffffff',bold=True)
            if level is not None:
                self.text(208,143,'dBFS',11,'#b9d7c3',anchor='e')
            self.canvas.create_rectangle(26,163,214,168,fill='#537665',outline='')
            if level is not None:
                self.canvas.create_rectangle(26,163,26+max(2,188*max(0,min(level+70,70))/70),168,
                                             fill='#a9e6bb',outline='')
            self.text(213,109,'Relative level',9,'#b9d7c3',anchor='e')
            led=self.status.get('led_on')
            devices=(('Blue LED','Unavailable' if led is None else 'On' if led else 'Off','#4184c5'),
                     ('Buzzer','Ready' if self.status.get('buzzer_ready') else 'N/A','#c46540'),
                     ('Touch','Ready','#23674d'))
            for index,(label,value,color) in enumerate(devices):
                x=12+index*74
                self.rect(x,190,68,56,10)
                self.canvas.create_oval(x+10,201,x+17,208,fill=color,outline='')
                self.text(x+23,199,label,9,'muted')
                self.text(x+10,218,value,14,bold=True)

    def draw_message(self):
        self.rect(12,62,216,184,16)
        self.text(27,77,'FROM MUSE',10,'muted')
        heading = clean_text(self.data.get('title','Muse reply')).replace('\n',' ') or 'Muse reply'
        self.text(27,98,shorten(heading,self.font(18,True).measure,185),18,bold=True)
        for index,line in enumerate(self.pages[self.page]):
            self.text(27,129+index*20,line,13,'#48584e')
        self.text(28,220,f'{self.page+1:02} / {len(self.pages):02}',10,'muted')
        if self.work_page_count('message') > 1:
            self.touch('previous',88,215,60,23,'Prev',lambda:self.flip(-1))
            self.touch('next',156,215,60,23,'Next',lambda:self.flip(1))

    def draw_history_card(self,card):
        entry,part,total,lines=card
        self.rect(12,62,216,184,16)
        label='VOICE NOTE' if entry['kind']=='voice' else 'MUSE REPLY'
        self.text(27,76,label+' · HISTORY',10,'green')
        stamp=datetime.datetime.fromtimestamp(entry['timestamp']).strftime('%m/%d %H:%M')
        self.text(213,76,stamp,9,'muted',anchor='ne')
        heading=clean_text(entry['title']).replace('\n',' ')
        self.text(27,98,shorten(heading,self.font(18,True).measure,185),18,bold=True)
        for index,line in enumerate(lines):
            self.text(27,129+index*20,line,13,'#48584e')
        self.text(28,220,f'{part:02} / {total:02}',10,'muted')
        self.touch('previous',88,215,60,23,'Prev',lambda:self.flip(-1))
        self.touch('next',156,215,60,23,'Next',lambda:self.flip(1))

    def draw_voice(self,state):
        recording = state == 'recording'
        self.rect(12,62,216,184,16,'#f7eee5' if recording else 'card', '#e9d8c9' if recording else 'line')
        labels = {'ready':('Work mode','Talk to Muse','Tap Record for 5 seconds','Replies appear here'),
                  'sending':('TO MUSE','Sending...','Recording done; uploading','Reply will appear here'),
                  'sent':('SENT TO MUSE','Waiting for reply','Shown when it arrives','Use A/B to turn pages'),
                  'failed':('NOT SENT','Send failed','Check link, then retry','Voice not confirmed')}
        if recording:
            self.text(120,80,'LISTENING',11,'orange',anchor='center')
            self.microphone(120,116,True)
            try:
                remaining = max(0,min(5,math.ceil(5-(time.time()-float(self.data.get('updated_at',time.time()))))))
            except (TypeError,ValueError):
                remaining = 5
            self.text(110,167,f'{remaining:02}',34,bold=True,anchor='center')
            self.text(142,175,'s',11,'orange',anchor='center')
            self.text(120,202,'Speak now · sends in 5s',11,'muted',anchor='center')
            # Decorative capture indicator, not a sound-level meter.
            for i,height in enumerate((6,12,18,10,21,15,8,13,6)):
                x=94+i*6
                self.canvas.create_line(x,222-height/2,x,222+height/2,fill=COLORS['orange'],width=3)
            self.canvas.create_line(31,238,209,238,fill='#e1caba',width=2)
            self.canvas.create_line(31,238,31+178*(5-remaining)/5,238,fill=COLORS['orange'],width=2)
        else:
            kicker,heading,line1,line2 = labels[state]
            self.text(120,80,kicker,11,'muted',anchor='center')
            self.microphone(120,122)
            self.text(120,166,heading,20,bold=True,anchor='center')
            self.text(120,201,line1,11,'muted',anchor='center')
            self.text(120,220,line2,11,'muted',anchor='center')

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    lock_path=Path('/run/muse-m10/display-ui.lock')
    lock_path.parent.mkdir(parents=True,exist_ok=True)
    with lock_path.open('w') as instance_lock:
        try:
            fcntl.flock(instance_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print('Muse UI already running',flush=True)
        else:
            MuseScreen().run()
