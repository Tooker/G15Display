"""Native menu-bar app, using Cocoa through PyObjC. No Terminal window needed."""

import io
import logging
from pathlib import Path
import sys

import AppKit as A
import Foundation as F
import objc
from PIL import Image

from .app_controller import AppController, Settings
from .dashboard import PAGES

PAGE_NAMES = ("Uhr", "Codex-Limits", "Laufende Codex-Aufgaben", "Timer", "Pomodoro", "Musik", "Netzwerk")


class G15Application(A.NSObject):
    def applicationDidFinishLaunching_(self, notification):
        self.defaults = F.NSUserDefaults.standardUserDefaults()
        self.defaults.registerDefaults_({"minutes": 5.0, "work": 25.0, "rest": 5.0, "rounds": 4})
        try:
            settings = Settings(self.defaults.doubleForKey_("minutes"), self.defaults.doubleForKey_("work"),
                                self.defaults.doubleForKey_("rest"), self.defaults.integerForKey_("rounds")).validate()
        except ValueError:
            settings = Settings()
        self.controller = AppController(settings)
        self.quitting = False
        self.revision = -1
        self.buildMenus()
        self.buildWindow(settings)
        self.controller.start()
        self.refreshTimer = F.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.25, self, "refresh:", None, True)
        self.showWindow_(None)

    @objc.python_method
    def item(self, title, action, key=""):
        item = A.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, key)
        item.setTarget_(self)
        return item

    @objc.python_method
    def buildMenus(self):
        menu = A.NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)
        menu.addItem_(self.item("G15 Display anzeigen", "showWindow:"))
        self.outputItem = self.item("Display trennen", "toggleOutput:")
        menu.addItem_(self.outputItem)
        menu.addItem_(A.NSMenuItem.separatorItem())
        menu.addItem_(self.item("Zugriffseinstellungen …", "openPermissions:"))
        menu.addItem_(self.item("Beenden", "quit:", "q"))
        self.statusItem = A.NSStatusBar.systemStatusBar().statusItemWithLength_(A.NSVariableStatusItemLength)
        self.statusItem.button().setTitle_("G15")
        self.statusItem.button().setToolTip_("G15 Display")
        self.statusItem.setMenu_(menu)
        main = A.NSMenu.alloc().init()
        app_item = A.NSMenuItem.alloc().init()
        app_item.setSubmenu_(menu)
        main.addItem_(app_item)
        edit_item = A.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Bearbeiten", None, "")
        edit_menu = A.NSMenu.alloc().initWithTitle_("Bearbeiten")
        for title, action, key in (("Ausschneiden", "cut:", "x"), ("Kopieren", "copy:", "c"),
                                   ("Einfügen", "paste:", "v"), ("Alles auswählen", "selectAll:", "a")):
            edit_menu.addItem_(A.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, key))
        edit_item.setSubmenu_(edit_menu)
        main.addItem_(edit_item)
        A.NSApplication.sharedApplication().setMainMenu_(main)

    @objc.python_method
    def label(self, text, frame, size=13, secondary=False):
        label = A.NSTextField.wrappingLabelWithString_(text)
        label.setFrame_(frame)
        label.setFont_(A.NSFont.systemFontOfSize_(size))
        label.setTextColor_(A.NSColor.secondaryLabelColor() if secondary else A.NSColor.labelColor())
        self.window.contentView().addSubview_(label)
        return label

    @objc.python_method
    def button(self, title, action, frame):
        button = A.NSButton.buttonWithTitle_target_action_(title, self, action)
        button.setFrame_(frame)
        button.setBezelStyle_(A.NSBezelStyleRounded)
        self.window.contentView().addSubview_(button)
        return button

    @objc.python_method
    def buildWindow(self, settings):
        style = A.NSWindowStyleMaskTitled | A.NSWindowStyleMaskClosable | A.NSWindowStyleMaskMiniaturizable
        self.window = A.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), (688, 540)), style, A.NSBackingStoreBuffered, False)
        self.window.setTitle_("G15 Display")
        self.window.setReleasedWhenClosed_(False)
        self.window.setDelegate_(self)
        self.window.center()
        self.label("Dein G15-Dashboard", ((24, 492), (640, 30)), size=23)
        self.connectionLabel = self.label("Verbindung wird vorbereitet …", ((24, 457), (640, 32)), secondary=True)
        self.preview = A.NSImageView.alloc().initWithFrame_(((24, 278), (640, 172)))
        self.preview.setImageScaling_(A.NSImageScaleNone)
        self.preview.setToolTip_("Live-Vorschau des 160 × 43 Pixel großen Displays")
        self.window.contentView().addSubview_(self.preview)
        self.lcdButtons = []
        for index, title in enumerate(("Zurück", "Weiter", "Aktion", "Menü")):
            button = self.button(title, "pressButton:", ((24 + index * 166, 235), (142, 32)))
            button.setTag_(index)
            self.lcdButtons.append(button)
        self.pagePopup = A.NSPopUpButton.alloc().initWithFrame_pullsDown_(((24, 192), (300, 30)), False)
        self.pagePopup.addItemsWithTitles_(PAGE_NAMES)
        self.pagePopup.setTarget_(self)
        self.pagePopup.setAction_("changePage:")
        self.window.contentView().addSubview_(self.pagePopup)
        self.connectButton = self.button("Verbinden", "connect:", ((442, 192), (105, 32)))
        self.disconnectButton = self.button("Trennen", "disconnect:", ((557, 192), (107, 32)))
        self.label("Timer & Pomodoro", ((24, 156), (400, 22)), size=15)
        self.fields = []
        for index, (name, value) in enumerate(zip(("Timer (Min.)", "Arbeit (Min.)", "Pause (Min.)", "Runden"),
                                                 (settings.minutes, settings.work, settings.rest, settings.rounds))):
            x = 24 + index * 126
            self.label(name, ((x, 130), (118, 18)), size=12, secondary=True)
            field = A.NSTextField.alloc().initWithFrame_(((x, 101), (100, 25)))
            field.setStringValue_(f"{value:g}")
            self.window.contentView().addSubview_(field)
            self.fields.append(field)
        self.button("Zeiten anwenden", "applySettings:", ((528, 98), (136, 32)))
        self.label("Zeiten anwenden setzt beide Timer zurück. Fenster schließen: läuft in der Menüleiste weiter.",
                   ((24, 72), (640, 25)), size=11, secondary=True)
        self.healthLabel = self.label("Datenquellen werden verbunden …", ((24, 20), (526, 44)), size=11, secondary=True)
        self.button("Zugriff …", "openPermissions:", ((562, 28), (102, 30)))

    def showWindow_(self, sender):
        self.window.makeKeyAndOrderFront_(None)
        A.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

    def windowShouldClose_(self, sender):
        sender.orderOut_(None)
        return False

    def applicationShouldHandleReopen_hasVisibleWindows_(self, app, visible):
        self.showWindow_(None)
        return True

    def changePage_(self, sender):
        self.controller.submit("page", PAGES[sender.indexOfSelectedItem()])

    def pressButton_(self, sender):
        self.controller.submit("key", ("L2", "L3", "L4", "L5")[sender.tag()])

    def connect_(self, sender):
        self.controller.submit("enabled", True)

    def disconnect_(self, sender):
        self.controller.submit("enabled", False)

    def toggleOutput_(self, sender):
        self.controller.submit("enabled", not self.controller.snapshot().get("enabled", True))

    def applySettings_(self, sender):
        try:
            values = [float(field.stringValue().replace(",", ".")) for field in self.fields]
            if not values[3].is_integer():
                raise ValueError("Die Rundenzahl muss eine ganze Zahl sein.")
            settings = Settings(*values[:3], int(values[3])).validate()
        except ValueError as exc:
            alert = A.NSAlert.alloc().init()
            alert.setMessageText_("Bitte die Timerzeiten prüfen")
            alert.setInformativeText_(str(exc))
            alert.runModal()
            return
        for key, value in zip(("minutes", "work", "rest", "rounds"), values):
            self.defaults.setDouble_forKey_(value, key)
        self.controller.submit("settings", settings)

    def openPermissions_(self, sender):
        url = F.NSURL.URLWithString_("x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent")
        A.NSWorkspace.sharedWorkspace().openURL_(url)

    def refresh_(self, timer):
        if self.quitting:
            if not self.controller.alive:
                timer.invalidate()
                A.NSApplication.sharedApplication().replyToApplicationShouldTerminate_(True)
            return
        state = self.controller.snapshot()
        if not state:
            return
        if state["connected"]:
            status = "G15 verbunden · Display und Tasten sind aktiv"
        elif not state["enabled"]:
            status = "Display getrennt · Vorschau und Timer laufen weiter"
        else:
            status = state["error"] or "G15 wird gesucht …"
        self.connectionLabel.setStringValue_(status)
        self.connectButton.setEnabled_(not state["enabled"] or not state["connected"])
        self.disconnectButton.setEnabled_(state["enabled"])
        self.outputItem.setTitle_("Display trennen" if state["enabled"] else "Display verbinden")
        self.pagePopup.selectItemAtIndex_(state["page"])
        self.lcdButtons[3].setTitle_("Zur Uhr" if state["menu"] else "Menü")
        health = state["health"]
        names = {"limits": "Codex-Limits", "activity": "Aufgaben", "music": "Musik", "network": "Netzwerk"}
        summaries = [f"{names[name]}: {error or 'verbunden'}" for name, error in health.items()]
        self.healthLabel.setStringValue_("  ·  ".join(summaries))
        if state["revision"] != self.revision and self.window.isVisible():
            self.revision = state["revision"]
            image = state["image"]
            colored = Image.new("RGB", image.size, (127, 182, 223))
            colored.paste((12, 30, 48), mask=image.convert("L"))
            output = io.BytesIO()
            colored.resize((640, 172), Image.Resampling.NEAREST).save(output, format="PNG")
            data = F.NSData.dataWithBytes_length_(output.getvalue(), len(output.getvalue()))
            preview = A.NSImage.alloc().initWithData_(data)
            preview.setSize_((640, 172))
            self.preview.setImage_(preview)

    def quit_(self, sender):
        A.NSApplication.sharedApplication().terminate_(None)

    def applicationShouldTerminate_(self, app):
        self.quitting = True
        self.connectionLabel.setStringValue_("G15 Display wird beendet …")
        self.controller.stop()
        return A.NSTerminateLater if self.controller.alive else A.NSTerminateNow


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--check-bundle":
        import json
        import platform
        from .display import _hid, encode_report
        from .render import clock_screen
        result = dict(frozen=bool(getattr(sys, "frozen", False)), architecture=platform.machine(),
                      report_bytes=len(encode_report(clock_screen())), hid_version=_hid().version_str())
        Path(sys.argv[2]).write_text(json.dumps(result, indent=2))
        return
    logs = Path.home() / "Library" / "Logs"
    logs.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=logs / "G15 Display.log", level=logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")
    app = A.NSApplication.sharedApplication()
    app.setActivationPolicy_(A.NSApplicationActivationPolicyAccessory)
    delegate = G15Application.alloc().init()
    app.setDelegate_(delegate)
    app.run()


if __name__ == "__main__":
    main()
