#!/usr/bin/python
# =============================================================================
# vl53l3cx_driver.py  --  DIE HARDWARE-NAHE ANBINDUNG (VENDORED / uebernommen)
# =============================================================================
#
# DAS MENTALE MODELL IN EINEM SATZ
# --------------------------------
# Diese Datei ist KEINE Mess-Software. Sie ist eine BRUECKE zwischen 
# Python und ST's
# fertig kompiliertem C-Treiber (schnell, kennt den Sensor in- und auswendig,
# weiss aber NICHTS von dem Raspberry Pi). 
#
# DIE ZWEI RICHTUNGEN 
# ---------------------------------------------------
#   Richtung 1  Python -> C : Wir rufen ST's C-Funktionen auf (z.B. getDistance).
#                           
#   Richtung 2  C -> Python : ST's C-Code ruft ZURUECK in unsere Python-Funktionen,
#                             naemlich immer dann, wenn er den I2C-Bus benutzen
#                             muss. 
#
# WARUM ueberhaupt diese Umkehrung?
# ---------------------------------
# ST hat ihren Treiber PORTABEL geschrieben. Er soll auf einem STM32, einem
# Arduino, einem Pi laufen -- . Deshalb hat ST KEINEN Bus-Code fest
# eingebaut. Stattdessen sagt der Treiber: "Gib mir zwei Funktionen, eine zum
# Lesen und eine zum Schreiben von Bytes. Wie du das auf DEINER Plattform
# machst, ist dein Problem." Wir liefern diese zwei Funktionen (mit smbus2,
# das den Linux-I2C-Treiber benutzt) und reichen sie als FUNKTIONSZEIGER an C
# durch. Der Treiber ruft sie dann selbststaendig auf.
#
# diese datei ist (kopiert) aus einem
# Open-Source-Projekt, also NICHT selbst geschrieben. Quelle:
#   https://github.com/FrgyCZ/VL53L3CX-python  (Datei python/VL53L3CX.py)
#
# Zwei Werkzeuge machen die Bruecke moeglich:
#   1. ctypes  -> Pythons eingebaute Faehigkeit, Funktionen IN einer
#                 kompilierten C-Bibliothek (.so) direkt aufzurufen. ctypes
#                 ubersetzt zur Laufzeit zwischen Python-Objekten und der
#                 rohen Byte-Darstellung, die C auf dem Stack erwartet.
#   2. I2C-Callbacks -> die zwei Python-Funktionen (Lesen/Schreiben), die der
#                 C-Treiber zurueckruft. Implementiert mit 'smbus2'.


# ----------------------------------------------------------------------------
# ctypes-Imports -- das Werkzeug, um C aus Python aufzurufen.
#
#   CDLL      -> laedt eine Shared Library (.so) zur Laufzeit.
#                Das zurueckgegebene Objekt hat als Attribute genau
#                die exportierten C-Funktionen: lib.getDistance(...) ruft die
#                C-Funktion getDistance auf.
#   CFUNCTYPE -> CFUNCTYPE legt fest, wie eine C-Funktion aussieht, 
#                also welchen Rückgabewert sie hat und welche Argumente sie erwartet. 
#                Wenn du damit eine Python-Funktion verpackst, kann C diese Funktion aufrufen. 
#                ctypes sorgt dann dafür, dass die Werte zwischen C und Python richtig umgewandelt werden:
#                Es nimmt die C-Werte entgegen, 
#                macht Python-Objekte daraus, ruft die Python-Funktion auf
#                und gibt das Ergebnis wieder in C-Form zurück.
#   POINTER   -> repraesentiert einen C-Zeiger auf einen Typ. POINTER(c_ubyte)
#                ist also "Zeiger auf unsigned byte", d.h. ein roher Bytepuffer,
#                in den/aus dem C liest und schreibt.
#   c_int, c_ubyte, c_uint16 -> exakte C-Ganzzahltypen (signed int 32-bit,
#                unsigned 8-bit, unsigned 16-bit). Sie MUESSEN bitgenau zu dem
#                passen, was ST's C-Prototyp deklariert -- sonst landen falsche
#                Bytes an falschen Stellen (Absturz oder Datenmuell).
from ctypes import CDLL, CFUNCTYPE, POINTER, c_int, c_ubyte, c_uint16
# smbus2: eine reine Python-Bibliothek fuer den Linux-I2C-Bus.
#   SMBus   -> ein offener I2C-Bus (z.B. /dev/i2c-1). Intern ein Datei-
#              Deskriptor, ueber den ioctl()-Aufrufe an den Kernel gehen.
#   i2c_msg -> baut einzelne Low-Level-I2C-Nachrichten (write/read), die man
#              zu KOMBINIERTEN Transfers zusammensetzen kann (siehe i2c_rdwr).
from smbus2 import SMBus, i2c_msg
# Standardbibliothek-Helfer, nur um die .so-Datei auf der Platte zu finden.
import os      # Pfad-Manipulation (dirname, realpath).
import site    # sagt, wo pip Pakete installiert (site-packages-Verzeichnisse).
import glob    # Dateinamen-Mustersuche mit Platzhaltern (findet *.so).


