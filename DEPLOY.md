# ResearchFlow: GitHub / Streamlit 公開手順

## 前提

- リポジトリ公開名（仮）：`researchflow-portfolio`
- GitHubアカウント：`furoito`（接続アカウントで確認済み）
- 公開前に本人がプロフィール文面やソースコードに非公開情報がないことを確認
- `.streamlit/secrets.toml`、`.env`、APIキーをGitHubへ入れない

## 1. GitHubのコードを確認（リポジトリ作成済み）

公開リポジトリ： https://github.com/furoito/researchflow-portfolio

GitHubの `main` に `app.py`、`requirements.txt`、`.streamlit/config.toml`、`researchflow/`、`samples/` とスタイルが揃っていることを確認します。個人情報やAPIキーが含まれていないことも確認してください。

## 2. Streamlitの公開前確認

公開アプリに認証は付けていません。第三者が公開URLを使用できることを理解した上で公開してください。公開URL取得ではrobots.txtとネットワーク制約を検査しますが、第三者サイトの利用条件やホスティング側の制約にも従ってください。Gemini APIは既定で無効です。

## 3. Streamlit Community Cloudで公開（本人操作）

1. https://share.streamlit.io へアクセスし、GitHubでサインイン
2. `Create app` → 「既存のリポジトリからデプロイ」を選択
3. Repository `furoito/researchflow-portfolio`、Branch `main`、Main file path `app.py`
4. Advanced settings の Python バージョンは `3.12` を推奨
5. `Secrets` は空欄のまま。標準のローカル分類で無料動作する
6. `Deploy` をクリック。作成された `.streamlit.app` URLを共有する

GitHubとStreamlitの認証や公開設定は本人が行う。

## 4. 公開後の検証

- [ ] デモの6件を実際に処理できる
- [ ] HTMLファイルを読み込んで分類できる
- [ ] 公開URL（例 `https://example.com/`）を取得できる。サイトのrobots.txtや制限次第では取得不能を正常なエラーとして扱う
- [ ] 分類・概要・確認状況を変更し、CSVに修正が反映される
- [ ] PCとスマートフォンで崩れず操作できる
- [ ] APIキー、個人情報、他プロジェクトの内部情報が公開されていない

公開URLの取得やStreamlit本体のレンダリングは、まだこの環境では実証できていない。GitHubにファイルを置いたことだけでデプロイ成功とは扱わない。

## 実行確認

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python -m streamlit run app.py
```
