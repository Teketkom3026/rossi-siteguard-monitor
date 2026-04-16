"""
SiteGuard Monitor Pro - Entry Point v1.1.3
Simple, direct launch: show window immediately, no wizard, no hidden startup.
"""
import sys
import os
import logging
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "SiteGuard Monitor" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("SiteGuard")

SERVER_NAME = "RossiSiteGuardMonitor_v2"


def send_show_to_existing() -> bool:
    """Try to connect to existing instance and send show command. Returns True if found."""
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if sock.waitForConnected(500):
        sock.write(b"show")
        sock.waitForBytesWritten(500)
        sock.disconnectFromServer()
        return True
    return False


def main():
    # Qt needs AA_EnableHighDpiScaling on some Windows setups
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("SiteGuard Monitor Pro")
    app.setOrganizationName("SiteGuard")
    app.setApplicationVersion("1.1.3")
    # CRITICAL: prevent app from quitting when window is hidden
    app.setQuitOnLastWindowClosed(False)

    # Single-instance check
    if send_show_to_existing():
        logger.info("Existing instance found — sent show command.")
        sys.exit(0)

    # Import here to avoid import errors before QApplication exists
    from ui.main_window import MainWindow

    window = MainWindow(setup_data={})

    # Force window visible — no conditions, no hiding
    window.setWindowState(Qt.WindowState.WindowNoState)
    window.show()
    window.raise_()
    window.activateWindow()

    logger.info("Main window shown, entering event loop")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
