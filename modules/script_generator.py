"""
script_generator.py (Week 2版)
キーワード + ターゲット層 + プラットフォーム + トレンド情報 から
JSON形式の動画台本を生成するモジュール

Week 2変更点:
  - トレンド情報の自動注入対応
  - サムネ画像生成用プロンプト(thumbnail_image_prompt)を出力に追加
  - バリエーション生成対応
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


def build_system_prompt(persona_key: str, platform_key: str, include_image_prompts: bool = True) -> str:
    persona = PERSONAS[persona_key]
    platform = PLATFORMS[platform_key]

    characteristics_text = "\n".join(f"  - {c}" for c in platform["characteristics"])
    ng_words = persona.get("ng_words", [])
    ng_text = f"\n【使用禁止ワード】{', '.join(ng_words)}" if ng_words else ""

    if include_image_prompts:
        scene_format = '{"time": "0-3s", "text": "字幕テキスト", "visual": "映像の指示", "narration": "ナレーション原稿", "scene_image_prompt": "このシーンを表す画像生成プロンプト(英語可、具体的に)"}'
        extra_fields = ''',
  "thumbnail_image_prompt": "サムネ画像生成用
