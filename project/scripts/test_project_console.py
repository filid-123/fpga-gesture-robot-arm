"""Offline HTTP/bridge tests. Fake bridge only; never contacts hardware."""
from contextlib import contextmanager
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import sys
import threading
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('project_console', ROOT/'web/project-console/server.py')
console = importlib.util.module_from_spec(spec)
spec.loader.exec_module(console)


def request(url, data=None, headers=None):
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


def payload(mode='B', ids=('red_cube', 'eraser', 'small_canister'), rid='request-0001', revision=0):
    return {'mode': mode, 'gesture_bindings': [{'gesture': i+1, 'object_id': obj} for i, obj in enumerate(ids)],
            'request_id': rid, 'expected_revision': revision}


@contextmanager
def running(server):
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .02}, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class FakeHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, body):
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.respond(self.server.state)

    def do_POST(self):
        value = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.posts.append(value)
        if self.server.bad_ack:
            self.respond({'request_id': 'wrong-id', 'applied': True})
            return
        self.server.state.update(active_mode=value['mode'], gesture_bindings=value['gesture_bindings'],
                                 revision=self.server.state['revision']+1, last_request_id=value['request_id'],
                                 last_request_outcome='applied')
        self.respond({'request_id': value['request_id'], 'applied': True, 'status': self.server.state})


@contextmanager
def fake_bridge():
    server = ThreadingHTTPServer(('127.0.0.1', 0), FakeHandler)
    server.state = {'contract': console.CONTRACT, 'connected': True, 'idle': True, 'revision': 0,
                    'active_mode': None, 'gesture_bindings': [], 'recognized_classes': sorted(console.KNOWN)}
    server.posts = []
    server.bad_ack = False
    with running(server) as url:
        yield server, console.Bridge({'bridge_url': url})


class ConsoleTests(unittest.TestCase):
    def test_page_and_offline_api_do_not_claim_device_applied(self):
        server = console.make_server('127.0.0.1', 0, {}, device={'name': 'TEST', 'model': 'FAKE'})
        with running(server) as url:
            code, config = request(url+'/api/config')
            self.assertEqual(code, 200)
            self.assertEqual(config['device']['model'], 'FAKE')
            self.assertEqual(request(url+'/api/status')[1]['connected'], False)
            code, result = request(url+'/api/mode-lock', payload(), {'X-Console-Token': config['csrf_token']})
            self.assertEqual(code, 503)
            self.assertEqual(result['outcome'], 'not_applied')
            self.assertFalse(server.bridge.processed)
            with urllib.request.urlopen(url+'/') as page:
                self.assertIn('知行'.encode(), page.read())
            with urllib.request.urlopen(url+'/state.mjs') as module:
                self.assertIn('javascript', module.headers['Content-Type'])
            self.assertEqual(request(url+'/../server.py')[0], 404)

    def test_mutation_requires_same_origin_and_token(self):
        server = console.make_server('127.0.0.1', 0, {}, device={})
        with running(server) as url:
            self.assertEqual(request(url+'/api/mode-lock', payload())[0], 403)
            headers = {'X-Console-Token': server.csrf_token, 'Origin': 'https://elsewhere.example'}
            self.assertEqual(request(url+'/api/mode-lock', payload(), headers)[0], 403)

    def test_ack_applies_exact_mode_and_order_once(self):
        with fake_bridge() as (server, bridge):
            value = payload()
            ack = bridge.apply(value)
            self.assertTrue(ack['applied'])
            self.assertEqual(ack['status']['gesture_bindings'], value['gesture_bindings'])
            self.assertEqual(len(server.posts), 1)
            with self.assertRaisesRegex(console.ApiError, '不会重复发送'):
                bridge.apply(value)
            self.assertEqual(len(server.posts), 1)

    def test_page_browse_and_status_never_post_to_bridge(self):
        with fake_bridge() as (server, bridge):
            for _ in range(3):
                self.assertTrue(bridge.status()['connected'])
            self.assertEqual(server.posts, [])

    def test_bad_ack_is_unknown_and_blocks_next_request_without_retry(self):
        with fake_bridge() as (server, bridge):
            server.bad_ack = True
            with self.assertRaises(console.ApiError) as caught:
                bridge.apply(payload())
            self.assertEqual(caught.exception.outcome, 'unknown')
            with self.assertRaisesRegex(console.ApiError, '上次请求结果尚未确认'):
                bridge.apply(payload(rid='request-0002'))
            self.assertEqual(len(server.posts), 1)
            server.state.update(last_request_id='request-0001', last_request_outcome='rejected')
            self.assertIsNone(bridge.status()['pending_request_id'])

    def test_busy_stale_and_unsupported_requests_never_forwarded(self):
        with fake_bridge() as (server, bridge):
            server.state['idle'] = False
            with self.assertRaisesRegex(console.ApiError, '执行任务'):
                bridge.apply(payload())
            server.state['idle'] = True
            with self.assertRaisesRegex(console.ApiError, '状态已变化'):
                bridge.apply(payload(revision=1))
            with self.assertRaisesRegex(console.ApiError, '尚未接入识别服务'):
                bridge.apply(payload(ids=('screwdriver',)))
            self.assertFalse(server.posts)

    def test_four_duplicate_or_gapped_gestures_rejected(self):
        bridge = console.Bridge({})
        for ids in [(), ('red_cube',)*2, ('red_cube', 'eraser', 'small_canister', 'scissors')]:
            with self.assertRaises(console.ApiError) as caught:
                bridge.apply(payload(ids=ids))
            self.assertEqual(caught.exception.code, 400)
        value = payload()
        value['gesture_bindings'][0]['gesture'] = 2
        with self.assertRaises(console.ApiError):
            bridge.apply(value)

    def test_mode_a_retains_fixed_color_order(self):
        with fake_bridge() as (server, bridge):
            with self.assertRaisesRegex(console.ApiError, '固定目标'):
                bridge.apply(payload(mode='A'))
            value = payload(mode='A', ids=('red_cube', 'yellow_cube', 'blue_cube'))
            self.assertEqual(bridge.apply(value)['status']['gesture_bindings'], console.FIXED)

    def test_nonmatching_ack_selection_is_not_accepted(self):
        with fake_bridge() as (server, bridge):
            original = bridge.request
            def altered(method, path, data=None):
                result = original(method, path, data)
                if method == 'POST':
                    result = copy.deepcopy(result)
                    result['status']['active_mode'] = 'A'
                return result
            bridge.request = altered
            with self.assertRaises(console.ApiError) as caught:
                bridge.apply(payload())
            self.assertEqual(caught.exception.outcome, 'unknown')
            self.assertEqual(len(server.posts), 1)


if __name__ == '__main__':
    unittest.main()
