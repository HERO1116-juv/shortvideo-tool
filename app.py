"""
app.py
Streamlit製のWeek 1 MVP UI
キーワードとターゲット層を入れると、3プラットフォーム分の台本JSONを生成・閲覧・ダウンロードできる
"""

import json
import os
from datetime import datetime
from pathlib import Path

import streamlit as st
import yaml

from modules.script_generator import (
    PERSONAS,
    PLATFORMS,
    generate_script,
    generate_for_all_platforms,
)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title="ショート動画 台本ジェネレーター",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 ショート動画 台本ジェネレーター")
st.caption("Week 1 MVP: キーワード + ターゲット層 → 3プラットフォームの台本を一括生成")

# --- サイドバー: 設定 ---
with st.sidebar:
    st.header("⚙️ 設定")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        api_key_input = st.text_input(
            "ANTHROPIC_API_KEY",
            type="password",
            help="環境変数に設定済みなら不要",
        )
        if api_key_input:
            os.environ["ANTHROPIC_API_KEY"] = api_key_input
    else:
        st.success("APIキー読み込み済み")

    model = st.selectbox(
        "モデル",
        ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
        index=0,
        help="Opusが最高品質。コスト重視ならHaiku",
    )

# --- メインフォーム ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📝 入力")

    keywords_text = st.text_area(
        "キーワード(改行 or カンマ区切りで複数)",
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
        "追加コンテキスト(任意・トレンド情報など)",
        value="",
        height=80,
        help="Week 2以降は自動取得。今は手動で「最近こういうのが流行ってる」と書くと反映されます",
    )

    mode = st.radio(
        "生成モード",
        ["3プラットフォーム一括", "1プラットフォームのみ"],
        horizontal=True,
    )

    if mode == "1プラットフォームのみ":
        platform_options = {key: data["label"] for key, data in PLATFORMS.items()}
        platform_key = st.selectbox(
            "プラットフォーム",
            options=list(platform_options.keys()),
            format_func=lambda k: platform_options[k],
        )

    generate_btn = st.button("🚀 台本を生成", type="primary", use_container_width=True)

# --- 生成処理 ---
with col2:
    st.subheader("📺 生成結果")

    if generate_btn:
        # キーワードをリスト化
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
                if mode == "3プラットフォーム一括":
                    with st.spinner("3プラットフォーム分の台本を生成中..."):
                        results = generate_for_all_platforms(
                            keywords, persona_key, extra_context
                        )
                    st.session_state["results"] = results
                    st.session_state["mode"] = "all"
                else:
                    with st.spinner(f"{PLATFORMS[platform_key]['label']}の台本を生成中..."):
                        result = generate_script(
                            keywords, persona_key, platform_key, extra_context, model=model
                        )
                    st.session_state["results"] = {platform_key: result}
                    st.session_state["mode"] = "single"

                # 自動保存
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = OUTPUT_DIR / f"script_{timestamp}.json"
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(st.session_state["results"], f, ensure_ascii=False, indent=2)
                st.success(f"生成完了 ✅ ({save_path.name} に自動保存)")

            except Exception as e:
                st.error(f"エラー: {e}")

# --- 結果表示 ---
if "results" in st.session_state:
    results = st.session_state["results"]

    tab_labels = [PLATFORMS[k]["label"] if k in PLATFORMS else k for k in results.keys()]
    tabs = st.tabs(tab_labels)

    for tab, (platform_key, script) in zip(tabs, results.items()):
        with tab:
            if "error" in script:
                st.error(f"生成失敗: {script['error']}")
                continue

            # タイトル・フック
            st.markdown(f"### 🎯 {script.get('title', '(タイトルなし)')}")
            st.info(f"**フック**: {script.get('hook', '')}")

            # シーン一覧
            st.markdown("#### 📋 シーン構成")
            scenes = script.get("scenes", [])
            for i, scene in enumerate(scenes, 1):
                with st.expander(f"Scene {i} ({scene.get('time', '')}): {scene.get('text', '')[:30]}..."):
                    st.markdown(f"**字幕**: {scene.get('text', '')}")
                    st.markdown(f"**映像**: {scene.get('visual', '')}")
                    st.markdown(f"**ナレーション**: {scene.get('narration', '')}")

            # CTA
            st.markdown(f"**🎤 CTA**: {script.get('cta', '')}")

            # キャプション・ハッシュタグ
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**📝 投稿キャプション**")
                st.code(script.get("caption", ""), language=None)
            with col_b:
                st.markdown("**🏷️ ハッシュタグ**")
                hashtags = script.get("hashtags", [])
                st.code(" ".join(hashtags), language=None)

            # サムネ文言
            if script.get("thumbnail_text"):
                st.markdown(f"**🖼️ サムネ文言**: `{script['thumbnail_text']}`")

            # 生JSON
            with st.expander("📦 生JSONを見る / コピー"):
                st.code(json.dumps(script, ensure_ascii=False, indent=2), language="json")

    # 全体ダウンロード
    st.download_button(
        "💾 全結果をJSONでダウンロード",
        data=json.dumps(results, ensure_ascii=False, indent=2),
        file_name=f"scripts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
    )

# --- フッター ---
st.divider()
with st.expander("📚 使い方 / 次のステップ"):
    st.markdown("""
**使い方**
1. サイドバーでANTHROPIC_API_KEYを設定(環境変数推奨)
2. キーワードを複数入力(改行区切り)
3. ターゲット層を選択
4. 「台本を生成」をクリック

**Week 2でやること**
- pytrends / TikTok Creative Center からトレンド自動取得
- 「extra_context」に自動注入
- 過去台本との重複チェック

**Week 3-4でやること**
- 画像生成(gpt-image-1 or SDXL)
- 音声合成(VOICEVOX)
- MoviePyで動画合成
- プラットフォーム別 縦横比・尺の自動調整
    """)
