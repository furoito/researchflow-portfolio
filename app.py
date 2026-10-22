"""ResearchFlow — a compact media-research portfolio demo.

The interface adopts an original, studio-style typographic hierarchy inspired by artvibes.co.jp.
The existing extraction, classification and export workflow remains unchanged.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from researchflow.classify import TRAINING_SAMPLES, CATEGORIES
from researchflow.presentation import DEMO_INTRO, FEATURE, FOOTER, HERO, SITE_HEADER, WORKFLOW
from researchflow.process import process_sources, to_csv_bytes
from researchflow.webfetch import FetchError, parse_url_lines, gather_web_sources
from researchflow.workflow import REVIEW_STATES, apply_review

BASE = Path(__file__).resolve().parent
SAMPLE_DIR = BASE / "samples"
CSS_FILE = BASE / "assets" / "editorial.css"

st.set_page_config(
    page_title="ResearchFlow | 公開ページの情報収集・分類・CSV出力",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Keep original app and offline preview visually aligned through one CSS file.
st.markdown(f"<style>{CSS_FILE.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def get_gemini_key() -> str:
    """Only read credentials from server configuration, not from public inputs."""
    key = os.getenv("GEMINI_API_KEY", "")
    if key:
        return key
    try:
        return st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        # Streamlit raises its own secret-file exception when no secrets exist.
        return ""


@st.cache_data(show_spinner=False)
def load_samples() -> list[dict]:
    return json.loads((SAMPLE_DIR / "index.json").read_text(encoding="utf-8"))



def localize_fetch_errors(errors: list[str]) -> list[str]:
    """Turn network diagnostics into succinct Japanese for portfolio visitors."""
    names = {
        "URL format is invalid or too long": "URLの形式が不正か、長すぎます",
        "Only public HTTP/HTTPS URLs without credentials are supported": "公開HTTP/HTTPSのURLのみ対応します",
        "Host could not be resolved": "ホストの名前解決に失敗しました",
        "Host has no DNS records": "DNSの登録がありません",
        "Host resolves to a private or reserved network": "内部ネットワークへのアクセスはできません",
        "Connection failed, was blocked, or timed out": "アクセスが拒否されたか、接続がタイムアウトしました",
        "Website returned HTTP 403": "サイトからアクセスを拒否されました（403）",
        "Website returned HTTP 429": "サイトの取得上限に達しました（429）",
        "URL did not return an HTML page": "HTML以外のコンテンツです",
        "Access not permitted by robots.txt": "robots.txtで取得が禁止されています",
        "Cannot confirm robots.txt permission": "robots.txtの許可を確認できませんでした",
        "Response exceeds the size limit": "ページのサイズが上限を超えています",
        "duplicate input": "同じURLが重複しています",
        "duplicate redirect target": "転送先が重複しています",
    }
    result = []
    for err in errors:
        message = err
        for english, japanese in names.items():
            message = message.replace(english, japanese)
        result.append(message)
    return result

st.markdown(SITE_HEADER + HERO + FEATURE, unsafe_allow_html=True)

st.markdown(WORKFLOW, unsafe_allow_html=True)
st.markdown(DEMO_INTRO, unsafe_allow_html=True)

# The content below replaces the previous sample-only Streamlit workbench.
col1, col2 = st.columns([1.55, 1.0], gap="large")
sources: list[tuple[str, str, str, str]] = []
input_urls: list[str] = []
input_errors: list[str] = []

with col1:
    st.markdown("**情報を取り込む**")
    input_choice = st.radio(
        "入力方法",
        ["公開URLを取得", "HTMLファイルをアップロード", "サンプルで試す"],
        horizontal=True, index=2, key="input_choice", label_visibility="collapsed",
    )
    if input_choice == "公開URLを取得":
        urls_raw = st.text_area(
            "調査したいページのURL（1行に1件、最大8件）",
            height=145,
            placeholder="https://www.example.org/article/\nhttps://www.example.org/news/",
            help="クリック後にのみアクセスします。社内サイト、ログインが必要なページ、PDFや大きなページは対象外です。",
        )
        try:
            input_urls = parse_url_lines(urls_raw)
        except FetchError:
            st.warning("一度に処理できるURLは最大8件です。")
        st.caption("ページの公開情報のみを取得。robots.txtを確認し、プライベートIP・非標準ポートを遮断します。")
    elif input_choice == "HTMLファイルをアップロード":
        uploads = st.file_uploader(
            "HTMLファイル（UTF-8、最大8件・各1MB以下）",
            type=["html", "htm"], accept_multiple_files=True,
        )
        if uploads:
            for upload in uploads[:8]:
                try:
                    if upload.size > 1_000_000:
                        input_errors.append(f"{upload.name}: ファイルサイズが1MBを超えています。")
                        continue
                    content = upload.getvalue().decode("utf-8-sig")
                    sources.append((upload.name, content, "", "uploaded-html"))
                except UnicodeDecodeError:
                    input_errors.append(f"{upload.name}: UTF-8で保存されたHTMLを使用してください。")
            if len(uploads) > 8:
                input_errors.append("先頭8件のみ処理します。")
        st.caption("サイトにアクセスできない場合は、保存したHTMLを読み込めます。")
    else:
        samples = load_samples()
        choice_map = {sample["label"]: sample for sample in samples}
        labels = st.multiselect(
            "対象ページ", options=list(choice_map), default=list(choice_map),
            help="架空の店舗・施設・イベントのHTMLです。",
        )
        for label in labels:
            sample = choice_map[label]
            content = (SAMPLE_DIR / sample["file"]).read_text(encoding="utf-8")
            sources.append((sample["id"], content, sample["url"], "demo-html"))
        st.caption("サンプルは架空の情報です。実際のURL取得は「公開URLを取得」で試せます。")

with col2:
    st.markdown("**分類方式**")
    gemini_key = get_gemini_key()
    remote_enabled = bool(gemini_key and os.getenv("ENABLE_REMOTE_AI", "") == "1")
    modes = ["ローカル分類（無料・APIキー不要）"]
    if remote_enabled:
        modes.append("Gemini API（外部送信）")
    mode_choice = st.radio("分類方式", modes, label_visibility="collapsed", key="mode_choice")
    mode = "gemini" if mode_choice.startswith("Gemini") else "local"
    st.markdown(
        '<div class="rf-subtle-note">標準は小規模な学習例で作った分類モデルです。'
        'カテゴリは推定値のため、結果を確認して修正できます。</div>',
        unsafe_allow_html=True,
    )
    if remote_enabled:
        st.warning("Gemini利用時は外部へ本文を送信します。公開可能なデータに限定してください。")
    else:
        st.caption("ローカル分類では外部AIに本文を送信しません。概要は抽出型で、生成AIによる文章生成ではありません。")

count = len(input_urls) if input_choice == "公開URLを取得" else len(sources)
st.markdown(f'<div class="rf-meta-line">INPUT / RUN　 ·　処理対象：{count}件</div>', unsafe_allow_html=True)
run_col, note_col = st.columns([1, 2], gap="large", vertical_alignment="center")
with run_col:
    run = st.button("情報収集を実行", type="primary", use_container_width=True, disabled=count == 0)
with note_col:
    st.caption("ボタンを押した場合にのみ処理します。処理したデータはこのセッション内で確認できます。")

if run:
    with st.spinner("公開ページの取得と分類を実行しています…"):
        actual_sources = sources
        fetch_errors = list(input_errors)
        if input_choice == "公開URLを取得":
            actual_sources, extra_errors = gather_web_sources(input_urls)
            fetch_errors.extend(localize_fetch_errors(extra_errors))
        records, parse_errors = process_sources(
            actual_sources, mode=mode, api_key=gemini_key if mode == "gemini" else "",
        )
    st.session_state["research_records"] = records
    st.session_state["research_errors"] = fetch_errors + parse_errors
    st.session_state["last_mode"] = mode
    st.session_state["result_serial"] = st.session_state.get("result_serial", 0) + 1

records = st.session_state.get("research_records")
errors = st.session_state.get("research_errors", [])
if records is not None:
    st.markdown('<div class="rf-stream-heading">RESULT / RESEARCH SHEET</div>', unsafe_allow_html=True)
    st.markdown('<h2 class="rf-results-title">収集・分類結果</h2>', unsafe_allow_html=True)
    cols = st.columns(3)
    cols[0].metric("取得・解析成功", f"{len(records)} 件")
    cols[1].metric("カテゴリ数", f"{len({record.category for record in records})} 種")
    cols[2].metric("エラー・重複", f"{len(errors)} 件")

    if records:
        st.markdown("**結果を確認・修正**")
        st.caption("分類・概要・所在地などを編集できます。編集内容をCSVに反映します。公開前に必ず原文を照合してください。")
        data = pd.DataFrame([record.display_dict() for record in records])
        editable = st.data_editor(
            data, hide_index=True, use_container_width=True, num_rows="fixed",
            height=min(420, 47 * (len(data) + 1) + 25),
            disabled=["参照URL", "抽出方法", "分類方法", "入力元"],
            column_config={
                "カテゴリ": st.column_config.SelectboxColumn("カテゴリ", options=list(CATEGORIES), required=True),
                "確認状況": st.column_config.SelectboxColumn(
                    "確認状況", options=list(REVIEW_STATES) + ["要確認（デモ）"], required=True,
                ),
                "参照URL": st.column_config.TextColumn("参照URL", width="large"),
                "概要": st.column_config.TextColumn("概要", width="large"),
                "確認メモ": st.column_config.TextColumn("確認メモ", width="medium"),
            },
            key=f'review_table_{st.session_state.get("result_serial", 0)}',
        )
        try:
            reviewed = apply_review(records, editable.to_dict("records"))
            included = [row for row in reviewed if row.review_status != "対象外"]
            col_export, col_hint = st.columns([1, 2], gap="large", vertical_alignment="center")
            with col_export:
                st.download_button(
                    "修正結果をCSVで保存", data=to_csv_bytes(included),
                    file_name="researchflow_research.csv", mime="text/csv",
                    type="primary", key=f'download_csv_{st.session_state.get("result_serial", 0)}',
                )
            with col_hint:
                st.caption(f"出力予定：{len(included)}件。「対象外」にした行はCSVから除きます。")
        except ValueError as exc:
            st.error(f"入力内容を確認してください：{exc}")
        with st.expander("抽出根拠と分類方式を見る"):
            st.caption("概要は原文からの抽出、分類は推定です。分類スコアは正確性の保証ではありません。")
            for index, record in enumerate(records, 1):
                st.text(f"{index}. {record.title}")
                st.caption(f"取得元：{record.source_kind} ／ 分類方式：{record.categorization_method}")
                if record.url:
                    st.code(record.url, language=None)
                if record.ml_score is not None:
                    st.caption(f"ローカル分類スコア：{record.ml_score:.3f}（参考値）")
                st.caption("原文からの抜粋")
                st.code(record.evidence_excerpt or "文章を抽出できませんでした。", language=None)
    else:
        st.info("取得できたページはありません。URLやHTMLを確認してください。")
    if errors:
        with st.expander(f"取得できなかった項目・重複（{len(errors)}件）", expanded=True):
            for error in errors:
                st.warning(error)
    st.caption("入力URLは取得先とリダイレクトを検査します。サイト側のアクセス制限やJavaScript専用ページには対応していません。")
else:
    st.markdown(
        '<div class="rf-subtle-note">公開URL、HTMLファイル、またはサンプルを選び、'
        '「情報収集を実行」を押すと結果を表示します。</div>', unsafe_allow_html=True,
    )

tab_structure, tab_profile = st.tabs(["実装と検証", "対応できる業務"])

with tab_structure:
    st.markdown('<div class="rf-stream-heading">IMPLEMENTATION / TECHNICAL SCOPE</div>', unsafe_allow_html=True)
    st.markdown('<h2 class="rf-section-title">実装内容と検証</h2>', unsafe_allow_html=True)
    st.markdown(
        '<p class="rf-section-lead">公開URLの取得・情報抽出・カテゴリ分類・確認表を、それぞれ独立した処理として実装しています。</p>',
        unsafe_allow_html=True,
    )
    st.markdown("#### 実装済み")
    st.markdown("""
