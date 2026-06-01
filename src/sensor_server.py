"""
Sensor server - streams live VL53L3CX readings to a remote GUI (NetworkSensor).
Lets the PyQt GUI run on a laptop while the real sensor stays on the Pi.

Run on the Pi:
    cd ~/embedded_tof_sensor/src
    source ../.venv/bin/activate
    python sensor_server.py

Protocol: client sends a byte -> server replies "distance_mm,status\\n".
Works over ANY transport that gives an IP link (Ethernet, USB-C gadget, Wi-Fi).
"""

import socket
from sensor import VL53L3CXSensor

HOST = "0.0.0.0"   # listen on all interfaces (eth0, usb0, wlan0 ...)
PORT = 9999


def main():
    sensor = VL53L3CXSensor()
    sensor.start()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(1)
    print(f"Sensor server listening on port {PORT} (all interfaces). Ctrl+C to stop.")

    try:
        while True:
            conn, addr = srv.accept()
            print(f"Client connected: {addr}")
            try:
                with conn:
                    while True:
                        req = conn.recv(16)
                        if not req:
                            break
                        r = sensor.read()
                        conn.sendall(f"{r.distance_mm},{r.status}\n".encode())
            except OSError:
                pass
            print("Client disconnected - waiting for next connection.")
    except KeyboardInterrupt:
        pass
    finally:
        sensor.stop()
        srv.close()
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
