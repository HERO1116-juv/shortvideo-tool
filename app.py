"""
app.py (Week 2版)
Streamlit製のショート動画台本ジェネレーター

Week 2追加機能:
  - トレンド自動取得(Googleトレンド + Claude Web検索)
  - 同条件バリエーション生成(3本出して比較)
  - サムネ画像生成プロンプトの出力(Week 3への準備)
"""

import json
import os
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

# Streamlit CloudのSecretsから環境変数へ
if "ANTHROPIC_API_KEY" in st.secrets:
    os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title="ショート動画 台本ジェネレーター v2",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 ショート動画 台本ジェネレーター")
st.caption("Week 2: トレンド自動取り込み + バリエーション生成 + サムネ画像プロンプト")

# --- サイドバー ---
with st.sidebar:
    st.header("⚙️ 設定")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        api_key_input = st.text_input("ANTHROPIC_API_KEY", type="password")
        if api_key_input:
            os.environ["ANTHROPIC_API_KEY"] = api_key_input
    else:
        st.success("APIキー読み込み済み")

    model = st.selectbox(
        "台本生成モデル",
        ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
        index=0,
        help="Opus=最高品質、Haiku=低コスト",
    )

    st.divider()
    st.subheader("🔥 トレンド取得")
    use_google_trends = st.checkbox(
        "Googleトレンド取得", value=True,
        help="無料・約5秒"
    )
    use_web_search = st.checkbox(
        "Claude Web検索でトレンド取得", value=False,
        help="プラットフォーム別の最新傾向を取得。1回約5-10円、20-40秒"
    )

    st.divider()
    st.subheader("🎨 画像生成準備")
    include_image_prompts = st.checkbox(
        "サムネ・シーン画像プロンプトを出力",
        value=True,
        help="Week 3で画像生成APIに渡せる形式で出力"
    )

# --- メインフォーム ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📝 入力")

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
    )

    extra_context = st.text_area(
        "追加コンテキスト(手動入力・任意)",
        value="",
        height=70,
        help="トレンド自動取得を有効にしていればここは空でOK"
    )

    mode = st.radio(
        "生成モード",
        ["3プラットフォーム一括", "1プラットフォーム1本", "1プラットフォーム3バリエーション"],
        help="バリエーション機能は同じ条件で異なる構成の台本を3本出します"
    )

    if mode in ["1プラットフォーム1本", "1プラットフォーム3バリエーション"]:
        platform_options = {key: data["label"] for key, data in PLATFORMS.items()}
        platform_key = st.selectbox(
            "プラットフォーム",
            options=list(platform_options.keys()),
            format_func=lambda k: platform_options[k],
        )

    # コスト警告
    if mode == "3プラットフォーム一括":
        n_generations = 3
    elif mode == "1プラットフォーム3バリエーション":
        n_generations = 3
    else:
        n_generations = 1

    n_web_searches = n_generations if use_web_search else 0
    cost_estimate = f"⏱️ 予想時間: {15 + n_web_searches * 25}秒〜 / 💰 概算: 約{(n_generations * (10 if 'opus' in model else 1)) + (n_web_searches * 5)}円"
    st.caption(cost_estimate)

    generate_btn = st.button("🚀 台本を生成", type="primary", use_container_width=True)

# --- 生成処理 ---
with col2:
    st.subheader("📺 生成結果")

    if generate_btn:
        keywords = [
            k.strip()
            for k in keywords_text.replace(",", "\n").replace("、", "\n").split("\n")
            if k.strip()
        ]

        if not keywords:
            st.error("キーワードを1つ以上入力してください")
        elif not os.environ.get("ANTHROPIC_API_KEY"):
            st.error("ANTHROPIC_API_KEYが設定されていません")
        else:
            try:
                # ----- トレンド取得 -----
                trends_by_platform = {}
                target_platforms = (
                    ["tiktok", "reels", "x"]
                    if mode == "3プラットフォーム一括"
                    else [platform_key]
                )

                if use_google_trends or use_web_search:
                    with st.spinner("🔥 トレンド情報を収集中..."):
                        for pf in target_platforms:
                            trends = collect_all_trends(
                                keywords, pf,
                                use_google_trends=use_google_trends,
                                use_web_search=use_web_search,
                            )
                            formatted = format_trends_for_prompt(trends)
                            trends_by_platform[pf] = formatted
                            if formatted:
                                with st.expander(f"📊 {PLATFORMS[pf]['label']}のトレンド情報"):
                                    st.markdown(formatted)

                # ----- 台本生成 -----
                if mode == "3プラットフォーム一括":
                    with st.spinner("3プラットフォーム分の台本を生成中..."):
                        results = generate_for_all_platforms(
                            keywords, persona_key, extra_context,
                            model=model,
                            include_image_prompts=include_image_prompts,
                            trends_by_platform=trends_by_platform,
                        )
                    st.session_state["results"] = results
                    st.session_state["display_mode"] = "platforms"

                elif mode == "1プラットフォーム1本":
                    ctx = extra_context
                    if trends_by_platform.get(platform_key):
                        ctx = (ctx + "\n\n" + trends_by_platform[platform_key]) if ctx else trends_by_platform[platform_key]
                    with st.spinner(f"{PLATFORMS[platform_key]['label']}の台本を生成中..."):
                        result = generate_script(
                            keywords, persona_key, platform_key, ctx,
                            model=model,
                            include_image_prompts=include_image_prompts,
                        )
                    st.session_state["results"] = {platform_key: result}
                    st.session_state["display_mode"] = "single"

                else:  # バリエーション
                    ctx = extra_context
                    if trends_by_platform.get(platform_key):
                        ctx = (ctx + "\n\n" + trends_by_platform[platform_key]) if ctx else trends_by_platform[platform_key]
                    with st.spinner(f"{PLATFORMS[platform_key]['label']}の3バリエーションを生成中..."):
                        variations = generate_variations(
                            keywords, persona_key, platform_key, ctx,
                            model=model, n=3,
                            include_image_prompts=include_image_prompts,
                        )
                    st.session_state["results"] = {
                        f"variation_{i+1}": v for i, v in enumerate(variations)
                    }
                    st.session_state["display_mode"] = "variations"
                    st.session_state["variation_platform"] = platform_key

                # 自動保存
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = OUTPUT_DIR / f"script_{timestamp}.json"
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(st.session_state["results"], f, ensure_ascii=False, indent=2)
                st.success(f"生成完了 ✅ ({save_path.name})")

            except Exception as e:
                st.error(f"エラー: {e}")
                import traceback
                with st.expander("詳細"):
                    st.code(traceback.format_exc())

