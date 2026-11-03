"""Reused JTAG transport and original telemetry helpers; no hardware on import."""
from pathlib import Path
import os
import queue,subprocess,threading,time
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PACKAGE=ROOT
XSA=PACKAGE/'hardware/roarm_closed_loop.xsa'
XSDB=Path(os.environ.get('GESTURE_XSDB', 'E:/Xilinx/2026.1/Vivado/bin/xsdb.bat'))
BASE=0x43C60000

def exposure_command(v):
    if type(v)!=int or not 0<=v<=0xffffffff or v & 0x7f000000:return False
    a=(v>>8)&65535
    return (v&255)==0 if v>>31 else a in (0x3500,0x3501,0x3502,0x3503,0x350a,0x350b)

def readable(a):
    return isinstance(a,int) and a%4==0 and (a in {0x43C30008,0x43C3000C,0x43C30010,0x43C40008,0x43C4000C,0x43C50004,0x43C50008,0x43C50010,0x43C60004,0x43C60008} or 0x43C60020<=a<=0x43C60038 or 0x43C60040<=a<=0x43C60094)

class Bridge:
    def __init__(self):
        if (HERE / "HARDWARE_RUN_BLOCKED.json").exists():
            raise RuntimeError("This version is offline-only; hardware entry is blocked")
        self.sequence = 0
        self.ready = False
        self.failed = False
        self.lines = []
        self.events = queue.Queue()
        self.log = (HERE / "jtag_actual.log").open("x", encoding="utf-8")
        command = ["cmd.exe", "/d", "/c", str(XSDB), str(HERE / "jtag_bridge.tcl"), "--run",
                   str(PACKAGE / "hardware/roarm_closed_loop.bit"), str(XSA), str(HERE)]
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()

    def _reader(self):
        for line in self.process.stdout:
            self.lines.append(line)
            self.log.write(line); self.log.flush()
            self.events.put(line.rstrip("\r\n"))
        self.events.put(None)

    def wait_ready(self):
        deadline = time.monotonic() + 60
        while True:
            line = self.events.get(timeout=max(.1, deadline-time.monotonic()))
            if line is None:
                raise RuntimeError("XSDB exited before bridge ready; see jtag_actual.log")
            if line.startswith(("VERIFY_ERROR", "RESTORE_ERROR")):
                raise RuntimeError(line)
            if line == "JTAG_READY":
                self.ready = True
                return
            if line.startswith("JTAG_"):
                print(line, flush=True)
            if time.monotonic() >= deadline:
                raise TimeoutError("JTAG setup exceeded 60 seconds")

    def call(self, command):
        try:
            self.sequence += 1
            seq = self.sequence
            self.process.stdin.write(f"{seq} {command}\n"); self.process.stdin.flush()
            deadline = time.monotonic() + 15
            while True:
                line = self.events.get(timeout=max(.1, deadline-time.monotonic()))
                if line is None:
                    raise RuntimeError("XSDB exited during request")
                if line.startswith(f"JTAG_REPLY {seq} "):
                    fields = line.split(maxsplit=3)
                    if fields[2] != "OK":
                        raise RuntimeError(line)
                    return fields[3] if len(fields)>3 else ""
                if line.startswith(("JTAG_FATAL", "VERIFY_ERROR")):
                    raise RuntimeError(line)
        except BaseException:
            self.failed = True
            raise

    def read(self, address, count=1):
        if not 1<=count<=32 or any(not readable(address+4*i) for i in range(count)):
            raise ValueError("Host read outside diagnostic whitelist")
        values = self.call(f"R 0x{address:08x} {count}").split()
        if len(values) != count:
            raise RuntimeError("Short MMIO read")
        return [int(v, 0) for v in values]

    def write(self,address,value):
        if not ((address==BASE+0x88 and exposure_command(value)) or (address==BASE+0x40 and value in (0,1)) or (address==BASE+0x4c and isinstance(value,int) and 0<=value<4096)):
            raise ValueError("Only snapshot or whitelisted exposure writes")
        self.call(f"W 0x{address:08x} {value}")

    def stream(self,count):
        if not isinstance(count,int) or not 1<=count<=256:raise ValueError("Stream size")
        values=self.call(f"S 0x43c60050 {count}").split()
        if len(values)!=count:self.failed=True;raise RuntimeError("Short snapshot stream")
        return [int(v,0) for v in values]

    def close(self):
        if self.process.poll() is None:
            try:
                if self.ready and not self.failed:
                    self.call("CLOSE")
            finally:
                self.process.stdin.close()
                self.process.wait(timeout=20)
        self.thread.join(timeout=2)
        self.log.close()
        if not all(any(line.strip() == expected for line in self.lines)
                   for expected in ("PS_ISOLATED_SHUTDOWN_VERIFIED", "PS_RESET_TERMINAL_CONTRACT 0xF8000240 0x0000000F POR_HIGH_BITS_NOT_RESTORED", "RESTORE_COMPLETE")):
            raise RuntimeError(f"XSDB exit {self.process.returncode}; restore completion not confirmed")
        if self.process.returncode not in (0,2) or not any(v.strip() in ("VERIFY_EXIT 0","VERIFY_EXIT 2") for v in self.lines) or any(v.startswith("RESTORE_ERROR") for v in self.lines):
            raise RuntimeError(f"XSDB exit {self.process.returncode}; restore completion not confirmed")


def signed(value):
    return value - (1 << 32) if value & (1 << 31) else value

def read_state(bridge):
    for _ in range(5):
        fid = bridge.read(BASE + 0x28)[0]
        status = bridge.read(BASE + 4)[0]
        a = bridge.read(BASE + 0x20, 7)
        b = bridge.read(BASE + 0x5c, 11)
        end = bridge.read(BASE + 0x28)[0]
        if fid == a[2] == end:
            break
    camera = b[7]
    return dict(host_monotonic_s=time.monotonic(), coherent=fid == a[2] == end,
                vision_status=status, result_frame_id=a[2], result_events=a[3],
                changes=a[4], stale_events=a[5], qualified=bool(a[6] & 1),
                detected=bool(status & (1 << 11)), candidate_class=(status >> 8) & 7,
                task_class=(status >> 5) & 7, raw_box=[a[0] & 511, a[0] >> 16,
                                                    a[1] & 511, a[1] >> 16],
                acquisition_ms=b[0], result_ms=b[1], latency_ms=b[2],
                model_class=(b[3] >> 16) & 7, margin=b[3] & 65535,
                confidence_i32=signed(b[4]), model_id=b[5], camera_abi=b[6],
                camera_status=camera, xclk_locked=bool(camera & 1),
                init_done=bool(camera & 2), init_error=bool(camera & 4),
                capture_enabled=bool(camera & 8), fifo_overflow=bool(camera & 16),
                pipeline_state=(camera >> 12) & 15, capture_state=(camera >> 16) & 7,
                dropped_while_owned=b[8], format_errors=b[9], now_ms=b[10])

def inert(bridge):
    state = dict(arm_status=bridge.read(0x43c30008)[0],
                 arm_error=bridge.read(0x43c3000c)[0],
                 planner_error=bridge.read(0x43c40008)[0],
                 task_status=bridge.read(0x43c50004)[0],
                 task_fault=bridge.read(0x43c50008)[0])
    if state["arm_status"] & (12 | 0x3000) or state["task_status"] & (15 | 128):
        raise RuntimeError("Require D5 low, backend OFF and S4 OFF/released")
    if state["arm_error"] or state["planner_error"] or state["task_fault"]:
        raise RuntimeError("Unexpected motion fault; stop")
    return state
