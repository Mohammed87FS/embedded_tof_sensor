# Electronics Components — Embedded ToF Sensor Project

This folder contains photos of all hardware components used in the embedded Time-of-Flight (ToF) distance sensor project built around a Raspberry Pi 5.

---

## Components

### 1. Raspberry Pi 5 — in Heatsink Case with Dual Fans
**Images:** `raspberry_pi5_heatsink_case_dual_fans_01.jpg`, `raspberry_pi5_heatsink_case_dual_fans_02.jpg`, `raspberry_pi5_usb_ethernet_ports_side.jpg`, `raspberry_pi5_heatsink_case_fan_side.jpg`

The main compute board for this project. The unit is housed in a **Berrybase aluminium heatsink case** (part number `RPI5-ARC-FA`) which replaces the standard plastic enclosure with a solid heatsink body and two integrated 30mm cooling fans connected via a 4-pin PWM header.

**Key specs:**
- SoC: Broadcom BCM2712 — quad-core Arm Cortex-A76 @ 2.4 GHz
- RAM: 4 GB or 8 GB LPDDR4X
- GPIO: 40-pin standard header (3.3 V logic)
- Connectivity: Gigabit Ethernet (Trxcom transformer), 2× USB 3.0 (blue), 2× USB 2.0, 2× micro-HDMI, USB-C power input
- I²C, SPI, UART exposed on GPIO header — used here for sensor communication

The heatsink case allows passive + active cooling in a compact form, suitable for continuous operation without throttling.

---

### 2. Raspberry Pi 27 W USB-C Power Supply
**Image:** `raspberry_pi_27w_usbc_power_supply.jpg`

Official Raspberry Pi USB-C power adapter (EU plug, white), model **P4123**.

**Specs:**
- Input: AC 100–240 V, 50/60 Hz, 0.8 A
- Output: 5.1 V / 5.0 A (25.5 W), 9.0 V / 3.0 A (27 W), 12.0 V / 2.25 A (27 W), 15.0 V / 1.8 A (27 W)
- Cable: 1.2 m captive 17AWG USB-C
- Protocol: USB Power Delivery (USB-PD)

The Raspberry Pi 5 requires USB-PD negotiation to unlock its full performance; a standard 5 V charger will work but limits the board to lower power states. This official supply guarantees stable 5.1 V at up to 5 A.

---

### 3. Pololu VL53L3CX Time-of-Flight Sensor Breakout (Item #3416)
**Images:** `vl53l3cx_tof_sensor_pololu_kit_01.jpg`, `vl53l3cx_tof_sensor_pololu_kit_02.jpg`, `vl53l3cx_tof_sensor_breakout_board_closeup.jpg`

