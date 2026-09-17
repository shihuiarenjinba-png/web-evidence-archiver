# Release Gate — Web Change Evidence Monitor

## Code / Safety — repositoryで完了可能

- [x] HTTPSのみを対象にする
- [x] allow_hosts外への通信をroute guardで拒否する
- [x] HTML / PNG / PDF / visible text / normalized textを保存する
- [x] 各成果物のSHA256を記録する
- [x] 可視テキスト変更 / render変更 / HTMLのみ変更を分離する
- [x] ignore_text_regexesで比較ノイズを除外できる
- [x] 原可視テキストは加工せず保存する
- [x] 前回との差分をJSON / Markdown / unified diffとして保存する
- [x] 法的証拠能力を保証しない旨を明記する
- [x] 回帰テストを配置する
- [x] Windows CI / Playwright Chromium / PyInstaller build定義を配置する

## Desktop-only validation

- [ ] Windows 10/11で配布物からChromiumを起動できることを確認
- [ ] EXEから実サイトを取得しHTML/PNG/PDFが生成されることを確認
- [ ] CDNを含む代表サイトでallow_hosts設定UXを確認
- [ ] 日本語サイト / 長いページ / JavaScript描画ページで確認
- [ ] SmartScreen / Defender / AV確認
- [ ] Playwright/Chromiumライセンス表記を配布物へ含める
- [ ] 配布ZIP SHA256確認

## Release rule

公開ページの保存権限・利用規約は利用者側で確認する。出力は技術的な取得・変更記録であり、法的証拠能力や真正性を保証しない。
