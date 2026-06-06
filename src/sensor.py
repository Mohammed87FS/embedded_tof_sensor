# =============================================================================
# sensor.py  --  DIE SENSOR-ABSTRAKTIONSSCHICHT (das Herzstueck des Projekts)
# -----------------------------------------------------------------------------
# Diese Datei definiert VIER Dinge:
#   1. SensorReading  - ein winziger Daten-Container fuer EINE Messung.
#   2. BaseSensor     - eine abstrakte "Schnittstelle" (Interface), die jeder
#                       Sensor erfuellen muss.
#   3. VL53L3CXSensor - der ECHTE Treiber, laeuft AUF DEM PI, spricht mit der
#                       Hardware ueber I2C.
#   4. NetworkSensor  - ein Stellvertreter-Sensor, laeuft AUF DEM LAPTOP,
#                       spricht ueber TCP mit dem Pi.
#
# Die clevere Idee ("Abstraktion" / "Polymorphismus"): Die GUI ist gegen
# BaseSensor geschrieben und ruft nur start(), read(), stop(), configure() auf.
# Es ist ihr EGAL, ob die Daten von echter I2C-Hardware oder aus dem Netzwerk
# kommen. Genau deshalb laeuft dieselbe gui.py unveraendert auf Pi UND Laptop.
# Das ist das "Strategy/Adapter"-Muster aus der objektorientierten Programmierung.
# =============================================================================

"""
VL53L3CX sensor abstraction — single-target mode.
Uses the FrgyCZ VL53L3CX-python bindings (ST VL53LX bare driver + smbus2) on Raspberry Pi.

Install on the Pi (full driver; PyPI sdist is incomplete — use Git):
  sudo apt install build-essential python3-dev git
  pip install -r requirements-rpi.txt
"""

# ----------------------------------------------------------------------------
# IMPORTS
# ----------------------------------------------------------------------------

# Standardbibliothek. time.time() liefert die aktuelle Zeit als Gleitkommazahl
# in Sekunden (seit dem 1.1.1970, "Unix-Zeit"). Wir nutzen es, um Messungen mit
# einem Zeitstempel zu versehen und um zu pruefen, wie alt eine
# zwischengespeicherte Messung ist (fuer die "letzten Wert halten"-Logik bei
# Aussetzern).
import time

# Standardbibliothek fuer TCP/IP-Netzwerk. Wird nur vom NetworkSensor benutzt,
# um eine Socket-Verbindung zum Pi zu oeffnen.
import socket

# 'abc' = Abstract Base Classes (abstrakte Basisklassen). ABC ist die
# Elternklasse, die eine Klasse abstrakt macht (nicht direkt instanziierbar).
# @abstractmethod markiert Methoden, die Unterklassen ZWINGEND implementieren
# muessen. Zusammen definieren sie eine strikte Schnittstelle, deren Einhaltung
# Python zur Laufzeit erzwingt.
from abc import ABC, abstractmethod

# 'typing' liefert Typ-Hinweise (type hints). Diese sind nur Dokumentation;
# Python erzwingt sie zur Laufzeit NICHT, aber Editoren und Leser nutzen sie.
#   Any         -> "irgendein beliebiger Typ" (fuer das C-Treiber-Objekt, dessen
#                  Klasse wir oben in der Datei nicht importieren koennen).
#   Optional[X] -> Kurzform fuer "X oder None".
from typing import Any, Optional

# ----------------------------------------------------------------------------
# MODUL-WEITE KONSTANTEN
# Ein fuehrender Unterstrich (_NAME) ist eine Python-Konvention fuer "privat /
# nur intern in diesem Modul". Es wird nicht erzwungen, ist nur ein Signal an
# den Leser. Das sind "magische Zahlen" aus ST's VL53LX-Treiber: Findet der
# Sensor KEIN Objekt, liefert er nicht 0 mm, sondern einen Sentinel-Wert
# (Platzhalter-Wert).
# ----------------------------------------------------------------------------

# 8191 (== 0x1FFF, alle 13 Bit gesetzt) ist der klassische
# "kein Ziel / Ueberlauf"-Wert, den der ST-Treiber meldet, wenn nichts in
# Reichweite ist.
_NO_TARGET_MM = 8191

