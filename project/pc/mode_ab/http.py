"""Loopback-only HTML console; every action awaits real device state."""
import hmac
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlsplit
from pc.mode_ab.control import ControlError
from pc.mode_ab.motion import ROOT
from pc.mode_ab.motion import boundaries
from pc.mode_ab.diagnostics import explain,vision_rows


class Console:
    def __init__(self,controller,camera,port=8765,runtime=None):
        self.control,self.camera,self.runtime=controller,camera,runtime
        self.token=secrets.token_urlsafe(32);owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass

            def send(self,code,payload,kind='application/json; charset=utf-8'):
                body=json.dumps(payload,allow_nan=False).encode() if isinstance(payload,(dict,list)) else payload
                self.send_response(code);self.send_header('Content-Type',kind)
                self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'")
                self.end_headers();self.wfile.write(body)

            def origin(self):
                return 'http://127.0.0.1:'+str(self.server.server_port)

            def valid_host(self):
                return self.headers.get('Host')=='127.0.0.1:'+str(self.server.server_port)

            def do_GET(self):
                if not self.valid_host():return self.send(403,dict(error='Use the exact loopback console address'))
                path=urlsplit(self.path).path
                if path=='/api/session':return self.send(200,dict(token=owner.token))
                if path=='/api/status':
                    cam=owner.camera.snapshot()
                    return self.send(200,dict(control=owner.control.status(),camera=cam,boundaries=boundaries(),
                        vision_diagnostics=vision_rows(cam),planning=owner.runtime.planning_status() if owner.runtime else None,
                        planning_error=explain(owner.runtime.planning_error) if owner.runtime and owner.runtime.planning_error else None))
                if path=='/api/devices':
                    from pc.rgb_dshow import inspect_devices
                    try:return self.send(200,inspect_devices())
                    except Exception as exc:return self.send(503,dict(error=str(exc)))
                if path=='/camera.jpg':
                    with owner.camera.lock:jpeg=owner.camera.jpeg
                    if jpeg:return self.send(200,jpeg,'image/jpeg')
                    return self.send(503,dict(error='Camera not ready'))
                files={'/':'index.html','/app.js':'app.js','/styles.css':'styles.css'}
                if path not in files:return self.send(404,dict(error='Not found'))
                types={'/':'text/html; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/styles.css':'text/css; charset=utf-8'}
                return self.send(200,(ROOT/'web/mode-ab'/files[path]).read_bytes(),types[path])

            def do_POST(self):
                if (not self.valid_host() or self.headers.get('Origin')!=self.origin()
                    or not hmac.compare_digest(self.headers.get('X-Session-Token',''),owner.token)):
                    return self.send(403,dict(error='Session token/origin mismatch'))
                if self.headers.get_content_type()!='application/json':return self.send(415,dict(error='JSON required'))
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=16384:raise ControlError(413,'Invalid request length')
                    body=json.loads(self.rfile.read(size))
                    path=urlsplit(self.path).path
                    if path=='/api/mode-lock':
                        return self.send(200,owner.control.submit(body,timeout_s=2))
                    if path=='/api/camera':
                        owner.camera.start(body['device_path']);return self.send(202,dict(started=True))
                    if path=='/api/observation':
                        if body.get('physical_success') not in (True,False) or type(body.get('physical_success')) is not bool:
                            raise ControlError(400,'Choose physical success or failure')
                        if not isinstance(body.get('note',''),str) or len(body.get('note',''))>1000:
                            raise ControlError(400,'Invalid observation note')
                        # This cannot change inventory or issue any board command.
                        with (owner.camera.out/'operator_observations.jsonl').open('a',encoding='utf-8') as log:
                            log.write(json.dumps(dict(monotonic_ns=time.monotonic_ns(),control=owner.control.status(),
                                physical_success=body['physical_success'],note=body.get('note','')))+'\n')
                        return self.send(200,dict(recorded=True))
                    return self.send(404,dict(error='Unknown action'))
                except ControlError as exc:
                    owner.control._record('api_rejected',path=urlsplit(self.path).path,reason=str(exc),outcome=exc.outcome)
                    return self.send(exc.code,dict(error=explain(exc),outcome=exc.outcome))
                except (ValueError,KeyError,TypeError) as exc:
                    owner.control._record('api_rejected',path=urlsplit(self.path).path,reason=str(exc))
                    return self.send(400,dict(error=explain(exc)))
                except Exception as exc:
                    owner.control._record('api_error',path=urlsplit(self.path).path,reason=repr(exc),outcome='unknown')
                    return self.send(503,dict(error=explain(exc),outcome='unknown'))
        self.server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)

    def start(self):
        self.thread.start();return 'http://127.0.0.1:'+str(self.server.server_port)

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
