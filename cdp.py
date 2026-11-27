"""A very small Chrome DevTools Protocol client: enough to load one page at an exact device size and screenshot it.

product_shots.py used to size the page with Chrome's --window-size flag. A desktop Chrome window cannot be made
as narrow as a phone on every system, so the page could be laid out wider than the screenshot, which cut off its
right-hand side and left everything looking off centre. Setting the device size through the protocol does not
depend on the window at all.

Standard library only. Chrome is started with a debugging port on 127.0.0.1 and talked to over a WebSocket.
"""
import base64, hashlib, json, os, socket, struct, subprocess, time, urllib.request

GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'


class CDPError(Exception):
    pass


# ---------------------------------------------------------------- websocket frames
def encode_frame(payload, opcode=0x1, mask=None):
    """One masked client frame. payload is bytes; mask is 4 bytes (random when not given)."""
    mask = os.urandom(4) if mask is None else mask
    n = len(payload)
    head = bytes([0x80 | opcode])
    if n < 126:
        head += bytes([0x80 | n])
    elif n < 65536:
        head += bytes([0x80 | 126]) + struct.pack('>H', n)
    else:
        head += bytes([0x80 | 127]) + struct.pack('>Q', n)
    return head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


def read_frame(read):
    """(fin, opcode, payload) for the next frame. read(n) must return exactly n bytes."""
    b0, b1 = read(2)
    n = b1 & 0x7F
    if n == 126:
        n = struct.unpack('>H', read(2))[0]
    elif n == 127:
        n = struct.unpack('>Q', read(8))[0]
    mask = read(4) if b1 & 0x80 else None
    data = read(n) if n else b''
    if mask:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return bool(b0 & 0x80), b0 & 0x0F, data


class WebSocket:
    def __init__(self, host, port, path, timeout=30):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.buf = b''
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f'GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                           f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        while b'\r\n\r\n' not in self.buf:
            self._fill()
        head, self.buf = self.buf.split(b'\r\n\r\n', 1)
        want = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest())
        if b' 101 ' not in head.split(b'\r\n', 1)[0] or want not in head:
            raise CDPError('Chrome refused the debugging connection')

    def _fill(self):
        chunk = self.sock.recv(1 << 16)
        if not chunk:
            raise CDPError('Chrome closed the debugging connection')
        self.buf += chunk

    def _read(self, n):
        while len(self.buf) < n:
            self._fill()
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, text):
        self.sock.sendall(encode_frame(text.encode('utf-8')))

    def recv(self, timeout):
        """The next whole text message, joining continuation frames and answering pings."""
        self.sock.settimeout(timeout)
        parts = []
        while True:
            try:
                fin, opcode, data = read_frame(self._read)
            except socket.timeout:
                raise CDPError('Chrome did not answer in time')
            if opcode == 0x9:
                self.sock.sendall(encode_frame(data, 0xA)); continue
            if opcode == 0x8:
                raise CDPError('Chrome closed the debugging connection')
            if opcode in (0x0, 0x1, 0x2):
                parts.append(data)
                if fin:
                    return b''.join(parts).decode('utf-8')

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


# ---------------------------------------------------------------- a page
class Page:
    def __init__(self, ws):
        self.ws, self.next_id, self.events = ws, 0, []

    def call(self, method, params=None, timeout=60):
        self.next_id += 1
        self.ws.send(json.dumps({'id': self.next_id, 'method': method, 'params': params or {}}))
        deadline = time.time() + timeout
        while True:
            msg = json.loads(self.ws.recv(max(0.1, deadline - time.time())))
            if msg.get('id') == self.next_id:
                if 'error' in msg:
                    raise CDPError(f"{method}: {msg['error'].get('message', 'failed')}")
                return msg.get('result', {})
            self.events.append(msg)

    def wait_event(self, name, timeout):
        """True once the named event has arrived, False if it does not arrive in time."""
        deadline = time.time() + timeout
        while True:
            if any(e.get('method') == name for e in self.events):
                self.events = [e for e in self.events if e.get('method') != name]
                return True
            left = deadline - time.time()
            if left <= 0:
                return False
            try:
                self.events.append(json.loads(self.ws.recv(left)))
            except CDPError:
                return False


