from __future__ import annotations

import json
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from archiver import WebEvidenceArchiver, browser_self_test, verify_run_integrity


class WebChangeEvidenceApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Web Change Evidence Monitor")
        self.geometry("900x500")
        self.minsize(780, 430)
        self.config_var = tk.StringVar()
        self.status_var = tk.StringVar(value="設定JSONを選択してください。")
        self.capture_button: ttk.Button | None = None
        self.self_test_button: ttk.Button | None = None
        self._build()

    def _build(self) -> None:
        root = ttk.Frame(self, padding=18)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)

        ttk.Label(root, text="Web Change Evidence Monitor", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(root, text="監視設定JSON").grid(row=1, column=0, sticky="w", pady=8)
        ttk.Entry(root, textvariable=self.config_var).grid(row=1, column=1, sticky="ew", pady=8)
        ttk.Button(root, text="選択", command=self._pick).grid(row=1, column=2, padx=(8, 0), pady=8)

        ttk.Label(
            root,
            text=(
                "HTTPSページをHTML・PNG・PDF・可視テキストとして保存し、前回記録との変更を"
                "content / render / HTML-onlyに分離します。保存後は全成果物SHA256を自己検証し、"
                "前回manifestにつながるEvidence Chainを記録します。"
            ),
            wraplength=850,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 4))

        ttk.Label(
            root,
            text="ignore_text_regexesは比較用正規化テキストだけに適用され、原HTML/PNG/PDF/可視テキストは変更しません。",
            wraplength=850,
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=4)

        buttons = ttk.Frame(root)
        buttons.grid(row=4, column=0, columnspan=3, sticky="w", pady=16)
        self.capture_button = ttk.Button(buttons, text="記録して前回と比較", command=self._run)
        self.capture_button.pack(side="left")
        self.self_test_button = ttk.Button(buttons, text="Chromiumセルフテスト", command=self._self_test)
        self.self_test_button.pack(side="left", padx=8)
        ttk.Button(buttons, text="保存済みRunを検証", command=self._verify_run).pack(side="left")

        ttk.Separator(root).grid(row=5, column=0, columnspan=3, sticky="ew", pady=8)
        ttk.Label(root, textvariable=self.status_var, wraplength=850).grid(row=6, column=0, columnspan=3, sticky="w")

    def _pick(self) -> None:
        value = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if value:
            self.config_var.set(value)

    def _set_busy(self, busy: bool) -> None:
        for button in (self.capture_button, self.self_test_button):
            if button:
                button.state(["disabled"] if busy else ["!disabled"])

    def _run(self) -> None:
        if not self.config_var.get().strip():
            messagebox.showwarning("設定不足", "監視設定JSONを選択してください。")
            return
        self._set_busy(True)
        self.status_var.set("取得・保存・SHA256検証中…")
        threading.Thread(target=self._run_worker, daemon=True).start()

    def _run_worker(self) -> None:
        try:
            output = WebEvidenceArchiver(self.config_var.get()).capture_all(compare_previous=True)
            report_path = Path(output) / "change_report.json"
            if report_path.exists():
                report = json.loads(report_path.read_text(encoding="utf-8"))
                summary = f"変更あり: {report['changed_targets']} / {report['total_targets']} URL"
            else:
                summary = "初回記録のため比較対象はありません。"
            self.after(0, self._show_result, output, summary)
        except Exception as exc:
            self.after(0, self._show_error, exc)

    def _show_result(self, output: Path, summary: str) -> None:
        self._set_busy(False)
        self.status_var.set(f"完了: {summary}\n保存先: {output}\nVerification: PASS / Evidence Chain作成済み")
        messagebox.showinfo("完了", f"{summary}\n保存後SHA256検証: PASS\n\n{output}")

    def _self_test(self) -> None:
        self._set_busy(True)
        self.status_var.set("Chromium起動セルフテスト中…")
        threading.Thread(target=self._self_test_worker, daemon=True).start()

    def _self_test_worker(self) -> None:
        try:
            result = browser_self_test()
            self.after(0, self._show_self_test, result)
        except Exception as exc:
            self.after(0, self._show_error, exc)

    def _show_self_test(self, result: dict) -> None:
        self._set_busy(False)
        self.status_var.set(f"Chromiumセルフテスト: {result['status']} / bundled_browser={result['bundled_browser']}")
        messagebox.showinfo("セルフテスト", json.dumps(result, ensure_ascii=False, indent=2))

    def _verify_run(self) -> None:
        path = filedialog.askdirectory(title="web_evidence_* フォルダを選択")
        if not path:
            return
        try:
            result = verify_run_integrity(path)
        except Exception as exc:
            messagebox.showerror("検証エラー", str(exc))
            return
        self.status_var.set(f"Run検証: {result['status']} / checked={result['checked']} / errors={len(result['errors'])}")
        if result["status"] == "pass":
            messagebox.showinfo("検証OK", "manifest記録済み成果物とEvidence Chainのhashが一致しました。")
        else:
            messagebox.showwarning("検証NG", "\n".join(result["errors"][:30]))

    def _show_error(self, exc: Exception) -> None:
        self._set_busy(False)
        self.status_var.set(f"エラー: {exc}")
        messagebox.showerror("処理エラー", str(exc))


def main() -> None:
    if "--self-test" in sys.argv:
        print(json.dumps(browser_self_test(), ensure_ascii=False, indent=2))
        return
    WebChangeEvidenceApp().mainloop()


if __name__ == "__main__":
    main()
