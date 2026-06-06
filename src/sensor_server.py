# =============================================================================
# sensor_server.py  --  DER TCP-SERVER AUF DER PI-SEITE
# -----------------------------------------------------------------------------
# Dies laeuft AUF DEM RASPBERRY PI. Es besitzt den echten Sensor und stellt ihn
# ueber das Netzwerk bereit, damit die GUI des Laptops (ueber NetworkSensor)
# Messungen abholen und Einstellungen aendern kann. Es ist ein klassischer,
# minimaler TCP-Server nach dem Anfrage/Antwort-Prinzip (request/response):
#
#   Laptop sendet "r"              -> Server antwortet "<distance_mm>,<status>\n"
#   Laptop sendet "c<modus>,<us>\n"-> Server konfiguriert um, antwortet "ok\n"
#
# Er bedient IMMER NUR EINEN Client gleichzeitig (srv.listen(1)), was hier reicht.
#
# BEGRIFFE: Ein "Socket" ist der Endpunkt einer Netzwerkverbindung. "TCP" ist
# ein zuverlaessiges, geordnetes Stream-Protokoll (im Gegensatz zu UDP). "Port"
# ist eine Nummer (hier 9999), die diesen Dienst auf dem Pi adressierbar macht.
# =============================================================================

"""
Sensor server - streams live VL53L3CX readings to a remote GUI (NetworkSensor).
Lets the PyQt GUI run on a laptop while the real sensor stays on the Pi.

Run on the Pi:
    cd ~/embedded_tof_sensor/src
    source ../.venv/bin/activate
    python sensor_server.py

Protocol: client sends a byte -> server replies "distance_mm,status\\n".
Works over ANY transport that gives an IP link (Ethernet, USB-C gadget, Wi-Fi).
"""

# TCP-Netzwerk aus der Standardbibliothek.
import socket
# Importiere NUR die echte Hardware-Sensorklasse aus unserer sensor.py. Der
# Server nutzt immer den physischen Sensor (er IST der Pi), niemals NetworkSensor.
from sensor import VL53L3CXSensor

# Modul-weite Konstanten, die beschreiben, wo gelauscht wird.
# "0.0.0.0" ist eine spezielle Adresse fuer "ALLE Netzwerk-Schnittstellen dieses
# Rechners" (Ethernet eth0, WLAN wlan0, USB-Gadget usb0 ...). Damit ist der
# Server unter jeder IP erreichbar, die der Pi gerade hat.
HOST = "0.0.0.0"
# Die TCP-Port-Nummer, auf der wir lauschen. Der NetworkSensor des Laptops
# verbindet sich hierher.
PORT = 9999


