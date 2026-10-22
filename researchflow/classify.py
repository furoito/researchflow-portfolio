"""Tiny local supervised ML model: free, offline, no hidden LLM API.

Demonstration only: training examples are curated illustrative text and are NOT
an externally validated benchmark. The returned score is not calibrated accuracy.
"""

from __future__ import annotations

from functools import lru_cache

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

CATEGORIES = ("グルメ", "観光", "イベント", "その他")
TRAINING_SAMPLES = {
    "グルメ": [
        "カフェで季節のスイーツとコーヒーが楽しめる飲食店 営業時間 メニュー",
        "焼き菓子専門店の新商品 クッキー ケーキ テイクアウト",
        "レストランのランチメニュー 洋食 ディナー 予約",
        "和菓子屋の限定商品 あんこ 抹茶 お菓子販売",
        "パン屋で焼き立てのパンを販売 ベーカリー 店舗案内",
        "喫茶店のモーニングセット トースト コーヒー",
        "ラーメン屋のメニュー 醤油ラーメン 定休日 店舗情報",
        "名物グルメを提供する食堂のメニューと営業案内",
        "ジェラート専門店のアイスクリーム フレーバー案内",
        "パティスリーで販売するタルト マカロン 洋菓子",
        "飲食店で提供する定食の値段とアクセス",
        "新しいスイーツ店のオープン テイクアウトメニュー",
        "カレー専門レストランでスパイス料理を提供",
        "ベーカリーカフェの朝食メニューとドリンク",
    ],
    "観光": [
        "展望台から港の夜景を眺める 観光スポットとアクセス",
        "歴史資料館の展示と見学コース 施設案内",
        "自然公園の散策ルートや景色 観光名所",
        "神社と古い町並みをめぐる観光モデルコース",
        "美術館の常設展示と入館方法 観光案内",
        "海辺の展望テラスとフォトスポットを紹介",
        "城跡公園を歩く歴史散策 見どころ案内",
        "水族館の生き物展示と施設情報",
        "渓谷の遊歩道や観光案内とアクセス情報",
        "地域の史跡と文化遺産を巡る観光案内",
        "温泉街の街歩きスポット 観光地の紹介",
        "庭園と日本建築の見どころ 施設見学",
        "旅行者向けに季節の風景や景勝地を紹介",
        "公園内の散歩道と展望スポットガイド",
    ],
    "イベント": [
        "週末マルシェ開催 出店者募集 開催日時 会場案内",
        "秋のライトアップイベント 開催期間 チケット情報",
        "夏祭りと花火大会の開催日 会場と参加方法",
        "ワークショップ開催のお知らせ 参加予約 受付",
        "地域フェスティバル 開催日時とプログラム",
        "期間限定の企画展 開催期間 イベント情報",
        "親子向け体験教室 参加費と申込締切",
        "音楽ライブ出演者と開催日時 チケット販売",
        "屋外フードフェス開催 出店情報 イベント",
        "週末限定市民マルシェ イベント開催告知",
        "地域の伝統祭事 当日の会場とタイムテーブル",
        "トークイベント開催 参加受付 会場の案内",
        "商店街スタンプラリー開催 キャンペーン期間",
        "イルミネーション点灯式 開催日とイベント概要",
    ],
    "その他": [
        "会社概要と法人情報 代表者 採用情報",
        "お問い合わせフォーム 個人情報保護方針",
        "製品の取扱説明書とサポートページ",
        "採用募集 エンジニアの求人情報と福利厚生",
        "プライバシーポリシーと利用規約について",
        "システムメンテナンスのお知らせ 障害情報",
        "物流センターの事業紹介 配送サービス",
        "学校の入学案内と授業プログラム",
        "ソフトウェアの更新履歴とダウンロード",
        "研究機関のニュースリリースと報告資料",
        "不動産会社の賃貸物件と契約について",
        "アプリの使い方とヘルプセンター",
        "証券市場の経済レポートと決算資料",
        "自動車保険の契約条件とお申し込み",
    ],
}


@lru_cache(maxsize=1)
def get_model() -> Pipeline:
    texts, labels = [], []
    for label, examples in TRAINING_SAMPLES.items():
        for example in examples:
            texts.append(example)
            labels.append(label)
    model = Pipeline([
        ("features", TfidfVectorizer(analyzer="char", ngram_range=(2, 4), sublinear_tf=True)),
        ("classifier", LogisticRegression(max_iter=600, class_weight="balanced", random_state=42)),
    ])
    model.fit(texts, labels)
    return model


def classify_local(text: str) -> tuple[str, float]:
    text = (text or "").strip()
    if not text:
        return "その他", 0.0
    model = get_model()
    probabilities = model.predict_proba([text[:5_000]])[0]
    best_index = int(probabilities.argmax())
    return str(model.classes_[best_index]), round(float(probabilities[best_index]), 3)
