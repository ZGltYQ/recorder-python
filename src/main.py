"""Main entry point for the Audio Recorder application."""

import sys
import signal
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from .utils.logger import setup_logging, get_logger
from .gui.main_window import MainWindow

logger = get_logger(__name__)


def setup_signal_handlers(app: QApplication):
    """Setup signal handlers for graceful shutdown."""

    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        app.quit()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def main():
    """Main application entry point."""
    # Setup logging
    logger = setup_logging(log_to_file=True)
    logger.info("Starting Audio Recorder STT - Python Edition")

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Audio Recorder STT")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("Audio Recorder Team")

    # Set application font
    font = QFont("Segoe UI", 10)
    if not QFont(font).exactMatch():
        font = QFont("Arial", 10)
    app.setFont(font)

    # Enable high DPI scaling
    app.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    # Setup signal handlers
    setup_signal_handlers(app)

    # Create and show main window
    try:
        window = MainWindow()
        window.show()

        logger.info("Application started successfully")

        # Run application
        sys.exit(app.exec())

    except Exception as e:
        logger.error("Failed to start application", error=str(e))
        raise


if __name__ == "__main__":
    main()
