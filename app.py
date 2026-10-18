"""Beginner-friendly capture workflow with offline review before live navigation."""
from __future__ import annotations

import json
import os
import queue
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from archiver import WebEvidenceArchiver
from gui_capture_plan import approved_revision, prepare_advanced_plan, prepare_manual_plan


class WebEvidenceArchiverApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Web Evidence Archiver — Webページ記録")
        self.geometry("970x760")
        self.minsize(800, 610)

        self.output_var = tk.StringVar()
        self.config_var = tk.StringVar()
        self.advanced_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(
            value="URLを入力し、保存先を選んで「記録前の確認」を押してください。"
        )
        self.overview_var = tk.StringVar(value="まだ試運転していません。")
        self._events = queue.Queue()
        self._running = False
        self._approval: str | None = None
        self._last_output: Path | None = None
        self._build()
        self.after(150, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)
        for var in (self.output_var, self.config_var, self.advanced_var):
            var.trace_add("write", self._invalidate_approval)

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(4, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(header, text="Web Evidence Archiver",
                  font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(header, text="許可されたHTTPSページをHTML・画像・PDFで記録します。"
                  "法的な証拠能力やページの完全再現を保証するものではありません。",
                  wraplength=880).pack(anchor="w")

        setup = ttk.LabelFrame(outer, text="① URLと保存先を設定", padding=10)
        setup.grid(row=1, column=0, sticky="ew", pady=(0, 9))
        setup.columnconfigure(0, weight=1)

        ttk.Label(setup, text="記録するHTTPS URL（1行に1件・最大20件）").grid(
            row=0, column=0, sticky="w")
        urlbox = ttk.Frame(setup)
        urlbox.grid(row=1, column=0, sticky="ew", pady=(3, 5))
        urlbox.columnconfigure(0, weight=1)
        self.url_text = tk.Text(urlbox, height=4, wrap="none", undo=True)
        self.url_text.grid(row=0, column=0, sticky="ew")
        scrollbar = ttk.Scrollbar(urlbox, command=self.url_text.yview, orient="vertical")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.url_text.configure(yscrollcommand=scrollbar.set)
        self.url_text.bind("<KeyRelease>", self._invalidate_approval)
        ttk.Button(setup, text="+ URLを追加", command=self._add_url_line).grid(
            row=2, column=0, sticky="w", pady=(0, 6))

        dest = ttk.Frame(setup)
        dest.grid(row=3, column=0, sticky="ew")
        dest.columnconfigure(1, weight=1)
        ttk.Label(dest, text="保存フォルダー").grid(row=0, column=0, padx=(0, 8))
        ttk.Entry(dest, textvariable=self.output_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(dest, text="参照", command=self._pick_output).grid(row=0, column=2, padx=(8, 0))

        ttk.Checkbutton(setup, text="詳細設定JSONを使用する（上級者向け）",
                        variable=self.advanced_var, command=self._toggle_advanced).grid(
                            row=4, column=0, sticky="w", pady=(10, 3))
        self.advanced_row = ttk.Frame(setup)
        self.advanced_row.columnconfigure(0, weight=1)
        ttk.Entry(self.advanced_row, textvariable=self.config_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(self.advanced_row, text="JSONを選択", command=self._pick_config).grid(
            row=0, column=1, padx=(8, 0))
        ttk.Label(self.advanced_row, text="チェックした場合のみJSONのURL・保存先・許可ホストを使います。"
                  "この設定は外部通信前に検証されます。").grid(row=1, column=0, columnspan=2, sticky="w")

        check = ttk.LabelFrame(outer, text="② 記録前に確認", padding=10)
        check.grid(row=2, column=0, sticky="ew", pady=(0, 9))
        ttk.Button(check, text="記録前の確認（通信なし）", command=self._preview).pack(
            side="left", padx=(0, 12))
        ttk.Label(check, textvariable=self.overview_var, wraplength=700,
                  justify="left").pack(side="left", fill="x", expand=True)

        run = ttk.LabelFrame(outer, text="③ 確認して記録", padding=10)
        run.grid(row=3, column=0, sticky="ew", pady=(0, 9))
        self.run_button = ttk.Button(run, text="Webページを記録（実通信）",
                                     command=self._run, state="disabled")
        self.run_button.pack(side="left", padx=(0, 10))
        self.open_button = ttk.Button(run, text="保存先を開く", command=self._open_output,
                                      state="disabled")
        self.open_button.pack(side="left")
        self.progress = ttk.Progressbar(run, mode="indeterminate")
        self.progress.pack(fill="x", expand=True, side="left", padx=(16, 0))

        results = ttk.LabelFrame(outer, text="記録結果（成功・失敗をURLごとに表示）", padding=10)
        results.grid(row=4, column=0, sticky="nsew")
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(results, columns=("status", "url", "http", "folder"),
                                 show="headings", height=6)
        for name, title, width in [
            ("status", "結果", 115), ("url", "対象URL", 430),
            ("http", "HTTP", 90), ("folder", "記録フォルダー", 210)
        ]:
            self.tree.heading(name, text=title)
            self.tree.column(name, width=width, anchor="w", stretch=name in {"url", "folder"})
        self.tree.grid(row=0, column=0, sticky="nsew")
        ttk.Scrollbar(results, command=self.tree.yview).grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=lambda *args: None)  # Tree handles result rows independently
        ttk.Label(outer, textvariable=self.status_var, wraplength=900,
                  justify="left").grid(row=5, column=0, sticky="ew", pady=(8, 0))

    def _invalidate_approval(self, *_args) -> None:
        self._approval = None
        if hasattr(self, "run_button"):
            self.run_button.state(["disabled"])

    def _add_url_line(self) -> None:
        if self._running:
            return
        text = self.url_text.get("1.0", "end-1c")
        self.url_text.insert("end", "\n" if text and not text.endswith("\n") else "")
        self.url_text.focus_set()
        self._invalidate_approval()

    def _toggle_advanced(self) -> None:
        if self._running:
            return
        if self.advanced_var.get():
            self.advanced_row.grid(row=5, column=0, sticky="ew", pady=(3, 0))
        else:
            self.advanced_row.grid_remove()
        self._invalidate_approval()

    def _pick_output(self) -> None:
        if self._running:
            return
        folder = filedialog.askdirectory(title="記録の保存先")
        if folder:
            self.output_var.set(folder)

    def _pick_config(self) -> None:
        if self._running:
            return
        file = filedialog.askopenfilename(title="詳細設定JSON", filetypes=[("JSON", "*.json")])
        if file:
            self.config_var.set(file)

    def _prepared(self) -> tuple[dict, str]:
        if self.advanced_var.get():
            plan, fingerprint = prepare_advanced_plan(self.config_var.get())
            return plan, approved_revision(plan, fingerprint)
        plan = prepare_manual_plan(self.url_text.get("1.0", "end-1c"),
                                   self.output_var.get())
        return plan, approved_revision(plan)

    def _preview(self) -> None:
        if self._running:
            return
        try:
            plan, revision = self._prepared()
        except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError) as exc:
            self._invalidate_approval()
            messagebox.showwarning("入力の確認", str(exc))
            self.overview_var.set("確認できませんでした。URL・JSON・保存先を確認してください。")
            return
        self._approval = revision
        self.run_button.state(["!disabled"])
        self.overview_var.set(
            f"URL: {len(plan['urls'])}件 / 許可ホスト: {len(plan['allow_hosts'])}件 / "
            f"保存先: {plan.get('output_dir', 'web_evidence')}。"
            "ここではWebに接続しません。外部素材の読み込みは許可ホストに限定されます。"
        )
        self.status_var.set("記録前の確認が終わりました。通信先と件数を確認して実行してください。")

    def _run(self) -> None:
        if self._running or not self._approval:
            return
        try:
            plan, revision = self._prepared()
        except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError):
            self._invalidate_approval()
            messagebox.showwarning("再確認してください", "設定に問題があります。もう一度確認してください。")
            return
        if revision != self._approval:
            self._invalidate_approval()
            messagebox.showwarning("再確認してください",
                                   "URL・保存先・JSONの内容が変わりました。記録前の確認をやり直してください。")
            return
        host_list = ", ".join(plan["allow_hosts"])
        if not messagebox.askyesno("実際のWebアクセスを確認",
                                   f"{len(plan['urls'])}件のWebページへアクセスします。\n"
                                   f"許可するホスト: {host_list}\n"
                                   "HTML・PNG・PDFを新しい記録フォルダーへ保存します。続行しますか？"):
            return
        self._invalidate_approval()  # Authorization is one-use, even when capture partially fails.
        self._running = True
        self.run_button.state(["disabled"])
        self.open_button.state(["disabled"])
        self.progress.start(15)
        self.status_var.set("Webページ記録中。ネットワーク接続しています。")
        self._last_output = None
        for child in self.tree.get_children():
            self.tree.delete(child)

        def worker() -> None:
            try:
                with tempfile.TemporaryDirectory() as temp:
                    path = Path(temp) / "approved_capture.json"
                    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
                    folder = WebEvidenceArchiver(path).capture_all()
                manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
                self._events.put((True, str(folder), manifest))
            except Exception as exc:
                # External errors can contain untrusted URLs / secrets; show just type.
                self._events.put((False, type(exc).__name__, {}))
        threading.Thread(target=worker, daemon=True).start()

    def _poll(self) -> None:
        try:
            while True:
                success, value, manifest = self._events.get_nowait()
                self._running = False
                self.progress.stop()
                if not success:
                    self.status_var.set(
                        f"取得に失敗しました（{value}）。HTTPS URL・通信状況・Chromium同梱状態と"
                        "保存先の空き容量/権限を確認して再試運転してください。")
                    messagebox.showerror("取得エラー", self.status_var.get())
                    continue
                self._last_output = Path(value)
                self.open_button.state(["!disabled"])
                for item in manifest.get("captures", [])[:200]:
                    self.tree.insert("", "end", values=(
                        item.get("capture_status", "unknown"),
                        item.get("original_url", ""), item.get("http_status", ""),
                        item.get("folder", "-")))
                summary = manifest.get("summary", {})
                self.status_var.set(
                    f"記録結果: 成功 {summary.get('captured', 0)}件 / 失敗 "
                    f"{summary.get('failed', 0)}件 / 未試行 "
                    f"{summary.get('not_attempted', 0)}件。"
                    f"保存先: {value}。失敗分はmanifest.jsonで確認してください。"
                )
                if summary.get("failed") or summary.get("not_attempted"):
                    messagebox.showwarning("一部失敗", self.status_var.get())
        except queue.Empty:
            pass
        self.after(150, self._poll)

    def _open_output(self) -> None:
        if not self._last_output or not self._last_output.is_dir():
            messagebox.showwarning("保存先", "記録完了後に保存先を開けます。")
            return
        try:
            if os.name == "nt":
                os.startfile(str(self._last_output))
            else:
                import webbrowser
                webbrowser.open(self._last_output.as_uri())
        except (OSError, ValueError):
            messagebox.showerror("保存先", "保存先を開けません。エクスプローラーから開いてください。")

    def _close(self) -> None:
        if self._running:
            messagebox.showwarning("処理中", "記録処理が完了するまでは閉じられません。")
            return
        self.destroy()


if __name__ == "__main__":
    WebEvidenceArchiverApp().mainloop()
