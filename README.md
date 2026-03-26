# VL53L3CX ToF Sensor — Embedded System Project

FH Wiener Neustadt — Embedded Systems

## Overview
Distance measurement GUI using the VL53L3CX Time-of-Flight sensor on a Raspberry Pi 5.

- **Sensor:** VL53L3CX (I²C, up to 3m range)
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

# 2. Install tools
sudo apt install i2c-tools python3-pip
pip install -r requirements.txt

# 3. Verify sensor
i2cdetect -y 1  # Should show 0x29

# 4. Run
python src/main.py --real-sensor
```
