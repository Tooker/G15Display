# Änderungen

## 1.0.0 – 19.10.2026

Erste öffentliche Version für die Logitech G15 der ersten Generation
(klappbares Display, blaue Beleuchtung) unter macOS auf Apple Silicon.

- Eigenständige Mac-App mit Menüleiste, Live-Vorschau und automatischer Wiederverbindung.
- Displayseiten für Uhr, Codex-Limits, lokale Codex-Aufgaben, Timer,
  Pomodoro, Spotify/Apple Music und Netzwerk.
- Bedienung über die Displaytasten sowie Erkennung von G1–G18 und M1–M3.
- Tastaturmakros mit Aufnahme, Zeitabständen und getrennten M-Bänken;
  Stoppen über die App oder MR.
- Python-Quellen, Build-Anleitung und 54 automatisierte Tests.

### Download

`G15-Display-1.0.0-macOS-arm64.zip` entpacken und `G15 Display.app` öffnen.
Python muss dafür nicht separat installiert werden. `SHA256SUMS.txt` enthält
die Prüfsumme des Archivs.

### Voraussetzungen und bekannte Einschränkungen

- macOS auf Apple Silicon; kein Windows- oder Intel-Mac-Build enthalten.
- Lokal signiert, ohne Apple-Notarisierung. macOS kann heruntergeladene
  Kopien zunächst blockieren.
- Makroaufnahme benötigt Eingabeüberwachung, Wiedergabe benötigt
  Bedienungshilfen. Aufzeichnung erfolgt nur nach ausdrücklich gestarteter
  Aufnahme, dann systemweit für maximal 60 Sekunden / 500 Ereignisse.
- Codex-Anzeigen benötigen eine vorhandene lokale Codex-Anmeldung;
  Aufgabenstatus basiert auf lokalen Logs und kann verzögert sein.
- Musik benötigt gegebenenfalls macOS-Freigaben für Spotify bzw. Music.
- M-LEDs werden noch nicht synchronisiert. Helligkeit und Autostart fehlen.
- Display und viele Sondertasten wurden an echter Hardware geprüft;
  Makroaufnahme und -wiedergabe sind automatisiert mit simulierten Ereignissen
  getestet, der vollständige Live-Test mit Nutzerfreigaben steht noch aus.
