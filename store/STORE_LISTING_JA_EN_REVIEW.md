# Microsoft Store掲載文｜Web Evidence Archiver｜レビュー準備稿
対象ブランチ: `ui/simple-product-flow-20261019`
状態: **文案完成 / 公開未承認 / Store ID・価格の実入力未済**
価格の仮設定: **¥2,980（仮）**。正式価格・対応市場は権限のある販売者が承認し、Partner Centerで指定する。

## ja-JP
**製品名（候補）:** Web Evidence Archiver

**短い説明:**
許可されたHTTPSページをHTML・画像・PDFで記録し、取得日時とファイルのハッシュを保存します。

**詳細説明（そのまま編集欄へ転記可能）:**
仕事で参照した公開Webページを、その時点の表示と関連ファイルで記録するためのWindowsツールです。複数URLを入力し、アクセス先を確認したうえで、HTML・PNG・PDFおよび記録情報を保存します。URLごとに失敗状況も表示します。

・HTTPS URLを複数指定しアクセス先を確認
・HTML・PNG・PDFと取得情報をローカル保存
・失敗・未取得ページをURL単位で確認

**対応範囲と重要な注意事項:**
ネットワークへ実際に接続します。ログインやアクセス制限を回避しません。外部素材、遅延表示、ページ全体の完全再現や法的な証拠能力は保証しません。

**What's new:** 初回提出時は空欄。製品更新の場合のみ新旧の違いを事実確認して記載。

## en-US
**Suggested title:** Web Evidence Archiver

**Short description:**
Capture allowed HTTPS pages as HTML, screenshots and PDF with timestamps and file hashes.

**Full description:**
Record selected public HTTPS pages for reference. Enter multiple URLs, review allowed hosts before network access, then capture HTML, PNG and PDF alongside timestamps and hashes. Review the outcome of each URL.

• Review and approve allowed HTTPS destinations
• Capture HTML, PNG, PDF and file hashes
• See captured, failed and unattempted URLs separately

**Important limitations:**
The app makes real network requests. It does not bypass site restrictions, guarantee complete capture of all assets, or guarantee legal admissibility of the recorded files.

**What's new:** Leave blank for the initial submission.

## Partner Center 編集チェック
- 描写の対象は各製品の現行ブランチで**実装が確認できる機能のみ**。未知の機能や完全安全保証を足さない。
- 正式名の重複確認、年齢区分質問票、価格、カテゴリ、地域、検索キーワード、機能欄は提出画面で設定する。価格は購入実績の裏付けがない仮説。
- スクリーンショットは実機撮影5枚。本文に外部URL、HTML、未確認の商標や第三者との提携表現を入れない。
- 最終チェック: ユーザー向けの日本語/英語を実画面と照合。英語UIが未合格なら対応言語を無理に追加しない。
- ソースWindows QA、MSIX、Store Identity、プライバシー・サポート情報、ライセンス承認が揃うまで掲載しない。

公式: https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/add-and-edit-store-listing-info