# --- 結果表示 ---
if "results" in st.session_state:
    results = st.session_state["results"]
    display_mode = st.session_state.get("display_mode", "single")

    if display_mode == "variations":
        platform_label = PLATFORMS[st.session_state.get("variation_platform", "tiktok")]["label"]
        tab_labels = [f"案{i+1} ({platform_label})" for i in range(len(results))]
    else:
        tab_labels = [
            PLATFORMS[k]["label"] if k in PLATFORMS else k
            for k in results.keys()
        ]

    tabs = st.tabs(tab_labels)

    for tab, (key, script) in zip(tabs, results.items()):
        with tab:
            if "error" in script:
                st.error(f"生成失敗: {script['error']}")
                continue

            st.markdown(f"### 🎯 {script.get('title', '(タイトルなし)')}")
            st.info(f"**フック**: {script.get('hook', '')}")

            st.markdown("#### 📋 シーン構成")
            scenes = script.get("scenes", [])
            for i, scene in enumerate(scenes, 1):
                preview = scene.get('text', '')[:30]
                with st.expander(f"Scene {i} ({scene.get('time', '')}): {preview}..."):
                    st.markdown(f"**字幕**: {scene.get('text', '')}")
                    st.markdown(f"**映像指示**: {scene.get('visual', '')}")
                    st.markdown(f"**ナレーション**: {scene.get('narration', '')}")
                    if scene.get('scene_image_prompt'):
                        st.markdown("**🎨 画像生成プロンプト(Week 3用)**")
                        st.code(scene['scene_image_prompt'], language=None)

            st.markdown(f"**🎤 CTA**: {script.get('cta', '')}")

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**📝 キャプション**")
                st.code(script.get("caption", ""), language=None)
            with col_b:
                st.markdown("**🏷️ ハッシュタグ**")
                st.code(" ".join(script.get("hashtags", [])), language=None)

            # サムネ情報
            if script.get("thumbnail_text") or script.get("thumbnail_image_prompt"):
                st.markdown("#### 🖼️ サムネイル情報")
                if script.get("thumbnail_text"):
                    st.markdown(f"**サムネ文言**: `{script['thumbnail_text']}`")
                if script.get("thumbnail_image_prompt"):
                    st.markdown("**サムネ画像生成プロンプト(Week 3で使用)**")
                    st.code(script['thumbnail_image_prompt'], language=None)

            with st.expander("📦 生JSONを見る"):
                st.code(json.dumps(script, ensure_ascii=False, indent=2), language="json")

    st.download_button(
        "💾 全結果をJSONダウンロード",
        data=json.dumps(results, ensure_ascii=False, indent=2),
        file_name=f"scripts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
    )

st.divider()
with st.expander("📚 Week 2の使い方"):
    st.markdown("""
**新機能の使い方**

1. **トレンド取得を有効化**
   - サイドバーで「Googleトレンド」「Claude Web検索」をON
   - 生成時に自動でトレンド情報を取得して台本に反映

2. **バリエーション生成**
   - 「1プラットフォーム3バリエーション」モードを選択
   - 同じ条件で異なる構成の台本を3本出力
   - ストーリー型 / 問題提起型 / 意外性型の3パターン

3. **画像生成プロンプト**
   - 「サムネ・シーン画像プロンプトを出力」をON
   - 各シーンとサムネに画像生成用プロンプトが付与される
   - Week 3で画像生成API(gpt-image-1等)にそのまま渡せる

**コストの目安**
- Haiku + トレンドOFF: 1〜3円
- Opus + トレンドON(3プラットフォーム): 50〜80円
""")
