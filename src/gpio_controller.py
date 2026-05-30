"""
GPIO hardware layer — 10-seg LED bar, passive buzzer, button, status LED.
Parking-sensor logic: closer object => more LEDs lit + faster beep.

Runs on Raspberry Pi via gpiozero. On any non-Pi machine (no gpiozero / no pin
factory) it degrades to a silent no-op so the GUI still runs for offline dev.
"""

import time

try:
    from gpiozero import LED, PWMOutputDevice, Button
    _GPIO_OK = True
except Exception:                      # gpiozero missing OR not on a Pi
    _GPIO_OK = False

# BCM pin map (matches electronics_imgs/README.md wiring table)
LED_BAR_PINS = [5, 6, 13, 19, 26, 21, 20, 16, 12, 7]  # seg1 (near) .. seg10 (far)
BUZZER_PIN = 18      # hardware PWM0
BUTTON_PIN = 27
STATUS_PIN = 22

MAX_LED_MM = 3000    # >= this distance => 0 LEDs lit
BUZZER_TONE_HZ = 1500


class GPIOController:
    def __init__(self, enabled: bool = True):
        self.active = enabled and _GPIO_OK
        self._button_event = False
        self._beep_on = False
        self._next_beep = 0.0
        self._status_on = False
        self._next_status = 0.0

        if not self.active:
            return

        self._leds = [LED(p) for p in LED_BAR_PINS]
        self._buzzer = PWMOutputDevice(BUZZER_PIN, frequency=BUZZER_TONE_HZ)
        self._status = LED(STATUS_PIN)
        self._button = Button(BUTTON_PIN, pull_up=True, bounce_time=0.05)
        self._button.when_pressed = self._on_button

    # --- button (thread-safe: GUI polls this, no cross-thread Qt calls) ---
    def _on_button(self):
        self._button_event = True

    def take_button_event(self) -> bool:
        if self._button_event:
            self._button_event = False
            return True
        return False

    # --- main update, call once per GUI tick ---
    def update(self, distance_mm: int, status: int) -> None:
        if not self.active:
            return
        now = time.time()
        valid = status == 0 and distance_mm > 0

        # LED bar: proximity (closer => more lit)
        if valid:
            frac = max(0.0, min(1.0, (MAX_LED_MM - distance_mm) / MAX_LED_MM))
            lit = round(frac * len(self._leds))
        else:
            lit = 0
        for i, led in enumerate(self._leds):
            led.on() if i < lit else led.off()

        # Buzzer: silent >2m, slow beep 1-2m, fast beep 0.5-1m, solid <0.5m
        if not valid or distance_mm > 2000:
            self._buzzer.value = 0
            self._beep_on = False
        elif distance_mm <= 500:
            self._buzzer.value = 0.5            # continuous tone
        else:
            period = 0.6 if distance_mm > 1000 else 0.25
            if now >= self._next_beep:
                self._beep_on = not self._beep_on
                self._buzzer.value = 0.5 if self._beep_on else 0
                self._next_beep = now + (0.1 if self._beep_on else period)

        # Status LED: solid=ok, slow blink=no target/waiting, fast blink=error
        if status == 0:
            self._status.on()
        else:
            period = 0.5 if status in (2, 4) else 0.1
            if now >= self._next_status:
                self._status_on = not self._status_on
                self._status.on() if self._status_on else self._status.off()
                self._next_status = now + period

    def all_off(self) -> None:
        if not self.active:
            return
        for led in self._leds:
            led.off()
        self._buzzer.value = 0
        self._status.off()

    def close(self) -> None:
        if not self.active:
            return
        self.all_off()
        for led in self._leds:
            led.close()
        self._buzzer.close()
        self._status.close()
        self._button.close()
        self.active = False
