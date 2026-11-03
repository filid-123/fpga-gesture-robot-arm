"""Local project console with an explicit, acknowledged FPGA bridge contract.

The page uses the standard library; optional inference is loaded on request.
Mode browsing is static; a mode-lock is forwarded once to a configured bridge.
"""
from __future__ import annotations

import argparse
import copy
import json
import mimetypes
import os
from pathlib import Path
import platform
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from vision import Vision, VisionError

PUBLIC = ROOT / 'public'
CONTRACT = 'zhixing.console.bridge.v1'
FIXED = [{'gesture': i + 1, 'object_id': name} for i, name in enumerate(('red_cube', 'yellow_cube', 'blue_cube'))]
KNOWN = {'red_cube', 'yellow_cube', 'blue_cube', 'small_canister', 'eraser', 'scissors'}


class ApiError(Exception):
    def __init__(self, code, message, outcome='not_applied'):
        super().__init__(message)
        self.code, self.message, self.outcome = code, message, outcome


def detect_device():
    """Read only the current host's public manufacturer/model; no NPU claim."""
    device = {'name': platform.node() or 'AI PC', 'model': platform.system()}
    if os.name == 'nt':
        try:
            result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command',
                'Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model | ConvertTo-Json -Compress'],
                capture_output=True, timeout=8, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            value = json.loads(result.stdout.decode('utf-8-sig'))
            device = {'name': value['Manufacturer'].strip(), 'model': value['Model'].strip()}
        except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
            pass
    return device