# Die Hauptroutine des Programms.
def main():
    # Erzeuge und starte den echten Sensor (mit allen Standardeinstellungen:
    # lange Reichweite, 50-ms-Budget). start() initialisiert die I2C-Hardware und
    # beginnt das Messen.
    sensor = VL53L3CXSensor()
    sensor.start()

    # Erzeuge ein TCP-Socket.
    #   AF_INET     -> verwende IPv4-Adressen.
    #   SOCK_STREAM -> verwende TCP (ein zuverlaessiger, geordneter Byte-Strom),
    #                  nicht UDP.
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # SO_REUSEADDR erlaubt uns, den Port sofort nach einem Neustart des Servers
    # erneut zu binden. Ohne diese Option reserviert das Betriebssystem den Port
    # noch ein bis zwei Minuten (der TCP-Zustand TIME_WAIT), und bind() wuerde mit
    # "Address already in use" scheitern. Die '1' schaltet die Option EIN.
    # (Das ist genau der Fehler, der bei dir auftrat, als noch ein alter Server
    #  lief.)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Binde das Socket an unsere Adresse+Port. Beachte die DOPPELTEN Klammern:
    # bind() nimmt EIN Argument, das ein Tupel (HOST, PORT) ist.
    srv.bind((HOST, PORT))
    # Beginne, auf eingehende Verbindungen zu lauschen. Das Argument 1 ist der
    # "Backlog" = wie viele wartende Verbindungen sich anstellen duerfen; wir
    # bedienen nur einen Client.
    srv.listen(1)
    # Teile dem Bediener mit, dass der Server laeuft. Der f-String setzt die
    # Port-Nummer ein.
    print(f"Sensor server listening on port {PORT} (all interfaces). Ctrl+C to stop.")

    # Aeusseres try/finally: Was auch passiert, der 'finally'-Block ganz unten
    # laeuft IMMER, um Sensor und Socket aufzuraeumen.
    try:
        # Endlosschleife, die Clients nacheinander annimmt.
        while True:
            # accept() BLOCKIERT, bis ein Client sich verbindet, und gibt dann ein
            # NEUES Socket 'conn' nur fuer diesen Client zurueck, plus die Adresse
            # 'addr' des Clients. (srv selbst lauscht weiter auf kuenftige Clients.)
            conn, addr = srv.accept()
            print(f"Client connected: {addr}")
            # Inneres try/except, damit ein fehlerhafter Client nicht den ganzen
            # Server zum Absturz bringt; wir verwerfen ihn nur und warten auf den
            # naechsten.
            try:
                # 'with conn:' ist ein Kontext-Manager: er garantiert, dass conn
                # automatisch geschlossen wird, wenn dieser Block endet (auch bei
                # einem Fehler).
                with conn:
                    # Bediene diesen Client, bis er die Verbindung trennt.
                    while True:
                        # Empfange bis zu 16 Bytes (unsere Befehle sind winzig).
                        req = conn.recv(16)
                        # recv() gibt leere Bytes b"" zurueck, wenn der Client die
                        # Verbindung geschlossen hat -> verlasse die Client-Schleife.
                        if not req:
                            break
                        # Dekodiere die rohen Bytes zu Text. errors="ignore"
                        # verwirft nicht dekodierbare Bytes, statt einen Fehler zu
                        # werfen. .strip() entfernt nachgestellten
                        # Zeilenumbruch/Leerraum.
                        cmd = req.decode(errors="ignore").strip()
                        # Ist das ein KONFIGURATIONS-Befehl? Diese beginnen mit "c",
                        # z. B. "c3,50000".
                        if cmd.startswith("c"):
                            # Das Parsen kann bei einem fehlerhaften Befehl
                            # scheitern, daher absichern. cmd[1:] entfernt das
                            # fuehrende 'c' und laesst "3,50000" uebrig;
                            # .split(",") -> ["3","50000"], entpackt in zwei
                            # Variablen.
                            try:
                                mode_s, budget_s = cmd[1:].split(",")
                                # In ints umwandeln und auf den laufenden Sensor
                                # anwenden.
                                sensor.configure(int(mode_s), int(budget_s))
                            # ValueError deckt beides ab: ein falsches split
                            # (falsche Anzahl Kommata) UND eine gescheiterte
                            # int()-Umwandlung.
                            except ValueError:
                                pass
                            # Bestaetige, damit der Laptop weiss, dass wir fertig
                            # sind.
                            conn.sendall(b"ok\n")
                        else:
                            # Jedes andere Byte (z. B. "r") = "gib mir eine Messung".
                            r = sensor.read()
                            # Formatiere die Antwort als "<distanz>,<status>\n" und
                            # .encode() sie zu Bytes fuer das Socket.
                            conn.sendall(f"{r.distance_mm},{r.status}\n".encode())
            # Wenn die Client-Verbindung einen Fehler hat, ignorieren und
            # weitermachen.
            except OSError:
                pass
            print("Client disconnected - waiting for next connection.")
    # Strg+C im Terminal loest KeyboardInterrupt aus; wir fangen es ab, damit das
    # Programm sauber endet, statt einen Traceback auszugeben.
    except KeyboardInterrupt:
        pass
    # Laeuft IMMER zuletzt: Hardware und Netzwerk-Port freigeben.
    finally:
        sensor.stop()
        srv.close()
        print("\nServer stopped.")


# Standard-Schutz: main() nur ausfuehren, wenn diese Datei direkt gestartet wird.
if __name__ == "__main__":
    main()
