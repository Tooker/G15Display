# G15 Display – Python-Prototyp

Ansteuerung des monochromen Displays der **Logitech G15, erste Generation**
(klappbares Display, blaue Beleuchtung) unter macOS. Python ab 3.10.

## macOS-App

Die fertige App liegt unter **`dist/G15 Display.app`**. Per Doppelklick öffnen;
für den Betrieb ist kein Terminal und keine separate Python-Installation nötig.
Die App wurde für diesen Apple-Silicon-Mac gebaut und ist etwa 34 MB groß.

- Live-Vorschau mit derselben Pixelschrift wie auf der Tastatur.
- Ansichten per Auswahlfeld, Bildschirmtasten oder den echten G15-Tasten wechseln.
- `Verbinden`/`Trennen` steuert den Gerätezugriff. Vorschau und laufende Timer
  bleiben beim Trennen aktiv; beim Beenden der App werden die Timer verworfen.
- Timer- und Pomodoro-Zeiten sind einstellbar und werden als macOS-Einstellung
  gespeichert. `Zeiten anwenden` setzt beide Timer zurück.
- Schließen des Fensters lässt die App unter **G15 in der Menüleiste** weiterlaufen.
  Dort kann das Fenster wieder geöffnet oder die App beendet werden.
- Nach Abziehen/Anstecken der G15 wird die Verbindung automatisch neu hergestellt.
- Pro Benutzer kann nur ein Programm das Display belegen. Ein noch laufendes
  altes Terminal-Menü zuerst dort mit Strg+C beenden. Die App wartet darauf und
  verbindet sich anschließend automatisch.

Für Musik kann macOS erneut eine Freigabe für **G15 Display** verlangen.
Bei fehlendem Tastaturzugriff öffnet `Zugriff …` die Eingabeüberwachung in den
Systemeinstellungen. Es werden keine Berechtigungen automatisch erteilt.
Codex-Limits benötigen weiterhin die angemeldete ChatGPT-/Codex-Installation;
die App bringt deren Zugangsdaten oder Programmdateien nicht mit.

Die App ist lokal signiert. Öffentlicher Vertrieb mit Developer-ID und
Notarisierung ist nicht Bestandteil dieses lokalen Builds. Sie kann als ganze
`.app` verschoben werden und greift nicht auf die Projekt-`.venv` zurück.

### App erneut bauen

```sh
.venv/bin/python -m pip install -e '.[app]'
.venv/bin/python scripts/build_app.py
```

`G15 Display.spec` bündelt Python, Cocoa/PyObjC, HIDAPI, Pillow und psutil.
Die Oberfläche bleibt auf dem macOS-Hauptthread; Datenabfragen, USB-Zugriff
und Wiederverbinden laufen getrennt davon. Die Gerätesperre wird auch von
den aktualisierten Kommandozeilenprogrammen verwendet.
Fehler der App werden in `~/Library/Logs/G15 Display.log` protokolliert.

## Starten

Im Projektordner einmalig eine lokale Python-Umgebung anlegen und installieren:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Danach:

```sh
# Angeschlossene Display-Schnittstellen auflisten
.venv/bin/python -m g15display devices

# Je Argument eine Zeile, maximal vier Zeilen
.venv/bin/python -m g15display text "Hallo Tobias!" "Python auf der G15" "160 x 43 Pixel"

# Laufende Uhr, beenden mit Strg+C
.venv/bin/python -m g15display clock

# Begrenzter Testlauf
.venv/bin/python -m g15display clock --seconds 5

# Display leeren
.venv/bin/python -m g15display clear

# Sondertasten live im Terminal und auf dem LCD anzeigen
.venv/bin/python -m g15display keys --display

# Tastentest nach 30 Sekunden beenden
.venv/bin/python -m g15display keys --display --seconds 30

# PNG-Vorschau ohne Zugriff auf USB
.venv/bin/python -m g15display clock --preview preview.png
```

Nach der Installation funktioniert alternativ `.venv/bin/g15` mit denselben
Argumenten. Ein übertragenes Bild bleibt beim Beenden stehen; `clear` leert es.
Die Uhr verwendet die lokale Zeitzone des Rechners.

## Dashboard-Menü

Zum Starten auf diesem Mac **`G15-Menue.command` doppelklicken**. Das Menü
läuft dann in einem eigenen Terminalfenster; dort beendet **Strg+C** das Programm.
So kann macOS auch sichtbar nach Zugriff auf die Musikplayer fragen.
Alternativ im Projektordner starten:

