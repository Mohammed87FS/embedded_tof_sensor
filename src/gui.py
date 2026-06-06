# =============================================================================
# gui.py  --  DIE GRAFISCHE BENUTZEROBERFLAECHE (PyQt6)
# -----------------------------------------------------------------------------
# Definiert MainWindow: das Fenster, das der Nutzer sieht. Es enthaelt:
#   - eine grosse Live-Distanz-Zahl,
#   - einen scrollenden "Distanz ueber Zeit"-Graphen,
#   - Start/Stop-Knoepfe,
#   - Range- und Budget-Dropdowns, um den Sensor live umzukonfigurieren.
#
# KERNIDEE: Eine GUI darf niemals "schlafen" oder blockieren, sonst wuerde sie
# einfrieren. Stattdessen nutzen wir einen QTimer, der alle 50 ms feuert; bei
# jedem Tick lesen wir EINEN Wert vom Sensor und aktualisieren die Anzeige. So
# bleibt das Fenster reaktionsfaehig. Dieses Muster (Timer statt sleep) ist der
# Standard in ereignisgesteuerten ("event-driven") GUI-Frameworks.
# =============================================================================

"""
Main GUI window — live distance display and time-series graph.
"""

# ----------------------------------------------------------------------------
# IMPORTS
# ----------------------------------------------------------------------------

# NumPy: schnelle numerische Arrays. 'import X as Y' gibt ihm den ueblichen
# Kurz-Alias 'np'. Wir nutzen es fuer den Ringpuffer hinter dem Graphen.
import numpy as np

# pyqtgraph: eine schnelle Plot-Bibliothek auf Basis von Qt. Ueblicher Alias
# 'pg'. Sie zeichnet das Live-Liniendiagramm.
import pyqtgraph as pg

# Qt ist in Untermodule aufgeteilt. Wir importieren nur die Klassen, die wir
# nutzen.
#   QtCore: nicht-grafische Kerntypen.
#     Qt     -> ein Namensraum von Enums/Flags (Ausrichtung usw.).
#     QTimer -> feuert wiederholt ein Signal in festem Intervall.
from PyQt6.QtCore import Qt, QTimer
#   QtGui: Grafiktypen. QFont beschreibt eine Schriftart (Familie, Groesse,
#   Staerke).
from PyQt6.QtGui import QFont
#   QtWidgets: die sichtbaren Bausteine. Die Klammern erlauben, dass der Import
#   ueber mehrere Zeilen geht (bessere Lesbarkeit).
#     QMainWindow -> ein Hauptfenster mit zentralem Bereich.
#     QWidget     -> ein leeres Rechteck; Basis aller Widgets, als Container genutzt.
#     QVBoxLayout -> stapelt Kind-Widgets VERTIKAL.
#     QHBoxLayout -> ordnet Kind-Widgets HORIZONTAL an.
#     QLabel      -> zeigt Text an.
#     QPushButton -> ein anklickbarer Knopf.
#     QComboBox   -> ein Auswahl-Dropdown.
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
)

# Unsere eigene Sensor-Schnittstelle. Wir brauchen BaseSensor nur fuer den
# TYP-HINWEIS unten; das tatsaechlich uebergebene Objekt ist ein NetworkSensor.
from sensor import BaseSensor


