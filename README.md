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

PowerShellから以下を実行してください。スクリプトは現在の作業フォルダーではなく、自身の配置場所からリポジトリを特定します。Python 3.13を優先し、3.12を次に使用します。3.14は既定で使いません。

```powershell
& "<Web Evidence Archiverの場所>\setup.ps1"
& "<Web Evidence Archiverの場所>\doctor.ps1"
& "<Web Evidence Archiverの場所>\run.ps1"
```

Python 3.13 / 3.12がない場合は、3.14を自動的に製品対応扱いにせず、全テストとChromium起動検証を行う明示的な試行だけを許可します。

```powershell
& "<Web Evidence Archiverの場所>\setup.ps1" -AllowExperimentalPython314
```

`setup.ps1`はリポジトリ内の`.venv`と`.pw-browsers`にだけ依存関係・Chromiumを導入し、unittest・compile・Chromium headless起動を確認します。既存の`.venv`が不適合なら削除・上書きせず停止します。`doctor.ps1`は状態を診断し、`run.ps1 -CheckOnly`はどの作業フォルダーから呼んでもパス解決を確認できます。

確認済みのJSON設定を起動時に読み込む場合は、`run.ps1 -ConfigPath .\config.json`または`python app.py --config .\config.json`を指定できます。省略した場合は画面から選択します。

例として、PowerShellの現在地が`C:\Users\aaron\Desktop\Windows-Automator`でも、リポジトリの保存場所にあるスクリプトの完全パスから起動します。

```powershell
& "<Web Evidence Archiverの保存場所>\run.ps1"
```

手動でvenvを作る場合の参考手順:

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