# ----------------------------------------------------------------------------
# DIE C-SIGNATUR DER CALLBACKS DEKLARIEREN  (Richtung 2 wird hier vorbereitet)
# ----------------------------------------------------------------------------
# Augenoeffnender Punkt: Diese zwei Zeilen TUN noch nichts -- sie sind reine
# TYP-Deklarationen
#
# C ist statisch typisiert und hat zur Laufzeit KEINE Typ-Information. Wenn der
# C-Treiber einen Funktionszeiger aufruft, legt er nur Bytes in einer FESTEN
# Reihenfolge auf den Stack und springt. C "weiss" nicht, dass dahinter Python
# steckt. Damit ctypes die Bytes korrekt auspacken kann, muessen WIR den
# Bauplan liefern:
#
#   CFUNCTYPE(rueckgabetyp, *argument_typen)
#     Rueckgabe: c_int                -> ein Statuscode (0 = OK)
#     Arg 1:     c_ubyte              -> I2C-Geraeteadresse (z.B. 0x29)
#     Arg 2:     c_uint16             -> 16-Bit-Registeradresse im Sensor
#     Arg 3:     POINTER(c_ubyte)     -> Zeiger auf den Bytepuffer
#     Arg 4:     c_ubyte              -> Anzahl der Bytes (Laenge)
#
# Diese Signatur ist NICHT frei waehlbar -- sie muss EXAKT dem Prototyp
# entsprechen, den ST im C-Code fuer seine Lese-/Schreib-Hooks erwartet. Ein
# einziger falscher Typ hier = Absturz waehrend des Messens.
# ----------------------------------------------------------------------------
_I2C_READ_FUNC = CFUNCTYPE(c_int, c_ubyte, c_uint16, POINTER(c_ubyte), c_ubyte)
_I2C_WRITE_FUNC = CFUNCTYPE(c_int, c_ubyte, c_uint16, POINTER(c_ubyte), c_ubyte)

# ----------------------------------------------------------------------------
# DIE KOMPILIERTE C-BIBLIOTHEK FINDEN UND LADEN (vl53l3cx_python*.so)
# ----------------------------------------------------------------------------
# Problem: pip legt kompilierte Erweiterungen je nach System an unterschiedliche
# Orte. Wir sammeln deshalb mehrere Kandidaten-Verzeichnisse und durchsuchen
# sie der Reihe nach.
# ----------------------------------------------------------------------------
# Start: der Ordner, in dem GENAU DIESE .py-Datei liegt.
#   __file__              = Pfad dieser Datei
#   os.path.realpath(...) = loest Symlinks zu einem echten Pfad auf
#   os.path.dirname(...)  = schneidet den Dateinamen ab, behaelt den Ordner
_POSSIBLE_LIBRARY_LOCATIONS = [os.path.dirname(os.path.realpath(__file__))]

# Globale site-packages-Verzeichnisse anhaengen (wo pip normalerweise landet).
# Manche minimalen Python-Builds (z.B. in manchen Containern) haben
# site.getsitepackages() nicht -> deshalb try/except als Absicherung.
try:
    # '+=' bei einer Liste haengt alle Elemente der rechten Liste an (extend).
    _POSSIBLE_LIBRARY_LOCATIONS += site.getsitepackages()