The **core sensor** of this project. The Pololu carrier board (item #3416) hosts an **STMicroelectronics VL53L3CX** multi-target Time-of-Flight ranging sensor.

**How ToF works:** An infrared VCSEL (Vertical-Cavity Surface-Emitting Laser) emits short pulses of 940 nm light. The sensor measures the round-trip travel time to calculate distance with high accuracy, independent of target colour or reflectivity.

**VL53L3CX specs:**
- Measurement range: up to 300 cm (3 m)
- Multi-target detection: can report distance to up to 2 objects simultaneously in the same field of view
- Field of view: 25° (diagonal)
- Interface: I²C (up to 400 kHz), address 0x52 (default)
- Operating voltage: 2.6 V – 3.5 V (the Pololu board includes a 3.3 V voltage regulator, making it safe to use with 3.3 V and 5 V systems)
- Control pins: XSHUT (shutdown / address change), GPIO1 (interrupt output)

The kit bag also contains:
- **1× Blue LED** — for status indication in the circuit
- **1× Signal diode** (1N4148 or similar) — for logic-level protection
- **1× 6-pin male header** — for breadboard mounting of the breakout board
- **1× Tactile push button** (SMD-style, black) — for user input / reset

---

### 4. Breadboard with Raspberry Pi GPIO Extension Board
**Image:** `breadboard_with_rpi_gpio_extension_board.jpg`

A **full-size 830-tie-point breadboard** with a **Raspberry Pi GPIO Extension Board** plugged into the top centre. The extension board is a T-shaped breakout that spreads all 40 GPIO pins into labelled breadboard-friendly rows, with pin names (SDA1, SCL1, GPIO4, GND, TXD0, RXD0, etc.) silkscreened in white on a blue PCB.

This is the central prototyping platform where the sensor, LED bar, button, and supporting passives are wired together without soldering.

---

### 5. 40-Pin GPIO Ribbon Cable (2×20 IDC)
**Images:** `gpio_ribbon_cable_40pin_idc_01.jpg`, `gpio_ribbon_cable_40pin_idc_02.jpg`

A **40-conductor flat ribbon cable** (~20 cm) with two IDC (Insulation-Displacement Connector) plugs — one 2×20 female socket on each end. Used to connect the Raspberry Pi 5's 40-pin GPIO header to the breadboard extension board.

Pin 1 is identified by the red/pink stripe on one edge of the cable. The cable carries all power rails (3.3 V, 5 V, GND) and GPIO signals between the Pi and the breadboard.

---

### 6. 40-Pin Male Pin Header — 2×20 (Straight)
**Image:** `40pin_male_pin_header_2x20_side.jpg`

A standard **2-row × 20-pin (40-pin total) straight male pin header**, 2.54 mm pitch. Used to solder onto the breadboard extension board or a custom PCB to provide a GPIO connector. Gold-plated pins are visible in the side-on photo.

---

### 7. 40-Pin Female Pin Header — 2×20 (Socket)
**Images:** `40pin_female_pin_header_2x20_socket.jpg`, `40pin_female_pin_header_stacked_side.jpg`, `40pin_female_pin_header_stacked_front.jpg`

A **2-row × 20-pin (40-pin total) female socket header**, 2.54 mm pitch, ~8.5 mm height. Used as the mating connector for the ribbon cable or for stacking HATs. The square socket openings and gold-plated internal contacts are visible.

---

### 8. IDC Box Connector — Male, 2×10 (20-pin)
**Image:** `idc_box_connector_male_2x10.jpg`

A **20-pin male IDC box header** (2×10, 2.54 mm pitch) with a polarising key slot and a transparent/clear housing. Designed for press-fit onto a ribbon cable. Used in conjunction with the ribbon cable to create reliable, polarised GPIO connections.

---

### 9. 10-Segment LED Bar Graph Display
**Image:** `10segment_led_bar_graph_display.jpg`

A **10-segment LED bar graph** module — a row of 10 individual LEDs in a single rectangular package, typically used as a level meter or progress indicator. Each segment has its own anode and cathode pin (20 pins total). In this project it is used as a visual distance indicator, lighting more segments as an object moves closer to the ToF sensor.

**Typical specs:**
- Forward voltage per segment: ~2.0 V (red) or ~3.0 V (green/yellow)
- Forward current: 10–20 mA per segment
- Driven via current-limiting resistors from GPIO pins

---

### 10. Passive Buzzer
**Images:** `buzzer_passive_side_view.jpg`, `buzzer_passive_bottom_label.jpg`, `buzzer_passive_top_pins.jpg`

A **passive piezo buzzer** (cylindrical, ~12 mm diameter, black). The label on the base reads "HYDZ — Remove seal after washing", which is a manufacturing seal present on passive buzzers. Unlike active buzzers (which buzz at a fixed frequency when powered), a passive buzzer requires an oscillating signal (PWM) to produce sound, allowing the firmware to control pitch.

Used in this project for distance alerts — a higher-frequency tone when an object is very close.

**Typical specs:**
- Operating voltage: 3–5 V
- Frequency range: ~500 Hz – 4 kHz
- Driven via GPIO PWM or software bit-banging

---

### 11. Jumper Wire Kit (Arduino/RPi Basic Kit)
**Images:** `jumper_wire_kit_box_closed.jpg`, `jumper_wire_kit_box_open_contents.jpg`

A plastic box containing a **Basic RPi jumper wire assortment**, including:
- Male-to-male and male-to-female dupont jumper wires in multiple colours and lengths
- Through-hole resistors (various values, colour-banded)
- Additional LEDs and small passive components

Used for all wiring on the breadboard between the extension board, sensor, LED bar, buzzer, and button.

---

### 12. Raspberry Pi Micro-HDMI Cable
**Image:** `raspberry_pi_micro_hdmi_cable.jpg`

Official Raspberry Pi **micro-HDMI to HDMI** cable (white, ~1 m). The Raspberry Pi 5 uses micro-HDMI (not full-size HDMI) for its two display outputs. This cable is used to connect the Pi to an external monitor or TV for display output during development and debugging.

---

## Wiring Summary

| Component | Pi GPIO Pins |
|---|---|
| VL53L3CX (I²C) | SDA1 (GPIO 2), SCL1 (GPIO 3), 3.3 V, GND |
| VL53L3CX XSHUT | GPIO 4 |
| VL53L3CX GPIO1 (interrupt) | GPIO 17 |
| LED Bar Graph (10 segments) | GPIO 5, 6, 13, 19, 26, 21, 20, 16, 12, 7 (via 330 Ω resistors) |
| Passive Buzzer | GPIO 18 (PWM0) |
| Tactile Button | GPIO 27 (with pull-up) |
| Status LED (blue) | GPIO 22 (via 330 Ω resistor) |

---

## Notes

- All I²C components share the same SDA/SCL bus; ensure each has a unique I²C address or use XSHUT to sequence initialisation.
- Enable I²C on the Pi with `sudo raspi-config` → Interface Options → I²C → Enable.
- The Pololu VL53L3CX board's onboard 3.3 V regulator means it is safe to connect VIN directly to the Pi's 3.3 V rail, avoiding the need for a separate level shifter.
- The LED bar graph and buzzer are powered directly from GPIO pins — keep total current draw per GPIO pin below 16 mA (absolute max 50 mA) and total GPIO bank current below 50 mA.
