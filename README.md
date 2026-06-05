# VL53L3CX Time-of-Flight Distance Monitor

**FH Wiener Neustadt — Embedded Systems**

A distributed embedded measurement system: a **VL53L3CX** Time-of-Flight (ToF)
sensor is read on a **Raspberry Pi 5** over I²C and streamed over TCP to a
**PyQt6** GUI running on a laptop, which displays the live distance and a
time-series graph.

---

## 1. System Overview

| Property | Value |
|----------|-------|
| Sensor | ST **VL53L3CX** ToF, multi-zone capable, used in single-target mode |
| Range | ~25 mm … ~5 m (long-range mode) |
| Interface | I²C (7-bit address `0x29`), Fast-mode 400 kHz |
| Measurement rate | 15–20 Hz (50 ms timing budget, sensor-limited) |
| Compute | Raspberry Pi 5, Raspberry Pi OS (Bookworm, 64-bit / aarch64) |
| Transport | TCP/IP, port `9999` (Ethernet, Wi-Fi, or USB-C gadget link) |
| GUI | PyQt6 + pyqtgraph, runs on a separate laptop |
| Real-time | Not required — see [`docs/real_time_decision.md`](docs/real_time_decision.md) |

### Why split Pi and laptop?

The sensor must be physically on the Pi (I²C is a short-range board bus). The
GUI, however, is heavy to render on a Pi over remote desktop. Splitting the two
keeps the rendering local and lag-free: the Pi does only acquisition, the laptop
does only visualization, and a thin TCP protocol connects them. The transport is
interchangeable — anything that provides an IP link works (LAN, Wi-Fi, or a
direct USB-C Ethernet-gadget cable for a self-contained demo).

---

## 2. Architecture

```
        I²C (0x29)                 TCP / port 9999
 ┌───────────┐   ┌──────────────────────┐        ┌──────────────────────┐
 │ VL53L3CX  │──▶│ Raspberry Pi 5        │───────▶│ Laptop                │
 │ ToF sensor│   │ sensor_server.py      │        │ main.py <PI_IP>       │
 └───────────┘   │  └ VL53L3CXSensor     │        │  └ NetworkSensor      │
                 │     └ vl53l3cx_driver │        │     └ gui.py (PyQt6)  │
                 └──────────────────────┘        └──────────────────────┘
   acquisition node (headless)                     visualization node
```

**Data flow per sample**

```
GUI QTimer (50 ms)
  → NetworkSensor.read()  ── sends 1 byte "r" ──▶  sensor_server.py
                                                     → VL53L3CXSensor.read()
                                                       → vl53l3cx_driver (ctypes → .so → I²C)
  ◀── "distance_mm,status\n" ───────────────────────┘
  → SensorReading → update label + graph
```

---

## 3. Repository Structure

```
embedded_tof_sensor/
├── src/
│   ├── main.py              # Laptop entry point: GUI + NetworkSensor
│   ├── gui.py               # PyQt6 main window (live value + time-series graph)
│   ├── sensor.py            # Sensor abstraction: BaseSensor, VL53L3CXSensor, NetworkSensor
│   ├── sensor_server.py     # Pi entry point: TCP server streaming sensor readings
│   └── vl53l3cx_driver.py   # Vendored ST VL53LX bindings (ctypes + smbus2 I²C callbacks)
├── docs/
│   └── real_time_decision.md  # Justification: no PREEMPT_RT kernel needed
├── electronics_imgs/        # Component / wiring reference photos
├── requirements.txt         # Laptop + shared Python deps
├── requirements-rpi.txt     # Pi-only deps (adds the native VL53L3CX driver)
└── README.md
```

### Module responsibilities

| Module | Runs on | Responsibility |
|--------|---------|----------------|
| `vl53l3cx_driver.py` | Pi | Loads `vl53l3cx_python*.so`, registers smbus2 I²C read/write callbacks, exposes `open / start_ranging / get_distance / …`. Vendored from upstream. |
| `sensor.py` | both | `SensorReading` data object + `BaseSensor` interface. `VL53L3CXSensor` wraps the driver (Pi); `NetworkSensor` is its drop-in TCP client (laptop). |
| `sensor_server.py` | Pi | Opens the sensor once, listens on TCP `9999`, answers each request with one reading. |
| `gui.py` | Laptop | `MainWindow`: 50 ms `QTimer` poll, large distance label, scrolling distance-over-time plot, Start/Stop. |
| `main.py` | Laptop | Parses the Pi IP, wires `NetworkSensor` into the GUI, auto-starts. |

---

## 4. Hardware Setup

### Wiring (I²C)

| VL53L3CX pin | Raspberry Pi 5 (40-pin header) |
|--------------|--------------------------------|
| VIN / VDD | 3V3 (pin 1) |
| GND | GND (pin 6) |
| SDA | GPIO2 / SDA1 (pin 3) |
| SCL | GPIO3 / SCL1 (pin 5) |

