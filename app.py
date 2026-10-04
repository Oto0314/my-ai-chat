import streamlit as st
import json
import os
from google import genai
from google.genai import types

# ページの設定
st.set_page_config(
    page_title="自分専用・AIチャット",
    page_icon="💬",
    layout="centered",
    initial_sidebar_state="expanded"
)

# ファイル名定数
HISTORY_FILE = "chat_histories.json"
MEMORY_FILE = "user_memory_list.json"
SETTINGS_FILE = "chat_settings.json"

# データの読み込み・保存関数
def load_data(filename, default_value):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"ファイル `{filename}` の読み込み中にエラーが発生しました: {e}")
            return default_value
    return default_value

def save_data(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"ファイル `{filename}` の保存中にエラーが発生しました: {e}")

# セッション状態の初期化
if "histories" not in st.session_state:
    st.session_state.histories = load_data(HISTORY_FILE, {"デフォルト": []})

if "current_chat" not in st.session_state:
    chat_keys = list(st.session_state.histories.keys())
    st.session_state.current_chat = chat_keys[0] if chat_keys else "デフォルト"

if "saved_memories" not in st.session_state:
    st.session_state.saved_memories = load_data(MEMORY_FILE, [])

if "chat_settings" not in st.session_state:
    st.session_state.chat_settings = load_data(SETTINGS_FILE, {})

current_chat_name = st.session_state.current_chat
if current_chat_name not in st.session_state.chat_settings:
    st.session_state.chat_settings[current_chat_name] = {
        "character_setting": "あなたは聖川真斗です。俺・お前口調で、小説形式で答えてください。( )は心の中、《 》は行動や光景、〈 〉は効果音。語尾に「よ」は使わない。「そっか」ではなく「そうか」を使う。"
    }

# ==========================================
# 【AI接続部分の独立関数】（google-genai SDK最新対応版）
# ==========================================
def generate_response(system_instruction, memories, history, user_message):
    api_key = None
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
    elif "general" in st.secrets and "GEMINI_API_KEY" in st.secrets["general"]:
        api_key = st.secrets["general"]["GEMINI_API_KEY"]

    if not api_key:
        raise ValueError("APIキーが設定されていません。StreamlitのSecretsを確認してください。")

    try:
        client = genai.Client(api_key=api_key)

        memories_text = "\n".join(memories)
        full_system_instruction = f"{system_instruction}\n\n【長期記憶・設定】\n{memories_text}"

        # 履歴の整理（直近20件に制限）
        trimmed_history = history[-20:] if len(history) > 20 else history

        formatted_history = []
        for m in trimmed_history:
            r = "user" if m["role"] == "user" else "model"
            formatted_history.append(
                types.Content(
                    role=r,
                    parts=[types.Part.from_text(text=m["content"])]
                )
            )

        model_name = "gemini-2.5-flash"
        config = types.GenerateContentConfig(
            system_instruction=full_system_instruction,
            temperature=0.7,
        )

        chat_session = client.chats.create(
            model=model_name,
            history=formatted_history,
            config=config
        )

        response = chat_session.send_message(user_message)
        return response.text

    except Exception as e:
        error_msg = str(e)
        if "API_KEY_INVALID" in error_msg or "API key not valid" in error_msg:
            raise ValueError("APIキーが無効です。StreamlitのSecretsの値を確認してください。")
        elif "RESOURCE_EXHAUSTED" in error_msg or "rate limit" in error_msg.lower():
            raise ValueError("APIの利用制限（レート制限）に達しました。しばらく時間を置いてから再度お試しください。")
        else:
            raise RuntimeError(f"通信エラーが発生しました: {e}")

# ==========================================
# サイドバー（設定・履歴管理）
# ==========================================
with st.sidebar:
    st.header("⚙ 設定・履歴管理")
    
    st.subheader("📁 チャット履歴の切り替え")
    chat_names = list(st.session_state.histories.keys())
    selected_chat = st.selectbox("会話を選ぶ", chat_names, index=chat_names.index(current_chat_name) if current_chat_name in chat_names else 0)
    
    if selected_chat != st.session_state.current_chat:
        st.session_state.current_chat = selected_chat
        st.rerun()
        
    new_chat_name = st.text_input("新しいチャット名")
    if st.button("新規チャット作成"):
        if new_chat_name and new_chat_name not in st.session_state.histories:
            st.session_state.histories[new_chat_name] = []
            st.session_state.chat_settings[new_chat_name] = {
                "character_setting": "あなたは聖川真斗です。俺・お前口調で、小説形式で答えてください。( )は心の中、《 》は行動や光景、〈 〉は効果音。語尾に「よ」は使わない。「そっか」ではなく「そうか」を使う。"
            }
            save_data(HISTORY_FILE, st.session_state.histories)
            save_data(SETTINGS_FILE, st.session_state.chat_settings)
            st.session_state.current_chat = new_chat_name
            st.rerun()
        elif new_chat_name in st.session_state.histories:
            st.warning("同名のチャットが既に存在します。")
            
    if st.button("現在のチャットを削除"):
        if len(st.session_state.histories) > 1:
            del st.session_state.histories[st.session_state.current_chat]
            if st.session_state.current_chat in st.session_state.chat_settings:
                del st.session_state.chat_settings[st.session_state.current_chat]
            save_data(HISTORY_FILE, st.session_state.histories)
            save_data(SETTINGS_FILE, st.session_state.chat_settings)
            st.session_state.current_chat = list(st.session_state.histories.keys())[0]
            st.rerun()
        else:
            st.warning("最後のチャットは削除できません。")

    st.subheader("🎭 キャラクター設定")
    current_setting = st.session_state.chat_settings[current_chat_name].get("character_setting", "")
    new_setting = st.text_area("このチャット専用の設定・口調", value=current_setting, height=150)
    if st.button("設定を保存"):
        st.session_state.chat_settings[current_chat_name]["character_setting"] = new_setting
        save_data(SETTINGS_FILE, st.session_state.chat_settings)
        st.success("キャラクター設定を保存しました！")

    st.subheader("🧠 長期記憶")
    new_memory_input = st.text_input("新しい記憶を追加")
    if st.button("記憶を追加する"):
        if new_memory_input.strip():
            st.session_state.saved_memories.append(new_memory_input.strip())
            save_data(MEMORY_FILE, st.session_state.saved_memories)
            st.success("記憶を追加しました！")
            st.rerun()
            
    if st.session_state.saved_memories:
        st.write("【保存されている記憶】")
        for i, mem in enumerate(st.session_state.saved_memories):
            cols = st.columns([4, 1])
            with cols[0]:
                st.markdown(f"- {mem}")
            with cols[1]:
                if st.button("削除", key=f"del_mem_{i}"):
                    st.session_state.saved_memories.pop(i)
                    save_data(MEMORY_FILE, st.session_state.saved_memories)
                    st.rerun()

