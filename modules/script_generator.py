"""
script_generator.py
キーワード + ターゲット層 + プラットフォーム から
JSON形式の動画台本を生成するモジュール
"""

import os
import json
import yaml
from pathlib import Path
from anthropic import Anthropic

CONFIG_DIR = Path(__file__).parent.parent / "config"


def load_yaml(filename: str) -> dict:
    with open(CONFIG_DIR / filename, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


PERSONAS = load_yaml("personas.yaml")
PLATFORMS = load_yaml("platforms.yaml")


def build_system_prompt(persona_key: str, platform_key: str) -> str:
    """ターゲット層 × プラットフォームからシステムプロンプトを組み立てる"""
    persona = PERSONAS[persona_key]
    platform = PLATFORMS[platform_key]

    characteristics_text = "\n".join(f"  - {c}" for c in platform["characteristics"])
    ng_words = persona.get("ng_words", [])
    ng_text = f"\n【使用禁止ワード】{', '.join(ng_words)}" if ng_words else ""

    return f"""あなたはショート動画のプロ構成作家です。
視聴維持率と保存率を最大化する台本を作ります。

【ターゲット】{persona['label']}({persona['age']}歳)
  関心事: {', '.join(persona['interests'])}
  悩み: {', '.join(persona['pain_points'])}
  トーン: {persona['tone']}
  視聴時間帯: {persona['watch_time']}

【プラットフォーム】{platform['label']}
  推奨尺: {platform['recommended_duration']}秒(最長{platform['max_duration']}秒)
  最初の{platform['hook_window_sec']}秒で必ず視聴者を掴む
  字幕スタイル: {platform['caption_style']}
  CTAスタイル: {platform['cta_style']}
  プラットフォーム特性:
{characteristics_text}
{ng_text}

【絶対ルール】
1. 出力は必ず以下のJSON形式のみ。前後の説明文・コードブロック記号は一切出力しない
2. 各sceneのtextは画面に表示される字幕でもあるので、簡潔に
3. visualには「何を映すか」を具体的に指示する
4. hookは指定された秒数以内で読み切れる長さに
5. ターゲットのトーンと禁止ワードを厳守する

【出力JSON形式】
{{
  "title": "動画のタイトル(社内管理用)",
  "hook": "最初の数秒のセリフ(視聴を止める強さ重視)",
  "scenes": [
    {{"time": "0-3s", "text": "字幕テキスト", "visual": "映像の指示", "narration": "ナレーション原稿"}},
    {{"time": "3-8s", "text": "...", "visual": "...", "narration": "..."}}
  ],
  "cta": "最後の行動喚起のセリフ",
  "caption": "投稿時のキャプション文",
  "hashtags": ["#xxx", "#yyy"],
  "thumbnail_text": "サムネに大きく載せる文言(15文字以内)"
}}
"""


def build_user_prompt(keywords: list[str], extra_context: str = "") -> str:
    """ユーザープロンプト(キーワード+任意の追加情報)"""
    keywords_text = "、".join(keywords)
    base = f"""【キーワード】{keywords_text}

このキーワードを軸にした、視聴者が思わず最後まで見てしまうショート動画の台本を1本作ってください。"""

    if extra_context:
        base += f"\n\n【追加の指示・トレンド情報】\n{extra_context}"

    return base


def generate_script(
    keywords: list[str],
    persona_key: str,
    platform_key: str,
    extra_context: str = "",
    model: str = "claude-opus-4-7",
) -> dict:
    """
    台本を1本生成する

    Args:
        keywords: キーワードのリスト
        persona_key: personas.yamlのキー (business/salaryman/housewife/student)
        platform_key: platforms.yamlのキー (tiktok/reels/x)
        extra_context: トレンド情報など追加の文脈(Week 2以降で自動注入)
        model: 使用するClaudeモデル

    Returns:
        台本のdict
    """
    client = Anthropic()

    system_prompt = build_system_prompt(persona_key, platform_key)
    user_prompt = build_user_prompt(keywords, extra_context)

    response = client.messages.create(
        model=model,
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = response.content[0].text.strip()

    # ```jsonで包まれてきた場合の保険
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        script = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSONパースに失敗しました: {e}\n生応答:\n{raw_text}")

    # メタ情報を付加
    script["_meta"] = {
        "keywords": keywords,
        "persona": persona_key,
        "platform": platform_key,
        "model": model,
    }
    return script


def generate_for_all_platforms(
    keywords: list[str],
    persona_key: str,
    extra_context: str = "",
) -> dict[str, dict]:
    """TikTok / Reels / X の3プラットフォーム分まとめて生成"""
    results = {}
    for platform_key in ["tiktok", "reels", "x"]:
        try:
            results[platform_key] = generate_script(
                keywords, persona_key, platform_key, extra_context
            )
        except Exception as e:
            results[platform_key] = {"error": str(e)}
    return results


if __name__ == "__main__":
    # 動作確認用
    result = generate_script(
        keywords=["副業", "AI活用", "月5万"],
        persona_key="salaryman",
        platform_key="tiktok",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
