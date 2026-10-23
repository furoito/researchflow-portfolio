"""Page-purpose classification for human-reviewed research sheets.

Explicit signals in the *main page title* take priority. A small local
character-n-gram model supplies only provisional suggestions when the page
doesn't identify its type directly. All labels remain reviewable. The score is
an uncalibrated model output, NOT a measured probability of correctness.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
import unicodedata
from urllib.parse import urlsplit

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

CATEGORIES = (
    "企業・団体",
    "商品・サービス",
    "採用・求人",
    "ニュース・記事",
    "イベント",
    "飲食・店舗",
    "観光・施設",
    "その他",
)

# Curated illustrative examples, NOT an empirical training corpus.
TRAINING_SAMPLES = {
    "企業・団体": [
        "企業概要 会社情報 本社所在地 代表取締役 会社沿革",
        "会社案内 会社概要 法人情報 事業内容 代表者",
        "私たちについて 株式会社の理念と会社の歴史",
        "団体概要 活動方針 組織紹介 役員一覧",
        "会社情報 法人名称 資本金 設立年月日",
        "企業情報 会社所在地 グループ企業のご案内",
        "運営会社について 組織と事業の概要",
        "会社概要 取締役 組織図 企業理念",
        "運営法人 概要 代表理事 設立と事業",
        "研究機関の組織概要 沿革と構成員",
        "About us company profile offices and leadership",
        "事業者概要 会社案内 主要事業 事業所",
        "コーポレート情報 企業について 会社概要",
        "当社の紹介 企業理念 会社沿革 拠点情報",
    ],
    "商品・サービス": [
        "業務管理クラウドサービスの機能紹介と料金プラン",
        "製品情報 新しいソフトウェアの仕様と価格",
        "Web制作サービスのご案内 ホームページ制作",
        "法人向けサービス一覧 ソリューションをご紹介",
        "プロダクト紹介 アプリの特長と機能",
        "サービス内容と導入プラン 申込方法",
        "製品紹介 機能比較 購入はこちら",
        "オンラインサービスの料金プランと導入事例",
        "クラウドサーバーの商品情報 利用料金",
        "業務効率化ツールの製品ページ 無料体験",
        "SaaS product features, pricing and trial",
        "商材の概要 サービスの利用方法と価格",
        "システム開発サービスのお見積もり",
        "ソフトウェア販売 プロダクトラインアップ",
    ],
    "採用・求人": [
        "採用情報 新卒採用 募集職種 応募方法",
        "キャリア採用 募集要項 エンジニア職",
        "中途採用 求人募集 福利厚生 勤務条件",
        "採用サイト 社員インタビューとエントリー",
        "採用募集 正社員 業務内容 勤務地",
        "アルバイト求人 時給 シフト 応募",
        "会社の採用ページ 選考フロー 採用担当",
        "新卒採用 募集職種 給与 エントリー",
        "求人情報 経験者募集 オープンポジション",
        "インターンシップ募集 応募資格",
        "Careers jobs recruit apply to join our team",
        "採用活動 仕事紹介 応募受付中",
        "スタッフ募集 給与 勤務形態",
        "採用説明会 募集要項 選考について",
    ],
    "ニュース・記事": [
        "最新ニュース 新製品発表のプレスリリース",
        "お知らせ サービス改定のご案内",
        "ニュースリリース 事業提携に関する発表",
        "技術ブログの解説記事 クラウドサービス",
        "専門コラム データ分析の手法を紹介",
        "取材レポート インタビュー記事を掲載",
        "報道発表 事業に関するニュース",
        "プレスリリース メディア向け発表資料",
        "お知らせ サイトリニューアルのお知らせ",
        "ニュース一覧 企業からの新着情報",
        "Blog post article industry research insights",
        "導入事例 お客様へのインタビュー記事",
        "記事一覧 最新の情報を発信",
        "企業ブログ 技術情報の解説",
    ],
    "イベント": [
        "週末マルシェ 開催日 出店案内 申込",
        "講演会とセミナーの開催情報 参加登録",
        "花火大会 開催日時 会場 チケット",
        "夏祭りの開催案内 出店者と来場者",
        "ワークショップ体験会 参加予約 受付",
        "展示会 開催期間 来場登録 会場",
        "ライブイベント開催日 出演者 チケット情報",
        "ライトアップイベント 開催期間と時間",
        "秋の企画展 観覧期間 展示イベント",
        "音楽フェスティバルの開催プログラム",
        "地域イベント 開催会場と参加申込",
        "Event schedule registration venue tickets",
        "ウェビナー開催 お申し込みフォーム",
        "トークイベント 講師と開催日時",
    ],
    "飲食・店舗": [
        "カフェの店舗案内 営業時間 メニュー",
        "レストラン ランチとディナーの予約",
        "ベーカリー 焼きたてパンの販売",
        "菓子専門店 スイーツとテイクアウト",
        "喫茶店のモーニングセット コーヒー",
        "ラーメン屋のメニューと定休日",
        "飲食店の予約 アクセスと店舗情報",
        "焼き菓子のパティスリー 商品案内",
        "カレー専門店のランチメニュー",
        "洋食食堂 料理 価格 店舗紹介",
        "店舗紹介 お店の営業時間とアクセス",
        "Restaurant cafe food menu opening hours",
        "パン屋の販売メニューとイートイン",
        "カフェレストランのフードとドリンク",
    ],
    "観光・施設": [
        "歴史資料館の展示と施設案内 見学",
        "展望台の景色と観光案内 アクセス",
        "美術館の常設展示 入館料 開館時間",
        "自然公園の観光名所と遊歩道",
        "博物館の施設案内 展示室と利用料金",
        "水族館の館内案内 生き物展示",
        "城跡公園の見どころと歴史散策",
        "庭園の見学情報 開園時間 入園料",
        "神社の参拝案内 境内の見どころ",
        "景勝地の観光情報 写真スポット",
        "温泉施設のご利用案内 営業時間",
        "Museum sightseeing spot visitor information",
        "史跡を巡る観光案内のページ",
        "観光施設 展望テラスと交通アクセス",
    ],
    "その他": [
        "プライバシーポリシー 個人情報の取扱い",
        "利用規約と免責事項 サイトのご利用",
        "お問い合わせ お問い合わせフォーム",
        "著作権に関する表記とサイトポリシー",
        "Cookieポリシーと設定について",
        "サイトマップ 全ページ一覧",
        "ウェブサイトのアクセシビリティ方針",
        "サイトの利用条件 法的免責事項",
        "特定商取引法に基づく表記",
        "ログインとパスワード再設定画面",
        "お問い合わせフォームの入力確認",
        "Terms of service privacy policy contact us",
        "セキュリティと個人情報保護方針",
        "システム利用規則および同意事項",
    ],
}

# Match a page's *purpose*, not every topic mentioned in site navigation or SEO.
TITLE_CUES = {
    "採用・求人": (r"採用", r"求人", r"募集要項", r"募集職種", r"インターン", r"recruit", r"careers?", r"job opportunities"),
    "ニュース・記事": (r"プレスリリース", r"ニュースリリース", r"ニュース", r"お知らせ", r"報道発表", r"記事", r"ブログ", r"コラム", r"導入事例", r"press release", r"news"),
    "イベント": (r"イベント", r"開催案内", r"開催のお知らせ", r"マルシェ", r"ワークショップ", r"フェス(?:ティバル)?", r"花火大会", r"夏祭り", r"秋祭り", r"ライトアップ", r"セミナー", r"展示会", r"企画展", r"講演会", r"体験会", r"event"),
    "企業・団体": (r"会社概要", r"企業概要", r"企業情報", r"会社情報", r"会社案内", r"法人概要", r"団体概要", r"組織概要", r"運営会社", r"運営者情報", r"事業者概要", r"会社紹介", r"about us", r"company profile", r"corporate profile"),
    "商品・サービス": (r"^サービス$", r"^製品$", r"サービス紹介", r"サービス一覧", r"サービス内容", r"製品紹介", r"製品一覧", r"製品情報", r"商品紹介", r"料金プラン", r"機能紹介", r"ホームページ制作", r"web制作", r"プロダクト", r"ソリューション", r"pricing", r"product"),
    "飲食・店舗": (r"カフェ", r"レストラン", r"ベーカリー", r"パン屋", r"焼き菓子", r"パティスリー", r"スイーツ", r"喫茶", r"飲食店", r"食堂", r"ラーメン", r"店舗案内", r"ランチメニュー"),
    "観光・施設": (r"観光", r"展望", r"資料館", r"美術館", r"博物館", r"水族館", r"庭園", r"史跡", r"神社", r"城跡", r"公園", r"施設案内", r"温泉", r"名所"),
    "その他": (r"プライバシーポリシー", r"利用規約", r"お問い合わせ", r"個人情報保護方針", r"特定商取引法", r"サイトマップ"),
}

# Prefer the actual page-title segment over a repeated brand/SEO suffix.
TITLE_SPLIT = re.compile(r"\s*[|｜│]\s*|\s+[-–—]\s+")


@dataclass(frozen=True)
class ClassificationResult:
    category: str
    method: str
    rationale: str
    ml_score: float | None = None
    needs_review: bool = False


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKC", (text or "")).casefold().strip()


def _title_rule(title: str) -> tuple[str, str] | None:
    primary = TITLE_SPLIT.split(_norm(title), maxsplit=1)[0]
    if not primary:
        return None
    matches = []
    for category, patterns in TITLE_CUES.items():
        found = next((match.group(0) for p in patterns if (match := re.search(p, primary, flags=re.I))), None)
        if found:
            matches.append((category, found))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        # Mixed-intent titles are ambiguous: prefer manual confirmation over
        # silently using an arbitrary rule-order tie-breaker.
        return None
    return None


@lru_cache(maxsize=1)
def get_model() -> Pipeline:
    texts, labels = [], []
    for label, examples in TRAINING_SAMPLES.items():
        for example in examples:
            texts.append(example)
            labels.append(label)
    model = Pipeline([
        ("features", TfidfVectorizer(analyzer="char", ngram_range=(2, 4), sublinear_tf=True)),
        ("classifier", LogisticRegression(max_iter=700, class_weight="balanced", random_state=42)),
    ])
    model.fit(texts, labels)
    return model


def classify_local(text: str) -> tuple[str, float]:
    """Raw, uncalibrated small-model prediction for compatibility/tests."""
    text = _norm(text)
    if not text:
        return "その他", 0.0
    model = get_model()
    probs = model.predict_proba([text[:5_000]])[0]
    i = int(probs.argmax())
    return str(model.classes_[i]), round(float(probs[i]), 3)


def classify_page(*, title: str = "", description: str = "", heading: str = "", body: str = "", url: str = "") -> ClassificationResult:
    """Classify page intent, with traceable evidence and an uncertainty gate."""
    for label, source in (("タイトル", title), ("見出し", heading)):
        strong = _title_rule(source)
        if strong:
            category, matched = strong
            return ClassificationResult(category, "明示語句による分類", f"{label}の「{matched}」")
    # A concrete URL path is useful when the headline itself is generic.
    # Domain names alone never determine the page category.
    try:
        path = urlsplit(url).path.casefold()
    except ValueError:
        path = ""
    hints = (
        ("採用・求人", r"/(?:recruit|careers?|jobs?)(?:/|$)"),
        ("ニュース・記事", r"/(?:news|press|blog|article)(?:/|$)"),
        ("企業・団体", r"/(?:company|corporate|about|organization)(?:/|$)"),
        ("商品・サービス", r"/(?:products?|services?|solutions?)(?:/|$)"),
        ("イベント", r"/(?:events?|seminars?)(?:/|$)"),
    )
    for category, regex in hints:
        if re.search(regex, path):
            return ClassificationResult(category, "URL構造による分類", f"URLのパス「{path[:65]}」", needs_review=True)
    combined = " ".join(part for part in (title, description, heading, body[:1500]) if part)
    if not combined.strip():
        return ClassificationResult("その他", "分類保留", "判定材料がないため要確認", needs_review=True)
    model = get_model()
    probs = model.predict_proba([_norm(combined)[:5000]])[0]
    ranked = sorted(range(len(probs)), key=lambda i: probs[i], reverse=True)
    first, second = float(probs[ranked[0]]), float(probs[ranked[1]])
    category = str(model.classes_[ranked[0]])
    if first < 0.30 or first - second < 0.08:
        return ClassificationResult("その他", "分類保留", "カテゴリを絞り込めないため要確認", round(first, 3), True)
    return ClassificationResult(category, "ローカル軽量ML（暫定）", "本文と概要からの推定（実運用精度は未評価）", round(first, 3), True)
