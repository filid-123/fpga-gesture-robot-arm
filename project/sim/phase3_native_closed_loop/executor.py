"""Simulator-only executor for the existing S1 BENCH RoArm JSON fixture.

TCP carries the same byte stream as the FPGA UART; --serial uses pyserial.
Feedback is encoded from scene reads, never from the command's target values.
Grasping is a geometric attachment in a stopped kinematic scene, not dynamics.
"""
from __future__ import annotations

import argparse
import json
import math
import socket
import threading
import time
from pathlib import Path

import bootstrap
from arm_bench_tools import load_bench
from arm_fixed_point import map_joint_vector
from roarm_json_reference import (JsonKeyLineParserModel, JsonParserConfig,
                                  encode_command, parse_feedback_line)
from roarm_controller import JOINT_LIMITS_RAD, RoArmController

SCRIPT_ALIAS = "gesture_execution_bridge_v1"
LUA = r'''
local sim = require('sim')
function observeAndApply(handles, positions, tcp, payloads, blocked)
    if sim.getSimulationState() ~= sim.simulation_stopped then
        error('This bridge requires a stopped kinematic scene')
    end
    if #positions > 0 then
        for i = 1, #handles do
            if i ~= blocked then sim.setJointPosition(handles[i], positions[i]) end
        end
    end
    local q = {}
    for i = 1, #handles do q[i] = sim.getJointPosition(handles[i]) end
    local p = sim.getObjectPosition(tcp, sim.handle_world)
    local attached, event = 0, ''
    for i, h in ipairs(payloads) do
        if sim.getObjectParent(h) == tcp then
            attached = i
            if q[6] >= 1.48 then
                sim.setObjectParent(h, sim.handle_world, true)
                attached, event = 0, 'release'
            end
        end
    end
    if attached == 0 and q[6] <= 0.02 then
        for i, h in ipairs(payloads) do
            local o = sim.getObjectPosition(h, sim.handle_world)
            local d = math.sqrt((o[1]-p[1])^2+(o[2]-p[2])^2+(o[3]-p[3])^2)
            if d <= 0.002 then
                sim.setObjectParent(h, tcp, true)
                attached, event = i, 'grasp'
                break
            end
        end
    end
    local objects = {}
    for i, h in ipairs(payloads) do objects[i] = sim.getObjectPosition(h, sim.handle_world) end
    return {joints=q, tcp=p, objects=objects, attached=attached, event=event}
end
'''


def q16(value):
    return int(math.copysign(math.floor(abs(float(value)) * 65536 + 0.5), value))


class FixtureCodec:
    def __init__(self, config_root=None):
        self.profile, self.protocol, self.config = load_bench(
            "roarm", config_root or bootstrap.ROOT / "config")
        if not self.profile.bench_only or not self.protocol.fixture:
            raise ValueError("Only BENCH / FIXTURE_NOT_OFFICIAL profiles are allowed")
        self.maps = self.profile.channel_maps()

    def decode(self, line):
        # Require the exact fixture command, rejecting partial/malformed updates.
        data = json.loads(line)
        if data == {"type": 7}:
            return None
        if set(data) != {"type", "j0", "j1", "j2", "j3", "j4", "j5"} or data["type"] != 101:
            raise ValueError("Not a complete S1 fixture frame")
        rec = parse_feedback_line(self.protocol, line)
        if rec is None or any(v is None for v in rec.device_values):
            raise ValueError("Missing or malformed six-channel values")
        values = tuple((v - j.zero_device) / (j.direction * j.device_units_per_rad)
                       for v, j in zip(rec.device_values, self.profile.joints))
        return RoArmController.validate_joint_positions(values)

    def feedback(self, measured_rad):
        values, limit, sat = map_joint_vector(tuple(q16(x) for x in measured_rad), self.maps)
        if limit or sat:
            raise ValueError("Measured simulator pose cannot be encoded in fixture units")
        return encode_command(self.protocol, "set_joints", values)

    def logical_feedback(self, line):
        event = JsonKeyLineParserModel(JsonParserConfig.from_protocol(self.protocol)).feed(line)
        rec = parse_feedback_line(self.protocol, line)
        if not event or rec is None or any(x is None for x in rec.device_values):
            raise ValueError("Feedback failed the existing S1 streaming parser")
        return tuple((v-j.zero_device)/(j.direction*j.device_units_per_rad)
                     for v, j in zip(rec.device_values, self.profile.joints))


