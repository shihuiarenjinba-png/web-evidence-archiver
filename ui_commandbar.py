from __future__ import annotations

import tkinter as tk
from typing import Callable


class CommandBar(tk.Frame):
    """Independent desktop command bar for the Group C tools."""

    def __init__(self, master, *, bg="#ffffff"):
        super().__init__(master, bg=bg, bd=0, highlightthickness=0)
        self._buttons: dict[str, tk.Button] = {}
        self._bg = bg

    def add_command(
        self,
        key: str,
        symbol: str,
        label: str,
        command: Callable[[], object],
        *,
        primary: bool = False,
        enabled: bool = True,
    ) -> tk.Button:
        fg = "#ffffff" if primary else "#20252b"
        bg = "#2f64a3" if primary else self._bg
        active_bg = "#28568d" if primary else "#edf3fa"
        button = tk.Button(
            self,
            text=f"{symbol}\n{label}",
            command=command,
            width=11,
            height=3,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            fg=fg,
            bg=bg,
            activeforeground=fg if primary else "#20252b",
            activebackground=active_bg,
            disabledforeground="#9aa1aa",
            cursor="hand2",
            padx=4,
            pady=3,
        )
        button.pack(side="left", padx=(0, 2), pady=4)
        button.configure(state="normal" if enabled else "disabled")
        self._buttons[key] = button
        return button

    def add_separator(self) -> None:
        tk.Frame(self, width=1, bg="#d9dee5").pack(side="left", fill="y", padx=7, pady=9)

    def add_spacer(self) -> None:
        tk.Frame(self, bg=self._bg).pack(side="left", fill="x", expand=True)

    def set_enabled(self, key: str, enabled: bool) -> None:
        button = self._buttons.get(key)
        if button is not None:
            button.configure(state="normal" if enabled else "disabled")

    def button(self, key: str) -> tk.Button | None:
        return self._buttons.get(key)


class StatusBar(tk.Frame):
    def __init__(self, master, *, initial="Ready"):
        super().__init__(master, bg="#f5f7fa", bd=0, highlightthickness=1, highlightbackground="#d9dee5")
        self.text = tk.StringVar(value=initial)
        tk.Label(
            self,
            textvariable=self.text,
            anchor="w",
            bg="#f5f7fa",
            fg="#4e5968",
            font=("Segoe UI", 9),
            padx=10,
            pady=5,
        ).pack(fill="x")

    def set(self, value: str) -> None:
        self.text.set(value)
