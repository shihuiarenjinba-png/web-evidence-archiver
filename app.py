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


class WebEvidenceArchiverApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Web Evidence Archiver")
        self.geometry("810x455")
        self.minsize(710, 400)
        self.config_var = tk.StringVar()
        self.url_var = tk.StringVar(value="https://example.com/")
        self.output_var = tk.StringVar()
        self.status_var = tk.StringVar(value="保存したいHTTPS URLと保存先を指定してください。")
        self._events = queue.Queue()
        self._running = False
        self._build()
        self.after(150, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self) -> None:
        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        ttk.Label(body, text="1. URLから記録（1サイト）",
                  font=("Segoe UI", 13, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=10)
        ttk.Label(body, text="HTTPS URL").grid(row=1, column=0, sticky="w", pady=7)
        ttk.Entry(body, textvariable=self.url_var).grid(row=1, column=1, sticky="ew")
        ttk.Label(body, text="出力フォルダ").grid(row=2, column=0, sticky="w", pady=7)
        ttk.Entry(body, textvariable=self.output_var).grid(row=2, column=1, sticky="ew")
        ttk.Button(body, text="参照", command=self._pick_output).grid(row=2, column=2, padx=8)

        ttk.Label(body, text="2. または既存の複数URL設定を使う",
                  font=("Segoe UI", 13, "bold")).grid(row=3, column=0, columnspan=3, sticky="w", pady=(18, 7))
        ttk.Label(body, text="設定JSON").grid(row=4, column=0, sticky="w", pady=7)
        ttk.Entry(body, textvariable=self.config_var).grid(row=4, column=1, sticky="ew")
        ttk.Button(body, text="選択", command=self._pick_config).grid(row=4, column=2, padx=8)

        ttk.Label(body, text=(
            "設定JSONが選択されていればJSONの設定を優先します。URLから取得する場合は入力URLの"
            "ホストだけを許可し、外部ホストの素材は取得しません。HTML・PNG・PDFとSHA256を保存します。"
        ), wraplength=760, justify="left").grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 6))
        self.run_button = ttk.Button(body, text="保存を開始", command=self._run)
        self.run_button.grid(row=6, column=0, columnspan=3, sticky="w", pady=(6, 6))
        self.progress = ttk.Progressbar(body, mode="indeterminate")
        self.progress.grid(row=7, column=0, columnspan=3, sticky="ew")
        ttk.Label(body, textvariable=self.status_var, wraplength=760, justify="left").grid(
            row=8, column=0, columnspan=3, sticky="w", pady=12
        )

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
        config = self.config_var.get().strip()
        url = self.url_var.get().strip()
        destination = self.output_var.get().strip()
        if not config:
            if not destination:
                messagebox.showerror("入力不足", "保存フォルダを選択してください。")
                return
            try:
                host = urlparse(url).hostname
                validate_url(url, [host] if host else [])
            except ValueError as exc:
                messagebox.showerror("URLエラー", str(exc))
                return
        self._running = True
        self.run_button.state(["disabled"])
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
                self.run_button.state(["!disabled"])
                if success:
                    message = (f"記録フォルダ: {value} / 成功: {summary['captured']} / "
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
        self.destroy()


if __name__ == "__main__":
    WebEvidenceArchiverApp().mainloop()
