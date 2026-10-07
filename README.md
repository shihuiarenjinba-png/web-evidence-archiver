# Web Evidence Archiver

指定したHTTPSページをローカルで開き、スクリーンショット・HTML・PDF・取得時刻・URL・SHA256を1セットの記録として保存するWindowsツールです。新規作成、保存済み設定の編集、保存済み設定での実行を別画面に分けています。

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
- GUIで複数URLを追加・編集・重複検出し、選択URLだけまたは設定内URLを一括取得
- URLから許可ホスト候補を抽出し、利用者が確認した場合だけ追加
- 保存済み設定をフォームへ読み込み、更新・別名保存・変更破棄を選択
- 原子的な設定保存と更新前バックアップ
- URLごとの失敗をmanifestへ記録し、一部失敗を完了と表示しない
- GUIから成果物フォルダーを開く

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

通常利用ではGUIへURLを1行ずつ入力し、必要なホストだけを許可リストへ明示します。候補表示はアクセス権やログイン権限を取得する機能ではありません。旧版の複数URL設定JSONも読み込めます。

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
- allowlist外のリソースはブロックされるため、ページが部分的に欠ける場合があります。manifestの `blocked_resources` と `errors` を確認してください。
- ログイン、CAPTCHA、DRM、動画、強いbot対策、複雑な動的ページの完全保存は保証しません。

## 販売前TODO

- 定期実行連携
- URLごとの差分サマリー
- 画面サイズプリセット
- Win10/11実機テスト
- Playwright/Chromium同梱方式の検討
- PyInstallerビルド・署名

> Sales release: NO。正式LICENSE、第三者表示、署名、Human UI/DPI確認が完了するまで販売用リリースではありません。
