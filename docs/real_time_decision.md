# Real-Time Entscheidung

## Fragestellung
Benötigt das System einen Echtzeit-Kernel (PREEMPT_RT)?

## Entscheidung: Nein

## Begründung

| Kriterium | Unser System | RT erforderlich ab |
|-----------|-------------|-------------------|
| Sensor-Abtastrate | max. 30 Hz (33 ms) | < 1 ms Zykluszeit |
| GUI-Latenz | 50–100 ms akzeptabel | Nicht relevant für RT |
| Regelung/Aktorik | Keine | Motorsteuerung, CNC |
| Datenverlust-Toleranz | Einzelne Drops unkritisch | Safety-critical Systems |

Der VL53L3CX liefert Messdaten mit konfigurierbarer Rate (typisch 10–30 Hz).
Die Latenzanforderung der GUI-Anzeige liegt im Bereich von 50–100 ms.
Standard-Linux (PREEMPT_DYNAMIC, Raspberry Pi OS Bookworm) erfüllt diese
Anforderung ohne relevante Jitter-Probleme.

Ein PREEMPT_RT-Kernel wäre nur bei harten Echtzeit-Anforderungen im
Sub-Millisekunden-Bereich erforderlich (z.B. Closed-Loop-Motorsteuerung,
Safety-Interlock-Systeme).

## Referenzen
- VL53L3CX Datasheet: max ranging frequency 30 Hz
- Raspberry Pi OS Kernel: PREEMPT_DYNAMIC (soft real-time sufficient)
