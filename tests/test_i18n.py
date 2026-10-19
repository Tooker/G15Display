import ast
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
import io
from pathlib import Path
from string import Formatter
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from g15display.app_controller import AppController
from g15display.dashboard import Dashboard, PAGES, TITLES, window_label
from g15display.i18n import CATALOG, LANGUAGES, Message, Translator, date_label, normalize_language
from g15display.pixelfont import SMALL, lcd_text
from g15display.sources import Snapshot


class TranslationTests(unittest.TestCase):
    def test_all_languages_have_matching_format_fields(self):
        formatter = Formatter()
        for source, translations in CATALOG.items():
            expected = {(field, spec, conversion) for _, field, spec, conversion in formatter.parse(source) if field is not None}
            self.assertEqual(set(translations), set(LANGUAGES), source)
            for language, translated in translations.items():
                self.assertTrue(translated.strip(), (language, source))
                actual = {(field, spec, conversion) for _, field, spec, conversion in formatter.parse(translated) if field is not None}
                self.assertEqual(actual, expected, (language, source))

    def test_region_codes_fallback_and_instances_do_not_interfere(self):
        for regional, expected in (("es-MX", "es"), ("fr_CA", "fr"), ("de-DE", "de"), ("en-GB", "en"), ("it-IT", "en"), (None, "en")):
            self.assertEqual(normalize_language(regional), expected)
        en, de = Translator("en"), Translator("de")
        en.language = "fr"
        self.assertEqual(en("Aufnehmen"), "Enregistrer")
        self.assertEqual(de("Aufnehmen"), "Aufnehmen")
        self.assertEqual(en("User text {untouched}"), "User text {untouched}")

    def test_device_errors_keep_their_template_until_displayed(self):
        error = ValueError(Message("Display-Übertragung fehlgeschlagen: {details}", {"details": "USB {gone}"}))
        self.assertEqual(Translator("en")(error), "Display transfer failed: USB {gone}")
        self.assertEqual(Translator("fr")(error), "Échec du transfert à l'écran : USB {gone}")

    def test_lcd_controls_and_week_labels_fit_without_truncation(self):
        for language in LANGUAGES:
            tr = Translator(language)
            for source in ("lcd.clock_button", "MENUE", "PAUSE", "START", "ZEIT", "TASK", "PLAY"):
                self.assertLessEqual(SMALL.width(tr(source)), 37, (language, source))
                self.assertNotIn("?", lcd_text(tr(source)), (language, source))
            self.assertLessEqual(SMALL.width(window_label({"windowDurationMins": 10080}, language)), 30)
            self.assertLessEqual(SMALL.width(tr("{remaining:.0f}% frei", remaining=100)), 55)
            for weekday in range(19, 26):
                label = date_label(datetime(2026, 10, weekday), language)
                self.assertLessEqual(SMALL.width(label), 158)
                self.assertNotIn("?", lcd_text(label))

    def test_fixed_ui_and_error_messages_have_translations(self):
        # Check actual UI entry points so new untranslated labels fail this test.
        root = Path(__file__).resolve().parents[1] / "g15display"
        for path in root.glob("*.py"):
            if path.name == "i18n.py":
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                source = None
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("label", "macroLabel", "button", "macroButton", "testLabel", "testButton", "item", "tr") and node.args:
                        source = node.args[0]
                    elif node.func.attr == "localize" and len(node.args) == 3:
                        source = node.args[2]
                if isinstance(source, ast.Constant) and isinstance(source.value, str) and source.value:
                    self.assertIn(source.value, CATALOG, (path.name, source.value))


