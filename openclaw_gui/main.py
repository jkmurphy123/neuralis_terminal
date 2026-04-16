"""Application entry point for Neuralis Terminal."""

from __future__ import annotations

import ctypes.util
import logging
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from openclaw_gui.app.controllers.app_controller import AppController
from openclaw_gui.app.ui.main_window import MainWindow


def configure_logging(data_root: str | Path | None = None) -> Path | None:
    """Initialize console and file logging."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    log_path: Path | None = None
    if data_root is not None:
        root = Path(data_root)
        root.mkdir(parents=True, exist_ok=True)
        logs_dir = root / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / "app.log"
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
    return log_path


def install_exception_logging() -> None:
    """Capture uncaught exceptions in the application logger."""

    def handle_exception(exc_type, exc_value, exc_traceback) -> None:
        logging.getLogger(__name__).exception(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception


def has_xcb_cursor_library() -> bool:
    """Return whether the X11 Qt plugin dependency is available."""
    return ctypes.util.find_library("xcb-cursor") is not None


def select_qt_platform() -> str | None:
    """Choose a Qt platform plugin before QApplication is created."""
    explicit_platform = os.environ.get("QT_QPA_PLATFORM")
    if explicit_platform:
        return explicit_platform

    headless_requested = os.environ.get("NEURALIS_TERMINAL_HEADLESS") == "1"
    display = os.environ.get("DISPLAY")
    wayland_display = os.environ.get("WAYLAND_DISPLAY")
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()

    if headless_requested or not (display or wayland_display):
        return "offscreen"

    if session_type == "wayland" and wayland_display:
        return "wayland"

    if display and not has_xcb_cursor_library():
        if wayland_display:
            return "wayland"
        return None

    return None


def validate_runtime_environment(platform_name: str | None) -> None:
    """Fail fast with an actionable message when required Qt runtime libs are missing."""
    explicit_platform = os.environ.get("QT_QPA_PLATFORM")
    display = os.environ.get("DISPLAY")

    if explicit_platform:
        return
    if platform_name in {"offscreen", "wayland"}:
        return
    if display and not has_xcb_cursor_library():
        raise SystemExit(
            "Neuralis Terminal cannot start the Qt X11 backend because "
            "`libxcb-cursor0` is not installed.\n"
            "Install it with: `sudo apt install libxcb-cursor0`\n"
            "If you are intentionally running headless, use: "
            "`NEURALIS_TERMINAL_HEADLESS=1 python -m openclaw_gui.main`"
        )


def create_application() -> QApplication:
    """Create the Qt application with a safe headless fallback."""
    platform_name = select_qt_platform()
    if platform_name and "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = platform_name
    validate_runtime_environment(platform_name)
    return QApplication(sys.argv)


def main() -> int:
    """Launch the desktop application."""
    app = create_application()
    controller = AppController.create_default()
    controller.initialize()
    configure_logging(controller.file_store.data_root)
    install_exception_logging()

    window = MainWindow(controller)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
