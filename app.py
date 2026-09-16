from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from archiver import WebEvidenceArchiver


class WebChangeEvidenceApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Web Change Evidence Monitor")
        self.geometry("820x420")
        self.minsize(720, 380)
        self.config_var = tk.StringVar()
        self.status_var = tk.StringVar(value="設定JSONを選択してください。")
        self._build()

    def _build(self) -> None:
        root = ttk.Frame(self, padding=18)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)

        ttk.Label(root, text="監視設定JSON").grid(row=0, column=0, sticky="w", pady=8)
        ttk.Entry(root, textvariable=self.config_var).grid(row=0, column=1, sticky="ew", pady=8)
        ttk.Button(root, text="選択", command=self._pick).grid(row=0, column=2, padx=(8, 0), pady=8)

        ttk.Label(
            root,
            text=(
                "許可ホストのHTTPSページをHTML・PNG・PDF・可視テキストとして保存し、"
                "前回記録がある場合はテキスト / HTML / スクリーンショットの変更を分離して比較します。"
            ),
            wraplength=760,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 4))

        ttk.Label(
            root,
            text="動的な日時やカウンタは ignore_text_regexes で比較対象から除外できます。元の可視テキスト自体は証跡として保存されます。",
            wraplength=760,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=4)

        ttk.Button(root, text="記録して前回と比較", command=self._run).grid(row=3, column=0, columnspan=3, pady=18)
        ttk.Separator(root).grid(row=4, column=0, columnspan=3, sticky="ew", pady=8)
        ttk.Label(root, textvariable=self.status_var, wraplength=760).grid(row=5, column=0, columnspan=3, sticky="w")

    def _pick(self) -> None:
        value = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if value:
            self.config_var.set(value)

    def _run(self) -> None:
        try:
            output = WebEvidenceArchiver(self.config_var.get()).capture_all(compare_previous=True)
            report_path = Path(output) / "change_report.json"
            if report_path.exists():
                report = json.loads(report_path.read_text(encoding="utf-8"))
                summary = f"変更あり: {report['changed_targets']} / {report['total_targets']} URL"
            else:
                summary = "初回記録のため比較対象はありません。"
        except Exception as exc:
            self.status_var.set(f"エラー: {exc}")
            messagebox.showerror("取得エラー", str(exc))
            return
        self.status_var.set(f"完了: {summary}\n保存先: {output}")
        messagebox.showinfo("完了", f"{summary}\n\n{output}")


if __name__ == "__main__":
    WebChangeEvidenceApp().mainloop()
