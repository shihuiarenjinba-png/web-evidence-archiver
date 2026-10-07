from __future__ import annotations

import json
import os
import tkinter as tk
import uuid
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse

from archiver import WebEvidenceArchiver, load_config, validate_url
from config_store import atomic_write_json, list_config_files

DEFAULT_OUTPUT = Path.home() / "Documents" / "Web Evidence Archiver" / "Output"
DEFAULT_CONFIGS = Path.home() / "Documents" / "Web Evidence Archiver" / "Configs"
DIAGNOSTIC_DIR = Path(os.getenv("LOCALAPPDATA", Path.home())) / "Web Evidence Archiver" / "Logs"
EXAMPLE_URL = "https://example.com/"


def normalize_urls(text: str) -> list[str]:
    values, seen = [], set()
    for value in text.splitlines():
        url = value.strip()
        if not url:
            continue
        key = url.casefold()
        if key in seen:
            raise ValueError(f"重複URLがあります: {url}")
        seen.add(key); values.append(url)
    return values


def host_candidates(urls: list[str]) -> list[str]:
    return sorted({urlparse(url).hostname.casefold() for url in urls if urlparse(url).hostname})


def build_managed_config(urls_text: str, hosts_text: str, output: str, name: str = "Web設定", memo_path: str = "") -> dict:
    urls = normalize_urls(urls_text)
    hosts = [value.strip() for value in hosts_text.split(",") if value.strip()]
    if not urls:
        raise ValueError("保存するHTTPS URLを1件以上入力してください。")
    if not hosts:
        raise ValueError("許可ホストを1件以上入力してください。")
    if not output.strip():
        raise ValueError("出力先を指定してください。")
    for url in urls:
        validate_url(url, hosts)
    config = {
        "name": name.strip() or "Web設定", "allow_hosts": hosts, "urls": urls,
        "output_dir": output.strip(), "timeout_seconds": 30, "browser_channel": "msedge",
        "viewport": {"width": 1440, "height": 1000},
    }
    if memo_path.strip():
        memo = Path(memo_path).expanduser()
        if memo.suffix.casefold() not in {".txt", ".md"}:
            raise ValueError("記録先メモは .txt または .md を指定してください。")
        config["memo_path"] = str(memo)
    return config


def merge_preserved_config(base: dict | None, edited: dict) -> dict:
    """Preserve legacy/extension fields not represented by the form."""
    if not base:
        return edited
    merged = dict(base)
    merged.update(edited)
    return merged


def safe_error_text(exc: Exception) -> str:
    text = str(exc)
    if "HTTPS" in text or "allow_hosts" in text or "ブラウ" in text:
        return text
    if "Timeout" in type(exc).__name__ or "timeout" in text.casefold():
        return "接続がタイムアウトしました。"
    return "Web記録の作成に失敗しました。URL、許可ホスト、Edge、保存先を確認してください。"


def record_failure(operation: str, exc: Exception) -> str:
    diagnostic_id = uuid.uuid4().hex[:12].upper()
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    with (DIAGNOSTIC_DIR / "diagnostics.log").open("a", encoding="utf-8") as handle:
        handle.write(
            f"[{datetime.now(timezone.utc).isoformat()}] Diagnostic ID={diagnostic_id} "
            f"operation={operation} error_category={type(exc).__name__}\n"
        )
    return diagnostic_id