# ==========================================
# メイン画面（チャット・編集・再生成）
# ==========================================
st.title("💬 自分専用・AIチャット")
st.caption(f"現在のチャット: **{current_chat_name}**")

if current_chat_name not in st.session_state.histories:
    st.session_state.histories[current_chat_name] = []

current_messages = st.session_state.histories[current_chat_name]

st.divider()

# 履歴の表示と個別編集機能
for i, msg in enumerate(current_messages):
    avatar = "👤" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])
        
        edit_key = f"edit_mode_{current_chat_name}_{i}"
        if st.button("✏️ 編集", key=f"btn_edit_{current_chat_name}_{i}"):
            st.session_state[edit_key] = not st.session_state.get(edit_key, False)
            st.rerun()
            
        if st.session_state.get(edit_key, False):
            edited_content = st.text_area("内容を修正して更新", value=msg["content"], key=f"text_edit_{current_chat_name}_{i}")
            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.button("💾 更新を保存", key=f"save_btn_{current_chat_name}_{i}"):
                    if msg["role"] == "user":
                        current_messages = current_messages[:i]
                        current_messages.append({"role": "user", "content": edited_content})
                        
                        system_prompt = st.session_state.chat_settings[current_chat_name].get("character_setting", "")
                        with st.spinner("AIが返答を生成中..."):
                            try:
                                reply = generate_response(
                                    system_prompt,
                                    st.session_state.saved_memories,
                                    current_messages[:-1],
                                    edited_content
                                )
                                current_messages.append({"role": "assistant", "content": reply})
                            except Exception as e:
                                st.error(str(e))
                    else:
                        current_messages[i]["content"] = edited_content
                        
                    st.session_state.histories[current_chat_name] = current_messages
                    save_data(HISTORY_FILE, st.session_state.histories)
                    st.session_state[edit_key] = False
                    st.rerun()
            with col_cancel:
                if st.button("❌ キャンセル", key=f"cancel_btn_{current_chat_name}_{i}"):
                    st.session_state[edit_key] = False
                    st.rerun()

st.divider()

# 一括操作ボタン
col_b1, col_b2, col_b3 = st.columns(3)
with col_b1:
    if st.button("🔄 最後の返答を再生成") and len(current_messages) >= 2:
        if current_messages[-1]["role"] == "assistant":
            last_assistant = current_messages.pop()
            last_user = current_messages[-1]["content"]
            
            system_prompt = st.session_state.chat_settings[current_chat_name].get("character_setting", "")
            with st.spinner("AIが新しい返答を生成中..."):
                try:
                    reply = generate_response(
                        system_prompt,
                        st.session_state.saved_memories,
                        current_messages[:-1],
                        last_user
                    )
                    current_messages.append({"role": "assistant", "content": reply})
                    save_data(HISTORY_FILE, st.session_state.histories)
                    st.rerun()
                except Exception as e:
                    current_messages.append(last_assistant)
                    st.error(str(e))
with col_b2:
    if st.button("↩ 1往復取り消し") and current_messages:
        current_messages.pop()
        if current_messages and current_messages[-1]["role"] == "assistant":
            current_messages.pop()
        save_data(HISTORY_FILE, st.session_state.histories)
        st.rerun()
with col_b3:
    if st.button("🗑️ 履歴クリア"):
        current_messages.clear()
        save_data(HISTORY_FILE, st.session_state.histories)
        st.rerun()

# チャット入力欄（スマホでの改行および複数行入力対応）
st.subheader("✉️ メッセージ送信")
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_area(
        "メッセージを入力（スマホのキーボードで改行可能・送信ボタンを押してください）",
        height=120,
        key="input_text_area",
        placeholder="ここに文章を入力してください。複数行の改行も可能です。"
    )
    submit_button = st.form_submit_button(label="送信")

if submit_button and user_input.strip():
    prompt = user_input.strip()
    current_messages.append({"role": "user", "content": prompt})
    save_data(HISTORY_FILE, st.session_state.histories)
    
    with st.spinner("思考中..."):
        try:
            system_prompt = st.session_state.chat_settings[current_chat_name].get("character_setting", "")
            reply = generate_response(
                system_prompt,
                st.session_state.saved_memories,
                current_messages[:-1],
                prompt
            )
            current_messages.append({"role": "assistant", "content": reply})
            save_data(HISTORY_FILE, st.session_state.histories)
            st.rerun()
        except Exception as e:
            current_messages.pop()
            st.error(str(e))
