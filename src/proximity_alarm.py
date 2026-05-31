"""
Proximity alarm — VL53L3CX ToF sensor -> 3 LEDs (green/yellow/red) + buzzer.
Closer object = more LEDs lit + faster buzzer; danger range = all LEDs + solid tone.

Run on the Pi (from the src/ folder, venv active):
    python proximity_alarm.py
Ctrl+C to stop (turns everything off cleanly).
"""

import time
from gpiozero import LED, PWMOutputDevice
from sensor import VL53L3CXSensor

# --- Wiring (BCM GPIO numbers) ---
GREEN = LED(17)                                  # physical pin 11
YELLOW = LED(23)                                  # physical pin 16
RED = LED(21)                                      # physical pin 40
buzzer = PWMOutputDevice(18, frequency=1500)     # physical pin 12

# --- Distance thresholds in mm (tune for your demo) ---
NEAR = 300      # closer than this  -> DANGER  (all 3 LEDs + solid tone)
MID = 600       # closer than this  -> CAUTION (green+yellow + beeping)
# farther than MID                  -> SAFE    (green only, silent)


def all_off():
    GREEN.off()
    YELLOW.off()
    RED.off()
    buzzer.value = 0


def main():
    sensor = VL53L3CXSensor()
    sensor.start()
    print("Proximity alarm running - wave your hand at the sensor. Ctrl+C to stop.")

    beep_on = False
    next_beep = 0.0
    try:
        while True:
            r = sensor.read()
            now = time.time()
            d = r.distance_mm

            if r.status != 0 or d <= 0:
                all_off()                         # no target / invalid
                label = "----"
            elif d >= MID:
                GREEN.on(); YELLOW.off(); RED.off()
                buzzer.value = 0
                label = "SAFE"
            elif d >= NEAR:
                GREEN.on(); YELLOW.on(); RED.off()
                if now >= next_beep:              # medium beep
                    beep_on = not beep_on
                    buzzer.value = 0.5 if beep_on else 0
                    next_beep = now + (0.1 if beep_on else 0.3)
                label = "CAUTION"
            else:
                GREEN.on(); YELLOW.on(); RED.on()
                buzzer.value = 0.5                # solid tone
                label = "DANGER"

            print(f"{d:5d} mm   {label}    ", end="\r")
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        all_off()
        sensor.stop()
        print("\nStopped.")


if __name__ == "__main__":
    main()
