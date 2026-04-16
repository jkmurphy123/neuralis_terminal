from __future__ import annotations

import logging

from openclaw_gui import main


def test_select_qt_platform_uses_offscreen_when_headless(monkeypatch) -> None:
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    monkeypatch.setenv("NEURALIS_TERMINAL_HEADLESS", "1")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)

    assert main.select_qt_platform() == "offscreen"


def test_select_qt_platform_prefers_wayland_when_session_is_wayland(monkeypatch) -> None:
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    monkeypatch.delenv("NEURALIS_TERMINAL_HEADLESS", raising=False)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")

    assert main.select_qt_platform() == "wayland"


def test_validate_runtime_environment_raises_for_missing_xcb_runtime(monkeypatch) -> None:
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    monkeypatch.setenv("DISPLAY", ":1")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(main, "has_xcb_cursor_library", lambda: False)

    try:
        main.validate_runtime_environment(None)
    except SystemExit as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected SystemExit for missing xcb runtime dependency")

    assert "libxcb-cursor0" in message


def test_configure_logging_creates_log_file(tmp_path) -> None:
    log_path = main.configure_logging(tmp_path)

    logger = logging.getLogger("test_logger")
    logger.info("hello logging")
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert log_path is not None
    assert log_path.exists()
    assert "hello logging" in log_path.read_text(encoding="utf-8")
