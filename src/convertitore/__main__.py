"""Application and worker entry point."""

import sys
import os


def main() -> int:
    if "--worker" in sys.argv:
        from .worker import worker_main
        return worker_main()
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMessageBox
    from .background import BackgroundController
    from .instance_lock import InstanceLock, default_lock_path
    from .window import Window

    app = QApplication([])
    from .theme import install
    install(app)
    lock_path = default_lock_path()
    if '--smoke-ui' in sys.argv:
        lock_path = lock_path.with_name(f'{lock_path.stem}-smoke-{os.getpid()}.lock')
    instance = InstanceLock(lock_path)
    if not instance.acquire():
        QMessageBox.information(None, 'Convertitore già aperto',
                                'Convertitore è già in esecuzione. Apri la finestra dalla barra menu.')
        return 0
    window = Window()
    controller = BackgroundController(window)
    app.setQuitOnLastWindowClosed(not QSystemTrayIcon.isSystemTrayAvailable())
    window.show()
    if "--smoke-ui" in sys.argv:
        QTimer.singleShot(500, app.quit)
    try:
        return app.exec()
    finally:
        instance.release()


if __name__ == "__main__":
    raise SystemExit(main())
