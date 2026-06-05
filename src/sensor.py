"""
VL53L3CX sensor abstraction — single-target mode.
Uses the FrgyCZ VL53L3CX-python bindings (ST VL53LX bare driver + smbus2) on Raspberry Pi.

Install on the Pi (full driver; PyPI sdist is incomplete — use Git):
  sudo apt install build-essential python3-dev git
  pip install -r requirements-rpi.txt
"""

import time
import socket
from abc import ABC, abstractmethod
from typing import Any, Optional

# ST VL53LX: common “no target” / wraparound sentinel in mm reports
_NO_TARGET_MM = 8191
_ST_INVALID_HIGH = 8000


class SensorReading:
    __slots__ = ("distance_mm", "status", "timestamp")

    # status: 0 = OK, 1 = error, 2 = waiting, 4 = no target
    def __init__(self, distance_mm: int, status: int = 0):
        self.distance_mm = distance_mm
        self.status = status
        self.timestamp = time.time()

    @property
    def valid(self) -> bool:
        return self.status == 0 and 0 < self.distance_mm < 6000


class BaseSensor(ABC):
    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def read(self) -> SensorReading: ...

    @abstractmethod
    def stop(self) -> None: ...


class VL53L3CXSensor(BaseSensor):
    """
    VL53L3CX via ST bare driver (VL53L3CX-python: ctypes + vl53l3cx_python.so).

    Long-range mode + ~50 ms timing budget matches typical indoor demos and
    keeps measurement rate around ~15–20 Hz (sensor-limited).
    """

    def __init__(
        self,
        i2c_bus: int = 1,
        i2c_address: int = 0x29,  # VL53L3CX 7-bit addr (0x52 8-bit) — i2cdetect shows 0x29
        distance_mode: int = 3,
        timing_budget_us: int = 50_000,
        stale_timeout_s: float = 0.5,
    ):
        self._i2c_bus = i2c_bus
        self._i2c_address = i2c_address
        self._distance_mode = distance_mode
        self._timing_budget_us = timing_budget_us
        self._stale_timeout_s = stale_timeout_s
        self._tof: Any = None
        self._last: Optional[SensorReading] = None

    def start(self) -> None:
        try:
            from vl53l3cx_driver import VL53L3CX as _VL53
        except (OSError, ImportError) as e:
            raise RuntimeError(
                "VL53L3CX native driver not found. On Raspberry Pi install build tools and "
                "the extension (PyPI wheel is armv7-only; use pip from Git on aarch64):\n"
                "  sudo apt install build-essential python3-dev git\n"
                "  pip install -r requirements-rpi.txt\n"
                f"Details: {e}"
            ) from e

        self._tof = _VL53(i2c_bus=self._i2c_bus, i2c_address=self._i2c_address)
        self._tof.open(reset=False)
        # Long range (3), then timing budget — order matches ST API expectations
        self._tof.set_distance_mode(self._distance_mode)
        self._tof.set_timing_budget(self._timing_budget_us)
        self._tof.start_ranging()
        self._last = None

    def read(self) -> SensorReading:
        if self._tof is None:
            raise RuntimeError("Sensor not started")

        if not self._tof.is_ranging_ready():
            # Return cached reading only if fresh; otherwise report "waiting"
            if (self._last is not None
                    and (time.time() - self._last.timestamp) < self._stale_timeout_s):
                return self._last
            return SensorReading(distance_mm=0, status=2)

        raw = int(self._tof.get_distance())

        if raw < 0:
            err = SensorReading(distance_mm=0, status=1)
            self._last = err
            return err

        if raw == 0 or raw >= _ST_INVALID_HIGH or raw == _NO_TARGET_MM:
            no_tgt = SensorReading(distance_mm=0, status=4)
            self._last = no_tgt
            return no_tgt

        reading = SensorReading(distance_mm=raw, status=0)
        self._last = reading
        return reading

    def stop(self) -> None:
        if self._tof is not None:
            try:
                self._tof.stop_ranging()
            except Exception:
                pass
            try:
                self._tof.close()
            except Exception:
                pass
            self._tof = None
        self._last = None


class NetworkSensor(BaseSensor):
    """
    Reads sensor data from a Raspberry Pi running sensor_server.py over the LAN.
    Lets the PyQt GUI run natively on a laptop while the real sensor stays on the Pi.

    Protocol: client sends a byte, server replies "distance_mm,status\\n".
    """

    def __init__(self, host: str, port: int = 9999, timeout: float = 5.0):
        self._host = host
        self._port = port
        self._timeout = timeout
        self._sock: Optional[socket.socket] = None
        self._buf = b""

    def start(self) -> None:
        self._sock = socket.create_connection((self._host, self._port), timeout=self._timeout)
        self._sock.settimeout(self._timeout)
        self._buf = b""

    def read(self) -> SensorReading:
        if self._sock is None:
            raise RuntimeError("NetworkSensor not started")
        try:
            self._sock.sendall(b"r")
            while b"\n" not in self._buf:
                data = self._sock.recv(64)
                if not data:
                    return SensorReading(distance_mm=0, status=1)
                self._buf += data
            line, self._buf = self._buf.split(b"\n", 1)
            dist_s, status_s = line.decode().strip().split(",")
            return SensorReading(distance_mm=int(dist_s), status=int(status_s))
        except (socket.timeout, OSError, ValueError):
            return SensorReading(distance_mm=0, status=1)

    def stop(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