# Jede Distanz ab 8000 mm gilt als unsinnig (die echte Reichweite des Sensors
# ist nur ~3 m). Werte so hoch bedeuten einen ungueltigen/Muell-Frame.
_ST_INVALID_HIGH = 8000


# =============================================================================
# 1) SensorReading  --  ein einfaches Datenobjekt fuer EINE Messung.
# =============================================================================
class SensorReading:
    # __slots__ ist eine Optimierung + Sicherheitsfunktion. Indem wir die
    # EINZIGEN erlaubten Attributnamen auflisten, sorgt Python dafuer, dass:
    #   (a) sie kompakter gespeichert werden (kein __dict__ pro Objekt) -> spart
    #       Speicher,
    #   (b) ein Tippfehler im Attributnamen (z. B. .distnce_mm) einen Fehler
    #       ausloest, statt still ein nutzloses neues Attribut anzulegen.
    __slots__ = ("distance_mm", "status", "timestamp")

    # Status-Codes, die im ganzen Projekt verwendet werden:
    #   0 = OK (gueltige Distanz), 1 = Fehler, 2 = wartet (noch nicht bereit),
    #   4 = kein Ziel.
    # __init__ ist der KONSTRUKTOR: laeuft automatisch bei SensorReading(412).
    # 'self' ist das neu gebaute Objekt. Die Typ-Hinweise (: int) dokumentieren
    # die erwarteten Typen; '= 0' gibt 'status' einen Standardwert, sodass man
    # ihn weglassen darf.
    def __init__(self, distance_mm: int, status: int = 0):
        # 'self.X = Y' speichert den Wert Y unter dem Attributnamen X im Objekt.
        self.distance_mm = distance_mm
        self.status = status
        # Stemple den Zeitpunkt der Erzeugung. Spaeter vergleichen wir diesen mit
        # time.time(), um zu entscheiden, ob die Messung noch "frisch" ist.
        self.timestamp = time.time()

    # @property macht aus einer Methode ein nur-lesbares, berechnetes Attribut.
    # Dadurch schreibt man 'reading.valid' (OHNE Klammern), und Python fuehrt
    # diesen Code bei jedem Zugriff aus. '-> bool' = liefert einen Wahr/Falsch-Wert.
    @property
    def valid(self) -> bool:
        # Eine Messung gilt nur als gueltig, wenn der Status OK (0) ist UND die
        # Distanz eine sinnvolle positive Zahl unter 6000 mm ist.
        # HINWEIS: '0 < self.distance_mm < 6000' ist Pythons verkettete
        # Vergleichs-Schreibweise, identisch zu
        # '(0 < distance_mm) and (distance_mm < 6000)'.
        return self.status == 0 and 0 < self.distance_mm < 6000


# =============================================================================
# 2) BaseSensor  --  die abstrakte SCHNITTSTELLE (Vertrag) fuer alle Sensoren.
# =============================================================================
# Das Erben von ABC macht diese Klasse abstrakt: BaseSensor() direkt geht NICHT.
# Ihr einziger Zweck ist es zu deklarieren, WELCHE Methoden jeder konkrete
# Sensor bereitstellen muss.
class BaseSensor(ABC):
    # @abstractmethod bedeutet: Jede Unterklasse MUSS diese Methode ueberschreiben,
    # sonst verweigert Python das Erzeugen von Instanzen dieser Unterklasse. Der
    # Rumpf ist nur '...' (das Ellipsis-Literal), ein Platzhalter fuer "keine
    # Implementierung hier". '-> None' = gibt nichts zurueck.
    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def read(self) -> SensorReading: ...

    @abstractmethod
    def stop(self) -> None: ...

    # Diese Methode ist NICHT abstrakt: Sie hat einen echten (leeren) Rumpf.
    # Unterklassen DUERFEN sie ueberschreiben, muessen es aber nicht. Der
    # Docstring erklaert, dass sie standardmaessig ein "No-op" ist (tut nichts).
    # VL53L3CXSensor und NetworkSensor ueberschreiben sie beide; ein kuenftiger
    # Sensor, der Konfiguration ignoriert, funktioniert trotzdem.
    def configure(self, distance_mode: int, timing_budget_us: int) -> None:
        """Optional runtime reconfiguration. No-op unless overridden."""