class WebEvidenceArchiverAppV2(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Web Evidence Archiver")
        self.geometry("1080x820")
        self.minsize(900, 680)
        self.status_var = tk.StringVar(value="「新規作成」「保存済み設定を編集」「保存済み設定で実行」から操作を選んでください。")
        self.edit_path_var = tk.StringVar()
        self.run_summary_var = tk.StringVar(value="設定を選択してください。")
        self.edit_original: dict | None = None
        self.run_paths: list[Path] = []
        self.extra_paths: list[Path] = []
        self.active_run_config: dict | None = None
        self.last_output: Path | None = None
        self._build(); self._refresh_library()

    def _build(self) -> None:
        root = ttk.Frame(self, padding=14); root.pack(fill="both", expand=True)
        ttk.Label(root, text="Web Evidence Archiver", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(root, text="許可したHTTPSページをEdgeで開き、HTML・PNG・PDF・SHA-256を新しいフォルダーへ保存します。許可ホストは通信先の制限であり、サイトのログイン権限を与えるものではありません。", wraplength=1020).pack(anchor="w", pady=(3, 10))
        ttk.Label(root, text="設定JSON = 何を取得するかを保存するファイル / Web記録 = 実際に取得したHTML・PNG・PDF・metadata・manifestの一式です。", wraplength=1020).pack(anchor="w", pady=(0, 10))
        notebook = ttk.Notebook(root); notebook.pack(fill="both", expand=True)
        new_tab, edit_tab, run_tab = ttk.Frame(notebook, padding=12), ttk.Frame(notebook, padding=12), ttk.Frame(notebook, padding=12)
        notebook.add(new_tab, text="1. 新規作成"); notebook.add(edit_tab, text="2. 保存済み設定を編集"); notebook.add(run_tab, text="3. 保存済み設定で実行")
        ttk.Label(new_tab, text="使い方: ①保存URLを1行ずつ入力 → ②「URLから許可ホスト候補を確認」→ ③必要ならメモを指定 → ④設定を保存", wraplength=980).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        self.new_form = self._make_form(new_tab, start_row=1)
        actions = ttk.Frame(new_tab); actions.grid(row=self.new_form["last_row"] + 1, column=0, columnspan=3, sticky="w", pady=8)
        ttk.Button(actions, text="公開ページの例", command=self._new_example).pack(side="left")
        ttk.Button(actions, text="URLから許可ホスト候補を確認", command=lambda: self._suggest_hosts(self.new_form)).pack(side="left", padx=8)
        ttk.Button(actions, text="新しい設定として保存", command=self._save_new).pack(side="left")

        edit_tab.columnconfigure(1, weight=1)
        ttk.Label(edit_tab, text="編集する設定JSON").grid(row=0, column=0, sticky="w")
        ttk.Entry(edit_tab, textvariable=self.edit_path_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(edit_tab, text="選択して読み込む", command=self._load_edit_dialog).grid(row=0, column=2)
        ttk.Label(edit_tab, text="既存設定にURLを追加する場合: JSONを読み込み、URL欄の一番下へ1行追加して更新します。既存URLは残り、更新前バックアップも作成されます。", wraplength=980).grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 8))
        self.edit_form = self._make_form(edit_tab, start_row=2)
        actions = ttk.Frame(edit_tab); actions.grid(row=self.edit_form["last_row"] + 1, column=0, columnspan=3, sticky="w", pady=8)
        ttk.Button(actions, text="許可ホスト候補を確認", command=lambda: self._suggest_hosts(self.edit_form)).pack(side="left")
        ttk.Button(actions, text="既存設定を更新（確認・バックアップ）", command=self._update_edit).pack(side="left", padx=8)
        ttk.Button(actions, text="別名で保存", command=self._save_edit_as).pack(side="left")
        ttk.Button(actions, text="変更を破棄", command=self._discard_edit).pack(side="left", padx=8)

        run_tab.columnconfigure(0, weight=1); run_tab.columnconfigure(2, weight=1); run_tab.rowconfigure(1, weight=1)
        ttk.Label(run_tab, text=f"設定一覧: {DEFAULT_CONFIGS}").grid(row=0, column=0, sticky="w")
        ttk.Label(run_tab, text="設定内URL（複数選択可）").grid(row=0, column=2, sticky="w")
        self.config_list = tk.Listbox(run_tab, exportselection=False, height=12)
        self.config_list.grid(row=1, column=0, sticky="nsew", pady=6); self.config_list.bind("<<ListboxSelect>>", self._select_config)
        controls = ttk.Frame(run_tab); controls.grid(row=1, column=1, sticky="ns", padx=8)
        for text, command in (("再読込", self._refresh_library), ("既存JSONを追加", self._add_existing), ("複製", self._duplicate), ("設定だけ削除", self._delete_config)):
            ttk.Button(controls, text=text, command=command).pack(fill="x", pady=2)
        self.url_list = tk.Listbox(run_tab, selectmode="extended", exportselection=False, height=12)
        self.url_list.grid(row=1, column=2, sticky="nsew", pady=6); self.url_list.bind("<<ListboxSelect>>", self._select_urls)
        ttk.Label(run_tab, textvariable=self.run_summary_var, wraplength=940).grid(row=2, column=0, columnspan=3, sticky="w", pady=6)
        actions = ttk.Frame(run_tab); actions.grid(row=3, column=0, columnspan=3, sticky="w")
        ttk.Button(actions, text="選択URLだけ記録", command=self._run_selected_urls).pack(side="left")
        ttk.Button(actions, text="設定内URLを一括記録", command=self._run_all_urls).pack(side="left", padx=8)
        self.open_button = ttk.Button(actions, text="最後の出力フォルダーを開く", command=self._open_output, state="disabled"); self.open_button.pack(side="left")
        ttk.Separator(root).pack(fill="x", pady=8)
        ttk.Label(root, textvariable=self.status_var, wraplength=1020).pack(anchor="w")

    def _make_form(self, parent, start_row: int = 0) -> dict:
        parent.columnconfigure(1, weight=1)
        name, hosts, output, memo = tk.StringVar(value="Web設定"), tk.StringVar(), tk.StringVar(value=str(DEFAULT_OUTPUT)), tk.StringVar()
        ttk.Label(parent, text="設定名").grid(row=start_row, column=0, sticky="w", pady=4); ttk.Entry(parent, textvariable=name).grid(row=start_row, column=1, columnspan=2, sticky="ew", pady=4)
        ttk.Label(parent, text="保存URL（1行1件）").grid(row=start_row+1, column=0, sticky="nw", pady=4)
        urls = tk.Text(parent, height=8, wrap="none"); urls.grid(row=start_row+1, column=1, columnspan=2, sticky="nsew", pady=4)
        ttk.Label(parent, text="許可ホスト（カンマ区切り）").grid(row=start_row+2, column=0, sticky="w", pady=4); ttk.Entry(parent, textvariable=hosts).grid(row=start_row+2, column=1, columnspan=2, sticky="ew", pady=4)
        ttk.Label(parent, text="候補は確認後に追加します。外部CDNを無条件には許可しません。").grid(row=start_row+3, column=1, columnspan=2, sticky="w")
        ttk.Label(parent, text="出力先").grid(row=start_row+4, column=0, sticky="w", pady=4); ttk.Entry(parent, textvariable=output).grid(row=start_row+4, column=1, sticky="ew", pady=4)
        ttk.Button(parent, text="選択", command=lambda: self._choose_output(output)).grid(row=start_row+4, column=2, padx=(6, 0))
        ttk.Label(parent, text="記録先メモ（任意 .txt/.md）").grid(row=start_row+5, column=0, sticky="w", pady=4); ttk.Entry(parent, textvariable=memo).grid(row=start_row+5, column=1, sticky="ew", pady=4)
        ttk.Button(parent, text="既存メモを選択", command=lambda: self._choose_memo(memo)).grid(row=start_row+5, column=2, padx=(6, 0))
        ttk.Label(parent, text="指定すると取得後にURL・取得日時・保存先・manifestを追記します。既存文があれば末尾、空なら先頭から書きます。", wraplength=820).grid(row=start_row+6, column=1, columnspan=2, sticky="w")
        return {"name": name, "urls": urls, "hosts": hosts, "output": output, "memo": memo, "base": None, "last_row": start_row+6}

    def _choose_output(self, variable: tk.StringVar) -> None:
        value = filedialog.askdirectory(parent=self, title="出力先フォルダーを選択")
        if value: variable.set(value)

    def _choose_memo(self, variable: tk.StringVar) -> None:
        value = filedialog.askopenfilename(parent=self, title="追記する既存メモを選択", filetypes=[("Text / Markdown", "*.txt *.md")])
        if value: variable.set(value)

    def _config_from(self, form: dict) -> dict:
        edited = build_managed_config(form["urls"].get("1.0", "end"), form["hosts"].get(), form["output"].get(), form["name"].get(), form["memo"].get())
        return merge_preserved_config(form.get("base"), edited)

    def _populate(self, form: dict, config: dict) -> None:
        form["base"] = json.loads(json.dumps(config))
        form["name"].set(str(config.get("name", "Web設定")))
        form["hosts"].set(", ".join(config.get("allow_hosts", [])))
        form["output"].set(str(config.get("output_dir", DEFAULT_OUTPUT)))
        form["memo"].set(str(config.get("memo_path", "")))
        form["urls"].delete("1.0", "end"); form["urls"].insert("1.0", "\n".join(config.get("urls", [])))

    def _new_example(self) -> None:
        self.new_form["name"].set("Example Domain"); self.new_form["urls"].delete("1.0", "end"); self.new_form["urls"].insert("1.0", EXAMPLE_URL); self.new_form["hosts"].set("example.com")
        self.status_var.set("公開サンプルを入力しました。まだ通信は行っていません。")

    def _suggest_hosts(self, form: dict) -> None:
        try: candidates = host_candidates(normalize_urls(form["urls"].get("1.0", "end")))
        except Exception as exc: messagebox.showwarning("URL確認", str(exc), parent=self); return
        if not candidates: messagebox.showwarning("候補なし", "URLからホストを抽出できませんでした。", parent=self); return
        if messagebox.askyesno("許可ホスト候補", "次のホストを許可リストへ追加しますか？\n\n" + "\n".join(candidates), parent=self):
            current = [v.strip() for v in form["hosts"].get().split(",") if v.strip()]
            form["hosts"].set(", ".join(dict.fromkeys(current + candidates)))

    def _choose_save(self, initial: str) -> str:
        DEFAULT_CONFIGS.mkdir(parents=True, exist_ok=True)
        return filedialog.asksaveasfilename(parent=self, initialdir=DEFAULT_CONFIGS, initialfile=initial, defaultextension=".json", filetypes=[("設定JSON", "*.json")])

    def _save_new(self) -> None:
        try:
            config = self._config_from(self.new_form); destination = self._choose_save("web-setting.json")
            if not destination: return
            atomic_write_json(destination, config, overwrite=False); self._refresh_library()
            self.status_var.set(f"新しい設定を保存しました（既存設定は変更していません）: {destination}")
        except Exception as exc: messagebox.showwarning("保存失敗", str(exc), parent=self)

    def _load_edit_dialog(self) -> None:
        path = filedialog.askopenfilename(parent=self, initialdir=DEFAULT_CONFIGS, filetypes=[("設定JSON", "*.json")])
        if path: self._load_edit(Path(path))

    def _load_edit(self, path: Path) -> None:
        try: config = load_config(path)
        except Exception as exc:
            messagebox.showwarning("読込失敗", str(exc), parent=self); self.status_var.set("読み込みに失敗しました。編集中のURL一覧は変更していません。"); return
        self._populate(self.edit_form, config); self.edit_original = config; self.edit_path_var.set(str(path.resolve()))
        self.status_var.set(f"{len(config['urls'])}件のURLをフォームへ読み込みました。追加しても既存URLは保持されます。")

    def _update_edit(self) -> None:
        if not self.edit_path_var.get(): messagebox.showwarning("設定未選択", "先に編集する設定を読み込んでください。", parent=self); return
        try: config = self._config_from(self.edit_form)
        except Exception as exc: messagebox.showwarning("入力エラー", str(exc), parent=self); return
        if not messagebox.askyesno("既存設定の更新", f"{len(config['urls'])}件のURLを含む設定へ更新し、変更前バックアップを作成します。続けますか？", parent=self): return
        try:
            _, backup = atomic_write_json(self.edit_path_var.get(), config, overwrite=True, backup=True); self.edit_original = config; self._refresh_library()
            self.edit_form["base"] = json.loads(json.dumps(config))
            self.status_var.set(f"設定を原子的に更新しました。バックアップ: {backup}")
        except Exception as exc: messagebox.showerror("更新失敗", str(exc), parent=self)

    def _save_edit_as(self) -> None:
        try:
            config = self._config_from(self.edit_form); destination = self._choose_save("web-setting-copy.json")
            if not destination: return
            atomic_write_json(destination, config, overwrite=False); self._refresh_library(); self.status_var.set("別名で保存しました。元の設定は変更していません。")
        except Exception as exc: messagebox.showwarning("保存失敗", str(exc), parent=self)

    def _discard_edit(self) -> None:
        if self.edit_original is not None: self._populate(self.edit_form, self.edit_original); self.status_var.set("未保存の変更を破棄しました。")

    def _refresh_library(self) -> None:
        defaults = list_config_files(DEFAULT_CONFIGS)
        self.run_paths = defaults + [p for p in self.extra_paths if p.exists() and p not in defaults]
        self.config_list.delete(0, "end"); self.url_list.delete(0, "end"); self.active_run_config = None
        for path in self.run_paths: self.config_list.insert("end", path.name)

    def _add_existing(self) -> None:
        path = filedialog.askopenfilename(parent=self, filetypes=[("設定JSON", "*.json")])
        if not path: return
        try: load_config(path)
        except Exception as exc: messagebox.showwarning("追加失敗", str(exc), parent=self); return
        resolved = Path(path).resolve()
        if resolved not in self.extra_paths: self.extra_paths.append(resolved)
        self._refresh_library()

    def _selected_config_path(self) -> Path | None:
        selected = self.config_list.curselection()
        return self.run_paths[selected[0]] if len(selected) == 1 else None

    def _select_config(self, _event=None) -> None:
        path = self._selected_config_path(); self.url_list.delete(0, "end")
        if path is None: self.active_run_config = None; return
        try:
            self.active_run_config = load_config(path)
            for url in self.active_run_config["urls"]: self.url_list.insert("end", url)
            self.run_summary_var.set(f"対象設定: {path.name}\n出力先: {self.active_run_config.get('output_dir')}\nURL: {len(self.active_run_config['urls'])}件 / HTML・PNG・PDF・SHA-256を新規保存 / ネットワーク: あり")
        except Exception as exc: self.active_run_config = None; self.run_summary_var.set(f"設定エラー: {exc}")

    def _select_urls(self, _event=None) -> None:
        if self.active_run_config is None: return
        count = len(self.url_list.curselection()); self.run_summary_var.set(f"選択中: {count}件 / 出力先: {self.active_run_config.get('output_dir')} / HTTPS通信あり")

    def _duplicate(self) -> None:
        path = self._selected_config_path()
        if path is None: messagebox.showwarning("1件選択", "複製する設定を1件選択してください。", parent=self); return
        try:
            destination = self._choose_save(f"{path.stem}-copy.json")
            if not destination: return
            atomic_write_json(destination, load_config(path), overwrite=False); self._refresh_library(); self.status_var.set("設定を複製しました。過去のWeb記録は変更していません。")
        except Exception as exc: messagebox.showwarning("複製失敗", str(exc), parent=self)

    def _delete_config(self) -> None:
        path = self._selected_config_path()
        if path is None: messagebox.showwarning("1件選択", "削除する設定を1件選択してください。", parent=self); return
        if not messagebox.askyesno("設定だけを削除", f"設定JSONだけを削除します。過去のHTML・PNG・PDFは削除しません。\n\n{path}", parent=self): return
        path.unlink(); self.extra_paths = [p for p in self.extra_paths if p != path]; self._refresh_library(); self.status_var.set("設定JSONだけを削除しました。過去の記録は残っています。")

    def _run_selected_urls(self) -> None:
        selected = list(self.url_list.curselection())
        if self.active_run_config is None or not selected: messagebox.showwarning("URL未選択", "設定と記録するURLを選択してください。", parent=self); return
        self._run_urls([self.active_run_config["urls"][i] for i in selected])

    def _run_all_urls(self) -> None:
        if self.active_run_config is None: messagebox.showwarning("設定未選択", "実行する設定を選択してください。", parent=self); return
        if messagebox.askyesno("一括記録", f"{len(self.active_run_config['urls'])}件を記録しますか？", parent=self): self._run_urls(list(self.active_run_config["urls"]))

    def _run_urls(self, urls: list[str]) -> None:
        path = self._selected_config_path()
        if path is None: return
        try:
            archiver = WebEvidenceArchiver(path); output = archiver.capture_urls(urls); result = archiver.last_result or {}
            self.last_output = output; self.open_button.configure(state="normal")
            state = "完了" if result.get("complete") else "一部失敗（成功とは表示しません）"
            details = []
            for capture in result.get("captures", []):
                details.append(
                    f"{capture.get('requested_url')} → {capture.get('final_url')} / "
                    f"HTTP {capture.get('http_status')} / 生成: {', '.join(capture.get('files', [])) or 'なし'}"
                )
            memo_status = ""
            if result.get("memo_path"):
                memo_status = f" / メモ追記: {result.get('memo_path')}"
            elif result.get("memo_error"):
                memo_status = f" / メモ追記失敗: {result.get('memo_error')}"
            self.status_var.set(
                f"{state}: {result.get('captured')}/{result.get('requested')}件 / 失敗 {result.get('failed')}件"
                f" / 保存先 {output} / manifest {result.get('manifest')} / ブロック資源 {result.get('blocked_resources')}"
                + memo_status
                + ("\n" + "\n".join(details) if details else "")
            )
            messagebox.showinfo("取得結果", self.status_var.get(), parent=self)
        except Exception as exc:
            diagnostic = record_failure("capture-saved-config", exc)
            self.status_var.set(f"失敗: {safe_error_text(exc)} Diagnostic ID: {diagnostic}")
            messagebox.showerror("取得失敗", self.status_var.get(), parent=self)

    def _open_output(self) -> None:
        if self.last_output: os.startfile(self.last_output)
