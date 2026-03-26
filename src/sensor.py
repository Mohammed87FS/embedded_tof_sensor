"""
VL53L3CX sensor abstraction with multi-target support.
The VL53L3CX can detect up to 2 objects simultaneously (Multi-Object Detection).
Provides a real I²C implementation and a dummy for development without hardware.
"""

import random
import math
import time
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class Target:
    distance_mm: int = 0
    signal_rate: float = 0.0
    ambient_rate: float = 0.0
    status: int = 0

    @property
    def valid(self) -> bool:
        return self.status == 0 and 0 < self.distance_mm < 4000

    @property
    def distance_m(self) -> float:
        return self.distance_mm / 1000.0


@dataclass
class SensorReading:
    targets: list[Target] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    @property
    def primary(self) -> Target:
        """Closest valid target, or first target if none valid."""
        valid = [t for t in self.targets if t.valid]
        if valid:
            return min(valid, key=lambda t: t.distance_mm)
        return self.targets[0] if self.targets else Target()

    @property
    def distance_mm(self) -> int:
        return self.primary.distance_mm

    @property
    def signal_rate(self) -> float:
        return self.primary.signal_rate

    @property
    def valid(self) -> bool:
        return self.primary.valid

    @property
    def num_targets(self) -> int:
        return len([t for t in self.targets if t.valid])


class BaseSensor(ABC):
    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def read(self) -> SensorReading: ...

    @abstractmethod
    def stop(self) -> None: ...


class DummySensor(BaseSensor):
    """
    Generates fake dual-target data:
    - Target 1: object moving back and forth (simulates a person)
    - Target 2: fixed wall behind, with some noise
    """

    def __init__(self):
        self._running = False
        self._t = 0.0

    def start(self) -> None:
        self._running = True
        self._t = 0.0

    def read(self) -> SensorReading:
        # Near object: oscillates 300–900mm (like someone swaying)
        near_base = 600 + 300 * math.sin(self._t * 0.4)
        near_dist = max(10, int(near_base + random.gauss(0, 12)))

        # Far object: wall at ~1700mm with slight noise
        far_dist = int(1700 + random.gauss(0, 8))

        # Occasionally drop the near target to simulate it leaving FOV
        drop_near = random.random() < 0.05

        targets = []
        if not drop_near:
            targets.append(Target(
                distance_mm=near_dist,
                signal_rate=random.uniform(2.0, 6.0),
                ambient_rate=random.uniform(0.1, 0.4),
                status=0,
            ))
        targets.append(Target(
            distance_mm=far_dist,
            signal_rate=random.uniform(0.5, 2.0),
            ambient_rate=random.uniform(0.2, 0.6),
            status=0,
        ))

        self._t += 0.1
        return SensorReading(targets=targets)

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
        # TODO: Replace with actual multi-object ranging result from ULD.
        # VL53L3CX_GetMultiRangingData() returns up to 2 targets per zone.
        try:
            raw = self._bus.read_i2c_block_data(self.I2C_ADDR, 0x00, 4)
            t1 = Target(distance_mm=(raw[0] << 8) | raw[1])
            t2 = Target(distance_mm=(raw[2] << 8) | raw[3])
            targets = [t for t in [t1, t2] if t.distance_mm > 0]
            return SensorReading(targets=targets if targets else [Target(status=1)])
        except Exception:
            return SensorReading(targets=[Target(status=1)])

    def stop(self) -> None:
        if self._bus:
            self._bus.close()
            self._bus = None
