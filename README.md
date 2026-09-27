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
- GUIから複数URL・許可ホスト・出力先を設定
- GUIで設定JSONを保存、またはそのまま記録を作成

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

通常利用ではGUIへURLを1行ずつ入力し、必要なホストを許可リストへ明示します。既存設定JSONの選択欄は上級者向けです。

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
