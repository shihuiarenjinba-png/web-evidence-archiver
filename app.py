from __future__ import annotations

import argparse
import queue
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from archiver import WebEvidenceArchiver, load_capture_summary, load_config


class WebEvidenceArchiverApp(tk.Tk):
    def __init__(self, config_path: str | None = None) -> None:
        super().__init__()
        self.title("Web Evidence Archiver")
        self.geometry("820x470")
        self.minsize(680, 400)
        self.config_var = tk.StringVar(value=config_path or "")
        self.status_var = tk.StringVar(value="設定JSONを選択してください。")
        self.summary_var = tk.StringVar(value="設定を選択すると、URL数・許可ホスト・保存先・timeoutをここに表示します。")
        self.events: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.start_button: ttk.Button | None = None
        self.cancel_button: ttk.Button | None = None
        self.open_output_button: ttk.Button | None = None
        self.close_when_idle = False
        self.last_output: str | None = None
        self._build()
        if config_path:
            self._refresh_summary(config_path)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_worker)

    def _build(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)

        ttk.Label(root, text="設定JSON").grid(row=0, column=0, sticky="w", pady=8)
        ttk.Entry(root, textvariable=self.config_var).grid(row=0, column=1, sticky="ew", pady=8)
        ttk.Button(root, text="選択", command=self._pick).grid(row=0, column=2, padx=(8, 0), pady=8)
        ttk.Label(root, textvariable=self.summary_var, wraplength=740, justify="left").grid(
            row=1, column=0, columnspan=3, sticky="ew", pady=(6, 0)
        )

        ttk.Label(
            root,
            text="1) HTTPS URLと保存先を設定JSONで確認  2) 記録を作成  3) 出力フォルダーでHTML・PNG・PDF・manifestを確認\n許可ホスト外への移動は拒否します。1ページごとにタイムアウト設定が適用されます。",
            wraplength=700,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))

        ttk.Label(root, textvariable=self.status_var, wraplength=700).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(16, 0)
        )
        self.start_button = ttk.Button(root, text="記録を作成", command=self._run)
        self.start_button.grid(row=4, column=0, pady=20, sticky="w")
        self.cancel_button = ttk.Button(root, text="中止（現在のページ処理後）", command=self._cancel, state="disabled")
        self.cancel_button.grid(row=4, column=1, pady=20, sticky="w")
        self.open_output_button = ttk.Button(root, text="保存先を開く", command=self._open_output, state="disabled")
        self.open_output_button.grid(row=4, column=2, pady=20, sticky="e")

    def _pick(self) -> None:
        value = filedialog.askopenfilename(parent=self, filetypes=[("JSON", "*.json")])
        if value:
            self.config_var.set(value)
            self._refresh_summary(value)

    def _refresh_summary(self, config_path: str) -> dict | None:
        try:
            config = load_config(config_path)
        except Exception as exc:
            self.summary_var.set(f"設定エラー / Configuration error: {type(exc).__name__}: {exc}")
            if self.start_button:
                self.start_button.config(state="disabled")
            return None
        hosts = ", ".join(str(host) for host in config["allow_hosts"])
        output_dir = Path(config.get("output_dir", "web_evidence")).expanduser()
        if not output_dir.is_absolute():
            output_dir = (Path(config_path).expanduser().resolve().parent / output_dir).resolve()
        self.summary_var.set(
            f"対象URL: {len(config['urls'])}件  |  許可ホスト: {hosts}\n"
            f"保存先: {output_dir}  |  timeout: {int(config.get('timeout_seconds', 30))}秒 / URL"
        )
        if self.start_button:
            self.start_button.config(state="normal")
        return config

    def _run(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        config_path = self.config_var.get().strip()
        if not config_path:
            messagebox.showinfo("設定が必要です", "capture設定JSONを選択してください。", parent=self)
            return
        config = self._refresh_summary(config_path)
        if config is None:
            messagebox.showerror("設定を確認してください", self.summary_var.get(), parent=self)
            return
        output_dir = config.get("output_dir", "web_evidence")
        if not messagebox.askokcancel(
            "capture開始の確認",
            f"対象URL: {len(config['urls'])}件\nURL: {', '.join(config['urls'])}\n"
            f"許可ホスト: {', '.join(config['allow_hosts'])}\n"
            f"保存先: {output_dir}\ntimeout: {int(config.get('timeout_seconds', 30))}秒 / URL\n\n"
            "この設定でcaptureを開始しますか？",
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
            daemon=False,
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
            message = f"{type(exc).__name__}: {exc}"
            if "Executable doesn't exist" in message or "Executable does not exist" in message:
                message = f"Chromiumが見つかりません。setup.ps1で導入してください。\n詳細: {message}"
            elif "BrowserType.launch" in message or "Failed to launch" in message:
                message = f"Chromiumの起動に失敗しました。doctor.ps1で診断してください。\n詳細: {message}"
            self.events.put(("error", message))

    def _cancel(self) -> None:
        self.cancel_event.set()
        self.status_var.set("中止を要求しました。現在のページ処理が終わるまで待機しています。")
        self.cancel_button.config(state="disabled")

    def _on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            self.close_when_idle = True
            self.cancel_event.set()
            self.status_var.set("終了を待機中です。現在のページ処理が終わると保存して閉じます。")
            if self.cancel_button:
                self.cancel_button.config(state="disabled")
            return
        self.destroy()

    def _open_output(self) -> None:
        if not self.last_output or not Path(self.last_output).is_dir():
            messagebox.showinfo("保存先", "保存先フォルダーを確認できません。", parent=self)
            return
        try:
            subprocess.Popen(["explorer.exe", self.last_output])
        except OSError as exc:
            messagebox.showerror("保存先を開けません", str(exc), parent=self)

    def _poll_worker(self) -> None:
        try:
            while True:
                item = self.events.get_nowait()
                if isinstance(item, tuple) and item[0] == "done":
                    output = item[1]
                    self.last_output = output
                    self.open_output_button.config(state="normal")
                    if self.close_when_idle:
                        self.status_var.set(f"中止要求を処理し、現在までの出力を保存しました: {output}")
                        self._set_idle()
                        continue
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
                    if self.close_when_idle:
                        self._set_idle()
                        continue
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
        if self.close_when_idle:
            self.after_idle(self.destroy)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Web Evidence Archiver")
    parser.add_argument("--config", help="設定JSONを指定して起動します。未指定の場合は画面から選択できます。")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    WebEvidenceArchiverApp(config_path=args.config).mainloop()
