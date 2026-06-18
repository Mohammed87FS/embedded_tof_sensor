const pptxgen = require("C:/Users/moham/AppData/Roaming/npm/node_modules/pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";          // 13.33 x 7.5 in
pres.author = "Mohammed Amaar";
pres.title = "VL53L3CX ToF Distanzmessung";

const W = 13.33, H = 7.5;

// ---- palette (matches the green-on-dark radar GUI) ----
const DARK = "0B1410", PANEL = "13241C", PANEL2 = "0F1A14";
const GREEN = "00C853", GREENSOFT = "00cc44";
const LIGHT = "FFFFFF", INK = "1E293B", MUTED = "64748B", LINE = "E2E8F0";
const DTXT = "E6F0EA";
const HEAD = "Trebuchet MS", BODY = "Calibri", MONO = "Consolas";

const shadow = () => ({ type: "outer", color: "000000", blur: 7, offset: 3, angle: 135, opacity: 0.12 });

function footer(slide, n, dark) {
  slide.addText("VL53L3CX ToF · FH Wiener Neustadt", {
    x: 0.6, y: H - 0.45, w: 8, h: 0.3, fontFace: BODY, fontSize: 9,
    color: dark ? "5C7268" : MUTED, align: "left", margin: 0,
  });
  slide.addText(String(n), {
    x: W - 1.1, y: H - 0.45, w: 0.5, h: 0.3, fontFace: BODY, fontSize: 9,
    color: dark ? "5C7268" : MUTED, align: "right", margin: 0,
  });
}

function sectionLabel(slide, txt) {
  slide.addText(txt.toUpperCase(), {
    x: 0.6, y: 0.55, w: 10, h: 0.35, fontFace: MONO, fontSize: 12,
    color: GREENSOFT, charSpacing: 3, bold: true, margin: 0,
  });
}
function title(slide, txt) {
  slide.addText(txt, {
    x: 0.6, y: 0.92, w: 12, h: 0.9, fontFace: HEAD, fontSize: 32,
    color: INK, bold: true, margin: 0,
  });
}

// draw a sonar/radar motif centered at (cx,cy)
function sonar(slide, cx, cy, rMax, blipAngleDeg, blipFrac) {
  const rings = 5;
  for (let i = 1; i <= rings; i++) {
    const r = rMax * i / rings;
    slide.addShape(pres.shapes.OVAL, {
      x: cx - r, y: cy - r, w: 2 * r, h: 2 * r,
      fill: { color: GREEN, transparency: 100 },
      line: { color: GREEN, width: 1, transparency: 35 },
    });
  }
  // crosshairs
  slide.addShape(pres.shapes.LINE, { x: cx - rMax, y: cy, w: 2 * rMax, h: 0, line: { color: GREEN, width: 0.75, transparency: 55 } });
  slide.addShape(pres.shapes.LINE, { x: cx, y: cy - rMax, w: 0, h: 2 * rMax, line: { color: GREEN, width: 0.75, transparency: 55 } });
  // sweep line
  const a = blipAngleDeg * Math.PI / 180;
  slide.addShape(pres.shapes.LINE, {
    x: cx, y: cy, w: rMax * Math.cos(a), h: -rMax * Math.sin(a),
    line: { color: GREEN, width: 2, transparency: 10 },
  });
  // center dot
  slide.addShape(pres.shapes.OVAL, { x: cx - 0.06, y: cy - 0.06, w: 0.12, h: 0.12, fill: { color: GREEN } });
  // blip
  const br = rMax * blipFrac;
  const bx = cx + br * Math.cos(a), by = cy - br * Math.sin(a);
  slide.addShape(pres.shapes.OVAL, { x: bx - 0.11, y: by - 0.11, w: 0.22, h: 0.22, fill: { color: GREEN } });
}

// =====================================================================
// SLIDE 1 — Titel (dark)
// =====================================================================
let s = pres.addSlide();
s.background = { color: DARK };
sonar(s, 10.95, 3.95, 2.15, 32, 0.62);
s.addText("ECHTZEIT · TIME-OF-FLIGHT · I²C", {
  x: 0.8, y: 1.7, w: 8, h: 0.4, fontFace: MONO, fontSize: 14, color: GREENSOFT, charSpacing: 3, bold: true, margin: 0,
});
s.addText("Distanzmessung mit einem\nTime-of-Flight Sensor", {
  x: 0.8, y: 2.15, w: 8.2, h: 1.7, fontFace: HEAD, fontSize: 40, color: LIGHT, bold: true, lineSpacingMultiple: 1.0, margin: 0,
});
s.addText("VL53L3CX  ·  Raspberry Pi 5  ·  PyQt6 GUI", {
  x: 0.8, y: 3.95, w: 8, h: 0.5, fontFace: BODY, fontSize: 18, color: DTXT, margin: 0,
});
s.addText([
  { text: "FH Wiener Neustadt — Embedded Systems", options: { breakLine: true, color: DTXT } },
  { text: "Mohammed Amaar", options: { color: MUTED } },
], { x: 0.8, y: 5.5, w: 8, h: 1, fontFace: BODY, fontSize: 14, margin: 0 });

// =====================================================================
// SLIDE 2 — Überblick (light) — 3 Schritte
// =====================================================================
s = pres.addSlide();
s.background = { color: LIGHT };
sectionLabel(s, "Überblick");
title(s, "Das System in drei Schritten");

const steps = [
  ["1", "Messen", "Der VL53L3CX am Raspberry Pi misst die Distanz über I²C — rund 20× pro Sekunde."],
  ["2", "Senden", "Ein kleiner Server am Pi streamt jede Messung als Text über das Netzwerk."],
  ["3", "Anzeigen", "Die PyQt6-GUI am Laptop empfängt die Daten und zeigt sie in Echtzeit an."],
];
const cw = 3.85, gap = 0.42, x0 = 0.6, cy = 2.3, ch = 3.4;
steps.forEach((st, i) => {
  const x = x0 + i * (cw + gap);
  s.addShape(pres.shapes.RECTANGLE, { x, y: cy, w: cw, h: ch, fill: { color: "F7FAF8" }, line: { color: LINE, width: 1 }, shadow: shadow() });
  s.addShape(pres.shapes.OVAL, { x: x + 0.4, y: cy + 0.45, w: 0.95, h: 0.95, fill: { color: GREENSOFT } });
  s.addText(st[0], { x: x + 0.4, y: cy + 0.45, w: 0.95, h: 0.95, align: "center", valign: "middle", fontFace: HEAD, fontSize: 32, bold: true, color: LIGHT, margin: 0 });
  s.addText(st[1], { x: x + 0.4, y: cy + 1.65, w: cw - 0.8, h: 0.55, fontFace: HEAD, fontSize: 22, bold: true, color: INK, margin: 0 });
  s.addText(st[2], { x: x + 0.4, y: cy + 2.2, w: cw - 0.8, h: 1.0, fontFace: BODY, fontSize: 14.5, color: "475569", margin: 0, lineSpacingMultiple: 1.05 });
});
footer(s, 2, false);

// =====================================================================
// SLIDE 3 — Messprinzip (light)
// =====================================================================
s = pres.addSlide();
s.background = { color: LIGHT };
sectionLabel(s, "Messprinzip");
title(s, "Wie funktioniert ein ToF-Sensor?");

// diagram: sensor box --pulse--> object box, reflection back
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 2.5, w: 2.5, h: 1.4, fill: { color: PANEL }, line: { color: GREEN, width: 1.5 }, rectRadius: 0.08 });
s.addText("Sensor", { x: 0.6, y: 2.5, w: 2.5, h: 1.4, align: "center", valign: "middle", fontFace: HEAD, fontSize: 18, bold: true, color: DTXT, margin: 0 });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.0, y: 2.5, w: 2.5, h: 1.4, fill: { color: "F1F5F4" }, line: { color: MUTED, width: 1.5 }, rectRadius: 0.08 });
s.addText("Objekt", { x: 6.0, y: 2.5, w: 2.5, h: 1.4, align: "center", valign: "middle", fontFace: HEAD, fontSize: 18, bold: true, color: INK, margin: 0 });
// pulse out
s.addShape(pres.shapes.LINE, { x: 3.15, y: 2.95, w: 2.8, h: 0, line: { color: GREENSOFT, width: 3, endArrowType: "triangle" } });
s.addText("IR-Laserpuls →", { x: 3.15, y: 2.55, w: 2.8, h: 0.35, align: "center", fontFace: BODY, fontSize: 11, color: GREENSOFT, bold: true, margin: 0 });
// reflection back
s.addShape(pres.shapes.LINE, { x: 5.95, y: 3.45, w: -2.8, h: 0, line: { color: MUTED, width: 3, dashType: "dash", endArrowType: "triangle" } });
s.addText("← Reflexion", { x: 3.15, y: 3.5, w: 2.8, h: 0.35, align: "center", fontFace: BODY, fontSize: 11, color: MUTED, bold: true, margin: 0 });

