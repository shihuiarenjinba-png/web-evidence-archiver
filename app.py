from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from archiver import WebEvidenceArchiver


class WebEvidenceArchiverApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Web Evidence Archiver")
        self.geometry("760x360")
        self.minsize(680, 330)
        self.config_var = tk.StringVar()
        self.status_var = tk.StringVar(value="設定JSONを選択してください。")
        self._build()

    def _build(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)

        ttk.Label(root, text="設定JSON").grid(row=0, column=0, sticky="w", pady=8)
        ttk.Entry(root, textvariable=self.config_var).grid(row=0, column=1, sticky="ew", pady=8)
        ttk.Button(root, text="選択", command=self._pick).grid(row=0, column=2, padx=(8, 0), pady=8)

        ttk.Label(
            root,
            text="許可ホストのHTTPSページのみを保存します。HTML・PNG・PDFとSHA256を記録します。",
            wraplength=700,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))

        ttk.Label(root, textvariable=self.status_var, wraplength=700).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(16, 0)
        )
        ttk.Button(root, text="記録を作成", command=self._run).grid(
            row=3, column=0, columnspan=3, pady=20
        )

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
    WebEvidenceArchiverApp().mainloop()
