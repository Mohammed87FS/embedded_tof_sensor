#!/usr/bin/python
# =============================================================================
# vl53l3cx_driver.py  --  DIE HARDWARE-NAHE ANBINDUNG (VENDORED / uebernommen)
# -----------------------------------------------------------------------------
# WICHTIG FUER DIE VERTEIDIGUNG: Diese Datei ist VENDORED (kopiert) aus einem
# Open-Source-Projekt, also NICHT selbst geschrieben. Quelle:
#   https://github.com/FrgyCZ/VL53L3CX-python  (Datei python/VL53L3CX.py)
# Es ist die duenne Python-Schicht, die ST's kompilierten C-Treiber (eine
# .so-Shared-Library) laedt und Python erlaubt, dessen Funktionen aufzurufen. ST
# hat den schweren C-Mess-Code geschrieben; diese Datei baut nur die Bruecke
# Python <-> C und stellt den I2C-Transport bereit.
#
# Zwei grosse Konzepte leben hier:
#   1. ctypes  -> Pythons eingebaute Moeglichkeit, Funktionen IN einer
#                 kompilierten C-Bibliothek (.so) direkt aufzurufen, ohne
#                 selbst C-Glue-Code zu schreiben.
#   2. I2C-Callbacks -> der C-Treiber weiss nicht, wie man den I2C-Bus des Pi
#                 benutzt. Also geben wir ihm zwei PYTHON-Funktionen (Lesen/
#                 Schreiben), die er ZURUECKRUFT, wann immer er den Bus
#                 ansprechen muss. Diese implementieren wir mit der Bibliothek
#                 'smbus2'.
# -----------------------------------------------------------------------------
# (Der originale Copyright-/Lizenz-Header steht unten und MUSS laut MIT-Lizenz
#  beim Code bleiben: der Hinweis muss erhalten werden.)
# =============================================================================

# Vendored from https://github.com/FrgyCZ/VL53L3CX-python (python/VL53L3CX.py).
# Requires vl53l3cx_python*.so from: pip install -r requirements-rpi.txt

# MIT License
#
# Copyright (c) 2017 John Bryan Moore
# Copyright (c) 2024 Jakub Frgal
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# ----------------------------------------------------------------------------
# ctypes-Imports: das Werkzeug, um C aus Python aufzurufen.
#   CDLL      -> laedt eine Shared Library (.so), damit wir ihre Funktionen
#                aufrufen koennen.
#   CFUNCTYPE -> baut aus einer Python-Funktion einen von C aufrufbaren
#                Funktions-TYP (um unsere I2C-Callbacks an den C-Treiber zu geben).
#   POINTER   -> repraesentiert einen C-Zeiger auf einen Typ.
#   c_int, c_ubyte, c_uint16 -> C-Ganzzahltypen (signed int, unsigned byte,
#                unsigned 16-bit), damit die uebergebenen Daten zu dem passen, was
#                C erwartet.
from ctypes import CDLL, CFUNCTYPE, POINTER, c_int, c_ubyte, c_uint16
# smbus2: eine reine Python-Bibliothek, um mit dem Linux-I2C-Bus zu sprechen.
#   SMBus   -> repraesentiert einen offenen I2C-Bus (z. B. /dev/i2c-1).
#   i2c_msg -> baut Low-Level-I2C-Lese-/Schreib-Nachrichten fuer kombinierte
#              Transfers.
from smbus2 import SMBus, i2c_msg
# Standardbibliothek-Helfer, um die .so-Datei auf der Festplatte zu finden.
import os      # Pfad-Manipulation (dirname, realpath).
import site    # sagt, wo pip Pakete installiert (site-packages-Verzeichnisse).
import glob    # Dateinamen-Mustersuche (findet vl53l3cx_python*.so).


# ----------------------------------------------------------------------------
# Definiere den C-TYP unserer I2C-Callback-Funktionen, damit der C-Treiber sie
# aufrufen kann. CFUNCTYPE(rueckgabetyp, *argument_typen) beschreibt eine
# C-Funktionssignatur:
#   Rueckgabe: c_int (Statuscode)
#   Argumente: c_ubyte (Geraeteadresse), c_uint16 (Register), POINTER(c_ubyte)
#              (Datenpuffer), c_ubyte (Laenge)
# Das passt exakt zu dem, was ST's C-Code fuer seine Lese-/Schreib-Hooks erwartet.
# ----------------------------------------------------------------------------
_I2C_READ_FUNC = CFUNCTYPE(c_int, c_ubyte, c_uint16, POINTER(c_ubyte), c_ubyte)
_I2C_WRITE_FUNC = CFUNCTYPE(c_int, c_ubyte, c_uint16, POINTER(c_ubyte), c_ubyte)

# ----------------------------------------------------------------------------
# Finde und lade die kompilierte C-Bibliothek (vl53l3cx_python*.so).
# Wir durchsuchen mehrere Verzeichnisse, weil pip die .so je nach System an
# unterschiedlichen Orten installieren kann.
# ----------------------------------------------------------------------------
# Beginne mit dem Ordner, in dem diese .py-Datei liegt. __file__ ist der Pfad
# dieser Datei; realpath loest Symlinks auf; dirname nimmt den Ordner darueber.
_POSSIBLE_LIBRARY_LOCATIONS = [os.path.dirname(os.path.realpath(__file__))]

