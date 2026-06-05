# VL53L3CX Time-of-Flight Distance Monitor — Full Technical Documentation

**FH Wiener Neustadt — Embedded Systems**

A real-time distance-measurement system built around an STMicroelectronics **VL53L3CX Time-of-Flight (ToF)** sensor on a **Raspberry Pi 5**, with a **PyQt6** graphical interface that visualises the distance as a live number, a time-series graph, and a sonar/radar display. The sensor runs on the Pi; the GUI runs on a laptop; the two communicate over a TCP network link (Wi-Fi hotspot, Ethernet, or USB gadget).

---

## 1. What the system does

1. The VL53L3CX fires invisible **940 nm infrared laser pulses** and measures the time they take to bounce back from an object. Time × speed-of-light ÷ 2 = distance. This happens inside the sensor chip; it reports a distance in millimetres over the **I²C** bus.
2. A Python program on the Pi (`sensor_server.py`) reads that distance ~20 times per second and **streams it over the network**.
3. A Python program on a laptop (`main.py` → `gui.py`) **receives** each reading and draws it in real time.

The key architectural decision: **the heavy/graphical part (GUI) runs on the laptop, the hardware part (sensor) runs on the Pi**, and they are decoupled by a tiny network protocol. This means the GUI is smooth (rendered locally) and the transport is interchangeable.

---

## 2. System architecture

```
   ┌─────────────────────── Raspberry Pi 5 ───────────────────────┐
   │                                                              │
   │   VL53L3CX ──I²C──► vl53l3cx_driver.py ──► VL53L3CXSensor     │
   │   (hardware)        (ctypes + smbus2)      (sensor.py)        │
   │                                               │              │
   │                                        sensor_server.py      │
   │                                        (TCP server :9999)     │
   └───────────────────────────────┬──────────────────────────────┘
                                    │  TCP/IP over Wi-Fi hotspot
                                    │  "distance,status\n"
   ┌────────────────────────────────▼─────────────────────────────┐
   │                          Laptop (Windows)                     │
   │                                                              │
   │   NetworkSensor ──► MainWindow (gui.py) ──► SonarWidget        │
   │   (sensor.py)       QTimer @ 20 Hz          pyqtgraph plot     │
   └──────────────────────────────────────────────────────────────┘
```

The two sides share **one common interface** (`BaseSensor`) and **one data object** (`SensorReading`). That is what makes the system clean: the GUI never knows whether the data came from real hardware, a network socket, or a fake generator.

---

## 3. Hardware

