# =============================================================================
# main.py  --  EINSTIEGSPUNKT AUF DER LAPTOP-SEITE
# -----------------------------------------------------------------------------
# Das ist das Programm, das du auf dem LAPTOP startest. Es erledigt vier Dinge:
#   1. liest die IP-Adresse des Raspberry Pi von der Kommandozeile,
#   2. erzeugt ein NetworkSensor-Objekt, das weiss, wie es mit dem Pi spricht,
#   3. erzeugt das Qt-GUI-Fenster und uebergibt ihm diesen Sensor,
#   4. startet die Qt-Event-Loop, damit das Fenster lebt und sich aktualisiert.
#
# Eine Python-Datei wie diese nennt man ein "Modul". Wenn du
#   python src/main.py 192.168.178.56
# ausfuehrst, arbeitet Python diese Datei von oben nach unten ab.
#
# ARCHITEKTUR-ERINNERUNG: Sensor laeuft auf dem Pi (sensor_server.py),
# die GUI laeuft auf dem Laptop. Die Verbindung ist eine TCP-Netzwerkverbindung.
# =============================================================================

# Ein String, der ganz oben allein in der Datei steht, ist der "Docstring" des
# Moduls. Er wird keiner Variable zugewiesen und nicht ausgegeben; Python
# speichert ihn als Dokumentation des Moduls (abrufbar ueber help(main)).
# Wir nutzen ihn hier als Kopfzeile/Beschreibung.
"""
Entry point for the VL53L3CX ToF Sensor Monitor.
Streams from a Raspberry Pi running sensor_server.py and shows the GUI locally.
"""

# ----------------------------------------------------------------------------
# IMPORTS
# 'import X' laedt ein anderes Modul, damit wir dessen Code benutzen koennen.
# ----------------------------------------------------------------------------

# 'sys' gehoert zur Standardbibliothek von Python (immer vorhanden, keine
# Installation noetig). Wir brauchen es fuer zwei Dinge: sys.argv (die
# Kommandozeilen-Argumente) und sys.exit() (das Programm mit einem Statuscode
# beenden).
import sys

# 'argparse' ist ebenfalls Standardbibliothek. Es verwandelt rohen
# Kommandozeilen-Text in gepruefte Python-Werte und erzeugt automatisch eine
# --help-Ausgabe sowie sinnvolle Fehlermeldungen.
import argparse

# 'from PAKET import NAME' importiert nur EINEN Namen aus einem Modul, nicht das
# ganze Modul. PyQt6 ist die Python-Anbindung an das in C++ geschriebene
# GUI-Framework Qt6. QtWidgets ist das Untermodul mit den sichtbaren Bausteinen
# (Fenster, Knoepfe, Beschriftungen). QApplication ist das EINE Pflicht-Objekt,
# das jedes Qt-Programm erzeugen muss, bevor es etwas Grafisches anzeigen kann
# (es besitzt die Event-Loop, siehe unten).
from PyQt6.QtWidgets import QApplication

# Diese beiden Imports holen UNSEREN EIGENEN Code aus den anderen Dateien in
# diesem Ordner. 'sensor' verweist auf sensor.py; wir brauchen daraus nur die
# Klasse NetworkSensor (der Laptop spricht ueber TCP Sockets uber das Netzwerk mit dem Pi und
# niemals direkt mit der Hardware).
from sensor import NetworkSensor
# 'gui' verweist auf gui.py; MainWindow ist die Klasse, die das Fenster baut.
from gui import MainWindow


