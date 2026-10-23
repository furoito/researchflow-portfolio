# ResearchFlow v0.9 検証記録

## v0.9 公開項目の整理
- 実務上の取得漏れが残った「所在地」「開催日」を、抽出結果・編集表・CSV・公開説明・静的プレビューから削除。タイトル・概要・用途分類・根拠・確認修正・URL・CSVを維持。
- 削除された列がCSVへ混入しない回帰テストを追加。下記の過去ログは当時の状態を示す履歴です。

---

# ResearchFlow v0.8 検証記録

## 2026-10-24 公開版実測（v0.8）
- [公開環境の企業ページ5件テスト](https://github.com/furoito/researchflow-portfolio/actions/runs/40001752965)：5件すべて取得・CSV出力に成功（エラー0件）。
- **ページ用途の分類結果：企業・団体4件、商品・サービス1件。** 5件とも期待用途に一致し、分類根拠をCSVへ記録。
- [GitHub Actionsの回帰テスト](https://github.com/furoito/researchflow-portfolio/actions/runs/40001598736)：76件合格、example.comの実URL取得・CSV保存も再確認。
- 画面更新時に古いPythonモジュールが残る問題を検知し、起動時の互換性確認と必要に応じた再読込を追加した。
- これは指定の5ページでの動作実測であり、一般のWebページでの分類精度を統計的に証明するものではない。

## 新分類の検証
- ページ用途の8分類へ変更。明示語句、URL構造、暫定ローカル機械学習を組み合わせ、曖昧な結果には確認メモを残す。
- 現地のサンプル・過去の実在企業サイト5件のタイトル・概要を使った回帰テストを追加。**実際の公開アプリで5件を再検証済み。**
- 開発環境での新機能テストは67件すべて合格、静的HTML版はPC/モバイル/320pxで操作検証済み。GitHub Actionsには既存の大容量HTML追加テストがあるため、公開リポジトリ上の合計件数は再実行で確認する。
- [分類QAの詳細](CLASSIFICATION_QA.md)

---

## 以下はv0.7時点の検証履歴


## 2026-10-23 ページサイズ上限修正
- HTTP HTML取得上限を450KBから4MBへ拡張し、上限を超えるページは先頭部分を解析する方式へ変更。不要な<script>・<style>・SVGを除去して、解析対象を最大30万文字へ制限。
- 部分取得時は画面に注意文を表示し、CSVに「公開URL（部分取得）」と確認メモを残す。
- robots.txtは従来どおり厳格な100KB上限を維持し、DNS/SSRF/リダイレクト対策は維持する。
- 増量・部分取得・巨大スクリプト・JSON-LD・非HTML拒否・robots・文字コードを回帰テストへ追加。

## 2026-10-23 公開環境での検証（現行）

- 公開URL： https://researchflow-portfolio-msr4p7iwappfodx5am4eshb.streamlit.app/
- GitHub Actions： https://github.com/furoito/researchflow-portfolio/actions/runs/39825897356
- Chromium経由の実ブラウザ操作で `https://example.com/` を入力、実行して取得・解析成功1件、エラー0件を確認。
- **CSVダウンロードにも成功**。実出力で `ページタイトル=Example Domain`、`参照URL=https://example.com/`、`入力元=公開URL`、`抽出方法=BeautifulSoup（HTML）`、`分類方法=ローカル軽量ML（無料）` を確認。
- サンプルHTML 6件の抽出・分類、CSV出力も別のブラウザテストで合格： https://github.com/furoito/researchflow-portfolio/actions/runs/39822090241
- 公開URLの到達性、サンプル処理、実URL処理、CSV出力まで確認済み。ただし**外部サイトごとのrobots.txt/403やページ構造、分類精度**は保証しない。Gemini実通信も未検証。
- 当初「実URL取得が失敗」となった理由は、Streamlitの`st.data_editor`内の値が通常のDOM本文に現れず、ブラウザテストがタイトル文字列を見つけられなかったこと。**CSV実データを検証する方法に変更し解消**。

---

## 以下はデプロイ前に作成した検証記録（当時の状態）


## Verified in this environment

- 46 pytest tests passed (including 3 deployment-contract checks) (HTML extraction, lightweight classification, validation, mock Gemini API, safe CSV, URL validation, DNS/private network blocking, redirects, robots, edit workflow).
- `scripts/build_preview.py`: builds an HTML browser preview from the actual synthetic HTML fixtures.
- `scripts/visual_qa.py`: Chromium desktop 1440 and mobile 390: anchors, filter, empty results, sample CSV, no horizontal overflow or runtime errors.
- `scripts/interactive_qa.py`: Chromium desktop 1440, mobile 390, narrow 320: upload two distinct HTML files, parse to two rows, edit confirmation status, exclude a row from CSV, save CSV, reset, no page errors or horizontal overflow. The standalone preview uses browser-only simplified keyword classification.
- Source code compiled using `python -m py_compile`.
- Public-source SSRF boundaries tested through mocked DNS and HTTP responses. Cross-site redirect checks and disallowed robots directives tested.

## Not verified

- No Streamlit package in the execution environment; Streamlit app cannot be launched for final visual/runtime QA here.
- DNS resolution to the public internet failed in this environment. Live public URL GET and any real-world site access are unverified, and site-specific blocks/robots rules may prevent fetching.
- Gemini API live key/requests were not supplied. Gemini remains optional.
- Local ML accuracy on previously unseen production data has not been measured.
- No externally hosted site or GitHub repository was changed.

## Decision gate

Before external publication: install dependencies on host, run Streamlit, import 1-2 public pages with permissive robots policies, inspect extracted content and edited CSV, and confirm no secrets in GitHub. Do not claim a live site is proven until those checks pass.

## v0.7追加確認

- 46件のpytestに合格。
- 初回訪問でサンプル6件を選択でき、ボタンが使用可能な初期状態へ変更した。
- テキスト表示時のMarkdown解釈を避け、実装済み見出しの重複を修正。
- 静的HTML版の検索をChromiumで再度確認（例：「資料館」で1件）。
- スクリプト`visual_qa.py`は今回の実行環境でタイムアウトした。以前の検証結果の再現性は保証しない。
- Streamlitのpipインストールを試みたが、この環境のパッケージ取得先では提供されていないため起動不可。
- GitHub接続は確認済み。専用の公開リポジトリはまだ存在せず、既存の別プロジェクトは変更していない。
