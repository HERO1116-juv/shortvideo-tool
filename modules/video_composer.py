"""
video_composer.py
台本JSON + 生成済み画像 + BGM から mp4 を合成
MoviePy + Pillowを使用
"""

import os
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


PLATFORM_RESOLUTIONS = {
    "tiktok": (1080, 1920),
    "reels": (1080, 1920),
    "x": (1920, 1080),
}


def parse_time_range(time_str):
    """"0-3s" や "3-8s" のような文字列を (start, end) 秒のタプルに変換"""
    match = re.match(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*s?", time_str.strip())
    if match:
        return float(match.group(1)), float(match.group(2))
    return 0.0, 3.0


def _find_japanese_font():
    """利用可能な日本語フォントパスを探す"""
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansJP-Bold.otf",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def create_caption_image(text, width, height, font_path=None, font_size_ratio=0.055, position="bottom"):
    """透明背景に大きなテロップを描画したPIL Imageを返す"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if not font_path:
        font_path = _find_japanese_font()

    font_size = int(width * font_size_ratio)
    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    max_width = int(width * 0.85)
    lines = _wrap_text_japanese(text, font, max_width, draw)

    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_heights.append(bbox[3] - bbox[1])

    total_text_height = sum(line_heights) + (len(lines) - 1) * 10

    if position == "bottom":
        start_y = int(height * 0.78) - total_text_height
    elif position == "center":
        start_y = (height - total_text_height) // 2
    else:
        start_y = int(height * 0.1)

    y = start_y
    for line, lh in zip(lines, line_heights):
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        x = (width - line_width) // 2

        stroke = max(3, font_size // 15)
        for dx in range(-stroke, stroke + 1):
            for dy in range(-stroke, stroke + 1):
                if dx == 0 and dy == 0:
                    continue
                draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 255))

        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += lh + 10

    return img


def _wrap_text_japanese(text, font, max_width, draw):
    """日本語向けに文字単位で折り返す"""
    lines = []
    current = ""
    for char in text:
        test = current + char
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def compose_video(script, image_paths, output_path, platform_key="tiktok", bgm_path=None, bgm_volume=0.3):
    """画像と台本JSONからmp4動画を合成する"""
    try:
        from moviepy import (
            ImageClip,
            CompositeVideoClip,
            AudioFileClip,
            concatenate_videoclips,
        )
    except ImportError:
        try:
            from moviepy.editor import (
                ImageClip,
                CompositeVideoClip,
                AudioFileClip,
                concatenate_videoclips,
            )
        except ImportError:
            return {"output_path": None, "duration": 0, "error": "moviepy未インストール"}

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, height = PLATFORM_RESOLUTIONS.get(platform_key, (1080, 1920))

    scenes = script.get("scenes", [])
    if not scenes or not image_paths:
        return {"output_path": None, "duration": 0, "error": "シーンまたは画像なし"}

    clips = []
    total_duration = 0.0
    temp_dir = output_path.parent / "_temp_captions"
    temp_dir.mkdir(exist_ok=True)

    for i, scene in enumerate(scenes):
        if i >= len(image_paths):
            break

        time_range = scene.get("time", f"{i*3}-{(i+1)*3}s")
        start, end = parse_time_range(time_range)
        duration = max(end - start, 1.0)
        total_duration += duration

        img_clip = ImageClip(str(image_paths[i])).with_duration(duration)
        img_clip = img_clip.resized(new_size=(width, height))

        caption_text = scene.get("text", "")
        if caption_text:
            caption_img = create_caption_image(caption_text, width, height)
            caption_png = temp_dir / f"caption_{i:02d}.png"
            caption_img.save(caption_png)
            caption_clip = ImageClip(str(caption_png)).with_duration(duration)
            scene_clip = CompositeVideoClip([img_clip, caption_clip], size=(width, height))
        else:
            scene_clip = img_clip

        clips.append(scene_clip)

    if not clips:
        return {"output_path": None, "duration": 0, "error": "クリップ生成失敗"}

    final = concatenate_videoclips(clips, method="compose")

    # BGM
    if bgm_path and Path(bgm_path).exists():
        try:
            audio = AudioFileClip(str(bgm_path))
            if audio.duration < final.duration:
                from moviepy.audio.AudioClip import concatenate_audioclips
                loops = int(final.duration / audio.duration) + 1
                audio = concatenate_audioclips([audio] * loops)
            audio = audio.subclipped(0, final.duration)
            try:
                from moviepy.audio.fx import MultiplyVolume
                audio = audio.with_effects([MultiplyVolume(bgm_volume)])
            except Exception:
                pass
            final = final.with_audio(audio)
        except Exception as e:
            print(f"BGM追加失敗(音声なしで続行): {e}")

    final.write_videofile(
        str(output_path),
        fps=24,
        codec="libx264",
        audio_codec="aac" if bgm_path else None,
        logger=None,
        threads=2,
    )

    try:
        for f in temp_dir.glob("*"):
            f.unlink()
        temp_dir.rmdir()
    except Exception:
        pass

    return {"output_path": output_path, "duration": total_duration, "error": None}
