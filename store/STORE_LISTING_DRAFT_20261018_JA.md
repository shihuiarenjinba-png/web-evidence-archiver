# Web Evidence Archiver — Microsoft Store商品ページ原稿（準備段階）

**状態：未登録/未確認の正式Identity・販売HOLD。Store未提出。**

## 商品名（候補）
Web Evidence Archiver

## 短い説明（原稿）
指定したWebページの表示・HTML・PDF・時刻・ハッシュ値を一式保存

## 想定購入者
自社サイトの公開内容や料金ページの変更履歴を残したい担当者

## 具体的な活用例
自社の価格案内ページを変更前に記録し、後日内容を照合する。

## 主な機能（実機確認後に掲載可否を判断）
- HTTPSページのスクリーンショット・HTML・PDF保存
- 取得URLやタイムスタンプをマニフェストで記録
- 成果物のSHA256を記録
- 許可ホスト制限と部分的な取得失敗の報告

## 制約・注意
取得物は保存記録であり、法的証拠としての採用を保証しません。外部素材や動的サイトには制約があります。Chromium同梱未検証のためMSIX作成はHOLD。

## 未入力・確認待ち
- 正式Store Product Identity / Package Family Name：Partner Center確認後に記録
- 製品名のStore可用性・商標・カテゴリ：未確定
- 価格：未確定。Document Version Auditの既存980円下書きは変更しない。
- 配布地域と言語：所有者判断待ち
- サポートURL、プライバシーポリシーURL：製品に適合する公開ページを確認後入力
- MSIX：パッケージ候補生成/静的チェック/Store Draftアップロード未完了
- スクリーンショット・ロゴ：製品別の承認/実画面撮影待ち
- 公開認証：実機・ライセンス・品質ゲートを終えるまで行わない

## 操作順序（Partner Center）
1. Apps and gamesで既存同名商品を検索。既存枠があれば再利用し、重複作成しない。
2. 新規候補のみ、MSIX or PWA appとして名前の可用性を確認し、予約する。
3. Product identityの正式値を `store/partner_center_registration.json` へ反映（機密情報は記録しない）。
4. 画像の権利と4サイズのロゴを承認して `store/assets/` に配置。
5. Windows上で `store/build-msix.ps1` でパッケージ候補を生成し、`store/verify-upload-inputs.py --msix <実際のファイル>` を実行。
6. Product release → Start submissionで下書き開始。Packagesに指定MSIXをアップロードし、保存。
7. **Submit for certificationは押さない。** 最終実機試験と所有者承認後に判断する。

公式：https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/create-app-submission
公式：https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/upload-app-packages

> この原稿は正確性と非誇張を優先した内部ドラフトであり、実機確認前に機能全体の保証をしない。
