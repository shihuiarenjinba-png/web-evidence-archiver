# Web Evidence Archiver — Microsoft Store提出準備・商品情報案
**開発中 / 未承認 / リリースHOLD。** 改良ブランチ `ui/simple-product-flow-20261019` の**現時点の機能だけ**を記載。正規Package Identity・Store ID・価格・年齢区分は、Partner Centerの実記録で確定し、架空データを記載しない。

## 提案する商品説明（日本語）
指定したHTTPSページをHTML・スクリーンショット・PDF・取得日時・ハッシュ値とともにパソコンへ記録します。

主な特徴：
- 複数のHTTPS URLをGUIで直接指定
- 通信前に許可サイトと保存先を確認
- URLごとの保存成功・失敗と取得ファイルを表示

制限・注意：
Webサイトの完全な再現、閲覧制限の回避、証拠能力の保証はしません。CDN等の外部素材が保存されない場合があります。

### 候補価格
2,980円（仮説・未承認）。**実際の購入データによる実証ではない。** 商品登録前に商業性・QA・顧客価値を再判定する。無料候補でも品質・権利審査は必須。

## 画面キャプチャ — 本物のWindows起動画面からのみ取得
- 対象: Windows Desktopのみ。JPEG画像をPNGへ変換した代替物、モック、別製品のUIを提出しない。
- Microsoft公式: 最低1枚、4枚以上推奨、最大10枚。PNG、**1366×768以上**、各50MB以下。
- 販売用推奨: **5枚**。次の手順を実機で実行して撮影し、初期ファイル名は `store-assets/screenshots/ja-JP/01.png` ～ `05.png` とする（保存先のディレクトリはWindows担当が新規作成）。
1. `01.png` — 複数URLの入力画面
2. `02.png` — 通信なしでの許可ホスト確認
3. `03.png` — 実通信前の実行確認
4. `04.png` — URL別の記録結果
5. `05.png` — HTML・PNG・PDF・manifestの保存フォルダー
- 英語表示に実際に対応し、QA済みの場合のみ en-US の5枚を同様に撮影。未完成の英語UIを売り物にしない。
- 個人情報を含まない**合成テストデータ**のみ表示。起動EXEのSHA、リポジトリコミットSHA、撮影解像度、実機OS、表示倍率を別ログに記録。

## MSIX
1. Partner Centerで、この製品固有のアプリ名予約と実際のPackage Identity Name・Publisher文字列を確認。**既存8製品のIdentityは流用しない**。
2. 対象ブランチのクリーンな状態でPythonソーステストを実行し、EXE候補を作成。実行ファイル名は `WebEvidenceArchiver.exe`。
3. 実際に権利を持つ `StoreLogo.png` (50×50)、`Square44x44Logo.png` (44×44)、`Square150x150Logo.png` (150×150) を `store-assets/assets/` に用意する。ダミー画像禁止。
4. Windows SDK MakeAppxを用いて `store/build-msix.ps1` に**本物の**Identity・Publisher・EXE・画像のパスを渡す。スクリプトはpack/unpack/SHA一致を検証し、正式なIdentityがなければ停止。
5. 生成されたMSIXは**提出候補であり販売承認ではない**。Store提出用MSIXはMicrosoftが公開時に再署名するため、CA証明書の購入は必須でない。通常のサイドロード/オフライン実機インストール時は適切な署名・信頼済み証明書が必要。開発環境での署名とStore提出を混同しない。
6. クリーンWindows 10/11でインストール/起動/保存/再起動/更新/削除/秘密データ流出なし/容量不足・権限拒否を実際に検査する。最新SDKでWACKが利用できる場合は補助実施（Microsoft最新文書ではdeprecation扱い）。
7. 商用利用権・OSSライセンス/NOTICE/SBOM・Chromium再配布の権利とライセンス同梱義務（該当時）をレビュー。製品サイトのプライバシーポリシーとサポートURLは実在・閲覧可能性を確認する。
8. 商品説明、Screenshots、ロゴ、カテゴリ、年齢区分、価格と提供地域をPartner Centerへ入力してドラフトを完成させる。**承認なしでSubmit/Publishはしない**。

## 禁止事項・提出ゲート
- 既存main、引継ぎ済み4製品、Store ID登録済み8製品へ直接マージ・上書きしない。
- MSIX署名/インストール・実ページ記録・QA未実施をPASS扱いしない。
- Windows CI 0ステップ実行失敗は「未実施」。Windowsテストログと撮影した正真正銘のスクリーンショットが必要。
- 本文で未対応機能を購入可能な機能として宣伝しない。
- 公開・課金の最終承認にはWindows実機ログ、第三者権利、Storeドラフト確認、Microsoft認定結果が必要。

公式: https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/create-app-submission
公式画像規定: https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/screenshots-and-images
公式署名: https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/app-package-requirements
