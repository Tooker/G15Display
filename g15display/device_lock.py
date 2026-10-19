"""One display writer per login user, shared by the CLI and the macOS app."""

import fcntl
import os
from pathlib import Path
import tempfile


class DeviceBusy(RuntimeError):
    pass


class DeviceLease:
    def __init__(self, path=None):
        self.path = Path(path or Path(tempfile.gettempdir()) / f"g15display-{os.getuid()}.lock")
        self.fd = None

    def acquire(self):
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            if os.fstat(fd).st_uid != os.getuid():
                raise DeviceBusy("Die G15-Sperrdatei gehört einem anderen Benutzer.")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise DeviceBusy("Ein anderes G15-Programm verwendet das Display bereits.") from exc
        except Exception:
            os.close(fd)
            raise
        self.fd = fd

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