| Component | Role |
|-----------|------|
| Raspberry Pi 5 (BCM2712, quad Cortex-A76) | Runs Linux, reads the sensor over I²C, hosts the server |
| Pololu VL53L3CX breakout (#3416) | The ToF sensor + onboard 3.3 V regulator |
| Official 27 W USB-C PSU | Powers the Pi (the Pi 5 needs more current than a laptop USB port can give) |
| Breadboard + 40-pin GPIO ribbon + T-extension board | Brings the Pi's GPIO header to the breadboard |

### Sensor wiring (I²C)
| Pololu pin | Pi pin | Meaning |
|-----------|--------|---------|
| VIN | 3.3 V (pin 1) | Power (regulated on-board) |
| GND | GND (pin 6) | Ground |
| SDA | GPIO2 / SDA1 (pin 3) | I²C data |
| SCL | GPIO3 / SCL1 (pin 5) | I²C clock |

The sensor appears on I²C bus 1 at **7-bit address `0x29`** (verifiable with `i2cdetect -y 1`).

---

## 4. End-to-end data flow (one reading)

1. **GUI tick** — a `QTimer` on the laptop fires every 50 ms and calls `MainWindow._tick()`.
2. `_tick()` calls `self._sensor.read()`. Here `self._sensor` is a `NetworkSensor`.
3. `NetworkSensor.read()` sends **one byte** (`b"r"`) to the Pi and waits for a line.
4. On the Pi, `sensor_server.py` receives the byte, calls `VL53L3CXSensor.read()`.
5. `VL53L3CXSensor.read()` asks the native driver "is a measurement ready?", gets the distance in mm, wraps it in a `SensorReading`, and the server sends back the text line `"485,0\n"` (distance, status).
6. `NetworkSensor.read()` parses that line back into a `SensorReading` object.
7. `_tick()` updates: the big number label, the statistics, the time-series graph, and the sonar widget.

This **request → response** design (the client asks for each sample) keeps the two sides in lockstep, so no stale data piles up in network buffers.

---

## 5. File-by-file deep dive

### 5.1 `sensor.py` — the heart of the abstraction

This file defines the **data model** and **four sensor implementations** that all look identical to the rest of the program.

#### `SensorReading` — the data object
```python
class SensorReading:
    __slots__ = ("distance_mm", "signal_rate", "ambient_rate", "status", "timestamp")
    def __init__(self, distance_mm, signal_rate=0.0, ambient_rate=0.0, status=0):
        ...
        self.timestamp = time.time()

    @property
    def valid(self) -> bool:
        return self.status == 0 and 0 < self.distance_mm < 6000
```
- A single immutable-ish bundle carrying one measurement.
- `__slots__` is a memory/speed optimisation: it tells Python not to give each object a flexible `__dict__`, which matters because thousands of these are created per minute.
- `status` is an integer code: **0 = OK, 1 = error, 2 = waiting, 3 = invalid sample, 4 = no target**. This single number lets the GUI decide what colour/text to show.
- `valid` is a computed property — the GUI uses it to decide whether a reading is trustworthy (status OK and within physical range).

#### `BaseSensor` — the interface (abstraction)
```python
class BaseSensor(ABC):
    @abstractmethod
    def start(self) -> None: ...
    @abstractmethod
    def read(self) -> SensorReading: ...
    @abstractmethod
    def stop(self) -> None: ...
```
- `ABC` = Abstract Base Class. It defines a **contract**: every sensor must implement `start()`, `read()`, `stop()`.
- This is the single most important design idea in the project. Because the GUI only ever talks to a `BaseSensor`, you can swap the real sensor for a fake one or a network one **without changing a single line of GUI code** (this is *polymorphism*).

#### `DummySensor` — fake data for development
```python
def read(self) -> SensorReading:
    base = 500 + 400 * math.sin(self._t * 0.5)   # smooth back-and-forth
    noise = random.gauss(0, 15)                  # realistic jitter
    distance = max(10, int(base + noise))
    self._t += 0.1
    return SensorReading(distance_mm=distance, ...)
```
- Generates a sine-wave distance with Gaussian noise, simulating an object moving toward/away.
- Lets the entire GUI be developed and tested **on a laptop with no hardware at all**.

#### `VL53L3CXSensor` — the real hardware driver wrapper
```python
def start(self):
    from vl53l3cx_driver import VL53L3CX as _VL53
    self._tof = _VL53(i2c_bus=self._i2c_bus, i2c_address=self._i2c_address)
    self._tof.open(reset=False)
    self._tof.set_distance_mode(self._distance_mode)   # 3 = long range (~up to several m)
    self._tof.set_timing_budget(self._timing_budget_us) # 50 ms per measurement
    self._tof.start_ranging()
```
```python
def read(self):
    if not self._tof.is_ranging_ready():
        # return the last reading only if it's still fresh (< 0.5 s old)
        if self._last and (time.time() - self._last.timestamp) < self._stale_timeout_s:
            return self._last
        return SensorReading(distance_mm=0, status=2)   # "waiting"
    raw = int(self._tof.get_distance())
    if raw < 0:                       return SensorReading(0, status=1)  # error
    if raw == 0 or raw >= 8000 or raw == 8191:
                                      return SensorReading(0, status=4)  # no target
    return SensorReading(distance_mm=raw, status=0)                      # good reading
```
Key engineering details:
- The sensor measures asynchronously. `is_ranging_ready()` polls whether a fresh sample exists; if not, we **reuse the last reading but only if it is younger than 0.5 s** (`stale_timeout_s`). This prevents the GUI freezing on an old value if the sensor hangs.
- ST's driver uses **sentinel values** (`8191`, `≥8000`) to mean "no target / out of range". We translate those into `status=4` so the GUI can show "NO TARGET" instead of a nonsense distance.
- The import of the native driver is done **inside** `start()` (not at the top of the file). That way the laptop — which has no I²C driver — can still import `sensor.py` for the `NetworkSensor` and `DummySensor` without crashing.

#### `NetworkSensor` — the laptop's window into the Pi
```python
def start(self):
    self._sock = socket.create_connection((self._host, self._port), timeout=self._timeout)

def read(self):
    self._sock.sendall(b"r")                  # ask for one sample
    while b"\n" not in self._buf:             # read until a full line arrives
        data = self._sock.recv(64)
        if not data: return SensorReading(0, status=1)
        self._buf += data
    line, self._buf = self._buf.split(b"\n", 1)   # keep any leftover bytes
    dist_s, status_s = line.decode().strip().split(",")
    return SensorReading(distance_mm=int(dist_s), status=int(status_s))
```
- This is the genius of the architecture: `NetworkSensor` **is a `BaseSensor`**, so to the GUI it is indistinguishable from a real sensor — but under the hood it fetches data over TCP.
- It does proper **stream framing**: TCP is a byte stream with no message boundaries, so we buffer bytes (`self._buf`) and split on the newline `\n` that the server appends to each message. Leftover bytes are kept for the next read.
- All network errors are caught and turned into `status=1` (error), so a dropped connection shows as "ERR" in the GUI instead of crashing it.

### 5.2 `vl53l3cx_driver.py` — talking to the chip (vendored)

This is a thin Python wrapper (from the open-source FrgyCZ project, MIT-licensed) around ST's official **C** driver for the sensor. Two techniques are at work:

1. **`ctypes`** loads a compiled C library (`vl53l3cx_python*.so`) and calls its functions (`startRanging`, `getDistance`, …) directly from Python.
2. **`smbus2`** performs the actual I²C reads/writes. The C library doesn't know how to talk to Linux I²C, so Python supplies two callback functions (`_i2c_read`, `_i2c_write`) that the C code calls whenever it needs to touch the bus:
```python
def _i2c_read(address, reg, data_p, length):
    msg_w = i2c_msg.write(address, [reg >> 8, reg & 0xff])  # send register address
    msg_r = i2c_msg.read(address, length)                   # read N bytes back
    self._i2c.i2c_rdwr(msg_w, msg_r)
```
This "C library + Python I²C callbacks" bridge is why the `.so` has to be **compiled on the Pi** (we used a relaxed compiler flag to build it on the newer OS).

### 5.3 `sensor_server.py` — the Pi-side network server

```python
sensor = VL53L3CXSensor(); sensor.start()
srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("0.0.0.0", 9999)); srv.listen(1)
while True:
    conn, addr = srv.accept()
    while True:
        req = conn.recv(16)
        if not req: break                 # client disconnected
        r = sensor.read()
        conn.sendall(f"{r.distance_mm},{r.status}\n".encode())
```
- A minimal **TCP server**. `0.0.0.0` means "listen on every network interface", so the same server works whether the client connects over Wi-Fi, Ethernet, or USB.
- `SO_REUSEADDR` lets the server restart immediately without "address already in use" errors.
- **Request/response loop**: it only sends a reading when the client asks (`recv` returns a byte). This naturally throttles the stream to the GUI's pace and avoids buffer build-up/lag.
- The text protocol (`"485,0\n"`) is deliberately trivial — easy to debug (you can literally read it), language-agnostic, and tiny.

### 5.4 `main.py` — entry point and mode selection

`argparse` defines the command-line options and picks **which `BaseSensor` to build**:
```python
if args.network:        sensor = NetworkSensor(host=args.network)   # laptop → Pi
elif args.real_sensor:  sensor = VL53L3CXSensor(...)                # GUI on the Pi
else:                   sensor = DummySensor()                      # dev mode
window = MainWindow(sensor, auto_start=args.real_sensor or bool(args.network))
```
This is the one place that decides the data source. Everything downstream is identical regardless of choice — the payoff of the `BaseSensor` abstraction.

### 5.5 `gui.py` — the main window and the update loop

`MainWindow` (a `QMainWindow`) builds the interface and drives everything from a timer.

#### The timer = the heartbeat
```python
self._timer = QTimer(self)
self._timer.setInterval(50)          # 50 ms ≈ 20 Hz
self._timer.timeout.connect(self._tick)
```
PyQt is **event-driven**: instead of a `while True` loop (which would freeze the UI), a `QTimer` fires `_tick()` 20 times a second between repaints, keeping the interface responsive.

#### `_tick()` — what happens every 50 ms
```python
reading = self._sensor.read()
self._data_buffer[self._buf_idx % self.BUFFER_SIZE] = reading.distance_mm
self._buf_idx += 1
```
- **Ring buffer**: a fixed NumPy array of 200 slots stores the most recent samples. `% BUFFER_SIZE` wraps the write index around, so memory never grows — the newest sample overwrites the oldest.

```python
if reading.valid:
    color = "#00cc44" if reading.distance_mm > 300 else "#ff4444"   # green / red
elif reading.status == 2:  text = "…"          # waiting
elif reading.status == 4:  text = "NO TARGET"
else:                      text = "ERR"
```
- The status code drives both the **text** and the **colour** of the big distance label.

```python
if self._buf_idx >= self.BUFFER_SIZE:
    ordered = np.roll(self._data_buffer, -(self._buf_idx % self.BUFFER_SIZE))
else:
    ordered = self._data_buffer[:filled]
```
- A subtle but important fix: a raw ring buffer is *out of order* in memory (the write head is somewhere in the middle). `np.roll` rotates it back into true oldest→newest order before plotting, so the graph scrolls smoothly instead of jumping where the write head wraps.

```python
valid_data = ordered[ordered > 0]
self._min_label.setText(f"Min: {int(valid_data.min())} mm")  # + Max, Avg
```
- Statistics are computed with NumPy over only the non-zero (valid) samples.

#### The adjustable range control
```python
self._range_spin = QSpinBox()
self._range_spin.setRange(250, self.SENSOR_MAX_MM)   # capped at 5000 mm (sensor limit)
self._range_spin.setValue(self.DISPLAY_MAX_MM)       # default 700 mm
self._range_spin.valueChanged.connect(self._on_range_changed)

def _on_range_changed(self, value):
    self._plot_widget.setYRange(0, value)   # rescale the graph
    self._sonar.set_max_range(value)        # rescale the sonar
```
- A spin box lets the user change the display range live. It is **hard-capped at the sensor's real maximum** so you can't zoom out past what the hardware can measure.

### 5.6 `sonar_widget.py` — the custom radar display

This is a hand-drawn widget. Instead of using a pre-made chart, it overrides `paintEvent()` and draws everything with `QPainter` (Qt's 2D drawing API). Every call to `update_distance()` advances a sweep angle and triggers a repaint.

Key pieces of the paint routine:
```python
# polar → screen: a distance becomes a radius from the centre
blip_r = (self._distance_mm / self._max_range) * radius
bx = cx + blip_r * math.cos(angle_rad)
by = cy - blip_r * math.sin(angle_rad)
```
- The measured distance is mapped onto a **radius** (near = centre, far = edge), then converted from polar (angle, radius) to screen (x, y) coordinates with sine/cosine.

```python
glow = QRadialGradient(QPointF(bx, by), 12)        # green radial glow for the "blip"
for i in range(1, 20):                             # fading trail behind the sweep
    alpha = max(5, 120 - i * 6)
```
- A rotating **sweep line**, a fading **trail** behind it, a glowing **blip** at the current distance, and a `deque` of the **last 60 readings** drawn as faint dots — all the classic radar aesthetics, drawn by hand each frame.
- `set_max_range()` lets the same widget rescale when the user changes the range spin box.

---

## 6. Programming concepts used (for the report)

| Concept | Where | Why it matters |
|---------|-------|----------------|
| **Abstraction / interface** (`ABC`) | `BaseSensor` | One contract, many implementations |
| **Polymorphism** | GUI uses any `BaseSensor` | Swap dummy/real/network with zero GUI changes |
| **Dependency injection** | `MainWindow(sensor)` | The sensor is passed in, not hard-coded |
| **Event-driven programming** | `QTimer` → `_tick` | Keeps the UI responsive (no blocking loop) |
| **Ring buffer** | `_data_buffer` + `np.roll` | Fixed memory, smooth scrolling history |
| **Client–server / request-response** | `sensor_server` ↔ `NetworkSensor` | Decouples hardware from display, no buffer lag |
| **Stream framing** | newline-delimited messages | Correctly splits a TCP byte-stream into messages |
| **Foreign function interface** | `ctypes` in the driver | Calls ST's C library from Python |
| **Hardware callbacks** | I²C read/write closures | Bridges the C driver to Linux I²C via `smbus2` |
| **Custom rendering** | `paintEvent` + `QPainter` | The bespoke sonar visualisation |

---

## 7. Deployment & networking (how it runs at the demo)

The sensor is on the Pi; the GUI is on the laptop. They are joined by a private network with **no router or internet required**:

- The Pi runs a **Wi-Fi hotspot** (`nmcli device wifi hotspot ssid ToFSensor …`). The Pi is `10.42.0.1`; the laptop joins that Wi-Fi and is given an address automatically.
- The server is registered as a **systemd service** (`tof-server.service`) so it **starts automatically on boot** — no manual SSH needed at the demo.

Demo flow:
1. Power the Pi → it auto-creates the `ToFSensor` Wi-Fi and auto-starts the server.
2. Laptop joins the `ToFSensor` Wi-Fi.
3. `python src/main.py --network 10.42.0.1` → GUI opens with live data.

*(The same code also works over Ethernet or a USB-C gadget link — only the IP changes — because the server listens on all interfaces.)*

---

## 8. How to run (all modes)

| Command | Where | Mode |
|---------|-------|------|
| `python src/main.py` | Laptop | Dummy data (no hardware) |
| `python src/main.py --real-sensor` | Pi (with a screen) | Real sensor, GUI on the Pi |
| `python src/sensor_server.py` | Pi | Stream sensor over the network |
| `python src/main.py --network 10.42.0.1` | Laptop | GUI on laptop, live data from the Pi |

---

## 9. Why the design is good (summary)

- **Separation of concerns**: hardware (Pi), transport (TCP), and presentation (GUI) are independent layers.
- **Testability**: the whole GUI runs on a laptop with `DummySensor`, no hardware needed.
- **Portability of transport**: Wi-Fi, Ethernet, or USB all work with the identical code because of the `0.0.0.0` server and the `BaseSensor` abstraction.
- **Robustness**: every failure mode (no target, sensor stall, dropped network) maps to a clean status code and a clear on-screen state, never a crash.
</content>