class LanguageStateTests(unittest.TestCase):
    def test_switching_language_keeps_timer_page_bank_and_user_content(self):
        now = [0]
        sources = SimpleNamespace(poll=Mock(), close=Mock(), snapshots={})
        controller = AppController(sources=sources, legacy_check=lambda: False, clock=lambda: now[0], language="de")
        controller.submit("enabled", False)
        controller.submit("page", "timer")
        controller.submit("bank", "M2")
        controller.submit("key", "L4")
        controller.step()
        timer = controller.dashboard.timer
        for language in LANGUAGES:
            now[0] += 10
            controller.submit("language", language)
            controller.step()
            self.assertIs(controller.dashboard.timer, timer)
            self.assertTrue(timer.running)
            self.assertEqual(timer.remaining, 300 - now[0])
            state = controller.snapshot()
            self.assertEqual((state["language"], state["bank"], state["page"]), (language, "M2", PAGES.index("timer")))

    def test_all_pages_render_in_each_language_and_user_titles_stay_unchanged(self):
        now = datetime(2026, 10, 19, 15)
        snapshots = {
            "limits": Snapshot([dict(usedPercent=0, windowDurationMins=10080)], ""),
            "activity": Snapshot(dict(active=[dict(name="Arbeit {user title}")], unknown=[], complete=[]), ""),
            "music": Snapshot(dict(title="Keine Wiedergabe", player="Spotify", state="playing", duration=0), ""),
            "network": Snapshot(dict(interface="en0", ip="192.0.2.1", down=None, up=0), ""),
        }
        sources = SimpleNamespace(snapshots=snapshots)
        for language in LANGUAGES:
            ui = Dashboard(sources, language=language)
            with patch("g15display.dashboard.fitted", wraps=__import__("g15display.dashboard", fromlist=["fitted"]).fitted) as fitted:
                for ui.page in range(len(PAGES)):
                    for ui.menu in (False, True):
                        self.assertEqual(ui.render(now).size, (160, 43))
                texts = [call.args[2] for call in fitted.call_args_list]
                self.assertIn("Arbeit {user title}", texts)
                self.assertIn("Keine Wiedergabe", texts)
                self.assertIn(Translator(language)(TITLES[0]), texts)
            snapshots["music"] = Snapshot(error="Musik-Zugriff erlauben")
            ui.page, ui.menu = PAGES.index("music"), False
            self.assertEqual(ui.render(now).mode, "1")
            snapshots["music"] = Snapshot(dict(title="Keine Wiedergabe", player="Spotify", state="playing", duration=0), "")

    @unittest.skipUnless(sys.platform == "darwin", "macOS recorder")
    def test_recording_language_switch_preserves_target_events_and_profile(self):
        from g15display.macos_macros import MacMacroService
        from g15display.macros import MacroStore, Stroke
        with tempfile.TemporaryDirectory() as root:
            service = MacMacroService(MacroStore(Path(root) / "macros.json"))
            service.target = ("M2", "G4", "User {macro}")
            service.events = [Stroke("down", 0), Stroke("up", 0)]
            service.message = Message("Aufnahme in {seconds} Sekunden – Zielprogramm auswählen.", dict(seconds=2))
            service.tr.language = "fr"
            self.assertIn("Enregistrement dans 2 secondes", service.snapshot()["message"])
            self.assertEqual(service.target, ("M2", "G4", "User {macro}"))
            self.assertEqual(len(service.events), 2)
            service.stop()
            self.assertEqual(service.store.get("M2", "G4").name, "User {macro}")
            service.tr.language = "es"
            self.assertEqual(service.snapshot()["message"], "M2/G4: 2 eventos guardados.")

    def test_cli_language_works_before_or_after_subcommand(self):
        from g15display.__main__ import main
        with tempfile.TemporaryDirectory() as root:
            for args in (["--language", "fr", "clock"], ["clock", "--language", "fr"]):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(args + ["--preview", str(Path(root) / "clock.png")]), 0)
                self.assertIn("Aperçu", output.getvalue())
            with redirect_stderr(io.StringIO()) as error:
                with self.assertRaises(SystemExit):
                    main(["clock", "--language", "es", "--seconds", "-1"])
            self.assertIn("positivo", error.getvalue())


if __name__ == "__main__":
    unittest.main()