class CoppeliaScene:
    def __init__(self, descriptor=None):
        self.controller = RoArmController.connect()
        self.sim = self.controller.sim
        self.controller.require_stopped()
        if descriptor is not None:
            self.descriptor = descriptor
            return
        from tcp_setup import ensure_tcp
        tcp, _ = ensure_tcp(self.sim, create=False)
        # Create our own temporary script; do not alter an existing model script.
        script = self.sim.createScript(self.sim.scripttype_customization, LUA, 0, "lua")
        self.sim.setObjectAlias(script, SCRIPT_ALIAS)
        self.sim.initScript(script)
        self.descriptor = {"script": script, "joints": list(self.controller.joint_handles),
                           "tcp": tcp, "payloads": [], "supports": []}
        self.initial = self.controller.get_joint_positions()

    def observe(self, positions=None, blocked=0):
        if positions is not None:
            positions = self.controller.validate_joint_positions(positions)
        d = self.descriptor
        return self.sim.callScriptFunction("observeAndApply", d["script"], d["joints"],
                                           list(positions or []), d["tcp"], d["payloads"], blocked)

    def add_support(self, z):
        h=self.sim.createPrimitiveShape(self.sim.primitiveshape_cuboid,[0.9,0.6,0.012],0)
        self.sim.setObjectAlias(h,'gesture_support_surface')
        self.sim.setObjectPosition(h,self.sim.handle_world,[0.15,0,z-0.006])
        self.descriptor['supports'].append(h)

    def add_payloads(self, positions):
        for i, position in enumerate(positions):
            handle = self.sim.createPrimitiveShape(self.sim.primitiveshape_cuboid, [0.016]*3, 0)
            self.sim.setObjectAlias(handle, f"gesture_payload_{i+1}")
            self.sim.setObjectPosition(handle, self.sim.handle_world, list(position))
            self.descriptor["payloads"].append(handle)

    def reset(self, home, positions):
        for h, p in zip(self.descriptor["payloads"], positions):
            self.sim.setObjectParent(h, self.sim.handle_world, True)
            self.sim.setObjectPosition(h, self.sim.handle_world, list(p))
        self.controller.set_joint_positions(home)

    def close(self):
        self.controller.set_joint_positions(self.initial)
        self.sim.removeObjects(self.descriptor["payloads"] + self.descriptor.get("supports",[]) + [self.descriptor["script"]])


class FixtureEndpoint:
    """Bounded streaming decoder; actuator returns measured joint positions."""
    def __init__(self, actuator, codec=None, log=None):
        self.actuator = actuator
        self.codec = codec or FixtureCodec()
        self.buffer = bytearray()
        self.discard = False
        self.suppress_feedback = False
        self.blocked_joint = 0  # Lua is one-based; 0 disables fault injection.
        self.frames = self.replies = self.rejected = 0
        self.observations = []
        self.log = log

    def feed(self, data):
        out = bytearray()
        for byte in data:
            if byte != 10:
                if not self.discard:
                    self.buffer.append(byte)
                    if len(self.buffer) > 512:
                        self.buffer.clear()
                        self.discard = True
                continue
            if self.discard:
                self.discard = False
                self.rejected += 1
                continue
            line = bytes(self.buffer) + b"\n"
            self.buffer.clear()
            try:
                positions = self.codec.decode(line)
            except (ValueError, TypeError, UnicodeError):
                self.rejected += 1
                continue
            observed = self.actuator(positions, self.blocked_joint)
            if positions is not None:
                self.frames += 1
            self.observations.append(observed)
            if self.log is not None:
                self.log.emit("executor_observation", frame=self.frames, commanded=positions,
                              measured=observed["joints"], tcp=observed.get("tcp"),
                              objects=observed.get("objects"), attached=observed.get("attached"),
                              action=observed.get("event"))
            if not self.suppress_feedback:
                out += self.codec.feedback(observed["joints"])
                self.replies += 1
        return bytes(out)


