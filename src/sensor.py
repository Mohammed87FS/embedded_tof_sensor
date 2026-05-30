"""
VL53L3CX sensor abstraction — single-target mode.
Uses the FrgyCZ VL53L3CX-python bindings (ST VL53LX bare driver + smbus2) on Raspberry Pi.

Install on the Pi (full driver; PyPI sdist is incomplete — use Git):
  sudo apt install build-essential python3-dev git
  pip install -r requirements-rpi.txt
"""

import random
import math
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

# ST VL53LX: common “no target” / wraparound sentinel in mm reports
_NO_TARGET_MM = 8191
_ST_INVALID_HIGH = 8000


class SensorReading:
    __slots__ = ("distance_mm", "signal_rate", "ambient_rate", "status", "timestamp")

    # status: 0 = OK, 1 = error, 2 = waiting, 3 = invalid sample, 4 = no target
    def __init__(self, distance_mm: int, signal_rate: float = 0.0,
                 ambient_rate: float = 0.0, status: int = 0):
        self.distance_mm = distance_mm
        self.signal_rate = signal_rate
        self.ambient_rate = ambient_rate
        self.status = status
        self.timestamp = time.time()

    @property
    def distance_m(self) -> float:
        return self.distance_mm / 1000.0

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


class DummySensor(BaseSensor):
    """Generates fake distance data that simulates an object moving back and forth."""

    def __init__(self):
        self._running = False
        self._t = 0.0

    def start(self) -> None:
        self._running = True
        self._t = 0.0

    def read(self) -> SensorReading:
        base = 500 + 400 * math.sin(self._t * 0.5)
        noise = random.gauss(0, 15)
        distance = max(10, int(base + noise))
        self._t += 0.1
        return SensorReading(
            distance_mm=distance,
            signal_rate=random.uniform(1.0, 5.0),
            ambient_rate=random.uniform(0.1, 0.5),
            status=0,
        )

    def stop(self) -> None:
        self._running = False


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
