"""script_generator.py (Week 2版)"""

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


def build_system_prompt(persona_key, platform_key, include_image_prompts=True):
    persona = PERSONAS[persona_key]
    platform = PLATFORMS[platform_key]
    characteristics_text = "\n".join(f"  - {c}" for c in platform["characteristics"])
    ng_words = persona.get("ng_words", [])
    ng_text = f"\n【使用禁止ワード】{', '.join(ng_words)}" if ng_words else ""

    if include_image_prompts:
        scene_format = '{"time": "0-3s", "text": "字幕", "visual": "映像", "narration": "ナレーション", "scene_image_prompt": "画像生成プロンプト"}'
        extra_fields = ',\n  "thumbnail_image_prompt": "サムネ画像生成用プロンプト(具体的・視覚的)"'
    else:
        scene_format = '{"time": "0-3s", "text": "字幕", "visual": "映像", "narration": "ナレーション"}'
        extra_fields = ""

    return f"""あなたはショート動画のプロ構成作家です。

【ターゲット】{persona['label']}({persona['age']}歳)
  関心事: {', '.join(persona['interests'])}
  悩み: {', '.join(persona['pain_points'])}
  トーン: {persona['tone']}

【プラットフォーム】{platform['label']}
  推奨尺: {platform['recommended_duration']}秒
  最初の{platform['hook_window_sec']}秒で掴む
  特性:
{characteristics_text}
{ng_text}

【ルール】
1. 出力はJSON形式のみ(前後の説明・コードブロック記号なし)
2. textは画面字幕も兼ねるので簡潔に
3. トレンド情報があれば必ず反映
4. 画像生成プロンプトは具体的に

【出力JSON形式】
{{
  "title": "タイトル",
  "hook": "最初のセリフ",
  "scenes": [
    {scene_format},
    {scene_format}
  ],
  "cta": "行動喚起",
  "caption": "キャプション",
  "hashtags": ["#xxx"],
  "thumbnail_text": "サムネ文言(15字以内)"{extra_fields}
}}
"""


def build_user_prompt(keywords, extra_context="", variation_seed=0):
    keywords_text = "、".join(keywords)
    variation_hint = ""
    if variation_seed > 0:
        styles = [
            "ストーリー型(自分の体験談から)",
            "問題提起型(視聴者の悩みを言い当てて)",
            "意外性型(常識を覆す事実から)",
        ]
        style = styles[(variation_seed - 1) % len(styles)]
        variation_hint = f"\n\n【バリエーション指示】{style}で構成してください。"

    base = f"【キーワード】{keywords_text}\n\nこのキーワードでショート動画の台本を1本作ってください。{variation_hint}"
    if extra_context:
        base += f"\n\n【追加情報】\n{extra_context}"
    return base


def generate_script(keywords, persona_key, platform_key, extra_context="", model="claude-opus-4-7", include_image_prompts=True, variation_seed=0):
    client = Anthropic()
    system_prompt = build_system_prompt(persona_key, platform_key, include_image_prompts)
    user_prompt = build_user_prompt(keywords, extra_context, variation_seed)

    response = client.messages.create(
        model=model,
        max_tokens=2500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        script = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSONパース失敗: {e}\n生応答:\n{raw_text}")

    script["_meta"] = {
        "keywords": keywords,
        "persona": persona_key,
        "platform": platform_key,
        "model": model,
        "variation_seed": variation_seed,
    }
    return script


def generate_for_all_platforms(keywords, persona_key, extra_context="", model="claude-opus-4-7", include_image_prompts=True, trends_by_platform=None):
    results = {}
    for platform_key in ["tiktok", "reels", "x"]:
        ctx = extra_context
        if trends_by_platform and platform_key in trends_by_platform:
            trend_text = trends_by_platform[platform_key]
            if trend_text:
                ctx = (ctx + "\n\n" + trend_text) if ctx else trend_text
        try:
            results[platform_key] = generate_script(
                keywords, persona_key, platform_key, ctx,
                model=model, include_image_prompts=include_image_prompts,
            )
        except Exception as e:
            results[platform_key] = {"error": str(e)}
    return results


def generate_variations(keywords, persona_key, platform_key, extra_context="", model="claude-opus-4-7", n=3, include_image_prompts=True):
    variations = []
    for i in range(n):
        try:
            script = generate_script(
                keywords, persona_key, platform_key, extra_context,
                model=model, include_image_prompts=include_image_prompts,
                variation_seed=i + 1,
            )
            variations.append(script)
        except Exception as e:
            variations.append({"error": str(e), "variation_seed": i + 1})
    return variations
