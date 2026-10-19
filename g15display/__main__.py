import argparse
from datetime import datetime
import math
from pathlib import Path
import sys
import time

from .display import G15, G15Error, list_devices
from .render import clock_screen, save_preview, text_screen
from .i18n import LANGUAGES, Translator, system_language


def positive_seconds(value: str, tr=None) -> float:
    tr = tr or Translator()
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError(tr("Bitte eine positive, endliche Sekundenzahl angeben."))
    return number


def main(argv=None) -> int:
    language_parser = argparse.ArgumentParser(add_help=False)
    language_parser.add_argument("--language", choices=tuple(LANGUAGES), default=system_language())
    language_args, _ = language_parser.parse_known_args(argv)
    tr = Translator(language_args.language)
    parser = argparse.ArgumentParser(description=tr("Logitech G15 v1 – Display-Ansteuerung"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("devices", help=tr("G15-Schnittstellen auflisten"))
    text = commands.add_parser("text", help=tr("Bis zu vier Textzeilen anzeigen"))
    text.add_argument("lines", nargs="+", help=tr("Je Argument eine Zeile"))
    clock = commands.add_parser("clock", help=tr("Uhr starten; Strg+C beendet sie"))
    clock.add_argument("--seconds", type=lambda value: positive_seconds(value, tr), help=tr("Nach dieser Dauer beenden"))
    keys = commands.add_parser("keys", help=tr("G-, M- und Displaytasten live anzeigen"))
    keys.add_argument("--seconds", type=lambda value: positive_seconds(value, tr), help=tr("Nach dieser Dauer beenden"))
    keys.add_argument("--display", action="store_true", help=tr("Tasten zusätzlich auf der G15 anzeigen"))
    menu = commands.add_parser("menu", help=tr("Dashboard mit Uhr, Codex, Timer, Musik und Netzwerk"))
    menu.add_argument("--seconds", type=lambda value: positive_seconds(value, tr), help=tr("Nach dieser Dauer beenden"))
    menu.add_argument("--page", choices=("clock", "limits", "activity", "timer", "pomodoro", "music", "network"), default="clock")
    menu.add_argument("--preview", type=Path, metavar="PNG", help=tr("Nur PNG-Vorschau speichern"))
    menu.add_argument("--timer-minutes", type=lambda value: positive_seconds(value, tr), default=5)
    menu.add_argument("--work-minutes", type=lambda value: positive_seconds(value, tr), default=25)
    menu.add_argument("--break-minutes", type=lambda value: positive_seconds(value, tr), default=5)
    menu.add_argument("--rounds", type=int, default=4)
    clear = commands.add_parser("clear", help=tr("Display leeren"))
    for command in (text, clock, clear):
        command.add_argument("--preview", type=Path, metavar="PNG", help=tr("Nur PNG-Vorschau speichern, ohne USB"))
    parser.add_argument("--language", choices=tuple(LANGUAGES), default=language_args.language, help=tr("Sprache"))
    for subparser in commands.choices.values():
        subparser.add_argument("--language", choices=tuple(LANGUAGES), default=argparse.SUPPRESS, help=tr("Sprache"))
    args = parser.parse_args(argv)
    try:
        if args.command == "menu":
            from .dashboard import run_menu
            return run_menu(args)
        if args.command == "devices":
            devices = list_devices()
            if not devices:
                raise G15Error("Keine G15 v1 gefunden (046d:c222).")
            for d in devices:
                print(f"{d.get('product_string', 'G15')} | 046d:c222 | "
                      f"Usage {d.get('usage_page', 0):04x}:{d.get('usage', 0):04x} | {d['path']!r}")
            return 0
        if args.command == "keys":
            with G15() as lcd:
                if args.display:
                    lcd.show(text_screen("\n".join(tr(line) for line in ("G15 Tastentest", "G-, M-, Displaytasten", "Bitte Taste druecken"))))
                print(tr("Tastentest läuft: G1–G18, M1–M3, MR, L1–L5, LIGHT. Strg+C beendet ihn."), flush=True)
                deadline = time.monotonic() + args.seconds if args.seconds else None
                while deadline is None or time.monotonic() < deadline:
                    timeout = 100
                    if deadline is not None:
                        timeout = min(timeout, max(1, math.ceil((deadline - time.monotonic()) * 1000)))
                    events = lcd.read_keys(timeout_ms=timeout)
                    for event in events:
                        action = tr("gedrückt" if event.pressed else "losgelassen")
                        print(f"{datetime.now().astimezone():%H:%M:%S.%f}"[:-3]
                              + f"  {event.name:5} {action}", flush=True)
                    if events and args.display:
                        last = events[-1]
                        action = tr("gedrueckt" if last.pressed else "losgelassen")
                        # Last event is always legible, even with many held keys.
                        count = len(lcd.held_keys)
                        lcd.show(text_screen(f"{tr('G15 Tastentest')}\n{last.name} {action}\n" + tr("{count} Taste(n) gehalten", count=count)))
            return 0
        if args.command == "text":
            image = text_screen("\n".join(args.lines))
        elif args.command == "clock":
            image = clock_screen(language=args.language)
        else:
            image = text_screen("")
        if args.preview:
            save_preview(image, args.preview)
            print(tr("Vorschau: {path}", path=args.preview.resolve()))
            return 0
        with G15() as lcd:
            lcd.show(image)
            print(tr("Display-Bild übertragen (992 Bytes)."), flush=True)
            if args.command == "clock":
                print(tr("Uhr läuft. Beenden mit Strg+C."), flush=True)
                deadline = time.monotonic() + args.seconds if args.seconds else None
                while deadline is None or time.monotonic() < deadline:
                    remaining = deadline - time.monotonic() if deadline else 1.0
                    time.sleep(min(1.0, max(0, remaining)))
                    if deadline is not None and time.monotonic() >= deadline:
                        break
                    lcd.show(clock_screen(language=args.language))
        return 0
    except KeyboardInterrupt:
        print("\n" + tr("Beendet."))
        return 0
    except (G15Error, OSError, ValueError) as exc:
        print(tr("Fehler: {details}", details=tr(exc)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
