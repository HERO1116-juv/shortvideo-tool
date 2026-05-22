"""
app.py (Week 3版)
台本生成 + 画像生成 + 動画合成 までを統合したUI
"""

import json
import os
import zipfile
import io
from datetime import datetime
from pathlib import Path

import streamlit as st

from modules.script_generator import (
    PERSONAS,
    PLATFORMS,
    generate_script,
    generate_for_all_platforms,
    generate_variations,
)
from modules.trend_collector import (
    collect_all_trends,
    format_trends_for_prompt,
)
from modules.image_generator import (
    generate_images_for_script,
    estimate_cost as estimate_image_cost,
)
from modules.video_composer import compose_video
from modules.bgm_manager import get_bgm_path, list_available_bgms


# Secrets読み込み
if "ANTHROPIC_API_KEY" in st.secrets:
    os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
if "OPENAI_API_KEY" in st.secrets:
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title="ショート動画ジェネレーター v3",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 ショート動画ジェネレーター")
st.caption("Week 3: 台本 → 画像生成 → mp4出力までフル自動")

# --- サイドバー ---
with st.sidebar:
    st.header("⚙️ 設定")

    anthropic_ok = bool(os.environ.get("ANTHROPIC_API_KEY"))
    openai_ok = bool(os.environ.get("OPENAI_API_KEY"))

    if anthropic_ok:
        st.success("✅ Anthropic APIキー OK")
    else:
        st.error("❌ Anthropic APIキー未設定")
    if openai_ok:
        st.success("✅ OpenAI APIキー OK")
    else:
        st.warning("⚠️ OpenAI APIキー未設定(画像生成不可)")

    st.divider()
    st.subheader("📝 台本生成")
    model = st.selectbox(
        "モデル",
        ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
        index=2,
    )
    use_google_trends = st.checkbox("Googleトレンド取得", value=True)
    use_web_search = st.checkbox("Claude Web検索", value=False)

    st.divider()
    st.subheader("🎨 画像生成")
    image_quality = st.selectbox(
        "画質",
        ["low", "medium", "high"],
        index=1,
        help="low=$0.011/枚, medium=$0.042/枚, high=$0.167/枚",
    )

    st.divider()
    st.subheader("🎬 動画合成")
    bgm_choice = st.selectbox(
        "BGM",
        ["なし"] + list_available_bgms() + ["アップロード"],
        index=1,
    )
    user_bgm = None
    if bgm_choice == "アップロード":
        bgm_file = st.file_uploader("BGMファイル(mp3)", type=["mp3", "wav"])
        if bgm_file:
            user_bgm = bgm_file.read()

    bgm_volume = st.slider("BGM音量", 0.0, 1.0, 0.3, 0.05)


# --- メインタブ ---
tab1, tab2, tab3 = st.tabs(["📝 1. 台本生成", "🎨 2. 画像生成", "🎬 3. 動画合成"])

# Tab 1: 台本生成
with tab1:
    st.subheader("台本を生成")

    col1, col2 = st.columns([1, 1])
    with col1:
        keywords_text = st.text_area(
            "キーワード(改行 or カンマ区切り)",
            value="副業\nAI活用\n月5万",
            height=100,
        )
        persona_options = {key: data["label"] for key, data in PERSONAS.items()}
        persona_key = st.selectbox(
            "ターゲット層",
            options=list(persona_options.keys()),
            format_func=lambda k: persona_options[k],
            key="persona_t1",
        )
        platform_options = {key: data["label"] for key, data in PLATFORMS.items()}
        platform_key = st.selectbox(
            "プラットフォーム",
            options=list(platform_options.keys()),
            format_func=lambda k: platform_options[k],
            key="platform_t1",
        )

    with col2:
        extra_context = st.text_area("追加コンテキスト(任意)", value="", height=80)
        st.info(f"💰 概算: {'約10円' if 'opus' in model else '約1円'}")

    if st.button("🚀 台本を生成", type="primary", use_container_width=True):
        keywords = [k.strip() for k in keywords_text.replace(",", "\n").replace("、", "\n").split("\n") if k.strip()]
        if not keywords:
            st.error("キーワードを入力してください")
        elif not anthropic_ok:
            st.error("Anthropic APIキーが必要")
        else:
            trends_text = ""
            if use_google_trends or use_web_search:
                with st.spinner("🔥 トレンド収集中..."):
                    trends = collect_all_trends(
                        keywords, platform_key,
                        use_google_trends=use_google_trends,
                        use_web_search=use_web_search,
                    )
                    trends_text = format_trends_for_prompt(trends)
                    if trends_text:
                        with st.expander("トレンド情報"):
                            st.markdown(trends_text)

            ctx = (extra_context + "\n\n" + trends_text) if trends_text else extra_context

            with st.spinner("台本生成中..."):
                try:
                    script = generate_script(
                        keywords, persona_key, platform_key, ctx,
                        model=model, include_image_prompts=True,
                    )
                    st.session_state["script"] = script
                    st.session_state["script_platform"] = platform_key
                    st.success("✅ 台本生成完了")
                except Exception as e:
                    st.error(f"エラー: {e}")

    if "script" in st.session_state:
        script = st.session_state["script"]
        st.divider()
        st.markdown(f"### 🎯 {script.get('title', '')}")
        st.info(f"**フック**: {script.get('hook', '')}")
        st.markdown("#### シーン")
        for i, scene in enumerate(script.get("scenes", []), 1):
            with st.expander(f"Scene {i} ({scene.get('time', '')})"):
                st.markdown(f"**字幕**: {scene.get('text', '')}")
                st.markdown(f"**画像プロンプト**: `{scene.get('scene_image_prompt', '')[:100]}...`")
        st.markdown(f"**サムネ文言**: `{script.get('thumbnail_text', '')}`")