- 公開URLの一括取得（最大8件）、HTMLアップロード、サンプル利用
- BeautifulSoupによるタイトル・説明文・JSON-LD情報の抽出
- 日本語文字n-gram＋ロジスティック回帰によるローカル分類
- 重複除外、取得エラー処理、編集可能な確認表、日本語CSV書き出し
- Gemini API用の任意実装（鍵の設定と明示的な有効化が必要）
""")
    st.markdown("#### 対象外・制約")
    st.markdown("""
- 自動巡回、定期実行、Google Sheets・Notionへの自動書き込みは未実装
- 無料ローカル分類は小規模な学習データを使用。未知の対象に対する精度は未評価
- 抽出した情報の事実確認は自動化していないため、掲載前に原文との照合が必要
- このアプリはポートフォリオ用の試作であり、顧客への導入や業務削減の実績を示すものではありません
""")
    st.markdown("#### 使用技術")
    st.caption("Python / Streamlit / BeautifulSoup / scikit-learn / pandas / http.client / TLS")
    st.caption(
        f"ローカル分類器の学習テキスト：{sum(len(v) for v in TRAINING_SAMPLES.values())}件。"
        "再現性を優先し、ローカルで都度学習します。"
    )

with tab_profile:
    st.markdown('<div class="rf-stream-heading">PROFILE / CAPABILITIES</div>', unsafe_allow_html=True)
    st.markdown('<h2 class="rf-section-title">対応できる業務</h2>', unsafe_allow_html=True)
    st.write("既存ツールで対応できる範囲を確認し、必要な処理を絞って開発します。")
    a, b = st.columns(2, gap="large")
    with a:
        st.markdown("#### 対応できる内容")
        st.markdown("""
- 情報収集・データ整理・リサーチ業務の効率化
- Python・GAS・API連携による小規模ツール開発
- Notion・Zapier等を活用した業務フロー設計
- Webメディア運営・分析業務の改善
""")
    with b:
        st.markdown("#### 基本的な進め方")
        st.markdown("""
1. 目的と現状の作業を確認
2. 既存ツールと独自開発を比較
3. 必要最小限の試作品を構築
4. 実際の入力で挙動を検証
""")


st.markdown(FOOTER, unsafe_allow_html=True)