# 'def name(parameter):' DEFINIERT eine Funktion. Der Code im Inneren laeuft
# erst, wenn die Funktion spaeter AUFGERUFEN wird (siehe ganz unten). 'main' ist
# nur ein ueblicher Name fuer die Startfunktion; in Python ist er NICHT speziell
# (anders als in C/Java, wo main zwingend ist).
def main():
    # Erzeuge das Parser-Objekt. 'description=' ist der Text, der oben bei
    # 'python main.py --help' erscheint. Es ist ein "keyword argument"
    # (benanntes Argument).
    parser = argparse.ArgumentParser(description="VL53L3CX ToF Distance Monitor")

    # Sage dem Parser, dass wir ein Kommandozeilen-Argument namens "host"
    # erwarten. Weil der Name KEINE fuehrenden Bindestriche hat, ist es ein
    # POSITIONALES Argument: es ist verpflichtend, und man tippt den Wert direkt,
    # z. B.:  python main.py 192.168.178.56
    # 'help=' ist die Beschreibung dieses Arguments in der --help-Ausgabe.
    parser.add_argument(
        "host",
        help="IP of a Pi running sensor_server.py (e.g. 192.168.7.2)",
    )

    # Lies tatsaechlich sys.argv ein, pruefe es gegen die obigen Regeln und gib
    # das Ergebnis zurueck. Hat der Nutzer den Host vergessen, gibt argparse
    # hier automatisch eine Fehlermeldung aus und beendet das Programm. 'args'
    # ist ein kleines Objekt, dessen Attribute nach den Argumenten benannt sind;
    # die IP ist also jetzt unter 'args.host' verfuegbar.
    args = parser.parse_args()

    # Gib eine Statuszeile im Terminal aus, damit der Nutzer sieht, was passiert.
    # Das Praefix f"..." macht daraus einen "f-String" (formatierter String):
    # alles in {geschweiften Klammern} wird ausgewertet und in den Text
    # eingesetzt. {args.host} wird also zur tatsaechlich eingegebenen IP.
    print(f"Streaming from Pi sensor server at {args.host}:9999 ...")

    # ERZEUGE das Sensor-Objekt. NetworkSensor(...) ruft die __init__-Methode der
    # Klasse auf. 'host=args.host' uebergibt die IP als benanntes Argument.
    # WICHTIG: Hier wird nur die Adresse gespeichert; es wird noch KEINE
    # Netzwerkverbindung aufgebaut (das passiert spaeter, wenn die GUI
    # sensor.start() aufruft).
    sensor = NetworkSensor(host=args.host)

    # Erzeuge das eine Pflicht-Qt-Objekt. Wir uebergeben sys.argv, weil Qt selbst
    # einige Kommandozeilen-Optionen versteht (z. B. zur Darstellung). 'app' MUSS
    # waehrend des gesamten Programms am Leben bleiben; deshalb speichern wir es
    # in einer Variable und werfen es nicht weg.
    app = QApplication(sys.argv)

    # Baue das Hauptfenster. Wir uebergeben unser Sensor-Objekt, damit das
    # Fenster weiss, woher es die Daten holt. 'auto_start=True' weist das Fenster
    # an, sofort zu verbinden und zu pollen, statt auf einen Klick auf "Start" zu
    # warten.
    window = MainWindow(sensor, auto_start=True)

    # Qt-Fenster sind nach der Erzeugung unsichtbar; .show() macht dieses
    # sichtbar.
    window.show()

    # app.exec() STARTET die Qt-Event-Loop. Dieser Aufruf BLOCKIERT (kehrt nicht
    # zurueck) und laeuft weiter, indem er Ereignisse verarbeitet: die
    # 50-ms-Timer-Ticks, Knopfdruecke, das Schliessen des Fensters usw. Er kehrt
    # erst mit einem ganzzahligen Exit-Code zurueck, wenn das Fenster geschlossen
    # wird. sys.exit(...) beendet dann den Python-Prozess und meldet diesen Code
    # an das Betriebssystem.
    sys.exit(app.exec())


# ----------------------------------------------------------------------------
# DER __name__-SCHUTZ ("name guard")
# Python setzt die spezielle Variable __name__ NUR dann auf den String
# "__main__", wenn diese Datei direkt ausgefuehrt wird (python main.py). Wuerde
# eine andere Datei 'import main' schreiben, waere __name__ stattdessen "main",
# und der Code unten wuerde NICHT laufen. So kann eine Datei sowohl ausfuehrbar
# als auch importierbar sein, ohne ungewollte Nebenwirkungen.
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    # Starte das Programm, indem die oben definierte Funktion aufgerufen wird.
    main()
