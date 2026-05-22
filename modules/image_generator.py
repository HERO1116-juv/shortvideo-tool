"""
image_generator.py
gpt-image-1で台本JSONから各シーンの画像とサムネを生成
"""

import os
import base64
from pathlib import Path
from openai import OpenAI


PLATFORM_SIZES = {
    "tiktok": "1024x1536",
    "reels": "1024x1536",
    "x": "1536x1024",
}


def generate_image(prompt: str, size: str = "1024x1536", quality: str = "medium") -> bytes:
    """gpt-image-1で画像1枚を生成し、PNGバイト列を返す"""
    client = OpenAI()
    response = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size=size,
        quality=quality,
        n=1,
    )
    b64 = response.data[0].b64_json
    return base64.b64decode(b64)


def generate_images_for_script(
    script,
    platform_key="tiktok",
    quality="medium",
    include_thumbnail=True,
    output_dir=None,
):
    """台本JSONから各シーンとサムネの画像を生成する"""
    if output_dir is None:
        output_dir = Path("./output/images")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    size = PLATFORM_SIZES.get(platform_key, "1024x1536")
    results = {"thumbnail": None, "scenes": [], "errors": []}

    # サムネ画像
    if include_thumbnail and script.get("thumbnail_image_prompt"):
        try:
            thumb_prompt = _build_thumbnail_prompt(script)
            img_bytes = generate_image(thumb_prompt, size=size, quality=quality)
            thumb_path = output_dir / "thumbnail.png"
            thumb_path.write_bytes(img_bytes)
            results["thumbnail"] = thumb_path
        except Exception as e:
            results["errors"].append(f"サムネ生成失敗: {e}")

    # 各シーン画像
    scenes = script.get("scenes", [])
    for i, scene in enumerate(scenes, 1):
        scene_prompt = scene.get("scene_image_prompt") or scene.get("visual", "")
        if not scene_prompt:
            results["errors"].append(f"Scene {i}: プロンプトなし、スキップ")
            continue

        try:
            full_prompt = _build_scene_prompt(scene_prompt, scene.get("text", ""))
            img_bytes = generate_image(full_prompt, size=size, quality=quality)
            scene_path = output_dir / f"scene_{i:02d}.png"
            scene_path.write_bytes(img_bytes)
            results["scenes"].append(scene_path)
        except Exception as e:
            results["errors"].append(f"Scene {i}生成失敗: {e}")

    return results


def _build_thumbnail_prompt(script):
    base = script.get("thumbnail_image_prompt", "")
    suffix = " The image should have empty space at the bottom third for text overlay. Do NOT include any text or letters in the image itself."
    return base + suffix


def _build_scene_prompt(scene_prompt, subtitle_text=""):
    suffix = " Cinematic composition with empty space at the bottom for subtitle overlay. Do NOT render any text, letters, captions, or words in the image."
    return scene_prompt + suffix


def estimate_cost(n_scenes, include_thumbnail=True, quality="medium"):
    """画像生成コスト見積もり"""
    n_images = n_scenes + (1 if include_thumbnail else 0)
    cost_per_image = {"low": 0.011, "medium": 0.042, "high": 0.167}.get(quality, 0.042)
    usd = n_images * cost_per_image
    jpy = usd * 155
    return {"images": n_images, "usd": round(usd, 3), "jpy": round(jpy)}
