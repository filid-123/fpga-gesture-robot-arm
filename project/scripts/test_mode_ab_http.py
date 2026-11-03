"""Loopback HTTP protocol with an explicitly fake device; no hardware access."""
import json
from pathlib import Path
import sys
import threading
import unittest
import urllib.error
import urllib.request
import uuid
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pc.mode_ab.control import Controller,CONTRACT
from pc.mode_ab.http import Console


class Camera:
    def __init__(self):self.ready=False;self.lock=threading.Lock();self.jpeg=None
    def snapshot(self):return dict(ready=self.ready,observation=None,error=None)


class Tests(unittest.TestCase):
    def setUp(self):
        self.control=Controller();self.camera=Camera();self.console=Console(self.control,self.camera,0)
        self.url=self.console.start();self.origin=self.url

    def tearDown(self):self.console.close()

    def request(self,path,body=None,origin=None,token=None):
        h={}
        if body is not None:h={'Content-Type':'application/json','Origin':origin or self.origin,'X-Session-Token':token or self.console.token}
        req=urllib.request.Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers=h)
        try:
            with urllib.request.urlopen(req,timeout=5) as r:return r.status,r.read(),r.headers
        except urllib.error.HTTPError as e:return e.code,e.read(),e.headers

    def payload(self):
        return dict(contract=CONTRACT,request_id=str(uuid.uuid4()),expected_revision=0,mode='B',
                    gesture_bindings=[dict(gesture=1,object_id='red_cube')])

    def test_disconnected_status_cannot_lock_or_fake_metrics(self):
        code,data,_=self.request('/api/status');self.assertEqual(code,200)
        self.assertFalse(json.loads(data)['control']['connected'])
        code,_,_=self.request('/api/mode-lock',self.payload());self.assertEqual(code,409)

    def test_cross_origin_and_invalid_token_never_enqueue_actions(self):
        for kwargs in [dict(origin='http://evil.invalid'),dict(token='invalid')]:
            code,_,_=self.request('/api/mode-lock',self.payload(),**kwargs);self.assertEqual(code,403)
        self.assertTrue(self.control.pending.empty())

    def test_real_owner_ack_is_returned_with_matching_revision(self):
        # Config is independent of RGB opening, freshness and visible objects.
        self.camera.ready=False
        self.control.update(dict(source='FPGA_REGISTER_SNAPSHOT',abi_verified=True,state='IDLE',at_home=True,
                                 holding=False,arm_fault=False,fault='NONE'))
        class FakeBoard:
            def configure_mode(self,mode,rows):
                return dict(mode=mode,gesture_bindings=rows,fpga_acknowledged=True,motion_started=True,
                            home_transition=dict(completed=True,to_mode=mode))
        def owner():
            request=self.control.pending.get(timeout=3);self.control.pending.put(request);self.control.process_one(FakeBoard())
        thread=threading.Thread(target=owner);thread.start()
        code,data,_=self.request('/api/mode-lock',self.payload());thread.join()
        self.assertEqual(code,200);self.assertTrue(json.loads(data)['applied']);self.assertEqual(self.control.revision,1)

    def test_static_html_has_self_only_policy_and_no_remote_scripts(self):
        code,data,h=self.request('/');self.assertEqual(code,200)
        self.assertIn("script-src 'self'",h['Content-Security-Policy']);self.assertNotIn(b'https://',data)
        code,_,_=self.request('/../../AI_INSTRUCTIONS.md');self.assertEqual(code,404)


if __name__=='__main__':unittest.main()