# =============================================================================
# 3) VL53L3CXSensor  --  der ECHTE Hardware-Treiber. Laeuft AUF DEM PI.
# =============================================================================
# 'class VL53L3CXSensor(BaseSensor)' bedeutet, dass die Klasse von BaseSensor
# ERBT und daher start/read/stop implementieren muss. Sie spricht ueber die
# vendored C-Erweiterung per I2C mit dem physischen Sensor.
class VL53L3CXSensor(BaseSensor):
    """
    VL53L3CX via ST bare driver (VL53L3CX-python: ctypes + vl53l3cx_python.so).

    Long-range mode + ~50 ms timing budget matches typical indoor demos and
    keeps measurement rate around ~15–20 Hz (sensor-limited).
    """

    # Der Konstruktor. Jeder Parameter hat einen STANDARDWERT (nach dem '='),
    # sodass der Server einfach VL53L3CXSensor() ohne Argumente aufrufen kann und
    # sinnvolle Einstellungen erhaelt.
    def __init__(
        self,
        i2c_bus: int = 1,                 # Linux-I2C-Busnummer (/dev/i2c-1 am Pi-Header)
        i2c_address: int = 0x29,          # 7-Bit-I2C-Adresse des Sensors (0x29 hex = 41). i2cdetect zeigt 0x29
        distance_mode: int = 3,           # 1 = kurz, 2 = mittel, 3 = lange Reichweite
        timing_budget_us: int = 50_000,   # Mikrosekunden pro Messung (Unterstriche sind nur Ziffern-Trenner: 50_000 == 50000)
        stale_timeout_s: float = 0.5,     # wie lange (Sekunden) eine zwischengespeicherte Messung wiederverwendet werden darf
    ):
        # Kopiere jedes Argument in ein privates Attribut (fuehrender Unterstrich
        # = "intern"). Wir speichern sie, damit read()/configure() sie spaeter
        # nutzen koennen.
        self._i2c_bus = i2c_bus
        self._i2c_address = i2c_address
        self._distance_mode = distance_mode
        self._timing_budget_us = timing_budget_us
        self._stale_timeout_s = stale_timeout_s
        # _tof haelt spaeter das eigentliche C-Treiber-Objekt. Es ist None, bis
        # start() aufgerufen wird. Das ': Any' ist nur ein Typ-Hinweis.
        self._tof: Any = None
        # _last speichert die zuletzt GUELTIGE Messung fuer die
        # "Wert-halten"-Logik in read(). Optional[SensorReading] = "ein
        # SensorReading oder None".
        self._last: Optional[SensorReading] = None

    # start() schaltet den Sensor ein, konfiguriert ihn und beginnt das Messen.
    def start(self) -> None:
        # Wir importieren den nativen Treiber HIER, in der Funktion, NICHT oben in
        # der Datei. Grund: Der Import von vl53l3cx_driver versucht sofort, eine
        # kompilierte .so-Bibliothek zu laden, die es NUR auf dem Pi gibt. Stuende
        # der Import oben, wuerde der Laptop schon beim Importieren von sensor.py
        # abstuerzen. Der "lazy import" (verzoegerter Import) hier sorgt dafuer,
        # dass der Laptop (der nur NetworkSensor nutzt) ihn nie ausloest.
        # 'import X as Y' gibt dem importierten Namen den kuerzeren Alias Y.
        try:
            from vl53l3cx_driver import VL53L3CX as _VL53
        # 'except (A, B) as e' faengt beide Fehlertypen ab und bindet sie an 'e'.
        # OSError     -> die .so-Datei konnte nicht geladen werden.
        # ImportError -> das Python-Modul/Paket fehlt.
        except (OSError, ImportError) as e:
            # Wirf einen klareren RuntimeError mit Installationshinweisen.
            # 'raise NeuerFehler(...) from e' verkettet die urspruengliche
            # Ausnahme, sodass der vollstaendige Traceback / die Ursache zur
            # Fehlersuche erhalten bleibt.
            raise RuntimeError(
                "VL53L3CX native driver not found. On Raspberry Pi install build tools and "
                "the extension (PyPI wheel is armv7-only; use pip from Git on aarch64):\n"
                "  sudo apt install build-essential python3-dev git\n"
                "  pip install -r requirements-rpi.txt\n"
                f"Details: {e}"
            ) from e

        # Erzeuge das Treiber-Objekt. Dies prueft den I2C-Bus und verifiziert,
        # dass der Sensor unter der angegebenen Adresse antwortet.
        self._tof = _VL53(i2c_bus=self._i2c_bus, i2c_address=self._i2c_address)
        # Oeffne den Bus und initialisiere die interne Zustandsmaschine des
        # Sensors. reset=False bedeutet: die Hardware-Reset-Leitung nicht
        # umschalten.
        self._tof.open(reset=False)
        # Die ST-API erwartet genau diese Reihenfolge: erst Distanzmodus setzen,
        # dann Timing-Budget, dann das kontinuierliche Messen starten.
        self._tof.set_distance_mode(self._distance_mode)
        self._tof.set_timing_budget(self._timing_budget_us)
        self._tof.start_ranging()
        # Loesche einen evtl. veralteten Cache aus einem frueheren Lauf.
        self._last = None

    # configure() wendet neue Einstellungen WAEHREND des Betriebs an (wird
    # aufgerufen, wenn der Nutzer die GUI-Dropdowns aendert). Ueberschreibt
    # BaseSensor.configure.
    def configure(self, distance_mode: int, timing_budget_us: int) -> None:
        # Merke dir die neuen Einstellungen (damit ein spaeteres start() sie
        # ebenfalls verwendet).
        self._distance_mode = distance_mode
        self._timing_budget_us = timing_budget_us
        # GUARD CLAUSE (Schutzklausel): Wurde der Sensor nie gestartet, gibt es
        # nichts zu rekonfigurieren -> einfach frueh zurueckkehren. Frueh
        # zurueckkehren haelt den Code flach (keine tiefe Verschachtelung).
        if self._tof is None:
            return
        # Der ST-Treiber moechte, dass das Messen vor einer
        # Konfigurationsaenderung gestoppt wird, also: stop -> anwenden -> neu
        # starten.
        self._tof.stop_ranging()
        self._tof.set_distance_mode(distance_mode)
        self._tof.set_timing_budget(timing_budget_us)
        self._tof.start_ranging()
        self._last = None

    # read() holt eine Messung und gibt ein SensorReading zurueck.
    def read(self) -> SensorReading:
        # GUARD: Lesen verweigern, wenn start() nicht zuvor aufgerufen wurde.
        if self._tof is None:
            raise RuntimeError("Sensor not started")

        # Halte die aktuelle Zeit EINMAL fest, damit alle Vergleiche unten
        # konsistent sind.
        now = time.time()
        # 'fresh' ist True, wenn wir eine zwischengespeicherte gueltige Messung
        # haben, die juenger als stale_timeout_s ist. HINWEIS: _last speichert
        # immer nur GUELTIGE Messungen (siehe unten in dieser Methode), daher ist
        # die Wiederverwendung sicher. Die Klammern erlauben, dass der boolesche
        # Ausdruck ueber zwei Zeilen geht.
        fresh = (self._last is not None
                 and (now - self._last.timestamp) < self._stale_timeout_s)

        # is_ranging_ready() fragt den C-Treiber, ob eine NEUE Messung fertig ist.
        # Wenn nicht, gib den zwischengespeicherten Wert zurueck (falls frisch),
        # sonst melde Status 2 ("wartet"). 'A if cond else B' ist Pythons
        # einzeiliges if/else (Ternaeroperator).
        if not self._tof.is_ranging_ready():
            return self._last if fresh else SensorReading(distance_mm=0, status=2)

        # Frage den C-Treiber nach der Distanz in mm. Er liefert eine Ganzzahl
        # oder -1 bei einem ungueltigen Frame. int(...) stellt sicher, dass es
        # ein einfacher Python-int ist.
        raw = int(self._tof.get_distance())

        # Ungueltige Frames verwerfen: negativ (Treiberfehler), >= 8000 (ST
        # ungueltig) oder genau 8191 (kein-Ziel-Sentinel). Der VL53L3CX laesst
        # zwischendurch gute Frames fallen; statt 0 zurueckzugeben (was den Graph
        # flackern liess), HALTEN wir den letzten guten Wert, solange er noch
        # frisch ist.
        if raw <= 0 or raw >= _ST_INVALID_HIGH or raw == _NO_TARGET_MM:
            return self._last if fresh else SensorReading(distance_mm=0, status=4)

        # Wir haben eine gute Messung: bauen, als letzten gueltigen Wert
        # zwischenspeichern und zurueckgeben.
        reading = SensorReading(distance_mm=raw, status=0)
        self._last = reading
        return reading

    # stop() faehrt den Sensor sauber herunter.
    def stop(self) -> None:
        # Nur etwas tun, wenn wir tatsaechlich gestartet wurden.
        if self._tof is not None:
            # Wir umschliessen jeden Aufruf mit try/except, weil die Hardware
            # bereits weg sein koennte (Stromverlust, abgesteckt).
            # 'except Exception: pass' heisst "jeden Fehler ignorieren und
            # weitermachen" -- beim Herunterfahren waere ein Absturz schlimmer als
            # ein still uebersprungener Aufraeumschritt.
            try:
                self._tof.stop_ranging()
            except Exception:
                pass
            try:
                self._tof.close()
            except Exception:
                pass
            # Auf den nicht-gestarteten Zustand zuruecksetzen, damit start()
            # spaeter erneut laufen kann.
            self._tof = None
        self._last = None


