# Web Change Evidence Monitor

**公開Webページをローカル保存し、前回と今回の変更を「可視テキスト・画面・HTML」に分けて証跡化するWindows向け監査ツール**です。

単なるスクリーンショット保存やURL監視ではなく、**原証跡を保存したまま比較用ノイズだけを除外し、変更の種類を分離して追跡できる**ことを専門機能にしています。

> Release Candidate。出力は技術的な取得・変更記録であり、法的証拠能力・真正性・変更の重要性を保証するものではありません。

## 専門性

### Multi-layer capture
1回の取得で以下を保存します。

- HTML
- Full-page PNG
- PDF
- 可視テキスト
- 比較用正規化テキスト
- URL / final URL / title / HTTP status / captured_at
- 各成果物SHA256

### Change classification
前回記録と比較して以下を区別します。

- `content_changed`: 読めるテキストが変化
- `render_changed`: テキストは同じだが画面表示が変化
- `html_only_changed`: テキスト・画面は同じだがHTMLが変化
- `unchanged`

広告やDOM変化と、本文変更を完全ではないものの切り分けやすくします。

### Noise control without altering evidence

- `selector`: 比較対象範囲を限定
- `ignore_text_regexes`: 日時・カウンタ等を比較時のみ除外

`visible_text.txt` / HTML / PNG / PDFは加工せず原証跡として保存します。

### Diff report

- 追加 / 削除テキスト行数
- unified diff
- JSON report
- Markdown report

## Network safety

- HTTPSのみ
- URL埋め込みusername/password拒否
- `allow_hosts`必須
- Playwright route guardでallowlist外通信を拒否
- ログイン回避 / CAPTCHA回避 / Access Control回避機能なし

外部CDNが必要なサイトではCDN hostも明示許可する必要があります。

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
  "settle_milliseconds": 750,
  "max_diff_lines": 1500
}
```

## 出力例

```text
web_evidence_YYYYMMDD_HHMMSS/
├─ 001_Pricing/
│  ├─ page.html
│  ├─ screenshot.png
│  ├─ page.pdf
│  ├─ visible_text.txt
│  ├─ normalized_text.txt
│  └─ metadata.json
├─ diffs/
├─ manifest.json
├─ change_report.json
└─ change_report.md
```

初回取得時は比較対象がないためchange reportはありません。

## Bundled browser support

`archiver.py --self-test` でChromium起動セルフテストを行えます。配布版ではアプリ隣接 `browsers/` を優先して利用する設計です。

```powershell
python archiver.py --self-test
```

## 想定用途

- 公開料金ページ変更記録
- 取引先仕様 / FAQ / 告知ページの変更確認
- 利用規約や公開文書の変更履歴
- 官公庁・業界団体ページの調査
- 調査レポートの「取得時点」保存
- 自社Web QAのBefore / After記録

## 利用上の注意

- 閲覧・保存する権限があるページに使用してください。
- 対象サイトの利用規約・robots.txt・著作権・データベース権等は利用者が確認してください。
- SHA256は保存後の同一性確認に役立ちますが、取得時内容の真実性や法的効力を保証しません。
- 動的ページはrender差分が頻発するため、selector / ignoreルール設定が重要です。

## Test / Build

```powershell
python -m unittest discover -s tests -v
```

Windows CI / Playwright Chromium / PyInstaller build定義は `.github/workflows/windows-ci.yml` にあります。

販売判定は [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) を基準にしてください。
