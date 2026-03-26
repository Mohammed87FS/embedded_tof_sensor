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
    args = parser.parse_args()

    if args.real_sensor:
        print("Using real VL53L3CX sensor on I²C bus 1...")
        sensor = VL53L3CXSensor()
    else:
        print("Using dummy sensor (development mode)...")
        sensor = DummySensor()

    app = QApplication(sys.argv)
    window = MainWindow(sensor)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
