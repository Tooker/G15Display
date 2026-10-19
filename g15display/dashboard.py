"""Four-button dashboard for the original G15's 160 x 43 LCD."""

from datetime import datetime
import time

from PIL import Image, ImageDraw

from .display import G15
from .render import save_preview
from .sources import Sources
from .timers import Timer
from .pixelfont import SMALL, LARGE, lcd_text
from .i18n import Translator, date_label

PAGES = ("clock", "limits", "activity", "timer", "pomodoro", "music", "network")
TITLES = ("UHR", "CODEX LIMITS", "CODEX AKTIV", "TIMER", "POMODORO", "MUSIK", "NETZWERK")
TEXT = SMALL


def fitted(draw, xy, text, font=TEXT, width=158, fill=1, scroll=0):
    text = lcd_text(text)
    if scroll and font.width(text) > width:
        cycle = text + "    "
        offset = scroll % len(cycle)
        text = cycle[offset:] + cycle[:offset]
    while text and font.width(text) > width:
        text = text[:-1]
    font.draw(draw, xy, text, fill=fill)


def window_label(window, language="de"):
    tr = Translator(language)
    minutes = window.get("windowDurationMins")
    return {300: "5h", 10080: tr("Woche")}.get(minutes, f"{minutes}m" if minutes else tr("Limit"))


def speed(value, language="de"):
    if value is None:
        return Translator(language)("misst ...")
    return f"{value / 1048576:.1f} MiB/s" if value >= 1048576 else f"{value / 1024:.0f} KiB/s"


