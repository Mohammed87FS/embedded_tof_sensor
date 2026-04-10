# VL53L3CX ToF Sensor — Embedded System Project

FH Wiener Neustadt — Embedded Systems

## Overview
Distance measurement GUI using the VL53L3CX Time-of-Flight sensor on a Raspberry Pi 5.

- **Sensor:** VL53L3CX (I²C, up to ~5 m in long-range mode)
- **Platform:** Raspberry Pi 5, Raspberry Pi OS (Bookworm 64-bit)
- **GUI:** PyQt6 + pyqtgraph
- **Real-Time:** Not required (sensor max 30 Hz, GUI latency ~50-100ms)

## Team
| Role | Scope |
|------|-------|
| Hardware (Kollege) | Sensor wiring, I²C bus, power, PCB |
| Software (Mohammed) | Linux setup, I²C driver, data pipeline, GUI |

## Branches
| Branch | Description |
|--------|-------------|
| `master` | Single-target mode — simple distance + graph + sonar |
| `feature/multi-target` | Multi-object detection, dual-target display, 3D view (pyqtgraph.opengl) |

## Project Structure
```
embedded_tof_sensor/
├── src/
│   ├── main.py              # Entry point
│   ├── sensor.py            # Sensor abstraction (real + dummy)
│   ├── gui.py               # PyQt6 main window
│   └── sonar_widget.py      # Sonar/radar visualization
├── docs/
│   └── real_time_decision.md # RT vs non-RT justification
├── tests/
├── requirements.txt
├── requirements-rpi.txt     # Pi + VL53L3CX native driver (from Git)
└── README.md
```

## Quick Start (Development on Laptop with Dummy Data)
```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Linux/Pi
pip install -r requirements.txt
python src/main.py
```

## Raspberry Pi Setup
```bash
# 1. Enable I²C
sudo raspi-config  # Interface Options → I2C → Enable

# 2. Build tools + driver (VL53L3CX uses ST’s C API; install from Git — see requirements-rpi.txt)
sudo apt install i2c-tools python3-pip python3-venv build-essential python3-dev git
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-rpi.txt

# 3. Verify sensor
i2cdetect -y 1  # Should show 0x29

# 4. Run (long-range mode and 50 ms timing budget are defaults)
python src/main.py --real-sensor
```
Optional flags: `--i2c-bus 1`, `--i2c-address 0x29`, `--distance-mode 3`, `--timing-budget-us 50000`.
