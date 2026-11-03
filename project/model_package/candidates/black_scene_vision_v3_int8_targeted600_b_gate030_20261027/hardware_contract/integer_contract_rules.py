"""PC reference for hardware-proposed B fusion/bank/ROM rules, not full CNN RTL."""
from __future__ import annotations

from numbers import Integral
import numpy as np

INT32_MIN, INT32_MAX = -(1 << 31), (1 << 31) - 1
ROM_BYTES, ROM_WORDS, ROM_WORD_ADDR_BITS = 16384, 4096, 12
ROM_REGIONS = (
    ("base_parameters", 0x0000, 7616),
    ("g1_weights", 0x1DC0, 1152),
    ("g1_bias", 0x2240, 32),
    ("g2_weights", 0x2260, 288),
    ("g2_bias", 0x2380, 16),
    ("relu_M_shift", 0x2400, 40),
    ("residual_M_shift", 0x2440, 32),
)
RELU_CONFIG_ORDER = ("conv1", "conv2", "conv3", "conv4", "g1")
RESIDUAL_CHANNEL_ORDER = ("dx", "dy", "width", "height")


def integer_in_range(value, low, high, label):
    if not isinstance(value, Integral) or isinstance(value, (bool, np.bool_)) or not low <= int(value) <= high:
        raise ValueError(f"Invalid {label}: {value}")
    return int(value)


def require_i32(array, shape):
    array = np.asarray(array)
    if array.dtype != np.int32 or array.shape != shape:
        raise ValueError(f"Expected signed int32 array shaped {shape}")
    return array


def wrap32(values):
    values = np.asarray(values, dtype=np.int64)
    low = values & np.int64(0xFFFFFFFF)
    return np.where(low >= 0x80000000, low - (1 << 32), low).astype(np.int32)


def fuse_geometry(base_i32, residual_i32, multipliers, shifts):
    base = require_i32(base_i32, (5, 16, 16))
    residual = require_i32(residual_i32, (4, 16, 16))
    if len(multipliers) != 4 or len(shifts) != 4:
        raise ValueError("Expected four M/shift pairs")
    ms = [integer_in_range(m, 1, INT32_MAX, "M") for m in multipliers]
    ss = [integer_in_range(s, 0, 31, "shift") for s in shifts]
    products = np.empty((4, 16, 16), dtype=np.int64)
    aligned = np.empty_like(products)
    for k in range(4):
        products[k] = residual[k].astype(np.int64) * np.int64(ms[k])
        shifted_input = products[k] if ss[k] == 0 else products[k] + np.int64(1 << (ss[k] - 1))
        aligned[k] = shifted_input if ss[k] == 0 else shifted_input >> ss[k]
    summed = base[1:].astype(np.int64) + aligned
    output = np.empty_like(base)
    output[0] = base[0]
    output[1:] = wrap32(summed)
    return output, {"product_i64": products, "aligned_i64": aligned, "sum_i64": summed,
                    "int32_overflow_count": int(((summed < INT32_MIN) | (summed > INT32_MAX)).sum())}


def residual_byte_location(k, byte, cell):
    k = integer_in_range(k, 0, 3, "residual channel")
    byte = integer_in_range(byte, 0, 3, "byte")
    cell = integer_in_range(cell, 0, 255, "cell")
    return 2*k + (byte >> 1), 0x200 + (byte & 1)*0x100 + cell


def encode_residual_banks(residual_i32, act0):
    residual = require_i32(residual_i32, (4, 16, 16))
    if act0.shape != (8, 4096) or act0.dtype != np.uint8:
        raise ValueError("Expected eight act0 uint8 banks of 4096 bytes")
    # Preserve all unrelated regions, including F3 0x000..0x1ff.
    banks = act0.copy()
    for k in range(4):
        flat = residual[k].reshape(-1).astype(np.int64) & np.int64(0xFFFFFFFF)
        for byte in range(4):
            bank, start = residual_byte_location(k, byte, 0)
            banks[bank, start:start+256] = ((flat >> (8*byte)) & 255).astype(np.uint8)
    return banks


def decode_residual_banks(act0):
    if act0.shape != (8, 4096) or act0.dtype != np.uint8:
        raise ValueError("Expected eight act0 uint8 banks of 4096 bytes")
    words = np.zeros((4, 256), dtype=np.int64)
    for k in range(4):
        for byte in range(4):
            bank, start = residual_byte_location(k, byte, 0)
            words[k] |= act0[bank, start:start+256].astype(np.int64) << (8*byte)
    return wrap32(words).reshape(4, 16, 16)


