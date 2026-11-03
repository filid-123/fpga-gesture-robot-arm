"""Private child-process IPC keeps Ryzen AI and ROCm DLL environments separate."""
import base64
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import threading
import time
import numpy as np


class SurfaceProcess:
    def __init__(self, python, package, backend='rocm', log_file=None, timeout=30):
        root = Path(__file__).resolve().parents[2]
        self.timeout, self.sequence = timeout, 0
        self.messages = queue.Queue()
        self.log = Path(log_file).open('w', encoding='utf8') if log_file else subprocess.DEVNULL
        self.process = subprocess.Popen([str(Path(python).resolve()), '-B', '-X', 'utf8',
            str(root/'scripts/multiobject_surface_worker.py'), '--package', str(Path(package).resolve()),
            '--backend', backend], cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.log, text=True, encoding='utf8', bufsize=1,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        def reader():
            try:
                for line in self.process.stdout:
                    self.messages.put(line)
            finally:
                self.messages.put(None)
        threading.Thread(target=reader, daemon=True).start()
        try:
            ready = self._receive()
            if ready.get('status') != 'READY' or ready['backend']['actual_backend'] != backend:
                raise RuntimeError(f'Surface worker failed: {ready}')
            self.info = {**ready['backend'], 'transport': 'PRIVATE_CHILD_STDIN_STDOUT_RAW_ROI_V1'}
        except Exception:
            self.close()
            raise

    def _receive(self):
        try:
            line = self.messages.get(timeout=self.timeout)
        except queue.Empty as exc:
            self.close()
            raise RuntimeError('Surface worker timed out; previous output invalid') from exc
        if line is None:
            raise RuntimeError('Surface worker terminated; no fallback')
        return json.loads(line)

    def run(self, frame, box):
        start = time.perf_counter_ns()
        h, w = frame.shape[:2]
        x, y = np.floor(box[:2]).astype(int)
        x2, y2 = np.ceil(box[2:]).astype(int)
        if min(x, y) < 0 or x2 > w or y2 > h or x2 <= x or y2 <= y:
            raise ValueError('Invalid process surface ROI')
        crop = np.ascontiguousarray(frame[y:y2, x:x2])
        if crop.dtype != np.uint8 or crop.shape[2:] != (3,):
            raise ValueError('BGR uint8 ROI required')
        raw = crop.tobytes()
        sha = hashlib.sha256(raw).hexdigest()
        self.sequence += 1
        request = {'id': self.sequence, 'shape': list(crop.shape), 'sha256': sha,
                   'data': base64.b64encode(raw).decode('ascii')}
        self.process.stdin.write(json.dumps(request)+'\n'); self.process.stdin.flush()
        result = self._receive()
        if result.get('id') != self.sequence or result.get('sha256') != sha or result.get('status') != 'OK':
            raise RuntimeError(f'Surface worker identity/error: {result.get("error", "frame mismatch")}')
        data = base64.b64decode(result['probabilities'], validate=True)
        p = np.frombuffer(data, dtype='<f4').reshape(crop.shape[:2])
        if not np.isfinite(p).all() or np.any(p < 0) or np.any(p > 1):
            raise ValueError('Invalid worker probabilities')
        return p, [int(x), int(y)], {'backend': dict(self.info),
            'worker_ms': result['total_ms'], 'total_ms': (time.perf_counter_ns()-start)/1e6}

    def close(self):
        if hasattr(self, 'process'):
            if self.process.poll() is None:
                self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait(timeout=5)
            for stream in (self.process.stdin, self.process.stdout):
                if stream:
                    stream.close()
        if hasattr(self.log, 'close'):
            self.log.close()