except AttributeError:
    pass

# Auch das benutzereigene site-packages anhaengen (Fall: pip install --user).
# Wieder abgesichert, falls die Funktion fehlt.
try:
    _POSSIBLE_LIBRARY_LOCATIONS += [site.getusersitepackages()]
except AttributeError:
    pass

# Jeden Kandidaten-Ordner durchgehen und nach der .so suchen.
for lib_location in _POSSIBLE_LIBRARY_LOCATIONS:
    # Der Stern '*' im Muster ist wichtig: pip benennt kompilierte Module mit
    # Plattform-Tags, z.B. "vl53l3cx_python.cpython-311-aarch64-linux-gnu.so".
    # Ein exakter Name wuerde NICHT treffen -- der Platzhalter schon.
    files = glob.glob(lib_location + "/vl53l3cx_python*.so")
    # Mindestens ein Treffer in diesem Ordner?
    if len(files) > 0:
        lib_file = files[0]
        try:
            # CDLL = das eigentliche Laden (dlopen). Bei Erfolg merken wir uns
            # das Handle global und brechen die Suche ab.
            _TOF_LIBRARY = CDLL(lib_file)
            break  # 'break' verlaesst die for-Schleife sofort.
        except OSError as e:
            # Datei existiert, liess sich aber nicht laden -- klassischer Fall:
            # falsche CPU-Architektur (z.B. ARM-.so auf x86), fehlende
            # abhaengige Bibliothek. Wir geben den Fehler aus und probieren
            # den naechsten Kandidaten.
            print("Could not load library: {}".format(e))
# 'for ... else' (eine oft uebersehene Python-Eigenheit): der else-Zweig laeuft
# NUR, wenn die Schleife komplett durchlief OHNE je 'break' zu erreichen -- also
# wenn KEINE Bibliothek erfolgreich geladen wurde. Eleganter als ein
# 'gefunden = False'-Flag: "scheitere erst, nachdem alle Optionen erschoepft sind".
else:
    raise OSError('Could not find vl53l3cx_python.so')