// formula callout
s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 4.5, w: 7.9, h: 0.95, fill: { color: "F0FBF4" }, line: { color: GREENSOFT, width: 1 } });
s.addText([
  { text: "Distanz  =  ", options: { color: INK } },
  { text: "(Lichtgeschwindigkeit × Laufzeit) ÷ 2", options: { color: GREENSOFT, bold: true } },
], { x: 0.6, y: 4.5, w: 7.9, h: 0.95, align: "center", valign: "middle", fontFace: MONO, fontSize: 18, margin: 0 });

// bullets right
s.addText([
  { text: "940 nm Infrarot-Laser (unsichtbar)", options: { bullet: true, breakLine: true } },
  { text: "Misst die Laufzeit des Lichts, nicht die Helligkeit", options: { bullet: true, breakLine: true } },
  { text: "Unabhängig von Farbe & Material des Objekts", options: { bullet: true, breakLine: true } },
  { text: "Reichweite bis zu mehreren Metern", options: { bullet: true } },
], { x: 9.0, y: 2.5, w: 3.7, h: 3.0, fontFace: BODY, fontSize: 15, color: INK, paraSpaceAfter: 10, margin: 0 });
footer(s, 3, false);

// =====================================================================
// SLIDE 4 — Hardware (light)
// =====================================================================
s = pres.addSlide();
s.background = { color: LIGHT };
sectionLabel(s, "Hardware");
title(s, "Hardware & Verkabelung");