class ExecutorServer:
    def __init__(self, descriptor, codec, log=None):
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.listener.settimeout(0.1)
        self.address = self.listener.getsockname()
        self.stop_event = threading.Event()
        self.ready = threading.Event()
        self.error = None
        self.endpoint = None
        self.descriptor, self.codec, self.log = descriptor, codec, log

    def serve(self):
        try:
            scene = CoppeliaScene(self.descriptor)  # ZMQ socket belongs to this thread.
            self.endpoint = FixtureEndpoint(scene.observe, self.codec, self.log)
            self.ready.set()
            while not self.stop_event.is_set():
                try:
                    conn, _ = self.listener.accept()
                except socket.timeout:
                    continue
                with conn:
                    conn.settimeout(0.1)
                    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    while not self.stop_event.is_set():
                        try:
                            data = conn.recv(4096)
                        except socket.timeout:
                            continue
                        if not data:
                            break
                        reply = self.endpoint.feed(data)
                        if reply:
                            conn.sendall(reply)
        except Exception as error:
            self.error = repr(error)
            self.ready.set()
        finally:
            self.listener.close()

    def start(self):
        self.thread = threading.Thread(target=self.serve, name="coppelia-executor", daemon=True)
        self.thread.start()
        if not self.ready.wait(10) or self.error:
            raise RuntimeError(f"Executor startup failed: {self.error}")
        return self

    def stop(self):
        self.stop_event.set()
        self.thread.join(3)
        if self.thread.is_alive():
            raise RuntimeError("Executor did not stop")


class VirtualUartClient:
    def __init__(self, address, codec, timeout=0.25):
        self.sock = socket.create_connection(address, timeout=1)
        self.sock.settimeout(timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.codec = codec
        self.buffer = bytearray()
        self.roundtrips_ms = []

    def exchange(self, data):
        started = time.perf_counter()
        self.sock.sendall(data)
        wanted = data.count(b"\n")
        lines = []
        deadline = time.monotonic() + self.sock.gettimeout()
        while len(lines) < wanted:
            while b"\n" in self.buffer:
                line, _, rest = self.buffer.partition(b"\n")
                self.buffer = bytearray(rest)
                lines.append(bytes(line)+b"\n")
            if len(lines) >= wanted:
                break
            if time.monotonic() >= deadline:
                return None
            try:
                data_rx = self.sock.recv(4096)
            except socket.timeout:
                return None
            if not data_rx:
                raise ConnectionError("Simulator executor disconnected")
            self.buffer += data_rx
            if len(self.buffer) > 8192:
                raise ValueError("Oversized feedback stream")
        self.roundtrips_ms.append((time.perf_counter()-started)*1000)
        return self.codec.logical_feedback(lines[-1])

    def close(self):
        self.sock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True, help="USB-UART COM port; no physical arm connected")
    parser.add_argument("--config-root", type=Path, default=bootstrap.ROOT/"config")
    parser.add_argument("--descriptor", type=Path, required=True,
                        help="Live scene descriptor written by prepare_scene.py")
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    import serial
    from phase3_event_log import EventLog
    codec = FixtureCodec(args.config_root)
    scene = CoppeliaScene(json.loads(args.descriptor.read_text(encoding="utf-8")))
    args.log.parent.mkdir(parents=True, exist_ok=True)
    log = EventLog("sim", args.log, meta={"simulation": True, "transport": "FPGA UART -> CoppeliaSim",
                                        "fixture": True, "physical_arm": False})
    endpoint = FixtureEndpoint(scene.observe, codec, log)
    try:
        with serial.Serial(args.serial, codec.profile.transport.baudrate, timeout=0.05) as port:
            print("READY: simulator-only S1 fixture executor", flush=True)
            while True:
                data = port.read(max(1, port.in_waiting))
                if data:
                    reply = endpoint.feed(data)
                    if reply:
                        port.write(reply)
    except KeyboardInterrupt:
        return 0
    finally:
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