# ============================================================================
# VL53L3CX: die Python-Wrapper-Klasse um die geladene C-Bibliothek.
# Sie haelt den Bus-Zugang, die Callback-Zeiger am Leben 
# und bietet nach aussen eine saubere, pythonische API.
# ============================================================================
class VL53L3CX:
    """VL53L3CX ToF."""

    # ------------------------------------------------------------------------
    # Konstruktor. Standardwerte: I2C-Bus 1 (/dev/i2c-1), Adresse 0x29
    # (Werksadresse des VL53L3CX).
    # ------------------------------------------------------------------------
    def __init__(self, i2c_bus=1, i2c_address=0x29):
        """Initialize the VL53L3X ToF Sensor from ST"""
        self._i2c_bus = i2c_bus
        self.i2c_address = i2c_address

        # SMBus-Objekt erzeugen, aber NOCH NICHT fuer die Mess-Sitzung oeffnen.
        # Gleich oeffnen wir es nur kurz, um zu pruefen, ob der Sensor da ist.
        self._i2c = SMBus()
        # Zuletzt gemessene Distanz; -1 = "es gab noch keine gueltige Messung".
        self.distance = -1

        # --- ANWESENHEITS-PRUEFUNG (rein in Python, ganz ohne den C-Treiber) ---
        # Idee: ein billiger "Ist der Sensor ueberhaupt am Bus?"-Test BEVOR wir
        # die schwere C-Maschinerie anwerfen. Wir oeffnen den Bus und lesen
        # versuchsweise ein einzelnes Byte aus Register 0x00.
        try:
            self._i2c.open(bus=self._i2c_bus)
            # read_byte_data(adresse, register): liest 1 Byte aus Register 0x00.
            # Antwortet an Adresse 0x29 niemand mit einem ACK, meldet der Kernel
            # einen IOError zurueck.
            self._i2c.read_byte_data(self.i2c_address, 0x00)
        except IOError:
            # Den technischen Low-Level-IOError in eine sprechende Meldung
            # uebersetzen. '{:02x}' formatiert die Adresse als 2-stellige
            # Hex-Zahl in Kleinbuchstaben (-> "29").
            raise RuntimeError("VL53L3CX not found on adddress: {:02x}".format(self.i2c_address))
        finally:
            # 'finally' laeuft IMMER -- egal ob der Versuch klappte oder eine
            # Ausnahme flog. So bleibt nach der Pruefung garantiert kein
            # offener Bus / Datei-Deskriptor zurueck (kein Ressourcenleck).
            self._i2c.close()

        # Platzhalter fuer den spaeter erhaltenen, fuer Python UNDURCHSICHTIGEN
        # Zeiger auf C's Geraetestruktur. None heisst "noch nicht initialisiert".
        self._dev = None

    # ------------------------------------------------------------------------
    # open(): den Sensor VOLLSTAENDIG fuer das Messen scharf machen.
    # Reihenfolge ist hier kein Zufall, sondern Pflicht.
    # ------------------------------------------------------------------------
    def open(self, reset=False):
        # 1) Bus fuer die echte Mess-Sitzung (erneut) oeffnen.
        self._i2c.open(bus=self._i2c_bus)
        # 2) ZUERST die Callbacks registrieren -- der Treiber muss wissen, WIE
        #    er den Bus benutzt, BEVOR er bei der Initialisierung das erste Mal
        #    Register liest/schreibt.
        self._configure_i2c_library_functions()
        # 3) ERST DANN C's initialise(adresse, reset) aufrufen. Diese Funktion
        #    spricht intern bereits ueber unsere Callbacks mit dem Sensor und
        #    gibt einen Zeiger auf ihre interne Geraetestruktur zurueck. Diesen
        #    Handle behalten wir und reichen ihn an JEDEN spaeteren C-Aufruf.
        #    (Gleiches Muster wie ein FILE* in C: die Bibliothek besitzt den
        #    Zustand, wir halten nur das Handle.)
        self._dev = _TOF_LIBRARY.initialise(self.i2c_address, reset)

    # ------------------------------------------------------------------------
    # close(): Bus freigeben und den Geraete-Handle vergessen.
    # ------------------------------------------------------------------------
    def close(self):
        self._i2c.close()
        self._dev = None

    # ========================================================================
    # DAS HERZSTUECK: die zwei I2C-Callbacks definieren und bei C registrieren.
    # Hier passiert die Kontroll-UMKEHRUNG. Alles davor war Vorbereitung.
    # ========================================================================
    def _configure_i2c_library_functions(self):

        # ---------------------------- LESE-Callback ----------------------------
        # WICHTIG: Diese Funktion ruft NICHT WIR auf -- der C-Treiber ruft sie
        # auf, mitten in einer Messung, wann immer er ein Sensor-Register lesen
        # muss. C uebergibt: Geraeteadresse, Registeradresse, einen Zeiger auf
        # einen Bytepuffer (den WIR fuellen sollen) und die gewuenschte Laenge.
        #
        # Nebenbei: _i2c_read ist ein CLOSURE. Es ist innerhalb der Methode
        # definiert und "faengt" dabei 'self' aus dem Umfeld ein. Genau deshalb
        # kann es auf self._i2c zugreifen, obwohl C es voellig ohne 'self'
        # aufruft. Darum stehen die Callbacks hier drinnen und nicht als freie
        # Funktionen draussen.
        def _i2c_read(address, reg, data_p, length):
            ret_val = 0

            # Der VL53L3CX hat 16-BIT-Registeradressen. Um ein Register zu LESEN,
            # muss man dem Sensor erst SAGEN, welches Register man will -- das
            # geschieht ueber eine kurze SCHREIB-Nachricht mit den zwei
            # Adressbytes. Reihenfolge: erst High-Byte, dann Low-Byte (Big-Endian).
            #   reg >> 8   = die oberen 8 Bit (High-Byte)
            #   reg & 0xff = die unteren 8 Bit (Low-Byte)
            msg_w = i2c_msg.write(address, [reg >> 8, reg & 0xff])
            # Danach die eigentliche LESE-Nachricht, die 'length' Bytes anfordert.
            msg_r = i2c_msg.read(address, length)

            # AUGENOEFFNER: i2c_rdwr(msg_w, msg_r) schickt BEIDE Nachrichten als
            # EINE EINZIGE, ununterbrochene Transaktion an den Kernel. Zwischen
            # Schreiben und Lesen wird der Bus NICHT freigegeben -- es gibt einen
            # "repeated start" statt eines Stop. Genau das verlangt das
            # Sensorprotokoll: "sag mir das Register und lies sofort, ohne dass
            # jemand anderes dazwischenfunkt". Zwei getrennte Transfers wuerden
            # NICHT funktionieren.
            self._i2c.i2c_rdwr(msg_w, msg_r)

            # DER ENTSCHEIDENDE TRICK, wie die Daten zurueck zu C kommen:
            # Wir schreiben die empfangenen Bytes DURCH den Zeiger 'data_p'
            # direkt in den Speicher, der C GEHOERT. ctypes erlaubt, einen
            # POINTER(c_ubyte) wie ein Array zu indizieren UND zu beschreiben.
            #
            # Merksatz: Der Rueckgabewert (return ret_val) traegt nur den
            # STATUS (0 = OK). Die eigentliche NUTZLAST reist NICHT ueber return,
            # sondern ueber den Zeiger -- klassisches C-Muster: "Fehlercode
            # zurueck, Daten ueber einen Ausgabe-Parameter".
            #
            # ord(...) wandelt jedes Byte aus smbus2's Puffer (ein Ein-Zeichen-
            # Wert) in die Ganzzahl, die ein c_ubyte-Slot erwartet.
            if ret_val == 0:
                for index in range(length):
                    data_p[index] = ord(msg_r.buf[index])

            # 0 = Erfolg, wie es die C-Seite erwartet.
            # EHRLICHER HINWEIS FUER DIE VERTEIDIGUNG: ret_val ist auf 0 gesetzt
            # und wird nie geaendert. Die if-Pruefung 'ret_val == 0' ist damit
            # immer wahr, und der Callback meldet IMMER Erfolg. Eine echte
            # Fehlerweitergabe aus der Bus-Schicht findet hier also nicht statt
            # (gutes Detail, falls jemand fragt "und wenn der Lesezugriff fehlschlaegt?").
            return ret_val

        # ---------------------------- SCHREIB-Callback ----------------------------
        # Spiegelbild des Lesens, nur einfacher: C uebergibt einen Puffer mit
        # Daten, die ZUM Sensor sollen, und wir schicken sie raus.
        def _i2c_write(address, reg, data_p, length):
            ret_val = 0
            data = []

            # Bytes aus C's Puffer in eine normale Python-Liste herauskopieren.
            # (Lesen DURCH den Zeiger -- Gegenrichtung zum Schreiben oben.)
            for index in range(length):
                data.append(data_p[index])

            # Eine einzige SCHREIB-Nachricht bauen: zuerst die 16-Bit-Register-
            # adresse (High-, dann Low-Byte), dann die Datenbytes. Das '+'
            # verkettet die zwei Listen zu einer durchgehenden Byte-Sequenz.
            msg_w = i2c_msg.write(address, [reg >> 8, reg & 0xff] + data)

            # Einzelner Schreib-Transfer -- hier braucht es keinen repeated
            # start, weil nichts zurueckgelesen wird.
            self._i2c.i2c_rdwr(msg_w)

            return ret_val

        # ------------------------------------------------------------------
        # DIE LEBENSDAUER-FALLE (das Detail, das echtes FFI-Verstaendnis zeigt)
        # ------------------------------------------------------------------
        # Jetzt verpacken wir die zwei Python-Funktionen mit den oben definierten
        # CFUNCTYPE-Typen in von C aufrufbare Funktionszeiger ("Trampoline").
        #
        # Warum auf 'self' speichern und nicht einfach inline uebergeben?
        # WEIL ES SONST ZUFAELLIG ABSTUERZT. ctypes gibt der C-Seite nur einen
        # rohen Zeiger -- KEINE Referenz, die Pythons Garbage Collector sehen
        # kann. Wuerde man schreiben:
        #     VL53LX_set_i2c(_I2C_READ_FUNC(_i2c_read), ...)
        # waere das Trampolin-Objekt nach dieser Zeile unreferenziert, der GC
        # raeumt es irgendwann ab -- und wenn C SPAETER (mitten in einer Messung)
        # den nun ungueltigen Zeiger aufruft, gibt es einen Segfault. Ein
        # gemeiner, sporadischer Absturz weit entfernt von der eigentlichen
        # Ursache.
        #
        # Indem wir die Trampoline an 'self' binden, leben sie genau so lange wie
        # das VL53L3CX-Objekt -- also so lange, wie C die Zeiger halten koennte.
        self._i2c_read_func = _I2C_READ_FUNC(_i2c_read)
        self._i2c_write_func = _I2C_WRITE_FUNC(_i2c_write)
        # Beide Zeiger an die C-Bibliothek uebergeben. Ab jetzt KANN und WIRD der
        # Treiber unseren Bus benutzen, indem er diese Funktionen zurueckruft.
        _TOF_LIBRARY.VL53LX_set_i2c(self._i2c_read_func, self._i2c_write_func)

    # ========================================================================
    # DIE DUENNEN WRAPPER (Richtung 1: Python -> C, voellig unspektakulaer).
    # Jede Methode reicht nur unseren Geraete-Handle self._dev an die passende
    # C-Funktion durch. Hier steckt keine Logik -- die liegt komplett in der .so.
    # ========================================================================

    def start_ranging(self):
        """Start VL53L3CX ToF Sensor Ranging"""
        # Startet die kontinuierliche Messung im Sensor.
        _TOF_LIBRARY.startRanging(self._dev)

    def set_distance_mode(self, mode):
        """Set distance mode

        :param mode: One of 1 = Short, 2 = Medium or 3 = Long

        """
        # Reichweiten-/Genauigkeits-Kompromiss: Short ist robuster gegen
        # Umgebungslicht, Long misst weiter.
        _TOF_LIBRARY.setDistanceMode(self._dev, mode)

    def stop_ranging(self):
        """Stop VL53L3CX ToF Sensor Ranging"""
        return _TOF_LIBRARY.stopRanging(self._dev)

    def get_distance(self):
        """Get distance from VL53L3CX ToF Sensor"""
        # Fragt C nach der aktuellen Distanz in mm, speichert und gibt sie zurueck.
        #
        # PROJEKT-RELEVANTER AUGENOEFFNER: Der Sensor UND ST's C-Code koennen
        # MEHRERE Ziele gleichzeitig erkennen (Mehrziel-/Histogramm-Detektion).
        # ABER dieser .so-Wrapper gibt nur die Reichweite des NAECHSTEN Objekts
        # zurueck -- oder -1, wenn kein gueltiges Ziel gefunden wurde. Die
        # Mehrziel-Information geht auf dem Weg durch diese Funktion verloren.
        # Konsequenz: Eine Mehrziel-Anzeige liesse sich NICHT in Python
        # nachruesten -- man muesste den C-Code mit einem anderen Rueckgabepfad
        # NEU KOMPILIEREN.
        self.distance = _TOF_LIBRARY.getDistance(self._dev)
        return self.distance

    def is_ranging_ready(self):
        """Check if ranging data is ready"""
        # Liefert ungleich null / True, sobald eine frische Messung zum Abholen
        # bereit liegt. Typischer Einsatz: pollen, bis es True ist, dann
        # get_distance() aufrufen.
        return _TOF_LIBRARY.isRangingReady(self._dev)

    def set_timing_budget(self, timing_budget):
        """Set the timing budget in microseocnds"""
        # "Timing Budget" = wie lange der Sensor pro Messung integriert. Mehr
        # Zeit -> weniger Rauschen / groessere Reichweite, aber niedrigere
        # Bildrate. Angabe in Mikrosekunden.
        _TOF_LIBRARY.setMeasurementTimingBudgetMicroSeconds(self._dev, timing_budget)