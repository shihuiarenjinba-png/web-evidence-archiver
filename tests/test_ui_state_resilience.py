"""Regression tests for fail-open desktop UI state persistence.

These tests are platform-neutral. They protect startup from corrupted preference
files and prevent a stale oversized window from being restored beyond the
reported display bounds. They do not replace real Windows DPI/visual QA.
"""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ui_desktop


class FakeRoot:
    def __init__(self, *, screen=(1280, 720), size=(900, 600), state="normal"):
        self.screen = screen
        self.size = size
        self.current_state = state
        self.geometry_calls = []
        self.bind_calls = []

    def winfo_screenwidth(self):
        return self.screen[0]

    def winfo_screenheight(self):
        return self.screen[1]

    def geometry(self, value):
        self.geometry_calls.append(value)

    def state(self, value=None):
        if value is not None:
            self.current_state = value
        return self.current_state

    def after_idle(self, callback):
        callback()

    def update_idletasks(self):
        return None

    def winfo_width(self):
        return self.size[0]

    def winfo_height(self):
        return self.size[1]

    def bind(self, sequence, handler, add=None):
        self.bind_calls.append((sequence, add))


class UiStateResilienceTests(unittest.TestCase):
    def test_corrupted_state_never_blocks_restore(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"LOCALAPPDATA": tmp}, clear=False):
            path = ui_desktop._state_file("qa")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{broken json", encoding="utf-8")
            root = FakeRoot()
            ui_desktop.restore_window_state(root, "qa", min_width=700, min_height=400)
            self.assertEqual(root.geometry_calls, [])

    def test_oversized_saved_window_is_clamped_to_screen(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"LOCALAPPDATA": tmp}, clear=False):
            path = ui_desktop._state_file("qa")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"width": 5000, "height": 4000}), encoding="utf-8")
            root = FakeRoot(screen=(1280, 720))
            ui_desktop.restore_window_state(root, "qa", min_width=700, min_height=400)
            self.assertEqual(root.geometry_calls[-1], "1280x720")

    def test_save_records_normal_window_size(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"LOCALAPPDATA": tmp}, clear=False):
            root = FakeRoot(size=(910, 610))
            ui_desktop.save_window_state(root, "qa")
            saved = json.loads(ui_desktop._state_file("qa").read_text(encoding="utf-8"))
            self.assertEqual(saved["width"], 910)
            self.assertEqual(saved["height"], 610)
            self.assertFalse(saved["zoomed"])


if __name__ == "__main__":
    unittest.main()
