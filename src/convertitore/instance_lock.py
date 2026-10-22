"""Prevent several installed copies from displaying overlapping drag wheels."""

import hashlib
import tempfile
from pathlib import Path

from PySide6.QtCore import QLockFile


def default_lock_path() -> Path:
    user_key = hashlib.sha256(str(Path.home()).encode('utf-8')).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / f'convertitore-suite-{user_key}.lock'


class InstanceLock:
    def __init__(self, path: Path | None = None):
        self.path = path or default_lock_path()
        self.lock = QLockFile(str(self.path))
        self.lock.setStaleLockTime(0)
        self.held = False

    def acquire(self) -> bool:
        self.held = self.lock.tryLock(0)
        return self.held

    def release(self) -> None:
        if self.held:
            self.lock.unlock()
            self.held = False
