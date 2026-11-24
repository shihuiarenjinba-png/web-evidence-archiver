from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from archiver import WebEvidenceArchiver, load_capture_summary, load_config


class WebEvidenceArchiverApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Web Evidence Archiver")
        self.geometry("760x360")
        self.minsize(680, 330)
        self.config_var = tk.StringVar()
        self.status_var = tk.StringVar(value="設定JSONを選択してください。")
        self.events: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.start_button: ttk.Button | None = None
        self.cancel_button: ttk.Button | None = None
        self._build()
        self.after(100, self._poll_worker)

    def _build(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)

        ttk.Label(root, text="設定JSON").grid(row=0, column=0, sticky="w", pady=8)
        ttk.Entry(root, textvariable=self.config_var).grid(row=0, column=1, sticky="ew", pady=8)
        ttk.Button(root, text="選択", command=self._pick).grid(row=0, column=2, padx=(8, 0), pady=8)

        ttk.Label(
            root,
            text="1) HTTPS URLと保存先を設定JSONで確認  2) 記録を作成  3) 出力フォルダーでHTML・PNG・PDF・manifestを確認\n許可ホスト外への移動は拒否します。1ページごとにタイムアウト設定が適用されます。",
            wraplength=700,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))

        ttk.Label(root, textvariable=self.status_var, wraplength=700).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(16, 0)
        )
        self.start_button = ttk.Button(root, text="記録を作成", command=self._run)
        self.start_button.grid(row=3, column=0, pady=20, sticky="w")
        self.cancel_button = ttk.Button(root, text="中止（現在のページ処理後）", command=self._cancel, state="disabled")
        self.cancel_button.grid(row=3, column=1, columnspan=2, pady=20, sticky="w")

    def _pick(self) -> None:
        value = filedialog.askopenfilename(parent=self, filetypes=[("JSON", "*.json")])
        if value:
            self.config_var.set(value)

    def _run(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        config_path = self.config_var.get().strip()
        if not config_path:
            messagebox.showinfo("設定が必要です", "capture設定JSONを選択してください。", parent=self)
            return
        try:
            config = load_config(config_path)
        except Exception as exc:
            self.status_var.set(f"設定エラー: {exc}")
            messagebox.showerror("設定を確認してください", str(exc), parent=self)
            return
        output_dir = config.get("output_dir", "web_evidence")
        if not messagebox.askokcancel(
            "capture開始の確認",
            f"{len(config['urls'])}件の許可済みHTTPSページを記録します。\n\n"
            f"保存先: {output_dir}\nホスト制限とtimeout設定を確認しましたか？",
            parent=self,
        ):
            return
        self.cancel_event.clear()
        self.start_button.config(state="disabled")
        self.cancel_button.config(state="normal")
        self.status_var.set("準備中…画面は操作可能です。")
        self.worker = threading.Thread(
            target=self._capture_worker,
            args=(config_path,),
            daemon=True,
        )
        self.worker.start()

    def _capture_worker(self, config_path: str) -> None:
        try:
            output = WebEvidenceArchiver(
                config_path,
                progress=self.events.put,
                cancel_event=self.cancel_event,
            ).capture_all()
            self.events.put(("done", str(output)))
        except Exception as exc:
            self.events.put(("error", f"{type(exc).__name__}: {exc}"))

    def _cancel(self) -> None:
        self.cancel_event.set()
        self.status_var.set("中止を要求しました。現在のページ処理が終わるまで待機しています。")
        self.cancel_button.config(state="disabled")

    def _poll_worker(self) -> None:
        try:
            while True:
                item = self.events.get_nowait()
                if isinstance(item, tuple) and item[0] == "done":
                    output = item[1]
                    try:
                        summary_data = load_capture_summary(output)
                        manifest_path = summary_data["manifest_path"]
                        captures = summary_data["captures"]
                        files = summary_data["files"]
                        if summary_data["cancelled"]:
                            title = "途中で中止しました"
                            summary = f"{len(captures)}件分のcaptureをmanifestへ保存しました。未処理URLがあります。"
                            self.status_var.set(f"中止: {len(captures)}件を保存: {output}")
                        else:
                            title = "完了"
                            file_text = "\n".join(files[:12]) if files else "成果物はありません。"
                            summary = f"{len(captures)}件のcaptureを保存しました。\n{file_text}"
                            self.status_var.set(
                                f"完了: {len(captures)}件。成果物とmanifestを確認してください: {output}"
                            )
                        messagebox.showinfo(
                            title,
                            f"{summary}\n\nmanifest: {manifest_path}",
                            parent=self,
                        )
                    except Exception as exc:
                        self.status_var.set(f"結果確認エラー: {type(exc).__name__}: {exc}")
                        messagebox.showerror(
                            "結果を確認できません",
                            f"capture処理は終了しましたが、manifestまたは成果物を確認できませんでした。\n\n"
                            f"{type(exc).__name__}: {exc}\n\n出力フォルダーを確認してください: {output}",
                            parent=self,
                        )
                    finally:
                        self._set_idle()
                elif isinstance(item, tuple) and item[0] == "error":
                    self.status_var.set(f"取得エラー: {item[1]}")
                    messagebox.showerror(
                        "取得に失敗しました",
                        f"{item[1]}\n\n設定・ネットワーク・ブラウザー依存関係を確認し、必要なら再試行してください。",
                        parent=self,
                    )
                    self._set_idle()
                else:
                    self.status_var.set(str(item))
        except queue.Empty:
            pass
        except Exception as exc:
            self.status_var.set(f"GUI結果表示エラー: {type(exc).__name__}: {exc}")
            messagebox.showerror(
                "結果表示エラー",
                f"capture結果の表示中にエラーが発生しました。\n{type(exc).__name__}: {exc}",
                parent=self,
            )
            self._set_idle()
        finally:
            self.after(100, self._poll_worker)

    def _set_idle(self) -> None:
        self.start_button.config(state="normal")
        self.cancel_button.config(state="disabled")


if __name__ == "__main__":
    WebEvidenceArchiverApp().mainloop()
