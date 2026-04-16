# Neuralis Terminal

Neuralis Terminal is a PySide6 desktop front-end for managing OpenClaw projects, personalities, and session state through a local persistence layer and a future gateway integration layer.

## Milestone 1 status

This repository currently implements the foundation layer:

- package scaffold
- dataclass models
- SQLite repositories
- filesystem-backed storage helpers
- JSON settings store
- lightweight controllers
- minimal Qt startup shell

Gateway communication and full session UI behavior are intentionally left for later milestones.

# Setup

/home/ubuntu/ai_projects/neuralis_terminal
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .[dev]


## Run

```bash
python -m openclaw_gui.main
```

If you are launching in a headless environment, the app will automatically fall back to Qt's `offscreen` platform.
You can also force that mode explicitly with `NEURALIS_TERMINAL_HEADLESS=1 python -m openclaw_gui.main`.

On Linux X11 desktops, Qt 6 also needs the system package `libxcb-cursor0`. If startup exits with an `xcb` platform plugin error, install it with:

```bash
sudo apt install libxcb-cursor0
```

## Test

```bash
pytest
```