s.addText([
  { text: "Raspberry Pi 5", options: { bold: true, breakLine: true } },
  { text: "Quad-Core, Linux, liest den Sensor & hostet den Server", options: { breakLine: true, color: "475569", fontSize: 12.5 } },
  { text: "Pololu VL53L3CX Breakout", options: { bold: true, breakLine: true } },
  { text: "ToF-Sensor mit eigenem 3,3-V-Regler", options: { breakLine: true, color: "475569", fontSize: 12.5 } },
  { text: "Offizielles 27-W-USB-C-Netzteil", options: { bold: true, breakLine: true } },
  { text: "Stabile Stromversorgung für den Pi 5", options: { color: "475569", fontSize: 12.5 } },
], { x: 0.6, y: 2.35, w: 5.4, h: 3.6, fontFace: BODY, fontSize: 15.5, color: INK, paraSpaceAfter: 7, margin: 0 });

// I2C wiring table
s.addText("I²C-Verkabelung", { x: 6.6, y: 2.2, w: 6, h: 0.4, fontFace: HEAD, fontSize: 16, bold: true, color: INK, margin: 0 });
const rows = [
  [{ text: "Sensor", options: { bold: true, color: LIGHT, fill: { color: GREENSOFT } } }, { text: "Raspberry Pi", options: { bold: true, color: LIGHT, fill: { color: GREENSOFT } } }],
  ["VIN", "3,3 V (Pin 1)"],
  ["GND", "GND (Pin 6)"],
  ["SDA", "GPIO2 / SDA1 (Pin 3)"],
  ["SCL", "GPIO3 / SCL1 (Pin 5)"],
];
s.addTable(rows, {
  x: 6.6, y: 2.7, w: 6.1, colW: [2.2, 3.9], rowH: 0.5,
  fontFace: BODY, fontSize: 14, color: INK, valign: "middle", align: "left",
  border: { type: "solid", pt: 1, color: LINE }, fill: { color: "FFFFFF" },
});
s.addText("Sichtbar mit  i2cdetect -y 1  →  Adresse 0x29", {
  x: 6.6, y: 5.55, w: 6.1, h: 0.4, fontFace: MONO, fontSize: 13, color: GREENSOFT, bold: true, margin: 0,
});
footer(s, 4, false);

