"""Inference backend entry for the AI PC (Phase 3 S6 candidate).

probe() reports what is ACTUALLY present (framework, version, HIP/ROCm version, device type/name)
- never the planned ROCm version.  select() refuses a CPU fallback unless explicitly allowed, and
every result made through run() carries the backend that produced it, so a CPU fallback can never
be reported as GPU inference.  GPU performance and "no CPU fallback" are NOT_RUN in this package
(the author environment has a CPU-only torch).  A test double for a ROCm torch is used in tests.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class BackendInfo:
    framework: str                 # "torch" | "none"
    framework_version: str
    device_type: str               # "rocm_gpu" | "cuda_gpu" | "cpu" | "none"
    device_name: str
    hip_version: Optional[str]
    cuda_version: Optional[str]

    @property
    def is_cpu_fallback(self) -> bool:
        return self.device_type in ("cpu", "none")


class CpuFallbackRefused(RuntimeError):
    pass


def probe(torch_module: Any = None) -> BackendInfo:
    if torch_module is None:
        try:
            import torch as torch_module          # noqa: F401
        except ImportError:
            return BackendInfo("none", "", "none", "", None, None)
    hip = getattr(torch_module.version, "hip", None)
    cuda = getattr(torch_module.version, "cuda", None)
    if torch_module.cuda.is_available():
        name = torch_module.cuda.get_device_name(0)
        kind = "rocm_gpu" if hip else "cuda_gpu"
    else:
        name, kind = "cpu", "cpu"
    return BackendInfo("torch", str(torch_module.__version__), kind, name, hip, cuda)


def select(info: BackendInfo, *, allow_cpu_fallback: bool = False, require: str = "rocm_gpu") -> BackendInfo:
    if info.device_type != require and not (allow_cpu_fallback and info.is_cpu_fallback):
        if info.is_cpu_fallback:
            raise CpuFallbackRefused(f"backend is {info.device_type} ({info.framework} {info.framework_version}); "
                                     f"{require} required and CPU fallback not allowed")
        raise CpuFallbackRefused(f"backend is {info.device_type}, {require} required")
    return info


@dataclass(frozen=True)
class InferenceResult:
    output: Any
    backend: BackendInfo
    cpu_fallback: bool
    latency_ms: float


def run(fn: Callable[[], Any], info: BackendInfo, clock: Callable[[], float] = time.perf_counter) -> InferenceResult:
    t0 = clock()
    out = fn()
    return InferenceResult(out, info, info.is_cpu_fallback, (clock() - t0) * 1000.0)