def output_address(buffer_id, channel, cell):
    buffer_id = integer_in_range(buffer_id, 0, 1, "output buffer")
    channel = integer_in_range(channel, 0, 4, "output channel")
    cell = integer_in_range(cell, 0, 255, "output cell")
    return (buffer_id << 11) | (channel << 8) | cell


def output_coordinates(address):
    address = integer_in_range(address, 0, 4095, "output address")
    buffer_id, channel, cell = address >> 11, (address >> 8) & 7, address & 255
    if channel > 4:
        raise ValueError("Unused output channel address")
    return buffer_id, channel, cell


def word_address(byte_address):
    byte_address = integer_in_range(byte_address, 0, ROM_BYTES-1, "ROM byte address")
    return byte_address >> 2  # byte_address[13:2], not old [12:2]


def relu_config_address(layer, shift=False):
    return 0x2400 + 8*RELU_CONFIG_ORDER.index(layer) + (4 if shift else 0)


def residual_config_address(channel, shift=False):
    return 0x2440 + 8*RESIDUAL_CHANNEL_ORDER.index(channel) + (4 if shift else 0)


class SynchronousBankModel:
    """Abstract one-edge read visibility; not a simulation of supplied RTL."""
    def __init__(self, values):
        if values.shape != (8, 4096) or values.dtype != np.uint8:
            raise ValueError("Invalid bank array")
        self.values = values.copy()
        self.pending_reads = {}

    def tick(self, reads=None, writes=None):
        reads, writes = reads or {}, writes or {}
        for bank, addr in reads.items():
            integer_in_range(bank, 0, 7, "bank")
            integer_in_range(addr, 0, 4095, "bank address")
            if bank in writes and writes[bank][0] == addr:
                raise ValueError("Same-address read/write collision behavior is not specified")
        for bank, (addr, value) in writes.items():
            integer_in_range(bank, 0, 7, "bank")
            integer_in_range(addr, 0, 4095, "bank address")
            integer_in_range(value, 0, 255, "bank byte")
        visible = self.pending_reads
        self.pending_reads = {bank: int(self.values[bank, addr]) for bank, addr in reads.items()}
        for bank, (addr, value) in writes.items():
            self.values[bank, addr] = value
        return visible


class FinalOutputMonitor:
    """Software contract monitor: no ready; cell-major stream, delayed DONE."""
    def __init__(self, frame_id, buffer_id):
        self.frame_id = integer_in_range(frame_id, 0, (1<<32)-1, "frame_id")
        self.buffer_id = integer_in_range(buffer_id, 0, 1, "buffer_id")
        self.cycle = 0
        self.output_count = 0
        self.last_output_cycle = None
        self.busy = True
        self.result = None
        self.best_cell = None
        self.best_score = None
        self.best_geometry = [None]*4

    def accept_start(self, frame_id, buffer_id):
        if self.busy:
            raise ValueError("Cannot accept a new job while current job is busy")
        self.__init__(frame_id, buffer_id)

    def tick(self, we=False, address=None, data=None, done=False):
        self.cycle += 1
        if not self.busy:
            if we or done:
                raise ValueError("Output/DONE without a live job")
            return
        if done:
            if we or self.output_count != 1280 or self.last_output_cycle is None or self.cycle <= self.last_output_cycle:
                raise ValueError("DONE must follow all final outputs on a separate receiving edge")
            if any(v is None for v in self.best_geometry):
                raise ValueError("Top-1 geometry is incomplete")
            self.result = {"frame_id":self.frame_id, "buffer_id":self.buffer_id,
                           "cell":self.best_cell, "score":self.best_score, "geometry":self.best_geometry.copy()}
            self.busy = False
            return
        if not we:
            return
        if self.output_count >= 1280:
            raise ValueError("Too many final outputs")
        expected_cell, expected_channel = divmod(self.output_count, 5)
        coordinates = output_coordinates(address)
        if coordinates != (self.buffer_id, expected_channel, expected_cell):
            raise ValueError("Output address/order/buffer identity differs from the live job")
        value = integer_in_range(data, INT32_MIN, INT32_MAX, "output word")
        if expected_channel == 0:
            # Strict > preserves the first maximum, including all-INT32_MIN maps.
            if self.best_score is None or value > self.best_score:
                self.best_score, self.best_cell = value, expected_cell
                self.best_geometry = [None]*4
        elif self.best_cell == expected_cell:
            self.best_geometry[expected_channel-1] = value
        self.output_count += 1
        self.last_output_cycle = self.cycle

    def reset(self):
        self.busy = False
        self.result = None
        self.output_count = 0
        self.pending_reads = {}