// =====================================================================
// SLIDE 5 — Architektur (dark)
// =====================================================================
s = pres.addSlide();
s.background = { color: DARK };
s.addText("ARCHITEKTUR", { x: 0.6, y: 0.55, w: 10, h: 0.35, fontFace: MONO, fontSize: 12, color: GREENSOFT, charSpacing: 3, bold: true, margin: 0 });
s.addText("Verteilte Architektur", { x: 0.6, y: 0.92, w: 12, h: 0.9, fontFace: HEAD, fontSize: 32, color: LIGHT, bold: true, margin: 0 });

// Pi panel
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.7, y: 2.3, w: 5.4, h: 3.6, fill: { color: PANEL }, line: { color: GREEN, width: 1.5 }, rectRadius: 0.06 });
s.addText("Raspberry Pi 5", { x: 0.7, y: 2.5, w: 5.4, h: 0.5, align: "center", fontFace: HEAD, fontSize: 18, bold: true, color: GREENSOFT, margin: 0 });
s.addText([
  { text: "VL53L3CX  (Hardware, I²C)", options: { breakLine: true } },
  { text: "↓", options: { breakLine: true, color: GREEN } },
  { text: "vl53l3cx_driver.py  (ctypes + smbus2)", options: { breakLine: true } },
  { text: "↓", options: { breakLine: true, color: GREEN } },
  { text: "VL53L3CXSensor  (sensor.py)", options: { breakLine: true } },
  { text: "↓", options: { breakLine: true, color: GREEN } },
  { text: "sensor_server.py  (TCP :9999)", options: {} },
], { x: 1.0, y: 3.05, w: 4.8, h: 2.7, fontFace: MONO, fontSize: 13, color: DTXT, align: "center", paraSpaceAfter: 4, margin: 0 });

// Laptop panel
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.2, y: 2.3, w: 5.4, h: 3.6, fill: { color: PANEL2 }, line: { color: "3A5A4A", width: 1.5 }, rectRadius: 0.06 });
s.addText("Laptop", { x: 7.2, y: 2.5, w: 5.4, h: 0.5, align: "center", fontFace: HEAD, fontSize: 18, bold: true, color: DTXT, margin: 0 });
s.addText([
  { text: "NetworkSensor  (sensor.py)", options: { breakLine: true } },
  { text: "↓", options: { breakLine: true, color: GREEN } },
  { text: "MainWindow  (gui.py)", options: { breakLine: true } },
  { text: "↓", options: { breakLine: true, color: GREEN } },
  { text: "Live-Zahl · Graph · Sonar", options: { breakLine: true } },
  { text: "QTimer @ 20 Hz", options: {} },
], { x: 7.5, y: 3.15, w: 4.8, h: 2.5, fontFace: MONO, fontSize: 13, color: DTXT, align: "center", paraSpaceAfter: 6, margin: 0 });

// connector
s.addShape(pres.shapes.LINE, { x: 6.1, y: 4.1, w: 1.1, h: 0, line: { color: GREEN, width: 3, beginArrowType: "oval", endArrowType: "triangle" } });
s.addText('TCP  ·  WLAN\n"485,0\\n"', { x: 5.85, y: 4.2, w: 1.6, h: 0.7, align: "center", fontFace: MONO, fontSize: 10, color: GREENSOFT, bold: true, margin: 0 });
s.addText("Eine gemeinsame Schnittstelle (BaseSensor) — die GUI weiß nicht, ob die Daten von echter Hardware, einem Netzwerk oder einem Simulator kommen.", {
  x: 0.7, y: 6.15, w: 11.9, h: 0.7, align: "center", fontFace: BODY, fontSize: 13, italic: true, color: "9DB3A8", margin: 0,
});
footer(s, 5, true);

// =====================================================================
// SLIDE 6 — Software (light)
// =====================================================================
s = pres.addSlide();
s.background = { color: LIGHT };
sectionLabel(s, "Software");
title(s, "Die wichtigsten Software-Bausteine");

