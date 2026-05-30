"""GPIO bench test — verify hardware in isolation (no sensor, no GUI).
Run on the Pi:  python src/gpio_bench.py
Walks each LED bar segment, beeps buzzer, blinks status LED, waits for button.
"""
from time import sleep
from gpiozero import LED, PWMOutputDevice, Button

LED_BAR_PINS = [5, 6, 13, 19, 26, 21, 20, 16, 12, 7]   # seg1 (near) .. seg10 (far)

leds = [LED(p) for p in LED_BAR_PINS]
buzzer = PWMOutputDevice(18, frequency=1500)
status = LED(22)
button = Button(27, pull_up=True)

print("1) LED bar: each segment seg1->seg10 (watch the order!)")
for i, led in enumerate(leds):
    print(f"   seg{i+1}  (GPIO{LED_BAR_PINS[i]})")
    led.on(); sleep(0.4); led.off()

print("2) Buzzer: 3 beeps")
for _ in range(3):
    buzzer.value = 0.5; sleep(0.2); buzzer.value = 0; sleep(0.2)

print("3) Status LED: 3 blinks")
for _ in range(3):
    status.on(); sleep(0.3); status.off(); sleep(0.3)

print("4) Button: press it within 10 s...")
print("   PRESSED" if button.wait_for_press(timeout=10) else "   no press detected")

print("Done. If anything misbehaved, the bug is hardware, not software.")
