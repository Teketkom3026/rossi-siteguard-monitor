"""
SiteGuard Monitor Pro - Desktop Application
Entry point with single-instance check, splash screen, first-run wizard,
and license validation on start.
"""
import sys
import os
import logging
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QFont, QPainter, QColor
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


# ---------------------------------------------------------------------------
# Single-instance check via QLocalSocket / QLocalServer
# ---------------------------------------------------------------------------
SERVER_NAME = "RossiSiteGuardMonitor"


def is_already_running() -> bool:
    """If another instance is running, send it a 'show' command and return True."""
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if sock.waitForConnected(500):
        sock.write(b"show")
        sock.waitForBytesWritten(500)
        sock.disconnectFromServer()
        return True
    return False


# ---------------------------------------------------------------------------
# Splash helpers
# ---------------------------------------------------------------------------
def _create_splash_pixmap() -> QPixmap:
    """Create a branded splash-screen pixmap programmatically."""
    pix = QPixmap(480, 300)
    pix.fill(QColor("#1a1a2e"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Border
    painter.setPen(QColor("#4a90d9"))
    painter.drawRoundedRect(1, 1, 478, 298, 12, 12)

    # Title text
    painter.setPen(QColor("#4a90d9"))
    title_font = QFont("Segoe UI", 22, QFont.Weight.Bold)
    painter.setFont(title_font)
    painter.drawText(pix.rect().adjusted(0, 60, 0, 0), Qt.AlignmentFlag.AlignHCenter, "SiteGuard Monitor Pro")

    # Subtitle
    painter.setPen(QColor("#e0e0e0"))
    sub_font = QFont("Segoe UI", 11)
    painter.setFont(sub_font)
    painter.drawText(pix.rect().adjusted(0, 110, 0, 0), Qt.AlignmentFlag.AlignHCenter, "Site Monitoring 24/7")

    painter.end()
    return pix


def _update_splash(splash: QSplashScreen, app: QApplication, message: str):
    splash.showMessage(
        message,
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        QColor("#e0e0e0"),
    )
    app.processEvents()


# ---------------------------------------------------------------------------
# Main window launcher
# ---------------------------------------------------------------------------
def show_main_window(app: QApplication, setup_data: dict, splash: QSplashScreen):
    """Instantiate and display the main application window."""
    from ui.main_window import MainWindow

    _update_splash(splash, app, "Loading dashboard...")
    window = MainWindow(setup_data)

    if "--minimized" in sys.argv:
        logger.info("Starting minimized to tray")
        window.hide()
    else:
        window.show()
        window.raise_()
        window.activateWindow()

    splash.close()
    logger.info("Main window displayed")
    return window


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    logger.info("=" * 50)
    logger.info("SiteGuard Monitor Pro starting...")
    logger.info("=" * 50)

    app = QApplication(sys.argv)
    app.setApplicationName("SiteGuard Monitor Pro")
    app.setOrganizationName("SiteGuard")
    app.setApplicationVersion("1.1.2")

    # Single-instance guard: signal existing instance to show, then exit
    if is_already_running():
        logger.info("Another instance is running — sent show command, exiting.")
        sys.exit(0)

    # Splash screen
    splash_pix = _create_splash_pixmap()
    splash = QSplashScreen(splash_pix)
    splash.show()
    _update_splash(splash, app, "Loading...")

    # Import local storage for first-run detection
    from core.license_manager import LicenseManager

    lm = LicenseManager()

    if lm.is_first_run():
        # --- First-run wizard ---
        splash.close()
        logger.info("First run - showing setup wizard")

        from ui.setup_wizard import SetupWizard

        wizard = SetupWizard()
        window_ref = None

        def on_setup_complete(setup_data: dict):
            nonlocal window_ref
            logger.info("Setup completed, launching main window")
            lm.mark_first_run_complete()
            lm.save_setup_data(setup_data)
            # Re-create splash briefly for the loading phase
            sp = QSplashScreen(splash_pix)
            sp.show()
            _update_splash(sp, app, "Loading dashboard...")
            window_ref = show_main_window(app, setup_data, sp)

        wizard.setup_completed.connect(on_setup_complete)
        if wizard.exec() != wizard.DialogCode.Accepted:
            logger.info("Setup cancelled, exiting")
            sys.exit(0)
    else:
        # --- Normal startup ---
        setup_data = lm.load_setup_data()

        _update_splash(splash, app, "Validating license...")

        # Offline HMAC validation — no network required
        from core.license_validator import validate_key

        stored_key = lm.get_stored_key()
        is_valid = False
        message = "No license key found. Please activate a license."
        if stored_key:
            if stored_key == "TRIAL-MODE":
                is_valid, message = True, "Trial mode active"
            else:
                is_valid, message, _info = validate_key(stored_key)

        if not is_valid:
            splash.close()
            logger.warning("License invalid: %s", message)
            reply = QMessageBox.warning(
                None,
                "License",
                f"Warning: {message}\n\nPlease enter a new key or renew your license.",
                QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Close,
            )
            if reply == QMessageBox.StandardButton.Retry:
                from ui.license_dialog import LicenseDialog

                dialog = LicenseDialog()
                if dialog.exec():
                    setup_data["license_key"] = dialog.get_activated_key()
                    lm.save_setup_data(setup_data)
                else:
                    sys.exit(0)
                # Recreate splash after dialog
                splash = QSplashScreen(splash_pix)
                splash.show()
            else:
                sys.exit(0)

        show_main_window(app, setup_data, splash)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