```sh
.venv/bin/python -m g15display menu

# Mit einer bestimmten Ansicht starten
.venv/bin/python -m g15display menu --page limits

# Eigene Timerzeiten in Minuten; vier Pomodoro-Arbeitsrunden
.venv/bin/python -m g15display menu --timer-minutes 10 --work-minutes 25 --break-minutes 5 --rounds 4

# Eine Seite ohne USB als PNG prüfen (liest echte Datenquellen)
.venv/bin/python -m g15display menu --page network --preview preview.png

# Alle sieben Ansichten und die Übersicht als gemeinsames Vorschaubild
.venv/bin/python scripts/preview_menu.py
```

Die **vier Funktionstasten unter dem Display, von links nach rechts**:

| Taste | In einer Ansicht | In der Menüübersicht |
| --- | --- | --- |
| L2 | Vorherige Ansicht | Vorherigen Eintrag auswählen |
| L3 | Nächste Ansicht | Nächsten Eintrag auswählen |
| L4 | Angezeigte Aktion, beim Loslassen | Gewählte Ansicht öffnen |
| L5 | Menüübersicht öffnen | Zur Uhr zurück |

Die Beschriftungen stehen immer unten auf dem LCD. L1 öffnet zusätzlich die
Übersicht. Das Menü umfasst sieben Seiten:

| Seite | Daten und Bedienung |
| --- | --- |
| Uhr | Lokale Uhrzeit, Datum, Wochentag und Kalenderwoche |
| Codex-Limits | Verbleibende Prozentwerte als Balken; L4 wechselt zu Reset-Zeitpunkten |
| Codex aktiv | Anzahl lokal erkannter aktiver Aufgaben und Chatname; L4 zeigt die nächste Aufgabe |
| Timer | Standardmäßig 5 Minuten; L4 startet/pausiert, L4 mindestens 1 Sekunde halten setzt zurück |
| Pomodoro | 25 Minuten Arbeit, 5 Minuten Pause, vier Arbeitsrunden; gleiche Bedienung wie Timer |
| Musik | Spotify und Apple Music: Titel, Interpret, Fortschritt; L4 schaltet Play/Pause |
| Netzwerk | Standard-Netzwerkinterface, IPv4 und aktuelle Down-/Uploadrate in KiB/s bzw. MiB/s |

Timer laufen beim Wechsel der Ansicht weiter und verwenden eine monotone Uhr.
Beim Phasenwechsel erscheint fünf Sekunden lang ein Hinweis in der Kopfzeile.
Nach der letzten Pomodoro-Arbeitsrunde ist die Sitzung fertig. Eine Aktion nach
Ablauf startet neu. Timer sind nicht persistent und geben derzeit kein Tonsignal
aus; das Beenden des Programms verwirft ihren Zustand.