# 'class MainWindow(QMainWindow)' -> unser Fenster ERBT das gesamte Verhalten
# von QMainWindow (Titelleiste, Groessenaenderung, Schliessen-Knopf) und fuegt
# eigene Widgets hinzu.
class MainWindow(QMainWindow):
    # -------------------------------------------------------------------------
    # KLASSEN-WEITE KONSTANTEN. Hier definiert (nicht in __init__), weil sie fuer
    # jede Instanz gleich sind. Zugriff ueber self.NAME innerhalb der Methoden.
    # -------------------------------------------------------------------------
    # Wie viele Messwerte der Graph auf dem Bildschirm behaelt.
    BUFFER_SIZE = 200
    # ~20 Hz UI; das Timing-Budget des VL53L3CX von 50 ms begrenzt die nutzbare
    # Rate auf ca. 15-20 Hz.
    UPDATE_INTERVAL_MS = 50
    # Y-Achsen-Obergrenze pro Distanzmodus (1 kurz, 2 mittel, 3 lang). Das ist
    # ein DICTIONARY (dict): {schluessel: wert, ...}. Zugriff via MODE_MAX_MM[mode].
    MODE_MAX_MM = {1: 1500, 2: 3000, 3: 5000}
    # Der beim Start gewaehlte Distanzmodus (3 = lang), passend zur
    # Server-Vorgabe und zur Standard-Auswahl im Dropdown.
    DEFAULT_MODE = 3

    # Der Konstruktor. 'sensor: BaseSensor' = das Objekt, von dem das Fenster
    # liest (als Schnittstelle typisiert, daher funktioniert jeder Sensor).
    # 'auto_start' entscheidet, ob sofort gepollt wird.
    def __init__(self, sensor: BaseSensor, auto_start: bool = False):
        # Rufe ZUERST __init__ von QMainWindow auf. super() verweist auf die
        # Elternklasse; das ist zwingend, damit Qt seinen internen Zustand
        # aufbaut, bevor wir Widgets hinzufuegen.
        super().__init__()
        # Speichere den Sensor, damit andere Methoden ihn nutzen koennen.
        self._sensor = sensor
        # Verfolge, ob wir gerade pollen (genutzt von Start/Stop/Schliessen).
        self._running = False
        # Der Ringpuffer hinter dem Graphen: ein NumPy-Array aus BUFFER_SIZE
        # Nullen. np.zeros(n) erzeugt ein Array aus n Gleitkomma-0.0-Werten.
        self._data_buffer = np.zeros(self.BUFFER_SIZE)
        # Ein Zaehler, wie viele Messwerte wir bisher geschrieben haben (waechst
        # unbegrenzt); zusammen mit dem Modulo-Operator als Index in den
        # Ringpuffer.
        self._buf_idx = 0

        # Setze den Text in der Titelleiste des Fensters.
        self.setWindowTitle("VL53L3CX — ToF Distance Monitor")
        # Verhindere, dass das Fenster kleiner als 800x500 Pixel wird.
        self.setMinimumSize(800, 500)
        # Baue alle Widgets (in der Hilfsmethode unten definiert).
        self._setup_ui()
        # Erzeuge den wiederholenden Timer (Hilfsmethode unten).
        self._setup_timer()

        # Falls gewuenscht, sofort mit dem Pollen beginnen (main.py uebergibt
        # auto_start=True).
        if auto_start:
            self._on_start()

    # Hilfsmethode, die jedes Widget baut und anordnet. '-> None' = gibt nichts
    # zurueck.
    def _setup_ui(self) -> None:
        # Ein QMainWindow braucht EIN "zentrales Widget", das seinen Inhalt
        # haelt. Wir machen dafuer ein leeres QWidget.
        central = QWidget()
        self.setCentralWidget(central)
        # Ein vertikales Layout, das Kinder von oben nach unten in 'central'
        # anordnet. Die Uebergabe von 'central' verbindet das Layout damit.
        layout = QVBoxLayout(central)

        # --- Die grosse Distanz-Zahl ---
        # Erzeuge das Label mit Platzhaltertext.
        self._dist_label = QLabel("--- mm")
        # Setze eine grosse, fette Monospace-Schrift: Familie "Monospace",
        # Groesse 36, fett.
        self._dist_label.setFont(QFont("Monospace", 36, QFont.Weight.Bold))
        # Zentriere den Text horizontal und vertikal. Qt.AlignmentFlag ist der
        # Enum-Namensraum; AlignCenter ist das konkrete Flag.
        self._dist_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Faerbe den Text gruen mit einem CSS-aehnlichen Stylesheet (#00cc44 ist
        # eine Hex-RGB-Farbe).
        self._dist_label.setStyleSheet("color: #00cc44;")
        # Fuege das Label als erste Zeile des vertikalen Layouts hinzu.
        layout.addWidget(self._dist_label)

        # --- Der Zeitreihen-Graph (pyqtgraph) ---
        # Schalte Anti-Aliasing global ein, fuer glattere Linien.
        pg.setConfigOptions(antialias=True)
        # Erzeuge das Plot-Widget mit Titel.
        self._plot_widget = pg.PlotWidget(title="Distance Over Time")
        # Beschrifte die Y-Achse (links) mit Einheit und die X-Achse (unten).
        self._plot_widget.setLabel("left", "Distance", units="mm")
        self._plot_widget.setLabel("bottom", "Samples")
        # Lege den sichtbaren Y-Bereich von 0 bis zur Obergrenze des
        # Standardmodus fest (Dictionary-Zugriff MODE_MAX_MM[3] = 5000).
        self._plot_widget.setYRange(0, self.MODE_MAX_MM[self.DEFAULT_MODE])
        # Dunkler Hintergrund passend zum Thema.
        self._plot_widget.setBackground("#1a1a1a")
        # Erzeuge die eigentliche Kurve (Linie), die wir staendig aktualisieren.
        # mkPen erstellt einen gruenen Stift, 2 Pixel breit. plot() gibt ein
        # Kurven-Objekt zurueck, das wir speichern.
        self._plot_curve = self._plot_widget.plot(pen=pg.mkPen(color="#00ff55", width=2))
        # Fuege den Graphen hinzu; stretch=1 laesst ihn freien vertikalen Platz
        # ausfuellen.
        layout.addWidget(self._plot_widget, stretch=1)

        # --- Range-Dropdown (Distanzmodus) ---
        self._mode_combo = QComboBox()
        # Fuelle es aus einer Liste von (Beschriftung, Wert)-Tupeln. Die
        # 'for'-Schleife entpackt jedes Tupel in 'label' und 'mode'.
        # addItem(text, userData) speichert einen versteckten Wert (die
        # Modus-Nummer) zusammen mit dem sichtbaren Text.
        for label, mode in [("Short", 1), ("Medium", 2), ("Long", 3)]:
            self._mode_combo.addItem(label, mode)
        # Index 2 (das dritte Element, "Long") vorauswaehlen, passend zu
        # DEFAULT_MODE.
        self._mode_combo.setCurrentIndex(2)  # Long = default

        # --- Timing-Budget-Dropdown ---
        self._budget_combo = QComboBox()
        # Wieder (Beschriftung, Mikrosekunden)-Paare. 33_000 == 33000
        # (Unterstriche sind nur optische Ziffern-Trenner).
        for label, us in [("33 ms", 33_000), ("50 ms", 50_000),
                          ("100 ms", 100_000), ("200 ms", 200_000)]:
            self._budget_combo.addItem(label, us)
        # Index 1 ("50 ms") vorauswaehlen, das Standard-Budget des Sensors.
        self._budget_combo.setCurrentIndex(1)  # 50 ms = default

        # SIGNAL/SLOT-Verbindung: Aendert der Nutzer ein Dropdown, SENDET Qt das
        # Signal 'currentIndexChanged'; .connect(...) verdrahtet es mit unserem
        # Handler, sodass _on_config_changed automatisch laeuft. Wir uebergeben
        # die Funktion selbst (OHNE Klammern) als Rueckruf (callback).
        self._mode_combo.currentIndexChanged.connect(self._on_config_changed)
        self._budget_combo.currentIndexChanged.connect(self._on_config_changed)

        # --- Untere Steuerzeile (Knoepfe + Dropdowns) ---
        # Ein horizontales Layout, das Elemente von links nach rechts platziert.
        ctrl = QHBoxLayout()
        self._start_btn = QPushButton("Start")
        self._stop_btn = QPushButton("Stop")
        # Stop ist deaktiviert, bis wir tatsaechlich laufen.
        self._stop_btn.setEnabled(False)
        # Verdrahte Knopf-Klicks mit ihren Handlern (wieder Signal/Slot).
        self._start_btn.clicked.connect(self._on_start)
        self._stop_btn.clicked.connect(self._on_stop)
        # Fuege die Knoepfe links hinzu.
        ctrl.addWidget(self._start_btn)
        ctrl.addWidget(self._stop_btn)
        # addStretch() fuegt einen flexiblen Platzhalter ein, der die folgenden
        # Widgets ganz nach rechts schiebt.
        ctrl.addStretch()
        # Beschriftete Dropdowns auf der rechten Seite.
        ctrl.addWidget(QLabel("Range:"))
        ctrl.addWidget(self._mode_combo)
        ctrl.addWidget(QLabel("Budget:"))
        ctrl.addWidget(self._budget_combo)
        # Fuege diese ganze horizontale Zeile als letztes Element des vertikalen
        # Layouts hinzu.
        layout.addLayout(ctrl)

        # Wende ein Stylesheet (Qts CSS-aehnliche Gestaltung) auf das ganze
        # Fenster an, fuer das dunkle Thema und das Aussehen der Knoepfe. Der
        # dreifach-zitierte String geht ueber mehrere Zeilen.
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #121212; color: #e0e0e0; }
            QPushButton {
                background: #1e1e1e; border: 1px solid #444;
                border-radius: 4px; padding: 8px 16px;
                color: #e0e0e0; font-size: 13px;
            }
            QPushButton:hover { background: #2a2a2a; }
            QPushButton:disabled { color: #555; }
        """)

    # Hilfsmethode, die den wiederholenden Timer erstellt.
    def _setup_timer(self) -> None:
        # QTimer(self) -> 'self' ist der Eltern; so raeumt Qt den Timer mit dem
        # Fenster auf.
        self._timer = QTimer(self)
        # Feuere alle UPDATE_INTERVAL_MS Millisekunden (50 ms = 20-mal pro
        # Sekunde).
        self._timer.setInterval(self.UPDATE_INTERVAL_MS)
        # Bei jedem Feuern sendet er 'timeout'; fuehre dann _tick aus.
        self._timer.timeout.connect(self._tick)

    # SLOT: laeuft, wann immer ein Dropdown sich aendert. Schiebt die neue
    # Konfiguration zum Sensor und skaliert den Graphen neu.
    def _on_config_changed(self) -> None:
        # currentData() liefert den versteckten Wert, der mit dem ausgewaehlten
        # Element gespeichert wurde (die Modus-Nummer / Mikrosekunden aus
        # addItem).
        mode = self._mode_combo.currentData()
        budget = self._budget_combo.currentData()
        # Sende die neuen Einstellungen an den Sensor (beim NetworkSensor ueber
        # TCP).
        self._sensor.configure(mode, budget)
        # Skaliere die Y-Achse passend zum neuen Reichweitenmodus.
        self._plot_widget.setYRange(0, self.MODE_MAX_MM[mode])

    # SLOT: Start-Knopf / Auto-Start. Beginnt das Pollen.
    def _on_start(self) -> None:
        # Mit dem Sensor verbinden / ihn einschalten.
        self._sensor.start()
        self._running = True
        # Starte den wiederholenden Timer -> _tick beginnt zu feuern.
        self._timer.start()
        # Aktiviert-Zustaende der Knoepfe umschalten: nicht erneut Start, jetzt
        # Stop moeglich.
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

    # SLOT: Stop-Knopf. Haelt das Pollen an.
    def _on_stop(self) -> None:
        # Zuerst den Timer stoppen, damit keine weiteren Lesungen versucht werden.
        self._timer.stop()
        # Dann den Sensor freigeben.
        self._sensor.stop()
        self._running = False
        # Knopf-Zustaende wiederherstellen.
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    # SLOT: das Herz der GUI. Laeuft alle 50 ms, solange wir laufen.
    def _tick(self) -> None:
        # Hole EINE frische Messung vom Sensor.
        reading = self._sensor.read()

        # Speichere die Distanz im Ringpuffer. Der Modulo-Operator '%' faltet den
        # staendig wachsenden Index zurueck auf 0..BUFFER_SIZE-1, sodass das Array
        # zyklisch wiederverwendet wird (der aelteste Messwert wird
        # ueberschrieben). Dann den Schreibindex erhoehen ('+= 1' = "addiere 1").
        self._data_buffer[self._buf_idx % self.BUFFER_SIZE] = reading.distance_mm
        self._buf_idx += 1

        # Aktualisiere die grosse Zahl + Farbe je nach Status der Messung.
        if reading.valid:
            # Gueltig: zeige den mm-Wert. Die Farbe ist normal gruen, rot wenn
            # naeher als 300 mm (einzeiliges if/else fuer die Farb-Zeichenkette).
            self._dist_label.setText(f"{reading.distance_mm} mm")
            color = "#00cc44" if reading.distance_mm > 300 else "#ff4444"
            self._dist_label.setStyleSheet(f"color: {color};")
        # 'elif' = "else if": wird nur geprueft, wenn die vorigen Bedingungen
        # False waren.
        elif reading.status == 2:
            # Status 2 = wartet auf den Sensor; zeige drei Punkte in Grau.
            self._dist_label.setText("…")
            self._dist_label.setStyleSheet("color: #888;")
        elif reading.status == 4:
            # Status 4 = kein Ziel in Reichweite; zeige eine Warnung in Orange.
            self._dist_label.setText("NO TARGET")
            self._dist_label.setStyleSheet("color: #ffaa44;")
        else:
            # Alles andere (Status 1) = Fehler; zeige ERR in Rot.
            self._dist_label.setText("ERR")
            self._dist_label.setStyleSheet("color: #ff4444;")

        # Ermittle, wie viel des Puffers tatsaechlich gefuellt ist (Minimum aus
        # geschriebenen Werten und Puffer-Kapazitaet).
        filled = min(self._buf_idx, self.BUFFER_SIZE)
        # Sobald der Puffer mindestens einmal uebergelaufen ist, muessen wir ihn
        # neu ordnen, damit der Plot aelteste -> neueste zeigt und keinen Sprung
        # an der Schreibposition hat.
        if self._buf_idx >= self.BUFFER_SIZE:
            # np.roll verschiebt das Array; der negative Versatz rotiert so, dass
            # die aktuelle Schreibposition zum Anfang wird. Ergebnis:
            # chronologisch.
            ordered = np.roll(self._data_buffer, -(self._buf_idx % self.BUFFER_SIZE))
        else:
            # Wird zum ersten Mal gefuellt: nimm einfach den gefuellten
            # Ausschnitt. 'array[:filled]' ist "Slicing": Elemente 0 bis
            # (ausschliesslich) filled.
            ordered = self._data_buffer[:filled]

        # Uebergib die geordneten Daten der Kurve; pyqtgraph zeichnet die Linie
        # neu.
        self._plot_curve.setData(ordered)

    # closeEvent ist eine Qt-Methode, die wir UEBERSCHREIBEN; Qt ruft sie
    # automatisch auf, wenn der Nutzer das X des Fensters klickt. 'event' traegt
    # die Schliess-Anfrage.
    def closeEvent(self, event) -> None:
        # Falls noch gepollt wird, zuerst sauber stoppen (gibt Sensor/Socket
        # frei).
        if self._running:
            self._on_stop()
        # accept() sagt Qt "ja, schliesse das Fenster".
        event.accept()
