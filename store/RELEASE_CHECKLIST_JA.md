# Web Evidence Archiver — 有料MSIX販売前の受入ゲート

**対象ブランチ：** `feature/store-paid-msix-quality-20261017` （mainと旧ブランチには変更しない）
**現在：** 未販売・正式Partner Identity未確認・実Windows MSIX未生成。**合格証明ではなく検査項目。**

## 本商品の提供価値と限界

閲覧権限のあるHTTPS公開ページの画面/HTML/PDF/SHA256を記録。サイトへのネット通信が必要。

## 改良状況

- `store/product.json`：この製品専用のEXE名/AppId/表示名。別製品のPackage Family Nameを再利用しない。
- `store/make-logo-candidates.ps1`：Windows端末で4サイズの仮ロゴ作成。**既存PNGは原則上書きせず、正式承認が必要**。
- `store/build-msix.ps1`：全Pythonテスト→PyInstaller→Windows SDK MakeAppxで**署名なしMSIX候補**を新フォルダに生成。エラーで停止し、ZIP/EXEをStore提出物と呼ばない。
- 署名なしMSIXは通常のユーザーPCでそのまま正常インストールできるとは限らない。Microsoft Store配布用はStore署名を利用する。開発実機テストでは正しく署名した検証用パッケージか適切なStoreテスト配布を使用する。

## Windowsコード担当：手順

1. v0.*など他作品と完全に独立した新しいWindows作業フォルダに、このブランチをclone/ZIP展開。
2. Windows 11 x64、Python 3.11/3.12、Windows 10/11 SDK (MakeAppx)、Node不要、PyInstallerの検証環境を用意。
3. 以下を順番に実施：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install pyinstaller==6.16.0
python -m unittest discover -s tests -p 'test*.py' -v
powershell -NoProfile -ExecutionPolicy Bypass -File .\store\make-logo-candidates.ps1
```

4. 候補ロゴを所有者が正式承認した後、Partner Centerのこの製品の `Identity.Name`・`Publisher`・正式な表示名を取得。環境変数で `STORE_IDENTITY_NAME`、`STORE_PUBLISHER`、`STORE_PUBLISHER_DISPLAY_NAME`、`STORE_VERSION`（例1.0.0.0）を指定。**実際に照合した後**に限り `STORE_IDENTITY_CONFIRMED=YES`、`STORE_BRAND_APPROVED=YES` を指定。
5. `powershell -NoProfile -ExecutionPolicy Bypass -File .\store\build-msix.ps1 -PreflightOnly` でゲート検査を通し、成功後に `powershell -NoProfile -ExecutionPolicy Bypass -File .\store\build-msix.ps1` で独立フォルダへ署名なしMSIX候補を生成。
6. `store-output/<日時>-<識別子>/MSIX_AUDIT.json`、`AppxManifest.xml`、MSIX中の.exeと画像、SHA256と正式Identity一致を確認。
7. WACK、Windows 11実機でインストール→起動→入力・出力→再起動・保存→更新→アンインストールを記録。100% / 125% / 150% DPI、キーボードとマウス、画面狭幅、例外メッセージも確認。

**固有の受入ポイント：** Chromium/Playwrightのオフライン同梱とアプリ相対参照が未確認のため、MSIXビルドは強制BLOCKED。許可ホスト/リダイレクト/SSR F・ZIP、JSサイト、依存CDN、保持権利に注意。

## 有料の判断基準

買い切りで、購入者が無料ソフトより**確実に時間を節約できる/監査の再現性が高い**ことを匿名化フィクスチャで証明する。
少なくとも正常5例、異常10例、境界10例、既存データ非上書き、セキュリティの厳しいケース5例、実PCでのユーザー操作記録が必要。
使用コンポーネントのライセンス・有料配布権限、プライバシー/サポートURL、Store掲載スクリーンショット(少なくとも1枚、4枚程度推奨)を別途確認。<Link>等のHTMLをそのまま商品説明に貼らない。

**Gate:** UNIT=未確認 / GUI=未確認 / MSIX=未生成 / WACK=未実行 / COMMERCIAL=HOLD。