# Fuege die globalen site-packages-Verzeichnisse hinzu (wo pip normal
# installiert). Manche minimalen Python-Builds haben diese Funktion nicht, daher
# mit try/except absichern.
try:
    # '+=' bei einer Liste haengt alle Elemente der rechten Liste an.
    _POSSIBLE_LIBRARY_LOCATIONS += site.getsitepackages()
except AttributeError:
    pass

# Fuege auch das benutzereigene site-packages-Verzeichnis hinzu
# (pip install --user), erneut abgesichert, falls nicht verfuegbar.
try:
    _POSSIBLE_LIBRARY_LOCATIONS += [site.getusersitepackages()]
except AttributeError:
    pass

# Gehe jeden Kandidaten-Ordner durch und suche die .so-Datei.
for lib_location in _POSSIBLE_LIBRARY_LOCATIONS:
    # glob liefert eine Liste von Pfaden, die zum Platzhalter-Muster '*' passen.
    files = glob.glob(lib_location + "/vl53l3cx_python*.so")
    # Wenn wir in diesem Ordner mindestens einen Treffer gefunden haben ...
    if len(files) > 0:
        lib_file = files[0]
        try:
            # ... lade ihn mit CDLL. Bei Erfolg speichern und Suche beenden.
            _TOF_LIBRARY = CDLL(lib_file)
            break  # 'break' verlaesst die for-Schleife vorzeitig.
        except OSError as e:
            # Die Datei existiert, liess sich aber nicht laden (falsche
            # Architektur usw.).
            print("Could not load library: {}".format(e))
# 'for ... else': der else-Zweig laeuft NUR, wenn die Schleife OHNE 'break' zu
# Ende ging (also keine Bibliothek erfolgreich geladen wurde). Dann koennen wir
# nicht fortfahren.
else:
    raise OSError('Could not find vl53l3cx_python.so')


