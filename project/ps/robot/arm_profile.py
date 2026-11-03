"""Unified six-channel arm profile (``gesture.phase3.arm_profile.v1``).

A profile describes one physical arm instance: channel order, device ids,
zero/direction/scale, soft limits, timeouts and calibration provenance.  The
protocol vocabulary (JSON command templates, Feetech instruction/register
numbers) lives in a separate, firmware-versioned protocol file referenced by
the profile.

Design rules enforced here:

* Every unknown physical value is ``null`` in the shipped profiles.  Structural
  loading still succeeds so dry-run and offline tests can run.
* ``missing_for_real_output()`` lists every field that blocks real output.
  Real serial/PL line output requires an empty list **and**
  ``real_output_enabled: true`` **and** a verified protocol file.
* A profile never inherits limits from another arm.  In particular the RoArm
  CoppeliaSim URDF limits are rejected as SO-ARM101 or physical limits.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from arm_fixed_point import (
    CHANNEL_COUNT,
    ChannelMap,
    FixedPointError,
    INT32_MAX,
    INT32_MIN,
    map_rad_q16_to_device,
    rad_to_q16_16,
    tolerance_rad_q16_to_device,
    units_per_rad_to_uq16_16,
)


PROFILE_SCHEMA = "gesture.phase3.arm_profile.v1"
BACKENDS = ("roarm_m3_json", "roarm_m3_binary_bridge", "so101_feetech")
TRANSPORT_KINDS = ("uart_json_line", "uart_binary", "half_duplex_bus")
CALIBRATION_METHODS = (
    "physical_measurement",
    "vendor_calibration_file",
    "lerobot_calibration_import",
)
DEVICE_ENCODINGS = ("json_fixed_decimal", "bridge_int16", "feetech_position_register")
LOGICAL_ROLES = (
    "base_or_shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
)
BENCH_ROBOT_MODEL = "BENCH_LOOPBACK_NO_ROBOT"

# Copied from sim/phase3_robot/roarm_controller.py (RoArm-M3 URDF, simulation
# only).  Used exclusively to *reject* profiles that reuse them as real limits.
ROARM_SIM_URDF_LIMITS_RAD: tuple[tuple[float, float], ...] = (
    (-3.1416, 3.1416),
    (-1.5708, 1.5708),
    (-1.0, 2.95),
    (-1.5708, 1.5708),
    (-3.1416, 3.1416),
    (0.0, 1.5),
)

MAX_ABS_SOFT_LIMIT_RAD = 8.0


class ProfileError(ValueError):
    """The profile file is structurally invalid."""


class RealOutputBlocked(RuntimeError):
    """Real output was requested while required inputs are missing."""

    def __init__(self, reasons: Sequence[str]):
        self.reasons = tuple(reasons)
        joined = "\n  - ".join(self.reasons)
        super().__init__(f"real output blocked (BLOCKED_EXTERNAL_INPUT):\n  - {joined}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        payload = yaml.safe_load(stream)
    if not isinstance(payload, dict):
        raise ProfileError(f"{path}: top level must be a mapping")
    return payload


def _require_keys(mapping: Mapping[str, Any], allowed: Sequence[str], *, where: str) -> None:
    if not isinstance(mapping, Mapping):
        raise ProfileError(f"{where} must be a mapping")
    unknown = sorted(set(mapping) - set(allowed))
    missing = sorted(set(allowed) - set(mapping))
    if unknown:
        raise ProfileError(f"{where}: unknown keys {unknown}")
    if missing:
        raise ProfileError(f"{where}: missing keys {missing} (use null for TBD)")


def _opt_number(value: Any, *, where: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProfileError(f"{where} must be a number or null")
    if not math.isfinite(float(value)):
        raise ProfileError(f"{where} must be finite")
    return float(value)


def _opt_int(value: Any, *, where: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProfileError(f"{where} must be an integer or null")
    return value


def _opt_str(value: Any, *, where: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProfileError(f"{where} must be a string or null")
    return value


@dataclass(frozen=True)
class JointProfile:
    logical_channel: int
    role: str
    name: str
    device_id: int | None
    zero_device: int | None
    direction: int | None
    device_units_per_rad: float | None
    soft_min_rad: float | None
    soft_max_rad: float | None
    max_velocity_rad_s: float | None
    max_accel_rad_s2: float | None
    arrival_tolerance_rad: float | None

    KEYS = (
        "logical_channel", "role", "name", "device_id", "zero_device", "direction",
        "device_units_per_rad", "soft_min_rad", "soft_max_rad", "max_velocity_rad_s",
        "max_accel_rad_s2", "arrival_tolerance_rad",
    )

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], index: int) -> "JointProfile":
        where = f"joints[{index}]"
        _require_keys(raw, cls.KEYS, where=where)
        channel = _opt_int(raw["logical_channel"], where=f"{where}.logical_channel")
        if channel != index:
            raise ProfileError(f"{where}.logical_channel must be {index} (fixed order)")
        role = raw["role"]
        if role != LOGICAL_ROLES[index]:
            raise ProfileError(f"{where}.role must be {LOGICAL_ROLES[index]!r}")
        name = _opt_str(raw["name"], where=f"{where}.name")
        if not name:
            raise ProfileError(f"{where}.name is required")
        direction = _opt_int(raw["direction"], where=f"{where}.direction")
        if direction not in (None, 1, -1):
            raise ProfileError(f"{where}.direction must be 1, -1 or null")
        device_id = _opt_int(raw["device_id"], where=f"{where}.device_id")
        if device_id is not None and not 0 <= device_id <= 0xFF:
            raise ProfileError(f"{where}.device_id must fit in one byte")
        return cls(
            logical_channel=index,
            role=role,
            name=name,
            device_id=device_id,
            zero_device=_opt_int(raw["zero_device"], where=f"{where}.zero_device"),
            direction=direction,
            device_units_per_rad=_opt_number(
                raw["device_units_per_rad"], where=f"{where}.device_units_per_rad"
            ),
            soft_min_rad=_opt_number(raw["soft_min_rad"], where=f"{where}.soft_min_rad"),
            soft_max_rad=_opt_number(raw["soft_max_rad"], where=f"{where}.soft_max_rad"),
            max_velocity_rad_s=_opt_number(
                raw["max_velocity_rad_s"], where=f"{where}.max_velocity_rad_s"
            ),
            max_accel_rad_s2=_opt_number(
                raw["max_accel_rad_s2"], where=f"{where}.max_accel_rad_s2"
            ),
            arrival_tolerance_rad=_opt_number(
                raw["arrival_tolerance_rad"], where=f"{where}.arrival_tolerance_rad"
            ),
        )

    @property
    def mapping_complete(self) -> bool:
        return None not in (
            self.zero_device,
            self.direction,
            self.device_units_per_rad,
            self.soft_min_rad,
            self.soft_max_rad,
        )


@dataclass(frozen=True)
class TransportProfile:
    kind: str
    port: str | None
    baudrate: int | None
    data_bits: int
    parity: str
    stop_bits: int
    half_duplex_lead_us: float | None
    half_duplex_lag_us: float | None

    KEYS = ("kind", "port", "baudrate", "data_bits", "parity", "stop_bits", "half_duplex")
    HD_KEYS = ("lead_us", "lag_us")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "TransportProfile":
        _require_keys(raw, cls.KEYS, where="transport")
        if raw["kind"] not in TRANSPORT_KINDS:
            raise ProfileError(f"transport.kind must be one of {TRANSPORT_KINDS}")
        if (raw["data_bits"], raw["parity"], raw["stop_bits"]) != (8, "N", 1):
            raise ProfileError("S1 PL UART supports 8N1 only; other formats need a new RTL version")
        baud = _opt_int(raw["baudrate"], where="transport.baudrate")
        if baud is not None and baud <= 0:
            raise ProfileError("transport.baudrate must be positive")
        lead = lag = None
        hd = raw["half_duplex"]
        if raw["kind"] == "half_duplex_bus":
            _require_keys(hd, cls.HD_KEYS, where="transport.half_duplex")
            lead = _opt_number(hd["lead_us"], where="transport.half_duplex.lead_us")
            lag = _opt_number(hd["lag_us"], where="transport.half_duplex.lag_us")
        elif hd is not None:
            raise ProfileError("transport.half_duplex must be null for full-duplex transports")
        return cls(
            kind=raw["kind"],
            port=_opt_str(raw["port"], where="transport.port"),
            baudrate=baud,
            data_bits=8,
            parity="N",
            stop_bits=1,
            half_duplex_lead_us=lead,
            half_duplex_lag_us=lag,
        )


@dataclass(frozen=True)
class DeviceEncoding:
    kind: str
    fraction_digits: int | None
    device_min: int | None
    device_max: int | None

    KEYS = ("kind", "fraction_digits", "device_min", "device_max")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "DeviceEncoding":
        _require_keys(raw, cls.KEYS, where="device_encoding")
        if raw["kind"] not in DEVICE_ENCODINGS:
            raise ProfileError(f"device_encoding.kind must be one of {DEVICE_ENCODINGS}")
        digits = _opt_int(raw["fraction_digits"], where="device_encoding.fraction_digits")
        if digits is not None and not 0 <= digits <= 6:
            raise ProfileError("device_encoding.fraction_digits must be 0..6")
        low = _opt_int(raw["device_min"], where="device_encoding.device_min")
        high = _opt_int(raw["device_max"], where="device_encoding.device_max")
        for label, value in (("device_min", low), ("device_max", high)):
            if value is not None and not INT32_MIN <= value <= INT32_MAX:
                raise ProfileError(f"device_encoding.{label} must fit in int32")
        if low is not None and high is not None and low > high:
            raise ProfileError("device_encoding.device_min must be <= device_max")
        return cls(raw["kind"], digits, low, high)


@dataclass(frozen=True)
class CalibrationRecord:
    date: str | None
    method: str | None
    operator: str | None
    source_files: tuple[tuple[str, str], ...]

    KEYS = ("date", "method", "operator", "source_files")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "CalibrationRecord":
        _require_keys(raw, cls.KEYS, where="calibration")
        method = _opt_str(raw["method"], where="calibration.method")
        if method is not None and method not in CALIBRATION_METHODS:
            raise ProfileError(
                f"calibration.method must be one of {CALIBRATION_METHODS}; "
                "simulation/URDF values are not a physical calibration"
            )
        files_raw = raw["source_files"]
        if not isinstance(files_raw, list):
            raise ProfileError("calibration.source_files must be a list")
        files: list[tuple[str, str]] = []
        for index, entry in enumerate(files_raw):
            _require_keys(entry, ("path", "sha256"), where=f"calibration.source_files[{index}]")
            files.append((str(entry["path"]), str(entry["sha256"])))
        return cls(
            date=_opt_str(raw["date"], where="calibration.date"),
            method=method,
            operator=_opt_str(raw["operator"], where="calibration.operator"),
            source_files=tuple(files),
        )


@dataclass(frozen=True)
class ArmProfile:
    path: Path
    profile_version: str
    robot_model: str
    backend: str
    serial_number: str | None
    real_output_enabled: bool
    bench_only: bool
    protocol_file: Path
    protocol_sha256: str | None
    transport: TransportProfile
    device_encoding: DeviceEncoding
    joints: tuple[JointProfile, ...]
    gripper_open_rad: float | None
    gripper_closed_rad: float | None
    gripper_open_device: int | None
    gripper_closed_device: int | None
    required_feedback_channels: tuple[int, ...]
    arrival_consecutive: int | None
    command_timeout_ms: float | None
    feedback_timeout_ms: float | None
    overall_timeout_ms: float | None
    response_timeout_ms: float | None
    calibration: CalibrationRecord
    notes: tuple[str, ...] = field(default_factory=tuple)

    TOP_KEYS = (
        "schema", "profile_version", "robot_model", "backend", "serial_number",
        "real_output_enabled", "bench_only", "protocol", "transport", "device_encoding",
        "joints", "gripper", "feedback", "timeouts", "calibration", "notes",
    )

    # ------------------------------------------------------------------ load
    @classmethod
    def load(cls, path: Path | str) -> "ArmProfile":
        path = Path(path).resolve()
        raw = load_yaml_mapping(path)
        _require_keys(raw, cls.TOP_KEYS, where=str(path.name))
        if raw["schema"] != PROFILE_SCHEMA:
            raise ProfileError(f"schema must be {PROFILE_SCHEMA!r}")
        if raw["backend"] not in BACKENDS:
            raise ProfileError(f"backend must be one of {BACKENDS}")
        if not isinstance(raw["real_output_enabled"], bool):
            raise ProfileError("real_output_enabled must be a boolean")
        if not isinstance(raw["bench_only"], bool):
            raise ProfileError("bench_only must be a boolean")
        if raw["bench_only"] != (raw["robot_model"] == BENCH_ROBOT_MODEL):
            raise ProfileError(
                f"bench_only must be true exactly when robot_model == {BENCH_ROBOT_MODEL!r}"
            )

        protocol = raw["protocol"]
        _require_keys(protocol, ("file", "sha256"), where="protocol")
        protocol_file = (path.parent / str(protocol["file"])).resolve()

        joints_raw = raw["joints"]
        if not isinstance(joints_raw, list) or len(joints_raw) != CHANNEL_COUNT:
            raise ProfileError("joints must be a list of exactly six channels")
        joints = tuple(JointProfile.from_mapping(j, i) for i, j in enumerate(joints_raw))

        gripper = raw["gripper"]
        _require_keys(
            gripper,
            ("logical_channel", "open_rad", "closed_rad", "open_device", "closed_device"),
            where="gripper",
        )
        if gripper["logical_channel"] != 5:
            raise ProfileError("gripper.logical_channel must be 5")

        feedback = raw["feedback"]
        _require_keys(feedback, ("required_channels", "arrival_consecutive"), where="feedback")
        required = feedback["required_channels"]
        if not isinstance(required, list) or any(
            (not isinstance(ch, int)) or isinstance(ch, bool) or not 0 <= ch < CHANNEL_COUNT
            for ch in required
        ) or len(set(required)) != len(required):
            raise ProfileError("feedback.required_channels must be unique channel numbers 0..5")
        arrival = _opt_int(feedback["arrival_consecutive"], where="feedback.arrival_consecutive")
        if arrival is not None and not 1 <= arrival <= 15:
            raise ProfileError("feedback.arrival_consecutive must be 1..15")

        timeouts = raw["timeouts"]
        _require_keys(
            timeouts,
            ("command_timeout_ms", "feedback_timeout_ms", "overall_timeout_ms", "response_timeout_ms"),
            where="timeouts",
        )
        notes = raw["notes"]
        if not isinstance(notes, list) or not all(isinstance(n, str) for n in notes):
            raise ProfileError("notes must be a list of strings")

        profile = cls(
            path=path,
            profile_version=str(raw["profile_version"]),
            robot_model=str(raw["robot_model"]),
            backend=raw["backend"],
            serial_number=_opt_str(raw["serial_number"], where="serial_number"),
            real_output_enabled=raw["real_output_enabled"],
            bench_only=raw["bench_only"],
            protocol_file=protocol_file,
            protocol_sha256=_opt_str(protocol["sha256"], where="protocol.sha256"),
            transport=TransportProfile.from_mapping(raw["transport"]),
            device_encoding=DeviceEncoding.from_mapping(raw["device_encoding"]),
            joints=joints,
            gripper_open_rad=_opt_number(gripper["open_rad"], where="gripper.open_rad"),
            gripper_closed_rad=_opt_number(gripper["closed_rad"], where="gripper.closed_rad"),
            gripper_open_device=_opt_int(gripper["open_device"], where="gripper.open_device"),
            gripper_closed_device=_opt_int(gripper["closed_device"], where="gripper.closed_device"),
            required_feedback_channels=tuple(required),
            arrival_consecutive=arrival,
            command_timeout_ms=_opt_number(timeouts["command_timeout_ms"], where="timeouts.command_timeout_ms"),
            feedback_timeout_ms=_opt_number(timeouts["feedback_timeout_ms"], where="timeouts.feedback_timeout_ms"),
            overall_timeout_ms=_opt_number(timeouts["overall_timeout_ms"], where="timeouts.overall_timeout_ms"),
            response_timeout_ms=_opt_number(timeouts["response_timeout_ms"], where="timeouts.response_timeout_ms"),
            calibration=CalibrationRecord.from_mapping(raw["calibration"]),
            notes=tuple(notes),
        )
        profile._check_structural_consistency()
        return profile

    def _check_structural_consistency(self) -> None:
        expected_transport = {
            "roarm_m3_json": "uart_json_line",
            "roarm_m3_binary_bridge": "uart_binary",
            "so101_feetech": "half_duplex_bus",
        }[self.backend]
        if self.transport.kind != expected_transport:
            raise ProfileError(
                f"backend {self.backend} requires transport.kind={expected_transport!r}"
            )
        expected_encoding = {
            "roarm_m3_json": "json_fixed_decimal",
            "roarm_m3_binary_bridge": "bridge_int16",
            "so101_feetech": "feetech_position_register",
        }[self.backend]
        if self.device_encoding.kind != expected_encoding:
            raise ProfileError(
                f"backend {self.backend} requires device_encoding.kind={expected_encoding!r}"
            )
        for joint in self.joints:
            if joint.soft_min_rad is not None and joint.soft_max_rad is not None:
                if joint.soft_min_rad >= joint.soft_max_rad:
                    raise ProfileError(f"joint {joint.logical_channel}: soft_min_rad >= soft_max_rad")
                if max(abs(joint.soft_min_rad), abs(joint.soft_max_rad)) > MAX_ABS_SOFT_LIMIT_RAD:
                    raise ProfileError(
                        f"joint {joint.logical_channel}: soft limits beyond +/-{MAX_ABS_SOFT_LIMIT_RAD} rad"
                    )
            if joint.device_units_per_rad is not None and joint.device_units_per_rad < 1.0:
                raise ProfileError(
                    f"joint {joint.logical_channel}: device_units_per_rad must be >= 1.0 "
                    "(choose a finer device unit, e.g. more JSON fraction digits)"
                )
        if self.backend == "so101_feetech":
            ids = [j.device_id for j in self.joints if j.device_id is not None]
            if len(ids) != len(set(ids)):
                raise ProfileError("SO-ARM101 device ids must be unique")

    # --------------------------------------------------------------- queries
    def uses_sim_urdf_limits(self) -> bool:
        limits = tuple((j.soft_min_rad, j.soft_max_rad) for j in self.joints)
        return all(
            a is not None and b is not None and abs(a - u[0]) < 1e-9 and abs(b - u[1]) < 1e-9
            for (a, b), u in zip(limits, ROARM_SIM_URDF_LIMITS_RAD, strict=True)
        )

    def mapping_complete(self) -> bool:
        return all(joint.mapping_complete for joint in self.joints)

    def missing_for_real_output(self) -> list[str]:
        """Profile-level reasons that block *robot* output (protocol checked elsewhere)."""

        reasons: list[str] = []
        if self.bench_only:
            reasons.append("bench_only profile can never drive a robot")
        if not self.real_output_enabled:
            reasons.append("real_output_enabled is false")
        if self.serial_number is None:
            reasons.append("serial_number is TBD")
        if self.protocol_sha256 is None:
            reasons.append("protocol.sha256 is TBD (freeze the verified protocol file)")
        elif self.protocol_file.exists() and sha256_file(self.protocol_file) != self.protocol_sha256:
            reasons.append("protocol file SHA-256 does not match protocol.sha256")
        if self.transport.port is None:
            reasons.append("transport.port is TBD")
        if self.transport.baudrate is None:
            reasons.append("transport.baudrate is TBD")
        if self.transport.kind == "half_duplex_bus":
            if self.transport.half_duplex_lead_us is None:
                reasons.append("transport.half_duplex.lead_us is TBD")
            if self.transport.half_duplex_lag_us is None:
                reasons.append("transport.half_duplex.lag_us is TBD")
        if self.device_encoding.device_min is None or self.device_encoding.device_max is None:
            reasons.append("device_encoding.device_min/device_max are TBD")
        if self.device_encoding.kind == "json_fixed_decimal" and self.device_encoding.fraction_digits is None:
            reasons.append("device_encoding.fraction_digits is TBD")
        for joint in self.joints:
            prefix = f"joints[{joint.logical_channel}]"
            for label in (
                "zero_device", "direction", "device_units_per_rad", "soft_min_rad",
                "soft_max_rad", "max_velocity_rad_s", "max_accel_rad_s2", "arrival_tolerance_rad",
            ):
                if getattr(joint, label) is None:
                    reasons.append(f"{prefix}.{label} is TBD")
            if self.backend == "so101_feetech" and joint.device_id is None:
                reasons.append(f"{prefix}.device_id is TBD")
        for label in ("gripper_open_rad", "gripper_closed_rad", "gripper_open_device", "gripper_closed_device"):
            if getattr(self, label) is None:
                reasons.append(f"gripper.{label.removeprefix('gripper_')} is TBD")
        if self.arrival_consecutive is None:
            reasons.append("feedback.arrival_consecutive is TBD")
        for label in ("command_timeout_ms", "feedback_timeout_ms", "overall_timeout_ms"):
            if getattr(self, label) is None:
                reasons.append(f"timeouts.{label} is TBD")
        if self.backend == "so101_feetech" and self.response_timeout_ms is None:
            reasons.append("timeouts.response_timeout_ms is TBD")
        cal = self.calibration
        if cal.date is None or cal.method is None or cal.operator is None:
            reasons.append("calibration date/method/operator are TBD")
        if not cal.source_files:
            reasons.append("calibration.source_files is empty (need measured data with SHA-256)")
        for rel_path, digest in cal.source_files:
            source = (self.path.parent / rel_path).resolve()
            if not source.exists():
                reasons.append(f"calibration source missing: {rel_path}")
            elif sha256_file(source) != digest:
                reasons.append(f"calibration source SHA-256 mismatch: {rel_path}")
        if self.uses_sim_urdf_limits():
            reasons.append("soft limits equal the RoArm CoppeliaSim URDF limits; measure the real arm")
        if self.mapping_complete():
            reasons.extend(self.device_range_violations())
        return reasons

    def device_range_violations(self) -> list[str]:
        """Soft-limit endpoints must map inside the protocol device range."""

        low, high = self.device_encoding.device_min, self.device_encoding.device_max
        if low is None or high is None:
            return []
        problems: list[str] = []
        for channel_map, joint in zip(self.channel_maps(), self.joints, strict=True):
            for endpoint in (channel_map.soft_min_q16, channel_map.soft_max_q16):
                mapped = map_rad_q16_to_device(endpoint, channel_map)
                if not low <= mapped.device_value <= high:
                    problems.append(
                        f"joints[{joint.logical_channel}] soft limit maps to device "
                        f"{mapped.device_value}, outside [{low}, {high}]"
                    )
        return problems

    # ----------------------------------------------------------- conversion
    def channel_maps(self) -> tuple[ChannelMap, ...]:
        """Integer PL mapping parameters; requires a complete numeric mapping."""

        if not self.mapping_complete():
            missing = [j.logical_channel for j in self.joints if not j.mapping_complete]
            raise ProfileError(f"unit mapping incomplete for channels {missing}")
        maps: list[ChannelMap] = []
        for joint in self.joints:
            scale = units_per_rad_to_uq16_16(joint.device_units_per_rad)  # type: ignore[arg-type]
            tolerance = 0
            if joint.arrival_tolerance_rad is not None:
                tolerance = tolerance_rad_q16_to_device(
                    rad_to_q16_16(joint.arrival_tolerance_rad), scale
                )
                if tolerance > 0xFFFF:
                    raise ProfileError(
                        f"joints[{joint.logical_channel}] arrival tolerance exceeds 16-bit device units"
                    )
            try:
                maps.append(
                    ChannelMap(
                        soft_min_q16=rad_to_q16_16(joint.soft_min_rad),  # type: ignore[arg-type]
                        soft_max_q16=rad_to_q16_16(joint.soft_max_rad),  # type: ignore[arg-type]
                        zero_dev=int(joint.zero_device),  # type: ignore[arg-type]
                        scale_uq16_16=scale,
                        dir_neg=joint.direction == -1,
                        device_id=joint.device_id or 0,
                        arrival_tol_dev=tolerance,
                    )
                )
            except FixedPointError as error:
                raise ProfileError(f"joints[{joint.logical_channel}]: {error}") from error
        return tuple(maps)

    def cycles(self, duration_ms: float | None, clock_hz: int = 100_000_000) -> int | None:
        if duration_ms is None:
            return None
        return int(round(duration_ms * clock_hz / 1000.0))


def find_config_root(start: Path | None = None) -> Path:
    """Locate ``config/`` in either the project or the version-package layout."""

    here = Path(start or __file__).resolve()
    for parent in here.parents:
        candidate = parent / "config" / "arm_profiles"
        if candidate.is_dir():
            return parent / "config"
    raise FileNotFoundError("could not locate config/arm_profiles above " + str(here))