class Bridge:
    def __init__(self, config):
        self.url = str(config.get('bridge_url') or '').rstrip('/')
        self.token = os.environ.get(config.get('bridge_token_env', 'PROJECT_CONSOLE_BRIDGE_TOKEN'), '')
        self.timeout = min(max(float(config.get('bridge_timeout_s', 3)), .1), 7)
        self.lock = threading.Lock()
        self.processed = {}
        self.uncertain_id = None
        self.uncertain_time = None
        self.last_connection_error = None
        vision = config.get('vision', {})
        self.vision = {'stream_url': vision.get('stream_url') or None}
        for url in (self.url, self.vision['stream_url']):
            if url and urllib.parse.urlparse(url).scheme not in ('http', 'https'):
                raise ValueError('Bridge and vision URLs must be http(s)')

    def request(self, method, path, data=None):
        headers = {'Accept': 'application/json'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        body = None
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode('utf8')
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(self.url + path, data=body, headers=headers, method=method)
        # No retries, including ambiguous POST timeouts.
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            if response.getcode() != 200:
                raise ValueError('Bridge returned a non-success status')
            return json.loads(response.read(65537).decode('utf-8'))

    @staticmethod
    def validate_status(value):
        if not isinstance(value, dict) or value.get('contract') != CONTRACT:
            raise ValueError('Bridge contract mismatch')
        if value.get('connected') is not True:
            raise ValueError('Bridge is not connected to FPGA')
        if type(value.get('revision')) is not int or value['revision'] < 0:
            raise ValueError('Bridge revision required')
        if type(value.get('idle')) is not bool or value.get('active_mode') not in ('A', 'B', None):
            raise ValueError('Bridge mode/idle state invalid')
        validate_bindings(value.get('gesture_bindings'), allow_empty=value['active_mode'] is None)
        if value['active_mode'] == 'A' and value['gesture_bindings'] != FIXED:
            raise ValueError('Mode A mapping must remain fixed')
        recognized = value.get('recognized_classes')
        if not isinstance(recognized, list) or any(not valid_id(x) for x in recognized):
            raise ValueError('Bridge recognized class capability required')
        return value

    def status(self):
        base = {'connected': False, 'active_mode': None, 'gesture_bindings': [],
                'revision': None, 'idle': None, 'vision': self.vision,
                'pending_request_id': self.uncertain_id}
        if not self.url:
            return {**base, 'bridge_configured': False}
        try:
            value = self.validate_status(self.request('GET', '/status'))
            # An unknown mutation remains blocked until that request is authoritatively resolved.
            if self.uncertain_id and value.get('last_request_id') == self.uncertain_id:
                if value.get('last_request_outcome') in ('applied', 'rejected'):
                    self.uncertain_id = None
                    self.uncertain_time = None
            return {**base, 'connected': True, 'active_mode': value['active_mode'],
                    'gesture_bindings': value['gesture_bindings'], 'revision': value['revision'],
                    'idle': value['idle'], 'recognized_classes': value['recognized_classes'],
                    'pending_request_id': self.uncertain_id, 'bridge_configured': True}
        except (OSError, ValueError, KeyError, TypeError):
            return {**base, 'bridge_configured': True}

    def apply(self, payload):
        if not isinstance(payload, dict):
            raise ApiError(400, '模式请求格式不正确。')
        request_id = payload.get('request_id')
        if not isinstance(request_id, str) or not 8 <= len(request_id) <= 80:
            raise ApiError(400, '缺少有效的请求编号。')
        mode = payload.get('mode')
        if mode not in ('A', 'B'):
            raise ApiError(400, '请选择模式A或模式B。')
        try:
            validate_bindings(payload.get('gesture_bindings'))
        except ValueError as exc:
            raise ApiError(400, str(exc)) from None
        if mode == 'A' and payload['gesture_bindings'] != FIXED:
            raise ApiError(400, '模式A保留红、黄、蓝三个固定目标。')
        if not self.url:
            raise ApiError(503, '设备尚未连接，模式未生效；页面选择已保留。')
        if not self.lock.acquire(blocking=False):
            raise ApiError(409, '另一条模式请求正在等待设备确认。')
        try:
            if request_id in self.processed:
                raise ApiError(409, '此请求已处理，不会重复发送。')
            current = self.status()
            if not current['connected']:
                raise ApiError(503, '设备未连接，未发送模式切换。')
            if self.uncertain_id:
                raise ApiError(409, '上次请求结果尚未确认，请先核对设备状态。', 'unknown')
            if not current['idle']:
                raise ApiError(409, '设备正在执行任务，请待任务结束后切换模式。')
            if type(payload.get('expected_revision')) is not int or payload['expected_revision'] != current['revision']:
                raise ApiError(409, '设备状态已变化，请核对后重新锁定。')
            unsupported = [x['object_id'] for x in payload['gesture_bindings'] if x['object_id'] not in current['recognized_classes']]
            if mode == 'B' and unsupported:
                raise ApiError(422, '所选类别尚未接入识别服务：' + '、'.join(unsupported))
            wire = {k: payload[k] for k in ('request_id', 'mode', 'gesture_bindings', 'expected_revision')}
            wire['contract'] = CONTRACT
            self.processed[request_id] = 'submitted'
            self.uncertain_id = request_id
            self.uncertain_time = time.monotonic()
            try:
                ack = self.request('POST', '/mode-lock', wire)
                if not isinstance(ack, dict) or ack.get('request_id') != request_id or ack.get('applied') is not True:
                    raise ValueError('No matching applied acknowledgment')
                result = self.validate_status(ack.get('status'))
                if (result['active_mode'] != mode or result['gesture_bindings'] != wire['gesture_bindings']
                        or result['revision'] <= current['revision'] or result.get('last_request_id') != request_id
                        or result.get('last_request_outcome') != 'applied'):
                    raise ValueError('Acknowledgment does not confirm submitted selection')
                self.processed[request_id] = 'applied'
                self.uncertain_id = None
                self.uncertain_time = None
                if len(self.processed) > 1000:
                    self.processed = dict(list(self.processed.items())[-500:])
                return {'applied': True, 'request_id': request_id, 'status': {
                    'connected': True, 'active_mode': mode, 'gesture_bindings': result['gesture_bindings'],
                    'revision': result['revision'], 'idle': result['idle'], 'pending_request_id': None,
                    'vision': self.vision}}
            except (OSError, ValueError, TypeError, KeyError):
                raise ApiError(504, '尚未收到有效设备确认，正在核对状态；不会自动重发。', 'unknown') from None
        finally:
            self.lock.release()


def valid_id(value):
    import re
    return isinstance(value, str) and re.fullmatch('[a-z][a-z0-9_]{1,39}', value) is not None


def validate_bindings(value, allow_empty=False):
    if not isinstance(value, list) or not (0 if allow_empty else 1) <= len(value) <= 3:
        raise ValueError('请选择1至3个物体。')
    ids = []
    for i, binding in enumerate(value):
        if (not isinstance(binding, dict) or set(binding) != {'gesture', 'object_id'}
                or type(binding['gesture']) is not int or binding['gesture'] != i + 1
                or not valid_id(binding['object_id'])):
            raise ValueError('手势映射须按1、2、3的选择顺序排列。')
        ids.append(binding['object_id'])
    if len(ids) != len(set(ids)):
        raise ValueError('不可重复选择同一物体。')


class ConsoleHandler(BaseHTTPRequestHandler):
    server_version = 'ZhixingConsole/1.0'

    def respond(self, code, value):
        body = json.dumps(value, ensure_ascii=False).encode('utf8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        route = urllib.parse.urlsplit(self.path).path
        if route == '/api/config':
            self.respond(200, {'device': self.server.device, 'csrf_token': self.server.csrf_token,
                               'max_selected': 3, 'contract': CONTRACT})
        elif route == '/api/status':
            status = self.server.bridge.status()
            status['vision'] = {**status['vision'], 'local': self.server.vision.status()}
            self.respond(200, status)
        elif route.startswith('/api/'):
            self.respond(404, {'message': '接口不存在。'})
        else:
            relative = urllib.parse.unquote(route).lstrip('/') or 'index.html'
            target = (PUBLIC / relative).resolve()
            if not target.is_relative_to(PUBLIC.resolve()) or not target.is_file():
                self.respond(404, {'message': '页面不存在。'})
                return
            body = target.read_bytes()
            mime = 'text/javascript' if target.suffix in ('.js', '.mjs') else mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
            self.send_response(200)
            self.send_header('Content-Type', mime + ('; charset=utf-8' if mime.startswith('text/') else ''))
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'same-origin')
            self.end_headers()
            self.wfile.write(body)

    def do_POST(self):
        route = urllib.parse.urlsplit(self.path).path
        if route not in ('/api/mode-lock', '/api/vision/infer', '/api/vision/sample'):
            self.respond(404, {'message': '接口不存在。'})
            return
        host = self.headers.get('Host', '')
        if (self.headers.get('Origin') not in (None, 'http://' + host, 'https://' + host)
                or self.headers.get('X-Console-Token') != self.server.csrf_token):
            self.respond(403, {'message': '请从本机工作台页面发起请求。', 'outcome': 'not_applied'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            limit = 12 * 1024 * 1024 if route == '/api/vision/infer' else 16384
            if not 0 < length <= limit:
                raise ApiError(400, '请求长度不正确。')
            payload = json.loads(self.rfile.read(length).decode('utf8'))
            if route == '/api/mode-lock':
                result = self.server.bridge.apply(payload)
            else:
                result = self.server.vision.infer(payload, sample=route.endswith('/sample'))
            self.respond(200, result)
        except ApiError as exc:
            self.respond(exc.code, {'message': exc.message, 'outcome': exc.outcome})
        except VisionError as exc:
            self.respond(exc.code, {'message': exc.message, 'physical_execution': False})
        except (ValueError, UnicodeError):
            self.respond(400, {'message': '请求格式不正确。', 'outcome': 'not_applied'})


def make_server(host, port, config, *, device=None):
    server = ThreadingHTTPServer((host, port), ConsoleHandler)
    server.daemon_threads = True
    server.bridge = Bridge(config)
    server.vision = Vision(config.get('vision', {}))
    server.device = config.get('device') or device or detect_device()
    server.csrf_token = secrets.token_urlsafe(32)
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--config', type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8-sig')) if args.config else {}
    server = make_server(args.host, args.port, config)
    print(f'PROJECT_CONSOLE: http://{args.host}:{server.server_port}/#/mode-b', flush=True)
    print('No robot/camera/FPGA connection is opened automatically. Bridge configured: ' + str(bool(server.bridge.url)), flush=True)
    try:
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
