from __future__ import annotations

import json
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from archiver import WebEvidenceArchiver, browser_runtime_self_test, validate_url


DEFAULT_OUTPUT = Path.home() / "Documents" / "Web Evidence Archiver" / "Output"


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
        self.geometry("860x650")
        self.minsize(780, 590)
        self.hosts_var = tk.StringVar()
        self.output_var = tk.StringVar(value=str(DEFAULT_OUTPUT))
        self.config_var = tk.StringVar()
        self.status_var = tk.StringVar(value="URL・許可ホスト・出力先を入力してください。")
        self._build()

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

        ttk.Label(root, text="保存URL").grid(row=2, column=0, sticky="nw", pady=6)
        self.urls_text = tk.Text(root, height=4, wrap="none")
        self.urls_text.grid(row=2, column=1, columnspan=2, sticky="ew", pady=6)
        ttk.Label(root, text="1行に1 URL。HTTPSのみ。").grid(row=3, column=1, columnspan=2, sticky="w")
        self._entry_row(root, 4, "許可ホスト", self.hosts_var)
        ttk.Label(root, text="カンマ区切り。ページが使うCDN等も必要に応じて追加します。").grid(
            row=5, column=1, columnspan=2, sticky="w"
        )
        self._entry_row(root, 6, "出力先", self.output_var, self._pick_output)

        actions = ttk.Frame(root)
        actions.grid(row=7, column=0, columnspan=3, sticky="w", pady=(12, 8))
        ttk.Button(actions, text="設定JSONを保存", command=self._save_form).pack(side="left")
        ttk.Button(actions, text="フォーム設定で記録を作成", command=self._run_form).pack(side="left", padx=8)

        ttk.Separator(root).grid(row=8, column=0, columnspan=3, sticky="ew", pady=10)
        ttk.Label(root, text="既存の設定JSON（上級者向け）").grid(row=9, column=0, sticky="w", pady=8)
        ttk.Entry(root, textvariable=self.config_var).grid(row=9, column=1, sticky="ew", pady=8)
        ttk.Button(root, text="選択", command=self._pick).grid(row=9, column=2, padx=(8, 0), pady=8)

        ttk.Label(
            root,
            text="許可ホストのHTTPSページのみを保存します。Windows標準のMicrosoft Edgeを使用し、HTML・PNG・PDFとSHA256を記録します。",
            wraplength=700,
        ).grid(row=10, column=0, columnspan=3, sticky="w", pady=(10, 0))

        ttk.Label(root, textvariable=self.status_var, wraplength=700).grid(
            row=11, column=0, columnspan=3, sticky="w", pady=(16, 0)
        )
        ttk.Button(root, text="記録を作成", command=self._run).grid(
            row=12, column=0, columnspan=3, pady=20
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
            self.status_var.set("取得に失敗しました。入力、許可ホスト、Edge、ネットワークを確認してください。")
            messagebox.showerror("取得エラー", str(exc))
            return
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
        self.status_var.set(f"完了: {output}")
        messagebox.showinfo("完了", f"Web記録を保存しました。\n\n{output}")

    def _pick(self) -> None:
        value = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if value:
            self.config_var.set(value)

    def _run(self) -> None:
        try:
            output = WebEvidenceArchiver(self.config_var.get()).capture_all()
        except Exception as exc:
            self.status_var.set(f"エラー: {exc}")
            messagebox.showerror("取得エラー", str(exc))
            return
        self.status_var.set(f"完了: {output}")
        messagebox.showinfo("完了", f"Web記録を保存しました。\n\n{output}")


if __name__ == "__main__":
    if "--self-test-browser" in sys.argv:
        browser_runtime_self_test()
        raise SystemExit(0)
    if len(sys.argv) == 3 and sys.argv[1] == "--acceptance-capture":
        WebEvidenceArchiver(sys.argv[2]).capture_all()
    else:
        WebEvidenceArchiverApp().mainloop()
