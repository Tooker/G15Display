"""USB transport and the G15 v1's vertically packed monochrome framebuffer."""

import ctypes
from functools import lru_cache
import sys

from PIL import Image

from .keys import KeyEvent, KeyTracker
from .device_lock import DeviceBusy, DeviceLease

WIDTH, HEIGHT = 160, 43
VENDOR_ID, PRODUCT_ID = 0x046D, 0xC222
REPORT_ID, HEADER_SIZE, REPORT_SIZE = 3, 32, 992


class G15Error(RuntimeError):
    pass


def encode_report(image: Image.Image) -> bytes:
    """A white pixel is active; (0, 0) is the top left of the LCD.

    Each byte contains eight vertical pixels, least significant bit first.
    Six horizontal bands follow a 32-byte header, including the report ID.
    The five unused bits in the last band remain zero.
    """
    if image.size != (WIDTH, HEIGHT):
        raise ValueError(f"Das Bild muss {WIDTH} × {HEIGHT} Pixel groß sein.")
    pixels = image.convert("1", dither=Image.Dither.NONE).load()
    report = bytearray(REPORT_SIZE)
    report[0] = REPORT_ID
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if pixels[x, y]:
                report[HEADER_SIZE + (y // 8) * WIDTH + x] |= 1 << (y % 8)
    return bytes(report)


@lru_cache(maxsize=1)
def _darwin_library(module_path: str):
    # cython-hidapi does not expose this public HIDAPI platform API. Load the
    # very same bundled library, not a second Homebrew/system HIDAPI instance.
    library = ctypes.CDLL(module_path)
    try:
        configure = library.hid_darwin_set_open_exclusive
    except AttributeError as exc:
        raise G15Error("Die HIDAPI-Version unterstützt keinen gemeinsamen macOS-Zugriff.") from exc
    configure.argtypes = [ctypes.c_int]
    configure.restype = None
    library.hid_error.argtypes = [ctypes.c_void_p]
    library.hid_error.restype = ctypes.c_wchar_p
    return library


def _hid():
    # Preview and framebuffer tests also work without the USB dependency.
    try:
        import hid
    except ImportError as exc:
        raise G15Error("USB-Bibliothek fehlt. Bitte 'python -m pip install -e .' ausführen.") from exc
    if sys.platform == "darwin":
        # The G15 is already used by macOS/keyboard tools. Do not seize it.
        _darwin_library(hid.__file__).hid_darwin_set_open_exclusive(0)
    return hid


def list_devices() -> list[dict]:
    """Only the original G15 display device, never the c221 typing device."""
    return _hid().enumerate(VENDOR_ID, PRODUCT_ID)


def select_device(devices: list[dict]) -> dict:
    # macOS enumerates each top-level HID collection separately. Prefer the
    # vendor collection that contains output report 3, not the keypad collection.
    by_path = {d["path"]: d for d in devices
               if d.get("vendor_id") == VENDOR_ID and d.get("product_id") == PRODUCT_ID}
    candidates = list(by_path.values())
    vendor = [d for d in candidates if d.get("usage_page") == 0xFF00]
    if vendor:
        candidates = vendor
    if not candidates:
        raise G15Error("Keine G15 v1 gefunden (046d:c222). Bitte USB-Verbindung prüfen.")
    if len(candidates) != 1:
        raise G15Error("Mehrere G15-Schnittstellen gefunden. Bitte nur eine G15 anschließen und 'devices' prüfen.")
    return candidates[0]


class G15:
    """Use as a context manager so the handle is closed even on Ctrl+C."""

    def __init__(self):
        self._device = None
        self._keys = KeyTracker()
        self._lease = None

    @property
    def held_keys(self) -> frozenset[str]:
        """Keys held in the most recently received valid input snapshot."""
        return self._keys.held

    def __enter__(self):
        if self._device is not None:
            raise G15Error("Diese G15-Verbindung ist bereits geöffnet.")
        self._lease = DeviceLease()
        try:
            self._lease.acquire()
            return self._open()
        except DeviceBusy as exc:
            self.close()
            raise G15Error(str(exc)) from exc
        except Exception:
            self.close()
            raise

    def _open(self):
        info = select_device(list_devices())
        hid = _hid()
        device = hid.device()
        try:
            device.open_path(info["path"])
        except OSError as exc:
            details = str(exc)
            if sys.platform == "darwin":
                details = _darwin_library(hid.__file__).hid_error(None) or details
            device.close()
            raise G15Error(
                "G15 lässt sich nicht öffnen. Andere Display-Programme schließen; "
                "falls macOS den Zugriff verweigert, die Eingabeüberwachung für "
                f"das startende Terminal bzw. Codex prüfen. Details: {details}"
            ) from exc
        self._device = device
        self._keys = KeyTracker()
        return self

    def read_keys(self, timeout_ms: int = 100) -> list[KeyEvent]:
        """Read one report with a bounded wait; return press/release events.

        A timeout or an unrelated report yields no events and preserves state.
        Poll repeatedly to receive further reports. Does not read normal typing.
        """
        if self._device is None:
            raise G15Error("Die G15 ist nicht geöffnet. Bitte 'with G15() as lcd:' verwenden.")
        if not isinstance(timeout_ms, int) or timeout_ms <= 0:
            raise ValueError("timeout_ms muss eine positive ganze Zahl sein.")
        try:
            report = bytes(self._device.read(9, timeout_ms))
        except OSError as exc:
            raise G15Error(f"Lesen der G15-Tasten fehlgeschlagen: {exc}") from exc
        return self._keys.update(report)

    def show(self, image: Image.Image):
        if self._device is None:
            raise G15Error("Die G15 ist nicht geöffnet. Bitte 'with G15() as lcd:' verwenden.")
        report = encode_report(image)
        try:
            written = self._device.write(report)
        except OSError as exc:
            raise G15Error(f"Display-Übertragung fehlgeschlagen: {exc}") from exc
        if written != len(report):
            raise G15Error(f"Display-Übertragung unvollständig: {written}/{len(report)} Bytes.")

    def __exit__(self, *_):
        self.close()

    def close(self):
        try:
            if self._device is not None:
                device, self._device = self._device, None
                device.close()
        finally:
            if self._lease is not None:
                self._lease.close()
                self._lease = None
