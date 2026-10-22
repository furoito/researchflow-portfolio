# v0.7 公開前検証結果

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
