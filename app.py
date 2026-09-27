from __future__ import annotations

import json
import os
import sys
import tempfile
import tkinter as tk
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from archiver import WebEvidenceArchiver, browser_runtime_self_test, validate_url


DEFAULT_OUTPUT = Path.home() / "Documents" / "Web Evidence Archiver" / "Output"
DIAGNOSTIC_DIR = Path(os.getenv("LOCALAPPDATA", Path.home())) / "Web Evidence Archiver" / "Logs"


def record_failure(operation: str, exc: Exception) -> str:
    diagnostic_id = uuid.uuid4().hex[:12].upper()
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    with (DIAGNOSTIC_DIR / "diagnostics.log").open("a", encoding="utf-8") as handle:
        handle.write(
            f"\n[{datetime.now(timezone.utc).isoformat()}] "
            f"Diagnostic ID={diagnostic_id} operation={operation}\n"
        )
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=handle)
    return diagnostic_id


def build_gui_config(urls_text: str, allow_hosts_text: str, output_dir: str) -> dict:
    urls = [value.strip() for value in urls_text.splitlines() if value.strip()]
    hosts = [value.strip() for value in allow_hosts_text.split(",") if value.strip()]
    if not urls:
        raise ValueError("保存するHTTPS URLを1件以上入力してください。")
    if not hosts:
        raise ValueError("許可ホストを1件以上入力してください。")
    if not output_dir.strip():
        raise ValueError("出力先を指定してください。")
    for url in urls:
        validate_url(url, hosts)
    return {
        "allow_hosts": hosts,
        "urls": urls,
        "output_dir": output_dir.strip(),
        "timeout_seconds": 30,
        "browser_channel": "msedge",
        "viewport": {"width": 1440, "height": 1000},
    }


class WebEvidenceArchiverApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Web Evidence Archiver")
        self.geometry("920x760")
        self.minsize(820, 650)
        self.hosts_var = tk.StringVar()
        self.output_var = tk.StringVar(value=str(DEFAULT_OUTPUT))
        self.config_var = tk.StringVar()
        self.status_var = tk.StringVar(value="URL・許可ホスト・出力先を入力してください。")
        self.summary_var = tk.StringVar()
        self.last_output: Path | None = None
        self._build()
        for variable in (self.hosts_var, self.output_var, self.config_var):
            variable.trace_add("write", self._update_summary)
        self.urls_text.bind("<KeyRelease>", self._update_summary)
        self._update_summary()

    def _build(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)

        ttk.Label(root, text="Web Evidence Archiver", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(
            root,
            text="許可したHTTPSページをMicrosoft Edgeで開き、HTML・PNG・PDF・取得時刻・SHA256を1セットで保存します。",
            wraplength=800,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 12))

        ttk.Label(root, text="Step 1 — 保存するページと出力先を入力", font=("Segoe UI", 11, "bold")).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(2, 4)
        )
        ttk.Label(root, text="保存URL").grid(row=3, column=0, sticky="nw", pady=6)
        self.urls_text = tk.Text(root, height=4, wrap="none")
        self.urls_text.grid(row=3, column=1, columnspan=2, sticky="ew", pady=6)
        ttk.Label(root, text="1行に1 URL。HTTPSのみ。").grid(row=4, column=1, columnspan=2, sticky="w")
        self._entry_row(root, 5, "許可ホスト", self.hosts_var)
        ttk.Label(root, text="カンマ区切り。ページが使うCDN等も必要に応じて追加します。").grid(
            row=6, column=1, columnspan=2, sticky="w"
        )
        self._entry_row(root, 7, "出力先", self.output_var, self._pick_output)

        actions = ttk.Frame(root)
        ttk.Label(root, text="Step 2 — 設定を確認・保存", font=("Segoe UI", 11, "bold")).grid(
            row=8, column=0, columnspan=3, sticky="w", pady=(10, 0)
        )
        actions.grid(row=9, column=0, columnspan=3, sticky="w", pady=(4, 8))
        ttk.Button(actions, text="設定JSONを保存", command=self._save_form).pack(side="left")
        ttk.Button(actions, text="フォーム設定で記録を作成", command=self._run_form).pack(side="left", padx=8)

        ttk.Separator(root).grid(row=10, column=0, columnspan=3, sticky="ew", pady=8)
        ttk.Label(root, text="既存の設定JSON（上級者向け）").grid(row=11, column=0, sticky="w", pady=6)
        ttk.Entry(root, textvariable=self.config_var).grid(row=11, column=1, sticky="ew", pady=6)
        ttk.Button(root, text="設定JSONを選択", command=self._pick).grid(row=11, column=2, padx=(8, 0), pady=6)

        ttk.Label(
            root,
            text="Step 3 — 実行前確認（この処理はインターネットへ接続します）",
            font=("Segoe UI", 11, "bold"),
        ).grid(row=12, column=0, columnspan=3, sticky="w", pady=(10, 2))
        ttk.Label(
            root,
            textvariable=self.summary_var,
            wraplength=700,
        ).grid(row=13, column=0, columnspan=3, sticky="w")

        ttk.Button(root, text="設定JSONからWeb記録を作成", command=self._run).grid(
            row=14, column=0, columnspan=3, pady=(8, 10)
        )
        ttk.Label(root, text="Step 4 — 結果を確認", font=("Segoe UI", 11, "bold")).grid(
            row=15, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(root, textvariable=self.status_var, wraplength=700).grid(
            row=16, column=0, columnspan=3, sticky="w", pady=(4, 6)
        )
        self.open_output_button = ttk.Button(
            root, text="出力フォルダを開く", command=self._open_last_output, state="disabled"
        )
        self.open_output_button.grid(row=17, column=0, columnspan=3, sticky="w")

    def _update_summary(self, *_args) -> None:
        urls = [value.strip() for value in self.urls_text.get("1.0", "end").splitlines() if value.strip()]
        source = f"{len(urls)}件のURL" if urls else self.config_var.get().strip() or "未指定"
        output = self.output_var.get().strip() or "設定JSON内の出力先"
        self.summary_var.set(
            f"入力: {source}\n出力先: {output}\n処理: HTML・PNG・PDF・SHA256を新規保存 / 上書き: なし / ネットワーク: あり"
        )

    def _entry_row(self, parent, row, label, variable, command=None) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=6)
        if command:
            ttk.Button(parent, text="選択", command=command).grid(row=row, column=2, padx=(8, 0), pady=6)

    def _pick_output(self) -> None:
        value = filedialog.askdirectory()
        if value:
            self.output_var.set(value)

    def _form_config(self) -> dict:
        return build_gui_config(
            self.urls_text.get("1.0", "end"), self.hosts_var.get(), self.output_var.get()
        )

    def _save_form(self) -> None:
        try:
            config = self._form_config()
            destination = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON", "*.json")],
                initialfile="web-evidence-archiver.json",
            )
            if not destination:
                return
            Path(destination).write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
            self.status_var.set(f"設定を保存しました: {destination}")
        except Exception as exc:
            messagebox.showerror("設定エラー", str(exc))

    def _run_form(self) -> None:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
                json.dump(self._form_config(), handle, ensure_ascii=False, indent=2)
                temporary = Path(handle.name)
            output = WebEvidenceArchiver(temporary).capture_all()
        except Exception as exc:
            diagnostic_id = record_failure("capture-form", exc)
            self.status_var.set("取得に失敗しました。入力、許可ホスト、Edge、ネットワークを確認してください。")
            messagebox.showerror(
                "取得エラー",
                f"Web記録の作成に失敗しました。入力、許可ホスト、Edge、ネットワークを確認してください。\nDiagnostic ID: {diagnostic_id}",
            )
            return
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
        self._show_success(output)

    def _pick(self) -> None:
        value = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if value:
            self.config_var.set(value)

    def _run(self) -> None:
        try:
            output = WebEvidenceArchiver(self.config_var.get()).capture_all()
        except Exception as exc:
            diagnostic_id = record_failure("capture-config", exc)
            self.status_var.set("取得に失敗しました。設定JSON、Edge、ネットワークを確認してください。")
            messagebox.showerror(
                "取得エラー",
                f"Web記録の作成に失敗しました。設定JSON、Edge、ネットワークを確認してください。\nDiagnostic ID: {diagnostic_id}",
            )
            return
        self._show_success(output)

    def _show_success(self, output) -> None:
        self.last_output = Path(output)
        self.open_output_button.configure(state="normal")
        self.status_var.set(f"処理が完了しました。Web記録フォルダ: {output}")
        messagebox.showinfo("完了", f"Web記録を保存しました。\n\n出力フォルダ: {output}")

    def _open_last_output(self) -> None:
        if self.last_output is None:
            return
        target = self.last_output if self.last_output.is_dir() else self.last_output.parent
        target.mkdir(parents=True, exist_ok=True)
        os.startfile(target)


if __name__ == "__main__":
    if "--self-test-browser" in sys.argv:
        browser_runtime_self_test()
        raise SystemExit(0)
    if len(sys.argv) == 3 and sys.argv[1] == "--acceptance-capture":
        WebEvidenceArchiver(sys.argv[2]).capture_all()
    else:
        WebEvidenceArchiverApp().mainloop()
