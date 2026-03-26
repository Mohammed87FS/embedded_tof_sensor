"""
VL53L3CX sensor abstraction — single-target mode.
Provides a real I²C implementation and a dummy for development without hardware.
"""

import random
import math
import time
from abc import ABC, abstractmethod


class SensorReading:
    __slots__ = ("distance_mm", "signal_rate", "ambient_rate", "status", "timestamp")

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
        return self.status == 0 and 0 < self.distance_mm < 4000


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
    Real sensor via I²C using smbus2.
    Only works on Raspberry Pi with the sensor connected.

    Integration path:
      1. STSW-IMG015 (ST's ULD for direct I²C) — recommended for RPi
      2. ned14/VL53L3CX_rasppi — community port with multi-object example
      3. 74ls04/vl53lx-pi — C lib with histogram, ZMQ publishing
    """

    I2C_ADDR = 0x29
    I2C_BUS = 1

    def __init__(self):
        self._bus = None

    def start(self) -> None:
        try:
            import smbus2
            self._bus = smbus2.SMBus(self.I2C_BUS)
        except ImportError:
            raise RuntimeError("smbus2 not installed — run: pip install smbus2")
        except FileNotFoundError:
            raise RuntimeError(
                "I²C bus not found — enable I²C via raspi-config"
            )
        # TODO: Initialize VL53L3CX via STSW-IMG015 ULD or ned14/VL53L3CX_rasppi.
        # The ULD init sequence sets timing budget, inter-measurement period,
        # and distance mode. See ST UM2778 for register-level details.

    def read(self) -> SensorReading:
        if self._bus is None:
            raise RuntimeError("Sensor not started")
        # TODO: Replace with actual register reads from VL53L3CX.
        # Placeholder — reads won't return meaningful data until ULD is wired up.
        try:
            raw = self._bus.read_i2c_block_data(self.I2C_ADDR, 0x00, 2)
            distance = (raw[0] << 8) | raw[1]
            return SensorReading(distance_mm=distance)
        except Exception:
            return SensorReading(distance_mm=0, status=1)

    def stop(self) -> None:
        if self._bus:
            self._bus.close()
            self._bus = None