> This build powers the Pololu VL53L3CX carrier (#3416) from **3V3**. That board
> has an onboard 3.3 V regulator, so 5V on VIN is also safe — but its I/O is
> 3.3 V, which matches the Pi directly. SDA/SCL have pull-ups on the Pi, and the
> carrier adds its own.

Reference photos are in [`electronics_imgs/`](electronics_imgs/).

---

## 5. Installation

### 5.1 Raspberry Pi (acquisition node)

```bash
# 1. Enable I²C
sudo raspi-config            # Interface Options → I2C → Enable, then reboot

# 2. System build tools (the VL53L3CX driver compiles a C extension)
sudo apt update
sudo apt install i2c-tools python3-pip python3-venv build-essential python3-dev git

# 3. Project + virtual environment
git clone <your-repo-url> embedded_tof_sensor
cd embedded_tof_sensor
python3 -m venv .venv
source .venv/bin/activate

# 4. Python deps (compiles vl53l3cx_python*.so from Git — pinned commit)
pip install -r requirements-rpi.txt

# 5. Verify the sensor is on the bus (expect 0x29)
i2cdetect -y 1
```

### 5.2 Laptop (visualization node)

```powershell
# Windows / PowerShell
cd embedded_tof_sensor
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

```bash
# Linux / macOS
cd embedded_tof_sensor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> The laptop does **not** need `smbus2`/the native driver to talk to the
> hardware — it only opens a TCP socket. `smbus2` is listed in the shared
> `requirements.txt` for convenience and is harmless on the laptop.

---

## 6. Running

**Step 1 — start the sensor server on the Pi:**

```bash
cd embedded_tof_sensor/src
source ../.venv/bin/activate
python sensor_server.py
# → Sensor server listening on port 9999 (all interfaces). Ctrl+C to stop.
```

Find the Pi's IP for the next step:

```bash
hostname -I
```

**Step 2 — start the GUI on the laptop**, passing the Pi's IP:

```powershell
.\.venv\Scripts\python.exe src\main.py 10.42.0.1
```

The window opens and auto-starts. Wave an object in front of the sensor — the
number and graph react in real time. Use **Stop/Start** to pause/resume.

---

## 7. Network Protocol

A deliberately minimal request/response protocol over a single TCP connection.

| Direction | Payload | Meaning |
|-----------|---------|---------|
| Laptop → Pi | any byte (e.g. `r`) | "give me a sample" |
| Pi → Laptop | `"<distance_mm>,<status>\n"` | the reading |
| Laptop → Pi | `"c<mode>,<timing_budget_us>\n"` | reconfigure the sensor |
| Pi → Laptop | `"ok\n"` | config applied |

Example exchange:

```
client: r              # request a sample
server: 412,0\n        # 412 mm, status OK
client: c1,33000\n     # switch to short range, 33 ms budget
server: ok\n
```

Distance mode and timing budget are chosen live from the **Range** and **Budget**
dropdowns in the GUI; the change is pushed to the Pi over this protocol and the
sensor is re-armed with the new settings.

### Status codes (`SensorReading.status`)

| Code | Meaning | GUI display |
|------|---------|-------------|
| `0` | OK — valid distance | green/red number (red < 300 mm) |
| `1` | Error (driver/socket failure) | `ERR` |
| `2` | Waiting — sensor not ready yet | `…` |
| `4` | No target in range | `NO TARGET` |

A reading is considered `valid` when `status == 0` and `0 < distance_mm < 6000`.

---

## 8. Configuration

Sensor defaults live in `VL53L3CXSensor.__init__` ([`src/sensor.py`](src/sensor.py)):

| Parameter | Default | Notes |
|-----------|---------|-------|
| `i2c_bus` | `1` | Pi GPIO I²C bus |
| `i2c_address` | `0x29` | VL53L3CX 7-bit address |
| `distance_mode` | `3` | 1 = short, 2 = medium, 3 = long |
| `timing_budget_us` | `50_000` | Higher = more accurate, lower rate |
| `stale_timeout_s` | `0.5` | Reuse last reading if newer than this while sensor is busy |

GUI constants live in `MainWindow` ([`src/gui.py`](src/gui.py)): `UPDATE_INTERVAL_MS`
(50 ms poll), `BUFFER_SIZE` (200 samples shown), `DISPLAY_MAX_MM` (2000 mm Y-axis).

---

## 9. Real-Time Considerations

The system intentionally runs on a **standard (non-PREEMPT_RT) kernel**. The
sensor caps out at ~30 Hz and the GUI tolerates 50–100 ms latency, so soft
real-time (Raspberry Pi OS `PREEMPT_DYNAMIC`) is sufficient. Full reasoning and
the decision matrix are in [`docs/real_time_decision.md`](docs/real_time_decision.md).

---

## 10. Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `i2cdetect` shows nothing at `0x29` | Check wiring/3V3 power; confirm I²C enabled and rebooted |
| GUI shows `ERR` immediately | Pi server not running, wrong IP, or firewall blocking port 9999 |
| `Could not find vl53l3cx_python.so` on the Pi | `pip install -r requirements-rpi.txt` inside the venv; needs `build-essential`, `python3-dev`, `git` |
| GUI window opens but values stay `…` | Sensor still warming up / not ranging; check server console for client connection |
| Connection refused | Server not started yet, or both devices not on the same network/link |

---

## 11. Team

| Role | Scope |
|------|-------|
| Hardware | Sensor wiring, I²C bus, power, PCB |
| Software | Linux/Pi setup, I²C driver integration, data pipeline, GUI |

---

## 12. Attribution

`vl53l3cx_driver.py` is vendored from
[FrgyCZ/VL53L3CX-python](https://github.com/FrgyCZ/VL53L3CX-python)
(MIT License — ST VL53LX bare driver bindings). The native shared library is
built during `pip install -r requirements-rpi.txt`.