# Tab 2: 画像生成
with tab2:
    st.subheader("画像を生成")

    if "script" not in st.session_state:
        st.warning("先にTab 1で台本を生成してください")
    else:
        script = st.session_state["script"]
        scenes = script.get("scenes", [])
        n_scenes = len(scenes)

        cost = estimate_image_cost(n_scenes, include_thumbnail=True, quality=image_quality)
        st.info(f"💰 概算: {cost['images']}枚 × {image_quality} = **約{cost['jpy']}円** (${cost['usd']})")

        include_thumb = st.checkbox("サムネも生成", value=True)

        if st.button("🎨 画像を生成", type="primary", use_container_width=True):
            if not openai_ok:
                st.error("OpenAI APIキーが必要")
            else:
                platform_key_t2 = st.session_state.get("script_platform", "tiktok")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                img_dir = OUTPUT_DIR / f"images_{timestamp}"

                with st.spinner(f"画像{cost['images']}枚を生成中(2〜5分)..."):
                    try:
                        results = generate_images_for_script(
                            script,
                            platform_key=platform_key_t2,
                            quality=image_quality,
                            include_thumbnail=include_thumb,
                            output_dir=img_dir,
                        )
                        st.session_state["images"] = results
                        st.session_state["image_dir"] = img_dir
                        st.success(f"✅ 画像生成完了({len(results['scenes'])}枚 + サムネ{'あり' if results['thumbnail'] else 'なし'})")
                        if results["errors"]:
                            with st.expander(f"⚠️ {len(results['errors'])}件のエラー"):
                                for err in results["errors"]:
                                    st.warning(err)
                    except Exception as e:
                        st.error(f"エラー: {e}")

    if "images" in st.session_state:
        results = st.session_state["images"]
        st.divider()
        st.subheader("生成された画像")
        if results.get("thumbnail"):
            st.markdown("**サムネ**")
            st.image(str(results["thumbnail"]), width=300)
        cols = st.columns(min(len(results["scenes"]), 4) or 1)
        for i, img_path in enumerate(results["scenes"]):
            with cols[i % len(cols)]:
                st.image(str(img_path), caption=f"Scene {i+1}", use_column_width=True)

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            if results.get("thumbnail"):
                zf.write(results["thumbnail"], "thumbnail.png")
            for p in results["scenes"]:
                zf.write(p, p.name)
        st.download_button(
            "💾 画像をZIPでダウンロード",
            data=zip_buf.getvalue(),
            file_name=f"images_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip",
        )

# Tab 3: 動画合成
with tab3:
    st.subheader("動画を合成")

    if "script" not in st.session_state:
        st.warning("先にTab 1で台本を生成してください")
    elif "images" not in st.session_state:
        st.warning("先にTab 2で画像を生成してください")
    else:
        script = st.session_state["script"]
        images = st.session_state["images"]
        platform_key_t3 = st.session_state.get("script_platform", "tiktok")

        st.info(f"📋 動画情報: {PLATFORMS[platform_key_t3]['label']} / シーン数 {len(script.get('scenes', []))} / 画像 {len(images['scenes'])}枚")

        if st.button("🎬 mp4を合成", type="primary", use_container_width=True):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = OUTPUT_DIR / f"video_{timestamp}.mp4"

            bgm_path = None
            if bgm_choice != "なし":
                with st.spinner("BGM準備中..."):
                    if bgm_choice == "アップロード" and user_bgm:
                        bgm_path = get_bgm_path(user_uploaded=user_bgm)
                    elif bgm_choice in list_available_bgms():
                        bgm_path = get_bgm_path(name=bgm_choice)

            with st.spinner("動画を合成中(3〜10分)..."):
                try:
                    result = compose_video(
                        script,
                        image_paths=images["scenes"],
                        output_path=output_path,
                        platform_key=platform_key_t3,
                        bgm_path=bgm_path,
                        bgm_volume=bgm_volume,
                    )
                    if result["error"]:
                        st.error(f"動画合成失敗: {result['error']}")
                    else:
                        st.session_state["video_path"] = result["output_path"]
                        st.success(f"✅ 動画合成完了({result['duration']:.1f}秒)")
                except Exception as e:
                    st.error(f"エラー: {e}")
                    import traceback
                    with st.expander("詳細"):
                        st.code(traceback.format_exc())

    if "video_path" in st.session_state:
        video_path = st.session_state["video_path"]
        if Path(video_path).exists():
            st.divider()
            st.subheader("🎉 完成した動画")
            with open(video_path, "rb") as f:
                video_bytes = f.read()
            st.video(video_bytes)
            st.download_button(
                "💾 mp4をダウンロード",
                data=video_bytes,
                file_name=Path(video_path).name,
                mime="video/mp4",
            )

st.divider()
with st.expander("📚 Week 3の使い方"):
    st.markdown("""
**3ステップで完成:**
1. **Tab 1**: 台本を生成(画像プロンプト付き)
2. **Tab 2**: gpt-image-1で画像を5〜8枚生成(2〜5分、50〜80円)
3. **Tab 3**: MoviePyでmp4合成(3〜10分、無料)

**コスト目安:**
- 台本(Haiku) + 画像7枚(medium) = 約30円
- 台本(Opus) + 画像7枚(high) = 約140円

**注意:**
- Streamlit Cloud無料プランは1GBメモリ制限。長尺やhigh画質はメモリ不足の可能性
- 動画合成は時間がかかるので途中で画面を閉じない
- 初回BGMダウンロードに時間がかかる場合あり
""")
