# Web Evidence Archiver — 有料Windows MSIX販売引継ぎ（2026-10-18）

**重要：まだ販売READYではありません。全て開発用の独立ブランチであり、正式MSIX・WACK・実機テスト・商業性の証拠を別途確認します。**

## 製品・価値

- 対象リポジトリ：`shihuiarenjinba-png/web-evidence-archiver`
- 作業ブランチ：`feature/store-paid-msix-quality-20261017`
- 商品の中心価値：HTTPSの許可ホストだけを、取得日時・HTML・PNG・PDF・SHA256付きで保存。URL認証情報の埋め込みを拒否。
- 買い切り初期価格：1,980～3,980円（仮説）
- 無料配布するなら機能制限したLite版のみ検討し、監査履歴や自動化などのPro機能は無料化しない。
- 既存main・元入力・他商品のリポジトリは絶対に上書きしない。

## 本ブランチに追加したもの

- `store/product.json`：製品ごとの固有実行ファイル名とAppId。**正式Store Identityではない**。
- `store/make-logo-candidates.ps1`：候補PNG4サイズをWindowsで生成。既存の承認済みロゴは上書きしない。
- `store/build-msix.ps1`：テスト→PyInstaller x64→Windows SDK MakeAppxで、独立した `store-output` 内に**未署名のMSIX候補**を生成。正式Identity/Publisher/Logoが欠ければ停止。
- `tests/test_store_candidate_structure.py`：MSIXの停止条件・商品識別・ファイル生成の安全性をチェック。
- `.github/workflows/store-candidate-qa.yml`：Linux/Windows PythonのCIを起動する設定。ただしGitHubのランナー未割当問題があり、PASS未確認。

## コード担当のWindows PCでの手順

1. **この専用ブランチだけを別フォルダへclone/展開**。既存作品のmainや旧リリースを変更しない。
2. Nodeではなく**Python 3.11**とWindows 11 x64を利用。専用仮想環境で依存ライブラリとPyInstallerを導入する。
3. 一度全回帰を実行し、不合格項目を修正する。
4. 候補ロゴを確認し、商用のデザイン・権利が問題なければ正式承認。製品**固有**のPartner CenterのProduct Identity Name、Publisher、版番号を取得して環境変数へ設定する。
5. Windows SDKのMakeAppxを使ってMSIX候補を生成する。**Store向けの正本はMSIX**であり、配布用ZIPや単独EXEで代替しない。
6. WACK、インストール、Windowsでの起動、150%表示倍率、Tab/Enter、入力非上書き、保存先、再起動・更新・アンインストールを検証する。
7. `store-output/<実行日時>/MSIX_AUDIT.json`と生成物のSHA256、全テスト結果を提出。**成果物が存在するだけで合格とはしない**。
8. サポートURL、プライバシー情報、利用条件・ライブラリライセンス、商標、Windowsスクリーンショット、Storeの年齢等級・価格・対象市場を確定。確認まではStore公開しない。

```powershell
# 独立ブランチのルートで実行（利用者のWindows PC）
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py" -v

# 正式承認するまではロゴは候補にすぎない
powershell -NoProfile -ExecutionPolicy Bypass -File .\store\make-logo-candidates.ps1

# 以下はPartner Centerの正式値・商用ロゴ承認の後に限る
# STORE_IDENTITY_NAME / STORE_PUBLISHER / STORE_PUBLISHER_DISPLAY_NAME
# STORE_VERSION=1.0.0.0 / STORE_IDENTITY_CONFIRMED=YES / STORE_BRAND_APPROVED=YES
powershell -NoProfile -ExecutionPolicy Bypass -File .\store\build-msix.ps1 -PreflightOnly
powershell -NoProfile -ExecutionPolicy Bypass -File .\store\build-msix.ps1
```

## 販売前の製品固有の残課題

最優先: Playwright Chromiumの完全オフライン同梱・起動、JS画面・広告/別CDN・リダイレクト、実ページ長文スクロールとスクリーンショット一致。**現在ビルドは意図的にBLOCKED**。

MSIXは未署名候補の生成段階であり、Microsoft Storeが認証後に署名する提出用の運用と、ローカル署名済MSIXを実機テストする運用は区別する。未署名MSIXを一般ユーザーPCにそのままインストールできると主張しない。

**現在の判定：SOURCE IMPROVED / FULL TEST UNVERIFIED / WINDOWS GUI HOLD / SIGNED MSIX HOLD / STORE HOLD。**