# =============================================================================
# 4) NetworkSensor  --  der Stellvertreter auf der LAPTOP-SEITE. Gleiche
#    Schnittstelle, spricht aber ueber TCP.
# =============================================================================
# Fuer die GUI sieht das identisch zu VL53L3CXSensor aus, aber statt Hardware
# anzufassen, sendet er winzige Text-Anfragen an sensor_server.py auf dem Pi und
# parst die Antworten. Das ist die Magie, die es der schweren GUI erlaubt, auf
# dem Laptop zu laufen.
class NetworkSensor(BaseSensor):
    """
    Reads sensor data from a Raspberry Pi running sensor_server.py over the LAN.
    Lets the PyQt GUI run natively on a laptop while the real sensor stays on the Pi.

    Protocol: client sends a byte, server replies "distance_mm,status\\n".
    """

    # Konstruktor. 'host' ist Pflicht (die IP des Pi); port und timeout haben
    # Standardwerte. 'timeout: float = 5.0' = maximal 5 Sekunden auf
    # Netzwerkoperationen warten.
    def __init__(self, host: str, port: int = 9999, timeout: float = 5.0):
        self._host = host
        self._port = port
        self._timeout = timeout
        # Das Socket-Objekt, None bis start() verbindet.
        self._sock: Optional[socket.socket] = None
        # Ein EMPFANGS-PUFFER. b"" ist ein leeres BYTES-Literal (TCP arbeitet mit
        # Bytes, nicht mit Text). TCP ist ein Datenstrom: Daten koennen in
        # mehreren Stuecken ankommen, daher sammeln wir Bytes hier, bis wir eine
        # vollstaendige Zeile haben, die mit '\n' endet, und schneiden dann eine
        # Zeile ab.
        self._buf = b""

    # start() oeffnet die TCP-Verbindung zum Pi.
    def start(self) -> None:
        # socket.create_connection((host, port)) erledigt den DNS- und
        # Verbindungsaufbau und liefert ein fertiges Socket. Es blockiert, bis
        # verbunden oder bis der Timeout greift, und wirft dann OSError, wenn der
        # Pi nicht erreichbar ist.
        self._sock = socket.create_connection((self._host, self._port), timeout=self._timeout)
        # Lass auch einzelne send/recv-Aufrufe per Timeout abbrechen, damit ein
        # eingefrorener Pi die GUI nicht ewig blockiert.
        self._sock.settimeout(self._timeout)
        # Mit leerem Puffer starten.
        self._buf = b""

    # configure() sendet einen Rekonfigurations-Befehl ueber dasselbe Socket an
    # den Server. Ueberschreibt BaseSensor.configure.
    def configure(self, distance_mode: int, timing_budget_us: int) -> None:
        # GUARD: kann nicht senden, wenn nicht verbunden.
        if self._sock is None:
            return
        try:
            # Baue den Befehls-String, z. B. "c3,50000\n", und .encode() ihn zu
            # Bytes. Das fuehrende 'c' sagt dem Server "das ist Konfiguration,
            # keine Lese-Anfrage". sendall() sendet weiter, bis jedes Byte
            # uebertragen ist (ein einzelnes send() koennte nur einen Teil
            # senden).
            self._sock.sendall(f"c{distance_mode},{timing_budget_us}\n".encode())
            # Lies, bis wir die Antwortzeile des Servers ("ok\n") empfangen haben.
            # recv(64) empfaengt bis zu 64 Bytes; wir haengen sie an den Puffer.
            while b"\n" not in self._buf:
                data = self._sock.recv(64)
                # Leere Bytes bedeuten, der Pi hat die Verbindung geschlossen.
                if not data:
                    return
                self._buf += data
            # Schneide die erste Zeile ab und VERWIRF sie (wir brauchten nur die
            # Bestaetigung). split(b"\n", 1) trennt nur am ersten Zeilenumbruch;
            # die Wegwerf-Variable '_' haelt das "ok", das wir ignorieren, und
            # self._buf behaelt evtl. uebrige Bytes fuer das naechste Mal.
            _, self._buf = self._buf.split(b"\n", 1)
        # Falls das Socket mitten in der Konfiguration einen Fehler hat,
        # ignorieren; das naechste read() wird das Problem sichtbar machen.
        except OSError:
            pass

    # read() fordert eine Messung vom Server an und parst die Antwort.
    def read(self) -> SensorReading:
        # GUARD: muss zuerst gestartet/verbunden sein.
        if self._sock is None:
            raise RuntimeError("NetworkSensor not started")
        try:
            # Sende ein einzelnes Byte b"r" = "gib mir eine Messung".
            self._sock.sendall(b"r")
            # Sammle Bytes, bis eine vollstaendige, mit Zeilenumbruch beendete
            # Zeile ankommt.
            while b"\n" not in self._buf:
                data = self._sock.recv(64)
                # Verbindung getrennt -> melde eine Fehlermessung.
                if not data:
                    return SensorReading(distance_mm=0, status=1)
                self._buf += data
            # Schneide die erste vollstaendige Zeile ab; behalte den Rest im
            # Puffer.
            line, self._buf = self._buf.split(b"\n", 1)
            # Bytes -> str dekodieren, Leerzeichen entfernen, am Komma trennen.
            # Der Server sendet z. B. "412,0", was ["412", "0"] ergibt; Python
            # entpackt das in zwei Variablen gleichzeitig.
            dist_s, status_s = line.decode().strip().split(",")
            # Die beiden Textstuecke in ints umwandeln und in ein Reading packen.
            return SensorReading(distance_mm=int(dist_s), status=int(status_s))
        # Fange die drei realistischen Fehler ab und verwandle sie in eine
        # Fehlermessung, statt die GUI abstuerzen zu lassen:
        #   socket.timeout -> Pi hat nicht rechtzeitig geantwortet,
        #   OSError        -> Verbindungsproblem,
        #   ValueError     -> Antwort war fehlerhaft (z. B. int("") schlug fehl).
        except (socket.timeout, OSError, ValueError):
            return SensorReading(distance_mm=0, status=1)

    # stop() schliesst die Verbindung.
    def stop(self) -> None:
        if self._sock is not None:
            # Schliessen kann fehlschlagen, wenn schon kaputt; das ignorieren.
            try:
                self._sock.close()
            except Exception:
                pass
            # Zurueck in den nicht-verbundenen Zustand.
            self._sock = None
