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
from .macos_macros import MacMacroService
from .i18n import LANGUAGES, Translator
from .keyboard_test import KEYS, KeyboardTest, result_message

PAGE_NAMES = ("Uhr", "Codex-Limits", "Laufende Codex-Aufgaben", "Timer", "Pomodoro", "Musik", "Netzwerk")


class G15Application(A.NSObject):
    def applicationDidFinishLaunching_(self, notification):
        self.defaults = F.NSUserDefaults.standardUserDefaults()
        self.defaults.registerDefaults_({"minutes": 5.0, "work": 25.0, "rest": 5.0, "rounds": 4})
        saved = self.defaults.stringForKey_("language")
        preferred = next((str(code) for code in F.NSLocale.preferredLanguages()
                          if str(code).replace("_", "-").split("-")[0] in LANGUAGES), "en")
        self.tr = Translator(saved or preferred)
        self.localizedViews = []
        try:
            settings = Settings(self.defaults.doubleForKey_("minutes"), self.defaults.doubleForKey_("work"),
                                self.defaults.doubleForKey_("rest"), self.defaults.integerForKey_("rounds")).validate()
        except ValueError:
            settings = Settings()
        self.macros = MacMacroService(language=self.tr.language)
        self.controller = AppController(settings, macros=self.macros, language=self.tr.language)
        self.keyboardTest = KeyboardTest()
        self.testWindow = None
        self.macroWindow = None
        self.lastGShown = None
        self.quitting = False
        self.revision = -1
        self.buildMenus()
        self.buildWindow(settings)
        self.controller.start()
        self.refreshTimer = F.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.25, self, "refresh:", None, True)
        # NSTerminateLater uses the modal run loop; keep the shutdown check alive.
        F.NSRunLoop.mainRunLoop().addTimer_forMode_(self.refreshTimer, F.NSRunLoopCommonModes)
        self.showWindow_(None)

    @objc.python_method
    def localize(self, view, setter, source):
        self.localizedViews.append((view, setter, source))
        getattr(view, setter)(self.tr(source))
        return view

    def changeLanguage_(self, sender):
        language = tuple(LANGUAGES)[sender.indexOfSelectedItem()]
        self.defaults.setObject_forKey_(language, "language")
        self.tr.language = language
        self.macros.tr.language = language
        self.controller.submit("language", language)
        for view, setter, source in self.localizedViews:
            getattr(view, setter)(self.tr(source))
        selected = self.pagePopup.indexOfSelectedItem()
        self.pagePopup.removeAllItems()
        self.pagePopup.addItemsWithTitles_([self.tr(title) for title in PAGE_NAMES])
        self.pagePopup.selectItemAtIndex_(selected)
        self.revision = -1
        self.refresh_(self.refreshTimer)

    @objc.python_method
    def item(self, title, action, key=""):
        item = A.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, key)
        item.setTarget_(self)
        return self.localize(item, "setTitle_", title)

    @objc.python_method
    def buildMenus(self):
        menu = A.NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)
        menu.addItem_(self.item("G15 Display anzeigen", "showWindow:"))
        menu.addItem_(self.item("G-Tasten / Makros …", "showMacros:"))
        menu.addItem_(self.item("Tastentest …", "showKeyboardTest:"))
        self.stopMacroItem = self.item("Aufnahme / Wiedergabe stoppen", "stopMacro:")
        menu.addItem_(self.stopMacroItem)
        self.outputItem = self.item("Display trennen", "toggleOutput:")
        menu.addItem_(self.outputItem)
        menu.addItem_(A.NSMenuItem.separatorItem())
        menu.addItem_(self.item("Zugriffseinstellungen …", "openPermissions:"))
        menu.addItem_(self.item("Beenden", "quit:", "q"))
        if not hasattr(self, "statusItem"):
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
            edit_entry = A.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, key)
            self.localize(edit_entry, "setTitle_", title)
            edit_menu.addItem_(edit_entry)
        self.localize(edit_item, "setTitle_", "Bearbeiten")
        self.localize(edit_menu, "setTitle_", "Bearbeiten")
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
        return self.localize(label, "setStringValue_", text)

    @objc.python_method
    def button(self, title, action, frame):
        button = A.NSButton.buttonWithTitle_target_action_(title, self, action)
        button.setFrame_(frame)
        button.setBezelStyle_(A.NSBezelStyleRounded)
        self.window.contentView().addSubview_(button)
        return self.localize(button, "setTitle_", title)

    @objc.python_method
    def buildWindow(self, settings):
        style = A.NSWindowStyleMaskTitled | A.NSWindowStyleMaskClosable | A.NSWindowStyleMaskMiniaturizable
        self.window = A.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), (688, 540)), style, A.NSBackingStoreBuffered, False)
        self.window.setTitle_("G15 Display")
        self.window.setReleasedWhenClosed_(False)
        self.window.setDelegate_(self)
        self.window.center()
        self.label("Dein G15-Dashboard", ((24, 492), (430, 30)), size=23)
        self.languagePopup = A.NSPopUpButton.alloc().initWithFrame_pullsDown_(((484, 491), (180, 30)), False)
        self.languagePopup.addItemsWithTitles_(list(LANGUAGES.values()))
        self.languagePopup.selectItemAtIndex_(tuple(LANGUAGES).index(self.tr.language))
        self.localize(self.languagePopup, "setToolTip_", "Sprache")
        self.languagePopup.setTarget_(self)
        self.languagePopup.setAction_("changeLanguage:")
        self.window.contentView().addSubview_(self.languagePopup)
        self.connectionLabel = self.label("Verbindung wird vorbereitet …", ((24, 457), (640, 32)), secondary=True)
        self.preview = A.NSImageView.alloc().initWithFrame_(((24, 278), (640, 172)))
        self.preview.setImageScaling_(A.NSImageScaleNone)
        self.localize(self.preview, "setToolTip_", "Live-Vorschau des 160 × 43 Pixel großen Displays")
        self.window.contentView().addSubview_(self.preview)
        self.lcdButtons = []
        for index, title in enumerate(("Zurück", "Weiter", "Aktion", "Menü")):
            button = self.button(title, "pressButton:", ((24 + index * 166, 235), (142, 32)))
            button.setTag_(index)
            self.lcdButtons.append(button)
        self.pagePopup = A.NSPopUpButton.alloc().initWithFrame_pullsDown_(((24, 192), (250, 30)), False)
        self.pagePopup.addItemsWithTitles_([self.tr(title) for title in PAGE_NAMES])
        self.pagePopup.setTarget_(self)
        self.pagePopup.setAction_("changePage:")
        self.window.contentView().addSubview_(self.pagePopup)
        self.button("G-Tasten …", "showMacros:", ((286, 192), (144, 32)))
        self.connectButton = self.button("Verbinden", "connect:", ((442, 192), (105, 32)))
        self.disconnectButton = self.button("Trennen", "disconnect:", ((557, 192), (107, 32)))
        self.label("Timer & Pomodoro", ((24, 156), (400, 22)), size=15)
        self.button("Tastentest …", "showKeyboardTest:", ((444, 151), (220, 30)))
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
        if sender == self.testWindow:
            self.keyboardTest.stop()
        if sender == self.macroWindow:
            self.macros.close()
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
            alert.setMessageText_(self.tr("Bitte die Timerzeiten prüfen"))
            alert.setInformativeText_(self.tr(exc))
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
        self.macros.tick()
        if self.testWindow is not None:
            self.refreshKeyboardTest()
        macro_state = self.macros.snapshot()
        self.stopMacroItem.setEnabled_(macro_state["recording"] or macro_state["playing"])
        self.statusItem.button().setTitle_("● REC" if macro_state["recording"] else "G15")
        state = self.controller.snapshot()
        if not state:
            return
        if self.macroWindow is not None:
            self.refreshMacros(state, macro_state)
        if state["connected"]:
            status = "G15 verbunden · Display und Tasten sind aktiv"
        elif not state["enabled"]:
            status = "Display getrennt · Vorschau und Timer laufen weiter"
        else:
            status = state["error"] or "G15 wird gesucht …"
        self.connectionLabel.setStringValue_(self.tr(status))
        self.connectButton.setEnabled_(not state["enabled"] or not state["connected"])
        self.disconnectButton.setEnabled_(state["enabled"])
        self.outputItem.setTitle_(self.tr("Display trennen" if state["enabled"] else "Display verbinden"))
        self.pagePopup.selectItemAtIndex_(state["page"])
        self.lcdButtons[3].setTitle_(self.tr("Zur Uhr" if state["menu"] else "Menü"))
        health = state["health"]
        names = {"limits": "Codex-Limits", "activity": "Aufgaben", "music": "Musik", "network": "Netzwerk"}
        summaries = [f"{self.tr(names[name])}: {self.tr(error or 'verbunden')}" for name, error in health.items()]
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
        self.controller.stop()
        self.macros.shutdown()
        self.keyboardTest.stop()
        self.connectionLabel.setStringValue_(self.tr("G15 Display wird beendet …"))
        return A.NSTerminateLater if self.controller.alive else A.NSTerminateNow

    @objc.python_method
    def macroLabel(self, text, frame, size=13):
        label = A.NSTextField.wrappingLabelWithString_(text)
        label.setFrame_(frame)
        label.setFont_(A.NSFont.systemFontOfSize_(size))
        self.macroWindow.contentView().addSubview_(label)
        return self.localize(label, "setStringValue_", text)

    @objc.python_method
    def macroButton(self, title, action, frame):
        button = A.NSButton.buttonWithTitle_target_action_(title, self, action)
        button.setFrame_(frame)
        self.macroWindow.contentView().addSubview_(button)
        return self.localize(button, "setTitle_", title)

    def showMacros_(self, sender):
        if self.macroWindow is None:
            style = A.NSWindowStyleMaskTitled | A.NSWindowStyleMaskClosable
            self.macroWindow = A.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                ((0, 0), (688, 450)), style, A.NSBackingStoreBuffered, False)
            self.localize(self.macroWindow, "setTitle_", "G-Tasten & Makros")
            self.macroWindow.setReleasedWhenClosed_(False)
            self.macroWindow.setDelegate_(self)
            self.macroWindow.center()
            self.macroLabel("G-Tasten & Makros", ((24, 398), (430, 32)), size=23)
            self.macroStatus = self.macroLabel("", ((24, 342), (640, 48)))
            self.macroLabel("Bank", ((24, 322), (100, 18)), size=12)
            self.macroLabel("G-Taste", ((144, 322), (100, 18)), size=12)
            self.macroLabel("Name für die neue Aufnahme", ((264, 322), (400, 18)), size=12)
            self.bankPopup = A.NSPopUpButton.alloc().initWithFrame_pullsDown_(((24, 286), (100, 30)), False)
            self.bankPopup.addItemsWithTitles_(("M1", "M2", "M3"))
            self.bankPopup.setTarget_(self)
            self.bankPopup.setAction_("macroBank:")
            self.macroWindow.contentView().addSubview_(self.bankPopup)
            self.gPopup = A.NSPopUpButton.alloc().initWithFrame_pullsDown_(((144, 286), (100, 30)), False)
            self.gPopup.addItemsWithTitles_([f"G{i}" for i in range(1, 19)])
            self.gPopup.setTarget_(self)
            self.gPopup.setAction_("macroKey:")
            self.macroWindow.contentView().addSubview_(self.gPopup)
            self.macroName = A.NSTextField.alloc().initWithFrame_(((264, 288), (400, 25)))
            self.localize(self.macroName, "setPlaceholderString_", "Zum Beispiel: Textbaustein")
            self.macroWindow.contentView().addSubview_(self.macroName)
            self.recordButton = self.macroButton("Aufnehmen", "recordMacro:", ((24, 236), (145, 32)))
            self.stopButton = self.macroButton("Stoppen", "stopMacro:", ((189, 236), (145, 32)))
            self.testButton = self.macroButton("Testen (3 Sek.)", "testMacro:", ((354, 236), (145, 32)))
            self.deleteButton = self.macroButton("Makro löschen", "deleteMacro:", ((519, 236), (145, 32)))
            self.bindingLabel = self.macroLabel("Noch kein Makro gespeichert.", ((24, 208), (640, 22)))
            self.macroLabel("Aufnehmen startet nach 3 Sekunden. Wechsle dann zum Zielprogramm. "
                            "Während der Aufnahme werden Tastendrücke systemweit erfasst. "
                            "Stoppen oder die MR-Taste beendet die Aufnahme.", ((24, 148), (640, 56)))
            self.lastKeyLabel = self.macroLabel("Letzte G-Taste: —", ((24, 114), (640, 22)))
            self.macroButton("Aufnahme freigeben …", "recordAccess:", ((24, 65), (300, 32)))
            self.macroButton("Wiedergabe freigeben …", "playAccess:", ((344, 65), (320, 32)))
            self.macroLabel("Maximal 60 Sekunden / 500 Ereignisse. MR stoppt auch eine Wiedergabe. "
                            "Fenster schließen verwirft eine laufende Aufnahme.", ((24, 18), (640, 36)), size=11)
            self.bankPopup.selectItemWithTitle_(self.controller.snapshot().get("bank", "M1"))
            self.macroKey_(None)
        self.macroWindow.makeKeyAndOrderFront_(None)
        A.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

    @objc.python_method
    def macroTarget(self):
        return str(self.bankPopup.titleOfSelectedItem()), str(self.gPopup.titleOfSelectedItem())

    def macroBank_(self, sender):
        self.controller.submit("bank", self.bankPopup.titleOfSelectedItem())
        self.macroKey_(None)

    def macroKey_(self, sender):
        self.shownMacroTarget = self.macroTarget()
        macro = self.macros.store.get(*self.macroTarget())
        self.macroName.setStringValue_(macro.name if macro else "")

    def recordMacro_(self, sender):
        bank, key = self.macroTarget()
        self.macros.arm(bank, key, str(self.macroName.stringValue()))

    def stopMacro_(self, sender):
        self.macros.stop()
        self.macros.request_stop()

    def testMacro_(self, sender):
        self.macros.test(*self.macroTarget())

    def deleteMacro_(self, sender):
        try:
            self.macros.store.set(*self.macroTarget(), None)
            self.macros.message = "Makro gelöscht."
            self.macroName.setStringValue_("")
        except (ValueError, OSError) as exc:
            self.macros.message = str(exc)

    def recordAccess_(self, sender):
        import Quartz as Q
        Q.CGRequestListenEventAccess()
        self.openPermissions_(None)

    def playAccess_(self, sender):
        import Quartz as Q
        Q.CGRequestPostEventAccess()
        A.NSWorkspace.sharedWorkspace().openURL_(F.NSURL.URLWithString_(
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"))

    @objc.python_method
    def refreshMacros(self, state, recording):
        self.macroStatus.setStringValue_(self.tr(recording["message"]))
        self.macroStatus.setTextColor_(A.NSColor.systemRedColor() if recording["recording"] else A.NSColor.labelColor())
        self.recordButton.setEnabled_(not recording["recording"] and not recording["playing"])
        self.stopButton.setEnabled_(recording["recording"] or recording["playing"])
        self.testButton.setEnabled_(not recording["recording"] and not recording["playing"])
        self.deleteButton.setEnabled_(not recording["recording"] and not recording["playing"])
        self.bankPopup.setEnabled_(not recording["recording"])
        self.gPopup.setEnabled_(not recording["recording"])
        self.macroName.setEnabled_(not recording["recording"])
        if not recording["recording"]:
            self.bankPopup.selectItemWithTitle_(state["bank"])
            if state["last_g_key"] != self.lastGShown:
                self.lastGShown = state["last_g_key"]
                if self.lastGShown:
                    self.gPopup.selectItemWithTitle_(self.lastGShown)
                    self.macroKey_(None)
            if self.macroTarget() != self.shownMacroTarget:
                self.macroKey_(None)
        self.lastKeyLabel.setStringValue_(self.tr("Aktive Bank: {bank}   ·   Letzte G-Taste: {key}", bank=state["bank"], key=state["last_g_key"] or "—"))
        bank, key = self.macroTarget()
        macro = self.macros.store.get(bank, key)
        summary = self.tr("{name} · {count} Ereignisse · {seconds:.1f} Sek.", name=macro.name, count=len(macro.events), seconds=sum(e.delay for e in macro.events)) if macro else self.tr("noch kein Makro")
        self.bindingLabel.setStringValue_(f"{bank}/{key}: {summary}")

    @objc.python_method
    def testLabel(self, text, frame, size=13):
        label = A.NSTextField.wrappingLabelWithString_(text)
        label.setFrame_(frame)
        label.setFont_(A.NSFont.systemFontOfSize_(size))
        self.testWindow.contentView().addSubview_(label)
        return self.localize(label, "setStringValue_", text)

    @objc.python_method
    def testButton(self, title, action, frame):
        button = A.NSButton.buttonWithTitle_target_action_(title, self, action)
        button.setFrame_(frame)
        self.testWindow.contentView().addSubview_(button)
        return self.localize(button, "setTitle_", title)

    def showKeyboardTest_(self, sender):
        if self.testWindow is None:
            style = A.NSWindowStyleMaskTitled | A.NSWindowStyleMaskClosable
            self.testWindow = A.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                ((0, 0), (800, 540)), style, A.NSBackingStoreBuffered, False)
            self.localize(self.testWindow, "setTitle_", "Normale G15-Tasten prüfen")
            self.testWindow.setReleasedWhenClosed_(False)
            self.testWindow.setDelegate_(self)
            self.testWindow.center()
            self.testLabel("Normale G15-Tasten prüfen", ((24, 486), (752, 32)), size=23)
            self.testLabel("Alle Tasten loslassen, Start drücken. Dann die Prüftaste genau zehnmal langsam drücken und jeweils ganz loslassen. Danach auswerten. Gemessen wird nur die physische G15; Texte werden nicht gespeichert.",
                           ((24, 408), (752, 70)))
            self.testTarget = A.NSPopUpButton.alloc().initWithFrame_pullsDown_(((24, 366), (300, 30)), False)
            self.testTarget.addItemsWithTitles_([self.tr(name) for _, name in KEYS])
            self.testTarget.setTarget_(self)
            self.testTarget.setAction_("testTarget:")
            self.testWindow.contentView().addSubview_(self.testTarget)
            self.testStart = self.testButton("Start", "startKeyboardTest:", ((344, 365), (100, 32)))
            self.testStop = self.testButton("Stoppen", "stopKeyboardTest:", ((454, 365), (100, 32)))
            self.testReset = self.testButton("Zurücksetzen", "resetKeyboardTest:", ((564, 365), (212, 32)))
            self.testStatus = self.testLabel("", ((24, 313), (540, 44)))
            self.testButton("Zugriff …", "recordAccess:", ((590, 318), (186, 32)))
            self.testFinish = self.testButton("Ich habe zehnmal gedrückt – auswerten", "finishKeyboardTest:", ((24, 270), (752, 32)))
            self.testMetrics = self.testLabel("", ((24, 119), (752, 142)), size=15)
            self.testResult = self.testLabel("", ((24, 54), (752, 60)))
            self.testLabel("Langes Halten und schnelle Wiederbetätigung sind Hinweise, kein Defektbeweis. Außerhalb dieses Fensters kann die Taste weiterhin normal wirken. Schließen stoppt die Messung.",
                           ((24, 8), (752, 42)), size=11)
        self.refreshKeyboardTest()
        self.testWindow.makeKeyAndOrderFront_(None)
        A.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

    def testTarget_(self, sender):
        self.keyboardTest.reset(KEYS[sender.indexOfSelectedItem()][0])

    def startKeyboardTest_(self, sender):
        import Quartz as Q
        if not Q.CGPreflightListenEventAccess():
            self.keyboardTest.reset(KEYS[self.testTarget.indexOfSelectedItem()][0])
            self.keyboardTest.status = "Tastaturzugriff verweigert. Eingabeüberwachung prüfen und App neu starten."
            self.keyboardTest.session_problem = True
            Q.CGRequestListenEventAccess()
            return
        self.keyboardTest.start(KEYS[self.testTarget.indexOfSelectedItem()][0])
        self.testWindow.makeFirstResponder_(None)

    def stopKeyboardTest_(self, sender):
        self.keyboardTest.stop()

    def resetKeyboardTest_(self, sender):
        self.keyboardTest.reset(KEYS[self.testTarget.indexOfSelectedItem()][0])

    def finishKeyboardTest_(self, sender):
        self.keyboardTest.finish(10)

    @objc.python_method
    def refreshKeyboardTest(self):
        data = self.keyboardTest.snapshot()
        self.testStatus.setStringValue_(self.tr(data["status"]))
        self.testTarget.setEnabled_(not data["running"])
        self.testStart.setEnabled_(not data["running"])
        self.testStop.setEnabled_(data["running"])
        self.testFinish.setEnabled_(not data["session_problem"] and (data["running"] or data["seen"]))
        self.testReset.setEnabled_(not data["running"])
        index = self.testTarget.indexOfSelectedItem()
        titles = [self.tr(name) for _, name in KEYS]
        if str(self.testTarget.itemTitleAtIndex_(0)) != titles[0]:
            self.testTarget.removeAllItems()
            self.testTarget.addItemsWithTitles_(titles)
            self.testTarget.selectItemAtIndex_(index)
        state = self.tr("Unklar") if data["uncertain"] or not data["seen"] else self.tr("Gedrückt" if data["held"] else "Losgelassen")
        self.testMetrics.setStringValue_(self.tr(
            "Drücken: {presses}    Loslassen: {releases}\nZustand: {state}    Gemeldete Haltedauer: {duration:.2f} s\nLängste Haltedauer: {max_hold:.2f} s\nSchnelle Wiederbetätigungen (≤ 50 ms): {rapid}\nUngültige/Rollover-Meldungen: {problems}",
            presses=data["presses"], releases=data["releases"], state=state,
            duration=data["duration"], max_hold=data["max_hold"], rapid=data["rapid"], problems=data["problems"]))
        self.testMetrics.setTextColor_(A.NSColor.systemOrangeColor() if data["held"] and data["duration"] >= 2 else A.NSColor.labelColor())
        self.testResult.setStringValue_(self.tr(result_message(data)))


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
