"""Local web evidence GUI with direct URL and failure-aware reporting."""
from __future__ import annotations

import json
import queue
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse

from archiver import WebEvidenceArchiver, validate_url
from ui_desktop import bind_shortcuts, restore_window_state, save_window_state


class WebEvidenceArchiverApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Web Evidence Archiver")
        self.geometry("810x500")
        self.minsize(710, 440)
        restore_window_state(self, "WebEvidenceArchiver", min_width=710, min_height=440)
        self.config_var = tk.StringVar()
        self.url_var = tk.StringVar(value="https://example.com/")
        self.output_var = tk.StringVar()
        self.status_var = tk.StringVar(value="保存したいHTTPS URLと保存先を指定してください。")
        self._events = queue.Queue()
        self._running = False
        self._build()
        self.after(150, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.config_var.trace_add("write", lambda *_: self._refresh_actions())
        self.url_var.trace_add("write", lambda *_: self._refresh_actions())
        self.output_var.trace_add("write", lambda *_: self._refresh_actions())
        bind_shortcuts(self, {
            "<Control-Return>": self._run,
            "<F5>": self._run,
            "<Control-O>": self._pick_config,
            "<Control-Shift-S>": self._pick_output,
        })
        self._refresh_actions()

    def _build(self) -> None:
        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        ttk.Label(body, text="Web Evidence Archiver", font=("Segoe UI", 17, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 3)
        )
        ttk.Label(
            body,
            text="① URLまたは設定JSONを選択  →  ② 保存先を確認  →  ③ HTML・PNG・PDF・SHA256を保存",
            wraplength=760,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 4))
        ttk.Label(
            body,
            text="入力したHTTPSホストだけを取得対象にし、外部ホストの素材は取得しません。",
            wraplength=760,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 6))
        self.mode_tabs = ttk.Notebook(body)
        self.mode_tabs.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(8, 6))
        self.mode_tabs.bind("<<NotebookTabChanged>>", lambda _event: self._refresh_actions())

        direct_tab = ttk.Frame(self.mode_tabs, padding=12)
        batch_tab = ttk.Frame(self.mode_tabs, padding=12)
        direct_tab.columnconfigure(1, weight=1)
        batch_tab.columnconfigure(1, weight=1)
        self.mode_tabs.add(direct_tab, text="1件を保存")
        self.mode_tabs.add(batch_tab, text="複数URL設定")

        ttk.Label(direct_tab, text="HTTPS URL").grid(row=0, column=0, sticky="w", pady=7)
        ttk.Entry(direct_tab, textvariable=self.url_var).grid(row=0, column=1, sticky="ew")
        ttk.Label(direct_tab, text="保存フォルダ").grid(row=1, column=0, sticky="w", pady=7)
        ttk.Entry(direct_tab, textvariable=self.output_var).grid(row=1, column=1, sticky="ew")
        ttk.Button(direct_tab, text="参照", command=self._pick_output).grid(row=1, column=2, padx=8)
        ttk.Label(
            direct_tab,
            text="このタブでは1ページだけ保存します。URLと保存先を選ぶと下の保存ボタンが使えるようになります。",
            wraplength=700, justify="left",
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

        ttk.Label(batch_tab, text="設定JSON").grid(row=0, column=0, sticky="w", pady=7)
        ttk.Entry(batch_tab, textvariable=self.config_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(batch_tab, text="選択", command=self._pick_config).grid(row=0, column=2, padx=8)
        ttk.Label(
            batch_tab,
            text="このタブでは設定JSONに書かれた複数URLを順番に保存します。設定ファイルを選ぶと保存できます。",
            wraplength=700, justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))

        self.run_button = ttk.Button(body, text="証拠セットを保存", command=self._run)
        self.run_button.grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 2))
        ttk.Label(body, text="押すと対象ページを取得し、HTML・PNG・PDF・SHA-256を1つの保存先にまとめます。", wraplength=760, justify="left").grid(row=5, column=0, columnspan=3, sticky="w", pady=(0, 6))
        self.progress = ttk.Progressbar(body, mode="indeterminate")
        self.progress.grid(row=6, column=0, columnspan=3, sticky="ew")
        ttk.Label(body, textvariable=self.status_var, wraplength=760, justify="left").grid(
            row=7, column=0, columnspan=3, sticky="w", pady=12
        )

    def _refresh_actions(self) -> None:
        selected = self.mode_tabs.index(self.mode_tabs.select()) if hasattr(self, "mode_tabs") else 0
        if selected == 0:
            ready = bool(self.url_var.get().strip() and self.output_var.get().strip())
        else:
            ready = bool(self.config_var.get().strip())
        ready = ready and not self._running
        self.run_button.state(["!disabled"] if ready else ["disabled"])

    def _pick_output(self) -> None:
        folder = filedialog.askdirectory(title="保存先フォルダ")
        if folder:
            self.output_var.set(folder)

    def _pick_config(self) -> None:
        value = filedialog.askopenfilename(filetypes=[("設定JSON", "*.json")])
        if value:
            self.config_var.set(value)
            self.status_var.set("設定JSONを選択しました。選択URL欄よりこちらを優先します。")

    def _run(self) -> None:
        if self._running:
            return
        selected = self.mode_tabs.index(self.mode_tabs.select())
        config = self.config_var.get().strip() if selected == 1 else ""
        url = self.url_var.get().strip()
        destination = self.output_var.get().strip()
        if selected == 0:
            if not destination:
                messagebox.showerror("入力不足", "保存フォルダを選択してください。")
                return
            try:
                host = urlparse(url).hostname
                validate_url(url, [host] if host else [])
            except ValueError as exc:
                messagebox.showerror("URLエラー", str(exc))
                return
        elif not config:
            messagebox.showerror("入力不足", "設定JSONを選択してください。")
            return
        self._running = True
        self._refresh_actions()
        self.progress.start(15)
        self.status_var.set("Webページの保存中です。処理完了まで閉じないでください。")

        def worker() -> None:
            try:
                if config:
                    folder = WebEvidenceArchiver(config).capture_all()
                else:
                    with tempfile.TemporaryDirectory() as temp:
                        config_path = Path(temp) / "config.json"
                        config_path.write_text(json.dumps({
                            "urls": [url], "allow_hosts": [host],
                            "output_dir": destination,
                            "timeout_seconds": 30,
                        }), encoding="utf-8")
                        folder = WebEvidenceArchiver(config_path).capture_all()
                manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
                self._events.put((True, str(folder), manifest["summary"]))
            except Exception as exc:
                self._events.put((False, str(exc), None))
        threading.Thread(target=worker, daemon=True).start()

    def _poll(self) -> None:
        try:
            while True:
                success, value, summary = self._events.get_nowait()
                self._running = False
                self.progress.stop()
                self._refresh_actions()
                if success:
                    message = (f"記録フォルダ: {Path(value).name} / 成功: {summary['captured']} / "
                               f"失敗: {summary['failed']} / 未試行: {summary['not_attempted']}。"
                               "詳細はmanifest.jsonで確認してください。")
                    self.status_var.set(message)
                    if summary["failed"] or summary["not_attempted"]:
                        messagebox.showwarning("一部の記録に失敗しました", message)
                    else:
                        messagebox.showinfo("記録完了", message)
                else:
                    self.status_var.set("取得失敗: " + value)
                    messagebox.showerror("取得エラー", value)
        except queue.Empty:
            pass
        self.after(150, self._poll)

    def _close(self) -> None:
        if self._running:
            messagebox.showwarning("処理中", "保存処理が完了するまで画面を閉じないでください。")
            return
        save_window_state(self, "WebEvidenceArchiver")
        self.destroy()


if __name__ == "__main__":
    from i18n import install_bilingual_ui

    app = WebEvidenceArchiverApp()
    install_bilingual_ui(app)
    app.mainloop()