def metrics(width, height, scale, mobile):
    """The Emulation.setDeviceMetricsOverride parameters for a device."""
    return {'width': width, 'height': height, 'deviceScaleFactor': scale, 'mobile': bool(mobile),
            'screenWidth': width, 'screenHeight': height}


def launch_args(chrome, profile):
    return [chrome, '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
            '--disable-extensions', f'--user-data-dir={profile}', '--remote-debugging-port=0',
            '--remote-allow-origins=*', 'about:blank']


def _debug_port(profile, proc, timeout=40):
    path = os.path.join(profile, 'DevToolsActivePort')
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise CDPError(f'Chrome exited at start-up (exit {proc.returncode})')
        try:
            with open(path, encoding='utf-8') as f:
                first = f.read().split('\n')[0].strip()
            if first.isdigit():
                return int(first)
        except OSError:
            pass
        time.sleep(0.1)
    raise CDPError('Chrome did not open its debugging port')


def _page_socket(port):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))      # never through a proxy: it is local
    deadline = time.time() + 20
    while True:
        try:
            with opener.open(f'http://127.0.0.1:{port}/json/list', timeout=10) as r:
                pages = [t for t in json.load(r) if t.get('type') == 'page' and t.get('webSocketDebuggerUrl')]
            if pages:
                return pages[0]['webSocketDebuggerUrl'].split(f':{port}', 1)[1]
        except (OSError, ValueError):
            pass
        if time.time() > deadline:
            raise CDPError('Chrome did not offer a page to control')
        time.sleep(0.2)


def _shut_down(proc, ws):
    """Ask Chrome to close itself, so its helper processes have stopped writing to the profile folder before the
    caller deletes it. Killing only the main process leaves them running for a moment."""
    if ws:
        try:
            ws.send(json.dumps({'id': 0, 'method': 'Browser.close'}))
            proc.wait(timeout=15)
        except (OSError, CDPError, subprocess.TimeoutExpired):
            pass
        ws.close()
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def screenshot(chrome, profile, url, out_png, width, height, scale, mobile=False, user_agent=None,
               color_scheme=None, wait_ms=4000, scroll_y=0, load_timeout=60):
    """Load url at exactly width x height CSS pixels and write a PNG of the visible page.

    Returns the layout viewport width Chrome reports, so the caller can check the page was laid out at the
    width that was asked for."""
    proc = subprocess.Popen(launch_args(chrome, profile), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    try:
        port = _debug_port(profile, proc)
        ws = WebSocket('127.0.0.1', port, _page_socket(port))
        page = Page(ws)
        page.call('Page.enable')
        page.call('Emulation.setDeviceMetricsOverride', metrics(width, height, scale, mobile))
        if user_agent:
            page.call('Emulation.setUserAgentOverride', {'userAgent': user_agent})
        if color_scheme:
            page.call('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-color-scheme', 'value': color_scheme}]})
        page.events = []
        nav = page.call('Page.navigate', {'url': url})
        if nav.get('errorText'):
            raise CDPError(f"the page did not load ({nav['errorText']})")
        page.wait_event('Page.loadEventFired', load_timeout)        # a page that never finishes loading still gets its wait
        time.sleep(wait_ms / 1000)
        if scroll_y:
            page.call('Runtime.evaluate', {'expression': f'window.scrollTo(0, {int(scroll_y)})'})
            time.sleep(0.4)
        laid_out = page.call('Runtime.evaluate', {'expression': 'document.documentElement.clientWidth',
                                                  'returnByValue': True}).get('result', {}).get('value')
        shot = page.call('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False}, timeout=120)
        with open(out_png, 'wb') as f:
            f.write(base64.b64decode(shot['data']))
        return laid_out
    finally:
        _shut_down(proc, ws)
