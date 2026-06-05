"""
Entry point for the VL53L3CX ToF Sensor Monitor.
Streams from a Raspberry Pi running sensor_server.py and shows the GUI locally.
"""

import sys
import argparse

from PyQt6.QtWidgets import QApplication

from sensor import NetworkSensor
from gui import MainWindow


def main():
    parser = argparse.ArgumentParser(description="VL53L3CX ToF Distance Monitor")
    parser.add_argument(
        "host",
        help="IP of a Pi running sensor_server.py (e.g. 192.168.7.2)",
    )
    args = parser.parse_args()

    print(f"Streaming from Pi sensor server at {args.host}:9999 ...")
    sensor = NetworkSensor(host=args.host)

    app = QApplication(sys.argv)
    window = MainWindow(sensor, auto_start=True)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
