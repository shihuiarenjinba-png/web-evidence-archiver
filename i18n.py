from __future__ import annotations

import locale
import os
import tkinter as tk
from tkinter import filedialog, messagebox

_LANGUAGE = "ja" if any((x or "").lower().startswith("ja") for x in (locale.getlocale()[0], os.environ.get("LANG"))) else "en"
_CONTROLLERS = []
_PATCHED = False

TEXTS = {
    "Web Evidence Archiver": ("Web Evidence Archiver", "Web証拠アーカイバー"),
    "1. URLから記録（1サイト）": ("1. Save one website", "1. URLから記録（1サイト）"),
    "HTTPS URL": ("HTTPS URL", "HTTPS URL"),
    "出力フォルダ": ("Output folder", "出力フォルダ"),
    "参照": ("Browse", "参照"), "選択": ("Choose", "選択"),
    "2. または既存の複数URL設定を使う": ("2. Or use a multi-URL JSON configuration", "2. または既存の複数URL設定を使う"),
    "設定JSON": ("Configuration JSON", "設定JSON"),
    "保存を開始": ("Start capture", "保存を開始"),
    "保存したいHTTPS URLと保存先を指定してください。": ("Enter an HTTPS URL and choose where to save the evidence.", "保存したいHTTPS URLと保存先を指定してください。"),
    "① URLまたは設定JSONを選択  →  ② 保存先を確認  →  ③ HTML・PNG・PDF・SHA256を保存":
        ("① Choose URL/config  →  ② Confirm output folder  →  ③ Save HTML, PNG, PDF and SHA256",
         "① URLまたは設定JSONを選択  →  ② 保存先を確認  →  ③ HTML・PNG・PDF・SHA256を保存"),
    "入力したHTTPSホストだけを取得対象にし、外部ホストの素材は取得しません。":
        ("Only the entered HTTPS host is captured; assets from other hosts are not fetched.",
         "入力したHTTPSホストだけを取得対象にし、外部ホストの素材は取得しません。"),
    "入力不足": ("Missing input", "入力不足"), "URLエラー": ("URL error", "URLエラー"),
    "一部の記録に失敗しました": ("Some captures failed", "一部の記録に失敗しました"),
    "記録完了": ("Capture complete", "記録完了"), "取得エラー": ("Capture error", "取得エラー"), "処理中": ("Working", "処理中"),
}

PHRASES = (
    ("保存フォルダを選択してください。", "Choose an output folder."),
    ("保存処理が完了するまで画面を閉じないでください。", "Keep this window open until capture finishes."),
    ("取得失敗:", "Capture failed:"), ("記録フォルダ:", "Evidence folder:"), ("成功:", "Captured:"), ("失敗:", "Failed:"), ("未試行:", "Not attempted:"),
    ("詳細はmanifest.jsonで確認してください。", "See manifest.json for details."),
)

def get_language():
    return _LANGUAGE

def translate(text):
    if not isinstance(text, str):
        return text
    if text in TEXTS:
        en, ja = TEXTS[text]
        return ja if _LANGUAGE == "ja" else en
    if _LANGUAGE == "en":
        for ja, en in PHRASES:
            text = text.replace(ja, en)
    return text

def set_language(lang):
    global _LANGUAGE
    if lang not in {"en", "ja"}:
        raise ValueError("language must be 'en' or 'ja'")
    _LANGUAGE = lang
    for controller in tuple(_CONTROLLERS):
        controller.refresh()

def _patch():
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True
    original_insert = tk.Listbox.insert
    tk.Listbox.insert = lambda self, index, *items: original_insert(self, index, *(translate(x) for x in items))
    for name in ("showinfo", "showwarning", "showerror", "askokcancel"):
        original = getattr(messagebox, name, None)
        if original is None:
            continue
        def make_wrapper(func):
            def wrapper(title, message, *args, **kwargs):
                return func(translate(title), translate(message), *args, **kwargs)
            return wrapper
        setattr(messagebox, name, make_wrapper(original))
    for name in ("askopenfilename", "askopenfilenames", "askdirectory"):
        original = getattr(filedialog, name, None)
        if original is None:
            continue
        def make_dialog(func):
            def wrapper(*args, **kwargs):
                if "title" in kwargs:
                    kwargs["title"] = translate(kwargs["title"])
                return func(*args, **kwargs)
            return wrapper
        setattr(filedialog, name, make_dialog(original))

class LanguageController:
    def __init__(self, root):
        self.root = root
        self.original_title = root.title()
        existing = list(root.winfo_children())
        self._snapshot(root)
        self.frame = tk.Frame(root, padx=12, pady=5)
        if existing:
            self.frame.pack(fill="x", before=existing[0])
        else:
            self.frame.pack(fill="x")
        tk.Label(self.frame, text="Language / 言語").pack(side="right", padx=(0, 8))
        self.button = tk.Button(self.frame, width=10, command=self.toggle)
        self.button.pack(side="right")
        _CONTROLLERS.append(self)
        self.refresh()

    def _snapshot(self, widget):
        try:
            widget._i18n_original_text = widget.cget("text")
        except Exception:
            pass
        for child in widget.winfo_children():
            self._snapshot(child)

    def _refresh(self, widget):
        if widget is not self.button and hasattr(widget, "_i18n_original_text"):
            try:
                widget.configure(text=translate(widget._i18n_original_text))
            except Exception:
                pass
        for child in widget.winfo_children():
            self._refresh(child)

    def refresh(self):
        self.root.title(translate(self.original_title))
        self._refresh(self.root)
        self.button.configure(text="English" if _LANGUAGE == "ja" else "日本語")

    def toggle(self):
        set_language("en" if _LANGUAGE == "ja" else "ja")

def install_bilingual_ui(root):
    _patch()
    return LanguageController(root)