**Codex-Limits:** Verwendet `codex app-server --stdio` und den bestehenden lokalen
Codex-Login. `codex` wird im PATH oder am bekannten Installationsort der
ChatGPT-/Codex-App gesucht. Es werden ausschließlich
Initialisierung und `account/rateLimits/read` aufgerufen, keine Modellanfragen,
Chatänderungen oder Kontingent-Resets. `ZEIT` zeigt nur den Reset-Zeitpunkt.
Die tatsächlich gelieferten Fenster werden ausgewertet; ein fehlendes Fenster
wird nicht als 0 % angezeigt. Aktualisierung alle 60 Sekunden. Grundlage:
[offizielle OpenAI-Dokumentation](https://learn.chatgpt.com/docs/app-server#6-rate-limits-chatgpt).

**Aufgabenstatus:** Ein eigener Codex-Server kennt die laufenden Aufgaben der
Desktop-App nicht. Daher liest diese Seite lokal die Metadaten aus
`~/.codex/state_*.sqlite` und die Ereignisse `task_started`, `task_complete`
und `turn_aborted` aus den zugehörigen Sessionlogs. Es werden die 32 zuletzt
aktualisierten, nicht archivierten Chats der letzten 24 Stunden betrachtet.
Die Datenbank wird ausschließlich lesend geöffnet; Logdateien werden nicht
verändert. Nach zehn Minuten ohne neue Logdaten wird eine vermeintlich aktive
Aufgabe als unklar behandelt. Remote-Aufgaben sind nicht enthalten. Diese
Auswertung ist eine lokale Annäherung und hängt vom installierten Codex-Logformat
ab; die Anzeige bezeichnet sie ausdrücklich als lokale Logs. Aktualisierung
alle drei Sekunden.

**Musik:** Nur bereits laufende Spotify-/Music-Prozesse werden abgefragt; es
wird kein Player gestartet. Wenn beide laufen, hat ein spielender Player Vorrang,
bei Gleichstand Spotify. Abfrage alle drei Sekunden. macOS kann eine
Automatisierungsfreigabe für Spotify/Music verlangen, die für das startende
Terminal bzw. Codex erteilt werden muss. Bei verweigertem Zugriff oder Timeout
zeigt das LCD einen passenden Fehlerhinweis (Zugriff, Timeout oder Abfragefehler).
Eine Playerabfrage wartet bis zu zehn Sekunden, damit auch die erste
macOS-Freigabe Zeit hat. Der andere Player wird weiterhin geprüft;
der betroffene Player wird nach 30 Sekunden erneut versucht. Ein `PLAY` ohne
ausgewählten Player startet keine Anwendung. Andere Multimedia-Tasten sind
weiterhin nicht Teil dieses Lesers.

**Netzwerk:** Misst die Bytezähler des Standardinterfaces; bei VPNs kann dies
ein Tunnelinterface sein. Das ist der beobachtete Datenverkehr und kein
Internet-Speedtest. Die erste Messung benötigt ein zweites Sample. Die
Aktualisierung erfolgt etwa einmal pro Sekunde.

Langsame Datenabfragen laufen im Hintergrund. Navigation und Timer bleiben
bedienbar, wenn Codex oder ein Player nicht antwortet. Fehlende Daten werden
als solche angezeigt, statt durch Beispielwerte ersetzt zu werden. Der
Dashboard-Modus benötigt für die Netzwerk- und Playererkennung zusätzlich
`psutil`; es wird beim Installieren des Projekts mit eingerichtet.

Die LCD-Schrift besteht aus fest gezeichneten 5×7-Pixel-Zeichen mit einer
freien Spalte Abstand. Die großen Zahlen werden exakt auf das Doppelte
vergrößert. Alle Texte erscheinen in Großbuchstaben; Umlaute werden als
AE/OE/UE und ß als SS dargestellt. Pro Textzeile passen maximal 26 Zeichen.
Laufschriften warten zunächst drei Sekunden und rücken dann ein Zeichen pro
Sekunde weiter. Nach Schrift- oder Layoutänderungen das laufende Menü mit
Strg+C beenden und erneut starten, damit es die Änderungen lädt.

## Eigene Inhalte

Pillow zeichnet ein 160 × 43 Pixel großes Schwarzweißbild. Weiß bedeutet hier
aktiver/dunkler LCD-Pixel, Schwarz bedeutet Hintergrund. Text wird rechts
abgeschnitten, wenn eine Zeile zu lang ist. Die Vorschau zeigt aktive Pixel
dunkel auf blauem Hintergrund.

```python
from PIL import Image, ImageDraw
from g15display import G15

image = Image.new("1", (160, 43))
draw = ImageDraw.Draw(image)
draw.rectangle((0, 0, 159, 42), outline=1)
draw.text((8, 12), "Mein erstes Display", fill=1)

with G15() as lcd:
    lcd.show(image)
```

`render.py` erzeugt Inhalte, `display.py` übernimmt die USB-Übertragung.
So lässt sich später die Transportschicht unabhängig in Rust ersetzen.

## Tasten auslesen

`keys` liest **G1–G18**, **M1–M3**, **MR**, **L1–L5** und die
Beleuchtungstaste **LIGHT**. L1 ist die Display-Umschalttaste, L2–L5 sind
die vier zugehörigen Funktionstasten. Die Zuordnung folgt dem G15-v1-Protokoll
in libg15; einzelne Tasten sollten am eigenen Gerät geprüft werden.
Normale Buchstaben-, Zahlen- und Medientasten liegen auf dem anderen
Tastaturgerät und werden von diesem Modus nicht ausgelesen.

Die G15 sendet einen neun Byte langen Input-Report mit ID **2**. Seine Bits
beschreiben die gerade gehaltenen Sondertasten. `keys.py` dekodiert diese
Zustände und erzeugt Ereignisse für **Drücken** und **Loslassen**.
Mehrere gleichzeitige Tasten sind möglich. Identische Reports erzeugen keine
doppelten Ereignisse; Timeouts und andere Report-IDs lösen keine Tasten.
Es gibt keine automatische Tastenwiederholung. Ein beim Start bereits
gehaltener Knopf wird beim ersten gültigen Report als gedrückt gemeldet.
Beim Abziehen der Tastatur endet das Programm mit einer Fehlermeldung.

Beispiel für eine Displaytaste, die zur Uhr wechselt:

```python
from g15display import G15, clock_screen

with G15() as lcd:
    while True:  # Strg+C beendet das Beispiel
        for event in lcd.read_keys(timeout_ms=100):
            if event.name == "L2" and event.pressed:
                lcd.show(clock_screen())
```

Das Beispiel zeichnet die Uhr einmal beim Drücken von L2. Eine laufende Uhr
muss zusätzlich regelmäßig neu gezeichnet werden. `read_keys()` wartet maximal
die angegebene positive Millisekundenzahl pro Report. `lcd.held_keys` liefert
den zuletzt empfangenen Zustand.

Mit `--display` ersetzt der Tastentest den bisherigen Display-Inhalt.
Ohne diese Option wird nur im Terminal ausgegeben. Die Funktion erzeugt keine
Tastaturbelegungen; bestehende Belegungen anderer Programme können parallel
weiter reagieren.

## USB und macOS

Der Prototyp verwendet `hidapi` (Python-Import `hid`) und Pillow. Er adressiert
ausschließlich **046d:c222**, das Display-/Sondertastengerät der G15 v1.
Das normale Tastaturgerät **046d:c221** wird nicht geöffnet.
Unter macOS wird die öffentliche HIDAPI-Funktion
`hid_darwin_set_open_exclusive(0)` für gemeinsamen Zugriff verwendet. Da der
Python-Wrapper diese Funktion nicht anbietet, wird sie mit `ctypes` aus genau
seiner mitgelieferten Bibliothek geladen. Eine zweite HIDAPI-Installation ist
nicht nötig. Die Einstellung verhindert, dass macOS oder andere Tastaturtools
vom Gerät ausgeschlossen werden.
Bei mehreren HID-Collections wird die herstellerspezifische Collection bevorzugt.
Mehrere angeschlossene G15-Geräte werden nicht automatisch ausgewählt.

Das LCD empfängt Output-Report **3** mit **992 Bytes**, einschließlich
32 Byte Header. Danach folgen sechs Bänder mit je 160 Bytes. Ein Byte beschreibt
acht vertikale Pixel, niedrigstes Bit oben. Im letzten Band sind nur drei Bits
sichtbar. Grundlage sind die Protokolldaten in
[libg15.h](https://github.com/vividnightmare/libg15/blob/master/libg15.h) und
[libg15.c](https://github.com/vividnightmare/libg15/blob/master/libg15.c).
Die Python-Implementierung ist neu geschrieben.

Bei Zugriffsfehlern andere Display-Programme schließen. Falls macOS eine
Zugriffsfreigabe verlangt, unter **Systemeinstellungen → Datenschutz & Sicherheit
→ Eingabeüberwachung** das startende Terminal bzw. Codex prüfen und anschließend
neu starten. Der Prototyp installiert keinen Systemtreiber und benötigt kein sudo.

Nach Abziehen der Tastatur beendet sich eine laufende Übertragung mit einer
Fehlermeldung. Nach erneutem Anschließen das Programm neu starten.
Makrobelegungen, Helligkeit und Autostart sind noch nicht implementiert.
Ein erfolgreicher Schreibaufruf bestätigt die USB-Übertragung; die tatsächliche
Darstellung muss zusätzlich am physischen Display geprüft werden.

## Tests

Am 19.10.2026 mit der angeschlossenen G15 v1 unter macOS auf Apple Silicon
geprüft: Erkennung, vollständige Übertragung eines Textbildes (992 Bytes) und
dreisekündiger Uhrlauf erfolgreich. Python 3.14.6, hidapi 0.15.0, Pillow 13.0.0.
Die PNG-Vorschau wurde visuell geprüft; die Textdarstellung auf dem physischen
LCD wurde vom Nutzer bestätigt. Im anschließenden Live-Tastentest wurden
Drücken und Loslassen von L2–L5 sowie G1–G5, G7–G10 und G12–G18 empfangen.
Die übrigen Tasten sind anhand des Protokolls implementiert und noch nicht
einzeln am Gerät bestätigt. Alle 44 automatischen Tests bestehen, einschließlich
Menünavigation, Timer/Pomodoro, Hintergrundlauf bei Seitenwechsel, Datenquellen
und Fehlerbehandlung. Limits, lokale Aufgabenmetadaten und Netzwerkdaten wurden
live abgerufen. Nach der macOS-Freigabe lieferte Spotify den pausierten Titel,
Position und Gesamtlänge; Apple Music antwortete mit dem Zustand `stopped`.
Apple-Music-Titel und die Play/Pause-Steuerung sind noch nicht live bestätigt;
beim Test wurde keine Wiedergabe verändert. Die gebündelte App wurde geöffnet:
Vorschau, echte Datenquellen und die G15-Verbindung sind aktiv. Der Pakettest
bestätigt arm64, gebündelte Python-Laufzeit, HIDAPI 0.15.0 und 992-Byte-Reports;
die lokale Codesignatur wurde geprüft. Die Menüansichten sind unter
`previews/dashboard.png` zusammengefasst.
USB-Zugriff war aus der Codex-Sandbox gesperrt; der Hardwaretest lief mit
freigegebenem Gerätezugriff. Bei eigenen Tests das Programm im Terminal starten.

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Die Tests prüfen Pixelpositionen, Bandgrenzen, Header, unbenutzte Bits,
Geräteauswahl, unvollständige Übertragungen, Tastendekodierung, gleichzeitige
Tasten, Drücken/Loslassen, ignorierte Reports und Schließen bei USB-Fehlern.