const blocks = [
  ["Abstraktion (BaseSensor)", "Eine Schnittstelle, drei Implementierungen: DummySensor (Test), VL53L3CXSensor (Hardware), NetworkSensor (Netzwerk). Austauschbar ohne GUI-Änderung."],
  ["Netzwerk-Protokoll", 'Einfaches Frage-Antwort-Prinzip über TCP: Der Laptop fragt, der Pi antwortet mit "Distanz,Status". Klein, robust, leicht zu debuggen.'],
  ["Echtzeit-Schleife", "Ein QTimer ruft 20× pro Sekunde die Anzeige-Funktion auf. Ein Ringpuffer (200 Werte) hält die Messhistorie für den Graphen."],
];
let by = 2.35;
blocks.forEach((b) => {
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: by, w: 12.1, h: 1.25, fill: { color: "F7FAF8" }, line: { color: LINE, width: 1 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: by, w: 0.09, h: 1.25, fill: { color: GREENSOFT } });
  s.addText(b[0], { x: 0.95, y: by + 0.16, w: 11.4, h: 0.45, fontFace: HEAD, fontSize: 17, bold: true, color: INK, margin: 0 });
  s.addText(b[1], { x: 0.95, y: by + 0.6, w: 11.5, h: 0.6, fontFace: BODY, fontSize: 13.5, color: "475569", margin: 0, lineSpacingMultiple: 1.03 });
  by += 1.42;
});
footer(s, 6, false);

// =====================================================================
// SLIDE 7 — Kabellos & portabel (light)
// =====================================================================
s = pres.addSlide();
s.background = { color: LIGHT };
sectionLabel(s, "Betrieb");
title(s, "Kabellos & portabel — ohne Router");

s.addText([
  { text: "Eigenes WLAN am Pi", options: { bold: true, breakLine: true } },
  { text: "Der Pi erzeugt sein eigenes Netzwerk (Hotspot „ToFSensor“).", options: { breakLine: true, color: "475569", fontSize: 13 } },
  { text: "Feste IP-Adresse", options: { bold: true, breakLine: true } },
  { text: "Der Pi ist immer unter 10.42.0.1 erreichbar — ändert sich nie.", options: { breakLine: true, color: "475569", fontSize: 13 } },
  { text: "Automatischer Start", options: { bold: true, breakLine: true } },
  { text: "Der Server startet beim Booten von selbst (systemd-Dienst).", options: { breakLine: true, color: "475569", fontSize: 13 } },
  { text: "Kein Router, kein Internet nötig", options: { bold: true, breakLine: true } },
  { text: "Funktioniert überall — nur eine Steckdose für den Pi.", options: { color: "475569", fontSize: 13 } },
], { x: 0.6, y: 2.35, w: 7.0, h: 4.2, fontFace: BODY, fontSize: 16, color: INK, paraSpaceAfter: 7, margin: 0 });

// visual: laptop <-wifi-> pi
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.1, y: 3.0, w: 1.9, h: 1.3, fill: { color: PANEL2 }, line: { color: "3A5A4A", width: 1.5 }, rectRadius: 0.08 });
s.addText("Laptop\n(GUI)", { x: 8.1, y: 3.0, w: 1.9, h: 1.3, align: "center", valign: "middle", fontFace: HEAD, fontSize: 14, bold: true, color: DTXT, margin: 0 });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 11.0, y: 3.0, w: 1.9, h: 1.3, fill: { color: PANEL }, line: { color: GREEN, width: 1.5 }, rectRadius: 0.08 });
s.addText("Pi\n(Sensor)", { x: 11.0, y: 3.0, w: 1.9, h: 1.3, align: "center", valign: "middle", fontFace: HEAD, fontSize: 14, bold: true, color: GREENSOFT, margin: 0 });
s.addShape(pres.shapes.LINE, { x: 10.0, y: 3.65, w: 1.0, h: 0, line: { color: GREEN, width: 2.5, beginArrowType: "oval", endArrowType: "oval" } });
s.addText("WLAN", { x: 9.9, y: 2.55, w: 1.2, h: 0.35, align: "center", fontFace: MONO, fontSize: 11, bold: true, color: GREENSOFT, margin: 0 });
s.addText("10.42.0.1", { x: 10.55, y: 4.35, w: 2.4, h: 0.35, align: "center", fontFace: MONO, fontSize: 11, color: MUTED, margin: 0 });
footer(s, 7, false);

