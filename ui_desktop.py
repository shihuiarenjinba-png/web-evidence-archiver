from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable


def _state_file(app_key: str) -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        root = Path(base) / "OkinawaDesktopTools" / app_key
    else:
        root = Path.home() / ".okinawa-desktop-tools" / app_key
    return root / "ui-state.json"


def _read_state(app_key: str) -> dict:
    try:
        value = json.loads(_state_file(app_key).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def restore_window_state(root, app_key: str, *, min_width: int, min_height: int) -> None:
    state = _read_state(app_key)
    try:
        screen_w = max(min_width, int(root.winfo_screenwidth()))
        screen_h = max(min_height, int(root.winfo_screenheight()))
        width = int(state.get("width", 0))
        height = int(state.get("height", 0))
        if width >= min_width and height >= min_height:
            width = min(width, screen_w)
            height = min(height, screen_h)
            root.geometry(f"{width}x{height}")
        if state.get("zoomed"):
            def maximize() -> None:
                try:
                    root.state("zoomed")
                except Exception:
                    pass
            root.after_idle(maximize)
    except Exception:
        # UI preferences must never prevent the application from opening.
        return


def save_window_state(root, app_key: str) -> None:
    try:
        path = _state_file(app_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        previous = _read_state(app_key)
        window_state = str(root.state())
        data = dict(previous)
        data["zoomed"] = window_state == "zoomed"
        if window_state == "normal":
            root.update_idletasks()
            data["width"] = max(1, int(root.winfo_width()))
            data["height"] = max(1, int(root.winfo_height()))
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        # Persisting convenience state is best-effort only.
        return


def bind_shortcuts(root, bindings: dict[str, Callable[[], object]]) -> None:
    for sequence, callback in bindings.items():
        def handler(_event=None, action=callback):
            action()
            return "break"
        root.bind(sequence, handler, add="+")
