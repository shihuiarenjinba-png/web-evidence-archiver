# Web Evidence Archiver

指定したHTTPSページをローカルで開き、スクリーンショット・HTML・PDF・取得時刻・URL・SHA256を1セットの記録として保存するMVPです。

## できること

- HTTPS URLのみ
- `allow_hosts` に登録したホストだけを対象
- ページスクリーンショット（PNG）
- DOM保存（HTML）
- 印刷用PDF保存
- タイトル / HTTP status / original URL / final URL / 取得時刻を記録
- 各成果物のSHA256をmanifestへ記録
- allowlist外ホストへの通信をブロック
- 1回の実行で複数URLを保存

## 想定用途

- 自社サイトや料金ページの変更前後記録
- 取引先の公開ページ保存
- 調査・監査時点の公開情報保存
- 定期的なWeb表示記録の作成

## セットアップ

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
python app.py
```

CLI:

```bash
python archiver.py config.example.json
```

## 設定例

```json
{
  "allow_hosts": ["example.com", "www.example.com"],
  "urls": ["https://example.com/pricing"],
  "output_dir": "C:/WebEvidence",
  "timeout_seconds": 30
}
```

## 利用上の注意

- 利用者が閲覧・保存する権限を持つページに使用してください。
- 本ツールの出力が法的証拠として採用されることを保証するものではありません。
- CDN等の外部リソースが必要なページでは、そのホストも `allow_hosts` に明示する必要があります。

## 販売前TODO

- 定期実行連携
- URLごとの差分サマリー
- 画面サイズプリセット
- Win10/11実機テスト
- Playwright/Chromium同梱方式の検討
- PyInstallerビルド・署名

> 現在はMVP開発版です。販売用リリースではありません。

## UI改良ブランチ（2026-10-19、開発・検証HOLD）

`ui/simple-product-flow-20261019` では既存のHTTPS取得エンジンと完全な記録仕様を残し、初心者向け画面を改善しています。

- 1行に1件の複数URL入力（最大20件）、URL追加、保存先指定。
- 通信せずにURL/ホスト/保存先を検証する「記録前の確認」。
- 同じ入力・設定の場合に限り1回有効な記録承認。URLや詳細JSONが変われば承認が失効。
- 実ネットワークへ接続する前の確認画面。
- Capture statusとURL/HTTP状態を1件ずつ一覧化、成功・失敗・未試行を合計と分けて表示。
- 元の詳細JSONモードは「詳細設定JSONを使用する」チェックでのみ明示使用。既存JSONは書き換えません。
- 追加テスト: `tests/test_gui_capture_plan.py`（ネット接続なし／実ブラウザ無しの入力検証）。
- **要検証**: 日本語・英語切替、DPI 100/125/150%、Windows GUI、MSIX同梱Chromium、HTML/PNG/PDF実ページ取得、失敗時UI。追加コードのWindows回帰試験結果はまだ未取得。

Microsoft Store提出不可（HOLD）。ブラウザーが自動同梱された、または法的な証拠能力を保証すると表現しません。
