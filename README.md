# Web Change Evidence Monitor

公開Webページをローカルへ記録し、**前回と今回で「何が変わったか」を証跡付きで比較する**Windows向け商品候補です。

単なるスクリーンショット保存ではなく、同じURLの記録履歴から、可視テキスト・HTML・画面レンダリングの変更を分けて追跡します。

## 現在の機能

- HTTPS URLのみ
- `allow_hosts` に登録したホストだけを通信対象にする
- 1回で複数URLを記録
- HTML保存
- フルページPNG保存
- 印刷用PDF保存
- 可視テキスト保存
- 比較用の正規化テキスト保存
- URL / final URL / title / HTTP status / 取得時刻を記録
- 各成果物のSHA256をmanifestへ記録
- 前回runを自動検出し、同一URLを比較
- `content_changed` / `render_changed` / `html_only_changed` / `unchanged` を区別
- 追加・削除テキスト行数を集計
- unified diffを `diffs/*.diff.txt` として保存
- JSON / Markdown変更レポートを生成
- `selector` でページの特定範囲だけを比較可能
- `ignore_text_regexes` で日時・カウンタ等の揺れを比較時だけ除外可能

元のHTML・PNG・PDF・可視テキストはそのまま保存し、ignoreルールは比較用テキストにだけ適用します。

## 変更状態の意味

- `content_changed`: 正規化後の可視テキストが変わった
- `render_changed`: テキストは同じだがスクリーンショットが変わった
- `html_only_changed`: テキストと画面は同じだがHTMLが変わった
- `unchanged`: 上記3種のSHA256が同じ

これにより、広告・装飾・DOM変更と、読める文章そのものの変更をある程度切り分けられます。

## 設定例

```json
{
  "allow_hosts": ["example.com", "www.example.com"],
  "urls": [
    {
      "name": "Pricing",
      "url": "https://example.com/pricing",
      "selector": "body",
      "ignore_text_regexes": ["Last updated:.*$"]
    }
  ],
  "output_dir": "C:/WebEvidence",
  "timeout_seconds": 30,
  "max_diff_lines": 1500
}
```

外部CDN等のリソースが必要なページでは、そのホストも `allow_hosts` に明示する必要があります。

## 出力例

```text
web_evidence_20260917_090000/
├─ 001_Pricing/
│  ├─ page.html
│  ├─ screenshot.png
│  ├─ page.pdf
│  ├─ visible_text.txt
│  ├─ normalized_text.txt
│  └─ metadata.json
├─ diffs/
│  └─ Pricing.diff.txt
├─ manifest.json
├─ change_report.json
└─ change_report.md
```

初回runには比較対象がないためchange reportは作られません。

## セットアップ

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
python app.py
```

CLI:

```powershell
python archiver.py config.example.json
python archiver.py config.example.json --no-compare
python archiver.py dummy.json --compare C:\WebEvidence\old_run C:\WebEvidence\new_run
```

## 想定用途

- 自社・競合の公開料金ページ変更記録
- 取引先の公開仕様 / FAQ / 告知ページ変更確認
- 利用規約や公開ドキュメントの変更履歴
- 官公庁・業界団体の公開ページ調査
- 調査レポート作成時の「取得時点」記録

## 利用上の注意

- 利用者が閲覧・保存する権限を持つ公開ページ等に使用してください。
- ログイン回避、アクセス制御回避、CAPTCHA回避などを行う機能ではありません。
- robots.txtやサイト利用規約、著作権、データベース権等は対象サイトごとに確認してください。
- 本ツールの出力が法的証拠として認められることは保証しません。
- SHA256は保存後の同一性確認に役立ちますが、取得内容の真実性や法的効力を単独で保証するものではありません。
- 動的ページではレンダリング差分が頻発するため、selector / ignoreルールの設定が重要です。

## 販売前チェック

- Windows 10/11実機テスト
- Chromium同梱 / 初回セットアップ方式の確定
- 日本語・長文ページ・SPA・遅延読み込みページの回帰テスト
- ネットワーク失敗 / timeout / HTTP error時のレポート改善
- 定期実行は既存 `scheduled-api-runner` / Windows Task Scheduler等と役割分離して設計
- 大量履歴の整理 / retention設定
- PyInstaller portable EXE
- コード署名、配布物SHA256、AVチェック

現在は製品化候補のMVPです。販売前に実機検証を通してください。