# ============================================================================
# VL53L3CX: die Python-Wrapper-Klasse um die geladene C-Bibliothek.
# ============================================================================
class VL53L3CX:
    """VL53L3CX ToF."""
    # Konstruktor. Standardwerte: I2C-Bus 1, Adresse 0x29.
    def __init__(self, i2c_bus=1, i2c_address=0x29):
        """Initialize the VL53L3X ToF Sensor from ST"""
        self._i2c_bus = i2c_bus
        self.i2c_address = i2c_address

        # Erzeuge ein SMBus-Objekt (hier noch nicht fuer das Messen geoeffnet;
        # gleich nur kurz geoeffnet, um die Anwesenheit des Sensors zu pruefen).
        self._i2c = SMBus()
        # Haelt die zuletzt gemessene Distanz; -1 bedeutet "noch keine Messung".
        self.distance = -1
        # ANWESENHEITS-PRUEFUNG: Bus oeffnen, ein Byte von der Sensoradresse zu
        # lesen versuchen. Ist er nicht da, wird ein IOError ausgeloest.
        try:
            self._i2c.open(bus=self._i2c_bus)
            # read_byte_data(addr, register) liest Register 0x00 vom Geraet.
            self._i2c.read_byte_data(self.i2c_address, 0x00)
        except IOError:
            # Verwandle den Low-Level-IOError in eine klarere Meldung. format()
            # fuegt die Adresse als 2-stelligen Hex-Wert ein (:02x).
            raise RuntimeError("VL53L3CX not found on adddress: {:02x}".format(self.i2c_address))
        finally:
            # 'finally' laeuft immer: Bus schliessen, egal ob es geklappt hat,
            # damit er nach dieser Pruefung nicht offen bleibt.
            self._i2c.close()

        # Haelt spaeter einen undurchsichtigen Zeiger auf das C-"Geraete"-Objekt,
        # sobald open() laeuft.
        self._dev = None

    # open(): den Sensor vollstaendig fuer das Messen initialisieren.
    def open(self, reset=False):
        # Den I2C-Bus fuer die eigentliche Sitzung erneut oeffnen.
        self._i2c.open(bus=self._i2c_bus)
        # Registriere unsere Python-I2C-Lese-/Schreib-Callbacks bei der
        # C-Bibliothek.
        self._configure_i2c_library_functions()
        # Rufe die C-Funktion 'initialise(adresse, reset)' auf. Sie gibt einen
        # Zeiger auf die Geraetestruktur zurueck, den wir behalten und an jeden
        # spaeteren Aufruf uebergeben.
        self._dev = _TOF_LIBRARY.initialise(self.i2c_address, reset)

    # close(): den Bus freigeben und den Geraete-Handle vergessen.
    def close(self):
        self._i2c.close()
        self._dev = None

    # Diese Methode definiert die zwei Callbacks, die der C-Treiber nutzt, um mit
    # dem I2C-Bus zu sprechen, und uebergibt sie dann der Bibliothek. Der C-Code
    # ruft ZURUECK in diese Python-Funktionen, wann immer er ein Sensor-Register
    # lesen/schreiben muss.
    def _configure_i2c_library_functions(self):
        # --- LESE-Callback ---
        # Wird von C aufgerufen mit: Geraeteadresse, Register, einem C-Puffer-
        # Zeiger zum Befuellen und der Anzahl zu lesender Bytes.
        def _i2c_read(address, reg, data_p, length):
            ret_val = 0

            # Baue eine 2-Byte-SCHREIB-Nachricht mit der 16-Bit-Registeradresse
            # (erst High-Byte, dann Low-Byte) -- das sagt dem Sensor, welches
            # Register wir wollen.
            msg_w = i2c_msg.write(address, [reg >> 8, reg & 0xff])
            # Baue eine LESE-Nachricht, die 'length' Bytes anfordert.
            msg_r = i2c_msg.read(address, length)

            # i2c_rdwr fuehrt eine kombinierte Schreib-dann-Lese-Transaktion aus
            # (einen "repeated start"), wie das Sensorprotokoll es verlangt.
            self._i2c.i2c_rdwr(msg_w, msg_r)

            # Kopiere die empfangenen Bytes zurueck in den C-Puffer 'data_p',
            # damit der C-Code sie sehen kann. ord() wandelt jedes erhaltene Byte
            # in eine Ganzzahl.
            if ret_val == 0:
                for index in range(length):
                    data_p[index] = ord(msg_r.buf[index])

            # 0 zurueckgeben = Erfolg, wie es die C-Seite erwartet.
            return ret_val

        # --- SCHREIB-Callback ---
        # Wird von C aufgerufen mit: Adresse, Register, Puffer mit zu sendenden
        # Daten, Laenge.
        def _i2c_write(address, reg, data_p, length):
            ret_val = 0
            data = []

            # Kopiere die Bytes des C-Puffers in eine Python-Liste.
            for index in range(length):
                data.append(data_p[index])

            # Baue eine SCHREIB-Nachricht: 16-Bit-Registeradresse gefolgt von den
            # Datenbytes (Listen-Verkettung mit '+').
            msg_w = i2c_msg.write(address, [reg >> 8, reg & 0xff] + data)

            # Fuehre das Schreiben aus.
            self._i2c.i2c_rdwr(msg_w)

            return ret_val

        # Verpacke die zwei Python-Funktionen mit den oben definierten
        # CFUNCTYPE-Typen in von C aufrufbare Funktionszeiger. Wir MUESSEN
        # Referenzen darauf in 'self' behalten, damit Pythons Garbage Collector
        # sie nicht freigibt, solange C die Zeiger noch haelt (eine klassische
        # ctypes-Falle: sonst Absturz).
        self._i2c_read_func = _I2C_READ_FUNC(_i2c_read)
        self._i2c_write_func = _I2C_WRITE_FUNC(_i2c_write)
        # Uebergib beide Zeiger der C-Bibliothek, damit sie unseren Bus nutzen kann.
        _TOF_LIBRARY.VL53LX_set_i2c(self._i2c_read_func, self._i2c_write_func)

    # Die restlichen Methoden sind duenne Einzeiler-Wrapper: jeder ruft nur die
    # passende C-Funktion in der .so auf und uebergibt unseren Geraetezeiger
    # self._dev.

    def start_ranging(self):
        """Start VL53L3CX ToF Sensor Ranging"""
        _TOF_LIBRARY.startRanging(self._dev)

    def set_distance_mode(self, mode):
        """Set distance mode

        :param mode: One of 1 = Short, 2 = Medium or 3 = Long

        """
        _TOF_LIBRARY.setDistanceMode(self._dev, mode)

    def stop_ranging(self):
        """Stop VL53L3CX ToF Sensor Ranging"""
        return _TOF_LIBRARY.stopRanging(self._dev)

    def get_distance(self):
        """Get distance from VL53L3CX ToF Sensor"""
        # Frage die C-Bibliothek nach der aktuellen Distanz (mm), speichere und
        # gib sie zurueck. Intern liest der C-Code Mehrziel-Daten, gibt aber nur
        # die Reichweite des NAECHSTEN Objekts zurueck, oder -1, wenn kein
        # gueltiges Ziel gefunden wurde. (Das ist der Grund, warum Mehrziel-
        # Anzeige eine Neukompilierung des C-Codes braeuchte.)
        self.distance = _TOF_LIBRARY.getDistance(self._dev)
        return self.distance

    def is_ranging_ready(self):
        """Check if ranging data is ready"""
        # Liefert ungleich null / True, wenn eine frische Messung zum Abholen
        # bereit ist.
        return _TOF_LIBRARY.isRangingReady(self._dev)

    def set_timing_budget(self, timing_budget):
        """Set the timing budget in microseocnds"""
        _TOF_LIBRARY.setMeasurementTimingBudgetMicroSeconds(self._dev, timing_budget)
