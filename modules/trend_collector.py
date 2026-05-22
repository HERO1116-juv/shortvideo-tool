"""
trend_collector.py
トレンド情報を収集してClaudeに渡せる形に整形するモジュール

2段ロケット構成:
  Layer 1: Googleトレンド (pytrends) - 関連急上昇ワード取得
  Layer 2: Claude Web検索 - プラットフォーム別の最新トレンド情報を取得
"""

import os
from datetime import datetime
from anthropic import Anthropic


# ============================================================
# Layer 1: Google トレンド
# ============================================================

def fetch_google_trends(keywords, geo: str = "JP", hours_back: int = 168):
    """
    Googleトレンドから関連ワードを取得する
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        return {
            "related_queries": {},
            "rising_terms": [],
            "error": "pytrends未インストール。requirements.txtを更新してください",
        }

    try:
        pytrends = TrendReq(hl="ja-JP", tz=540, timeout=(10, 25))
        kw_list = keywords[:5]
        pytrends.build_payload(kw_list, cat=0, timeframe="now 7-d", geo=geo)

        related = pytrends.related_queries()
        related_queries = {}
        rising_terms = []

        for kw in kw_list:
            if kw in related and related[kw]:
                top = related[kw].get("top")
                rising = related[kw].get("rising")
                related_queries[kw] = {
                    "top": top.head(5).to_dict("records") if top is not None else [],
                    "rising": rising.head(5).to_dict("records") if rising is not None else [],
                }
                if rising is not None:
                    rising_terms.extend(rising["query"].head(3).tolist())

        return {
            "related_queries": related_queries,
            "rising_terms": list(set(rising_terms))[:10],
            "error": None,
        }
    except Exception as e:
        return {
            "related_queries": {},
            "rising_terms": [],
            "error": f"Googleトレンド取得失敗: {str(e)[:200]}",
        }


# ============================================================
# Layer 2: Claude Web検索を使ったプラットフォーム別トレンド取得
# ============================================================

PLATFORM_QUERY_TEMPLATES = {
    "tiktok": [
        "{kw} TikTok 流行 2026",
        "{kw} TikTok バズる 最新",
    ],
    "reels": [
        "{kw} Instagram Reels 人気 2026",
        "{kw} リール バズる 最新",
    ],
    "x": [
        "{kw} X Twitter 話題 2026",
        "{kw} ツイッター バズ 最新",
    ],
}


def fetch_platform_trends_via_claude(
    keywords,
    platform_key: str,
    model: str = "claude-haiku-4-5-20251001",
) -> dict:
    """
    Claude Web検索ツールで指定プラットフォームの最新トレンドを取得し要約する
    """
    try:
        client = Anthropic()

        kw_text = "、".join(keywords[:3])
        queries = [t.format(kw=kw_text) for t in PLATFORM_QUERY_TEMPLATES.get(platform_key, [])]

        prompt = f"""次のキーワードについて、{platform_key.upper()}で今(2026年)流行している切り口・フォーマット・話題を調査してください。

【キーワード】{kw_text}

以下を必ず行ってください:
1. web_searchツールで関連する最新情報を検索する(必要に応じて2-3回)
2. {platform_key}での流行傾向を以下の観点でまとめる:
   - どんなフックや切り口が伸びているか
   - 流行りのフォーマットや構成パターン
   - 関連する話題のキーワードやハッシュタグ
   - 注意すべき廃れた表現

出力は箇条書きで200字程度に要約してください。前置きや説明は不要、要点のみ。
"""

        response = client.messages.create(
            model=model,
            max_tokens=1500,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
            messages=[{"role": "user", "content": prompt}],
        )

        summary_parts = []
        for block in response.content:
            if hasattr(block, "text") and block.text:
                summary_parts.append(block.text)

        summary = "\n".join(summary_parts).strip()

        return {
            "summary": summary,
            "platform": platform_key,
            "queries_used": queries,
            "error": None,
        }
    except Exception as e:
        return {
            "summary": "",
            "platform": platform_key,
            "queries_used": [],
            "error": f"Claude Web検索失敗: {str(e)[:200]}",
        }


# ============================================================
# 統合: 両レイヤーをまとめて取得し、Claudeに渡す形にフォーマット
# ============================================================

def collect_all_trends(
    keywords,
    platform_key: str,
    use_google_trends: bool = True,
    use_web_search: bool = True,
) -> dict:
    """全レイヤーのトレンド情報をまとめて取得する"""
    result = {
        "keywords": keywords,
        "platform": platform_key,
        "fetched_at": datetime.now().isoformat(),
        "google_trends": None,
        "web_search": None,
    }

    if use_google_trends:
        result["google_trends"] = fetch_google_trends(keywords)

    if use_web_search:
        result["web_search"] = fetch_platform_trends_via_claude(keywords, platform_key)

    return result


def format_trends_for_prompt(trends: dict) -> str:
    """トレンド情報をClaudeのextra_contextに注入できる形式に整形する"""
    if not trends:
        return ""

    parts = ["# 最新トレンド情報(これを台本に必ず反映してください)"]

    gt = trends.get("google_trends")
    if gt and not gt.get("error"):
        rising = gt.get("rising_terms", [])
        if rising:
            parts.append(f"\n## Googleトレンド急上昇関連ワード\n{', '.join(rising[:10])}")

    ws = trends.get("web_search")
    if ws and not ws.get("error") and ws.get("summary"):
        platform = ws.get("platform", "").upper()
        parts.append(f"\n## {platform}での最新傾向(Web調査結果)\n{ws['summary']}")

    if len(parts) == 1:
        return ""

    return "\n".join(parts)