// =====================================================================
// SLIDE 8 — GUI (dark)
// =====================================================================
s = pres.addSlide();
s.background = { color: DARK };
s.addText("ERGEBNIS", { x: 0.6, y: 0.55, w: 10, h: 0.35, fontFace: MONO, fontSize: 12, color: GREENSOFT, charSpacing: 3, bold: true, margin: 0 });
s.addText("Die Benutzeroberfläche", { x: 0.6, y: 0.92, w: 12, h: 0.9, fontFace: HEAD, fontSize: 32, color: LIGHT, bold: true, margin: 0 });

// left: feature list
s.addText([
  { text: "Live-Distanz", options: { bold: true, color: GREENSOFT, breakLine: true } },
  { text: "Große, farbcodierte Zahl in Echtzeit", options: { breakLine: true, color: DTXT, fontSize: 13 } },
  { text: "Verlaufsgraph", options: { bold: true, color: GREENSOFT, breakLine: true } },
  { text: "Distanz über die Zeit", options: { breakLine: true, color: DTXT, fontSize: 13 } },
  { text: "Sonar-Radar", options: { bold: true, color: GREENSOFT, breakLine: true } },
  { text: "Drehender Sweep mit Blip", options: { breakLine: true, color: DTXT, fontSize: 13 } },
  { text: "Einstellbare Reichweite", options: { bold: true, color: GREENSOFT, breakLine: true } },
  { text: "Bis max. Sensor-Reichweite", options: { color: DTXT, fontSize: 13 } },
], { x: 0.7, y: 2.4, w: 5.2, h: 4.2, fontFace: BODY, fontSize: 16, paraSpaceAfter: 8, margin: 0 });

// right: sonar mock
s.addShape(pres.shapes.RECTANGLE, { x: 6.4, y: 2.25, w: 6.3, h: 4.3, fill: { color: "060C09" }, line: { color: "27332C", width: 1 } });
sonar(s, 9.55, 4.35, 1.75, 48, 0.55);
s.addText("485 mm", { x: 8.3, y: 6.0, w: 2.5, h: 0.4, align: "center", fontFace: MONO, fontSize: 16, bold: true, color: GREENSOFT, margin: 0 });
footer(s, 8, true);

// =====================================================================
// SLIDE 9 — Zusammenfassung (dark)
// =====================================================================
s = pres.addSlide();
s.background = { color: DARK };
sonar(s, 11.6, 1.6, 1.4, 200, 0.5);
s.addText("ZUSAMMENFASSUNG", { x: 0.7, y: 1.5, w: 10, h: 0.4, fontFace: MONO, fontSize: 13, color: GREENSOFT, charSpacing: 3, bold: true, margin: 0 });
s.addText("Was wir gebaut haben", { x: 0.7, y: 2.0, w: 11, h: 0.9, fontFace: HEAD, fontSize: 34, color: LIGHT, bold: true, margin: 0 });
s.addText([
  { text: "Echtzeit-Distanzmessung mit dem VL53L3CX läuft auf echter Hardware", options: { bullet: { code: "2713" }, breakLine: true } },
  { text: "Saubere Trennung: Hardware am Pi, Anzeige am Laptop", options: { bullet: { code: "2713" }, breakLine: true } },
  { text: "Verbindung kabellos & portabel — eigenes WLAN, kein Router", options: { bullet: { code: "2713" }, breakLine: true } },
  { text: "Robust: jeder Fehlerfall wird sauber angezeigt, kein Absturz", options: { bullet: { code: "2713" } } },
], { x: 0.7, y: 3.2, w: 11.5, h: 2.6, fontFace: BODY, fontSize: 18, color: DTXT, paraSpaceAfter: 14, margin: 0 });
s.addText("Vielen Dank!", { x: 0.7, y: 6.1, w: 8, h: 0.6, fontFace: HEAD, fontSize: 22, bold: true, color: GREENSOFT, margin: 0 });

pres.writeFile({ fileName: "C:/Users/moham/Coding-Projects/FH_WN/embedded_tof_sensor/docs/Praesentation.pptx" })
  .then(f => console.log("WROTE", f));
