"""
bgm_manager.py
無料BGMを管理する
初回利用時にネット経由でフリーBGMをダウンロードしキャッシュ
"""

import os
import urllib.request
from pathlib import Path


DEFAULT_BGM_URLS = {
    "upbeat": "https://archive.org/download/jamendo-070483/01.mp3",
    "calm": "https://archive.org/download/jamendo-070483/02.mp3",
    "dramatic": "https://archive.org/download/jamendo-070483/03.mp3",
}

CACHE_DIR = Path.home() / ".shortvideo_bgm_cache"


def get_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def download_bgm(name="upbeat"):
    """指定したBGMをダウンロードまたはキャッシュから返す"""
    cache_dir = get_cache_dir()
    cache_path = cache_dir / f"{name}.mp3"

    if cache_path.exists() and cache_path.stat().st_size > 1000:
        return cache_path

    url = DEFAULT_BGM_URLS.get(name)
    if not url:
        return None

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as response:
            data = response.read()
        cache_path.write_bytes(data)
        return cache_path
    except Exception as e:
        print(f"BGMダウンロード失敗 ({name}): {e}")
        return None


def get_bgm_path(name="upbeat", user_uploaded=None):
    """BGMファイルパスを取得する"""
    cache_dir = get_cache_dir()

    if user_uploaded:
        path = cache_dir / "user_bgm.mp3"
        path.write_bytes(user_uploaded)
        return path

    return download_bgm(name)


def list_available_bgms():
    return list(DEFAULT_BGM_URLS.keys())
