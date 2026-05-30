"""
Entry point for the VL53L3CX ToF Sensor Monitor.
Run with --real-sensor on the Raspberry Pi, or without for dummy data.
"""

import sys
import argparse

from PyQt6.QtWidgets import QApplication

from sensor import DummySensor, VL53L3CXSensor
from gui import MainWindow


def main():
    parser = argparse.ArgumentParser(description="VL53L3CX ToF Distance Monitor")
    parser.add_argument(
        "--real-sensor",
        action="store_true",
        help="Use real VL53L3CX sensor via I²C (requires Raspberry Pi + sensor)",
    )
    parser.add_argument(
        "--i2c-bus",
        type=int,
        default=1,
        help="Linux I²C bus number (default: 1 — GPIO I²C on most Raspberry Pi boards)",
    )
    parser.add_argument(
        "--i2c-address",
        type=lambda x: int(x, 0),
        default=0x29,
        help="7-bit I²C address (default: 0x29)",
    )
    parser.add_argument(
        "--distance-mode",
        type=int,
        choices=(1, 2, 3),
        default=3,
        help="1=short, 2=medium, 3=long range (default: 3)",
    )
    parser.add_argument(
        "--timing-budget-us",
        type=int,
        default=50_000,
        help="Measurement timing budget in microseconds (default: 50000)",
    )
    parser.add_argument(
        "--gpio",
        action="store_true",
        help="Drive LED bar / buzzer / button / status LED (Raspberry Pi only)",
    )
    args = parser.parse_args()

    if args.real_sensor:
        print(
            f"Using real VL53L3CX on I²C bus {args.i2c_bus}, address 0x{args.i2c_address:02x}, "
            f"mode {args.distance_mode}, budget {args.timing_budget_us} µs..."
        )
        sensor = VL53L3CXSensor(
            i2c_bus=args.i2c_bus,
            i2c_address=args.i2c_address,
            distance_mode=args.distance_mode,
            timing_budget_us=args.timing_budget_us,
        )
    else:
        print("Using dummy sensor (development mode)...")
        sensor = DummySensor()

    app = QApplication(sys.argv)
    window = MainWindow(sensor, auto_start=args.real_sensor, gpio=args.gpio)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