class Dashboard:
    def __init__(self, sources, *, page="clock", minutes=5, work=25, rest=5, rounds=4, clock=time.monotonic, language="de"):
        self.tr = Translator(language)
        self.sources, self.clock = sources, clock
        self.page = PAGES.index(page)
        self.menu = False
        self.timer = Timer(minutes, clock=clock)
        self.pomodoro = Timer(work=work, rest=rest, rounds=rounds, clock=clock)
        self.show_reset = False
        self.activity_index = 0
        self.action_down = None
        self.notice = ""
        self.notice_until = 0
        self.page_started = clock()

    @property
    def titles(self):
        return tuple(self.tr(title) for title in TITLES)

    def tick(self):
        for timer, name in ((self.timer, "TIMER"), (self.pomodoro, "POMODORO")):
            before = timer.transitions
            timer.tick()
            if timer.transitions != before:
                self.notice = (name, "FERTIG" if timer.finished else timer.phase)
                self.notice_until = self.clock() + 5

    def handle(self, event):
        if event.name == "L4":
            if event.pressed:
                self.action_down = self.clock()
            elif self.action_down is not None:
                held = self.clock() - self.action_down
                self.action_down = None
                if self.menu:
                    self.menu = False
                elif PAGES[self.page] in ("timer", "pomodoro"):
                    timer = self.timer if PAGES[self.page] == "timer" else self.pomodoro
                    timer.reset() if held >= 1 else timer.toggle()
                elif PAGES[self.page] == "limits":
                    self.show_reset = not self.show_reset
                elif PAGES[self.page] == "activity":
                    self.activity_index += 1
                elif PAGES[self.page] == "music":
                    self.sources.toggle_music()
            return
        if not event.pressed:
            return
        # Cancel a pending action if the view changes while its key is held.
        self.action_down = None
        if event.name in ("L2", "L3"):
            self.page = (self.page + (-1 if event.name == "L2" else 1)) % len(PAGES)
            self.page_started = self.clock()
        elif event.name in ("L1", "L5"):
            if self.menu:
                self.page, self.menu = 0, False
            else:
                self.menu = True

    def render(self, now=None):
        self.tick()
        now = now or datetime.now().astimezone()
        image = Image.new("1", (160, 43))
        draw = ImageDraw.Draw(image)
        page = PAGES[self.page]
        scroll = max(0, int(self.clock() - self.page_started - 3))
        footer = ["<", ">", "--", "MENUE"]
        if self.menu:
            fitted(draw, (1, 0), f"{self.tr('MENU')} {self.page + 1}/{len(PAGES)}", SMALL)
            # Three compact rows; selected row in the centre.
            for row, offset in enumerate((-1, 0, 1)):
                y = 9 + row * 8
                label = self.titles[(self.page + offset) % len(PAGES)]
                if offset == 0:
                    draw.rectangle((0, y - 1, 159, y + 6), fill=1)
                fitted(draw, (2, y), label, SMALL, fill=0 if offset == 0 else 1)
            footer = ["<", ">", "OK", self.tr("lcd.clock_button")]
        else:
            title = f"{self.tr(self.notice[0])}: {self.tr(self.notice[1])}" if self.clock() < self.notice_until else self.titles[self.page]
            fitted(draw, (1, 0), title, SMALL, width=133)
            fitted(draw, (143, 0), f"{self.page + 1}/7", SMALL, width=17)
            if page == "clock":
                fitted(draw, (1, 9), now.strftime("%H:%M:%S"), LARGE)
                fitted(draw, (1, 25), date_label(now, self.tr.language), SMALL)
            elif page in ("timer", "pomodoro"):
                timer = self.timer if page == "timer" else self.pomodoro
                fitted(draw, (1, 9), timer.label, LARGE, width=95)
                status = "FERTIG" if timer.finished else ("LAEUFT" if timer.running else "GESTOPPT")
                info = self.tr(status) if page == "timer" else f"{self.tr(timer.phase)} {timer.round}/{timer.rounds} {self.tr(status)}"
                fitted(draw, (1, 25), info, SMALL)
                footer[2] = "PAUSE" if timer.running else "START"
            else:
                name = {"limits": "limits", "activity": "activity", "music": "music", "network": "network"}[page]
                snapshot = self.sources.snapshots[name]
                if snapshot.error:
                    fitted(draw, (1, 11), self.tr(snapshot.error), SMALL)
                    fitted(draw, (1, 23), self.tr("Neuer Abruf automatisch"), SMALL)
                elif page == "limits":
                    windows = snapshot.value[:2]
                    for row, window in enumerate(windows):
                        y = 12 + row * 11
                        label = window_label(window, self.tr.language)
                        if self.show_reset:
                            reset = window.get("resetsAt")
                            value = datetime.fromtimestamp(reset).astimezone().strftime("%d.%m. %H:%M" if self.tr.language == "de" else "%d/%m %H:%M") if reset else self.tr("unbekannt")
                            fitted(draw, (1, y), f"{label}: {value}", SMALL)
                        else:
                            used = window.get("usedPercent")
                            if used is None:
                                fitted(draw, (1, y), self.tr("{label}: nicht verfuegbar", label=label), SMALL)
                                continue
                            remaining = max(0, min(100, 100 - used))
                            fitted(draw, (1, y), label, SMALL, width=30)
                            draw.rectangle((34, y, 98, y + 6), outline=1)
                            length = int(63 * remaining / 100)
                            if length:
                                draw.rectangle((35, y + 1, 34 + length, y + 5), fill=1)
                            fitted(draw, (104, y), self.tr("{remaining:.0f}% frei", remaining=remaining), SMALL, width=55)
                    if len(windows) == 1:
                        fitted(draw, (1, 23), self.tr("Nur ein Limitfenster"), SMALL)
                    footer[2] = "%" if self.show_reset else "ZEIT"
                elif page == "activity":
                    data = snapshot.value
                    tasks = data["active"]
                    if tasks:
                        task = tasks[self.activity_index % len(tasks)]
                        fitted(draw, (1, 11), self.tr("{count} aktiv (lokale Logs)", count=len(tasks)), SMALL)
                        fitted(draw, (1, 22), task["name"] or self.tr("Unbenannter Chat"), SMALL, scroll=scroll)
                    elif data["unknown"]:
                        fitted(draw, (1, 11), self.tr("Status unklar / Log alt"), SMALL)
                        fitted(draw, (1, 22), data["unknown"][0]["name"] or self.tr("Unbenannter Chat"), SMALL)
                    else:
                        fitted(draw, (1, 11), self.tr("Kein aktiver lokaler Task"), SMALL)
                        fitted(draw, (1, 22), (data["complete"][0]["name"] or self.tr("Unbenannter Chat")) if data["complete"] else self.tr("Lokal / letzte 24 Stunden"), SMALL)
                    footer[2] = "TASK"
                elif page == "music":
                    data = snapshot.value
                    fitted(draw, (1, 10), data["title"] if data.get("player") else self.tr(data["title"]), TEXT, scroll=scroll)
                    fitted(draw, (1, 22), data.get("artist", ""), SMALL, scroll=scroll)
                    duration = data.get("duration", 0)
                    if duration > 0:
                        fraction = max(0, min(1, data["position"] / duration))
                        draw.line((1, 31, 1 + int(157 * fraction), 31), fill=1)
                    footer[2] = "PAUSE" if data.get("state") == "playing" else "PLAY"
                elif page == "network":
                    data = snapshot.value
                    fitted(draw, (1, 10), f"{data['interface']}  {self.tr(data['ip'])}", SMALL)
                    fitted(draw, (1, 20), f"D {speed(data['down'], self.tr.language)}  U {speed(data['up'], self.tr.language)}", SMALL)
        draw.line((0, 33, 159, 33), fill=1)
        for index, label in enumerate(footer):
            fitted(draw, (index * 40 + 2, 35), self.tr(label), SMALL, width=37)
        return image


def run_menu(args):
    sources = Sources()
    tr = Translator(args.language)
    dashboard = Dashboard(sources, page=args.page, minutes=args.timer_minutes,
                          work=args.work_minutes, rest=args.break_minutes, rounds=args.rounds, language=args.language)
    try:
        if args.preview:
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                sources.poll()
                time.sleep(0.05)
            save_preview(dashboard.render(), args.preview)
            print(tr("Vorschau: {path}", path=args.preview.resolve()))
            return 0
        with G15() as lcd:
            print(tr("G15-Menü läuft: L2 <, L3 >, L4 Aktion (Timer: lang=Reset), L5 Menü."), flush=True)
            deadline = time.monotonic() + args.seconds if args.seconds else None
            previous = None
            next_frame = 0
            while deadline is None or time.monotonic() < deadline:
                sources.poll()
                dashboard.tick()
                for event in lcd.read_keys(timeout_ms=50):
                    before = (dashboard.page, dashboard.menu)
                    dashboard.handle(event)
                    if before != (dashboard.page, dashboard.menu):
                        print(f"{tr('Menü' if dashboard.menu else 'Ansicht')}: {dashboard.titles[dashboard.page]}", flush=True)
                if time.monotonic() >= next_frame:
                    image = dashboard.render()
                    frame = image.tobytes()
                    if frame != previous:
                        lcd.show(image)
                        previous = frame
                    next_frame = time.monotonic() + 0.2
        return 0
    finally:
        sources.close()
