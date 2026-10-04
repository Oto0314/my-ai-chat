import streamlit as st
import json
import os
from google import genai
from google.genai import types

# ページの設定
st.set_page_config(
    page_title="自分専用・AIチャット",
    page_icon="💬",
    layout="centered"
)

# ファイル名定数
HISTORY_FILE = "chat_histories.json"
SETTINGS_FILE = "chat_settings.json"

def load_data(filename, default_value):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default_value
    return default_value

def save_data(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception:
        pass

# セッション状態の初期化
if "histories" not in st.session_state:
    st.session_state.histories = load_data(HISTORY_FILE, {"デフォルト": []})

if "current_chat" not in st.session_state:
    chat_keys = list(st.session_state.histories.keys())
    st.session_state.current_chat = chat_keys[0] if chat_keys else "デフォルト"

if "chat_settings" not in st.session_state:
    st.session_state.chat_settings = load_data(SETTINGS_FILE, {})

current_chat_name = st.session_state.current_chat
if current_chat_name not in st.session_state.chat_settings:
    st.session_state.chat_settings[current_chat_name] = {
        "character_setting": "あなたは聖川真斗です。俺・お前口調で、小説形式で答えてください。( )は心の中、《 》は行動や光景、〈 〉は効果音。語尾に「よ」は使わない。「そっか」ではなく「そうか」を使う。"
    }

# ==========================================
# 【Gemini API 通信関数（最新SDK・完全安定版）】
# ==========================================
def generate_ai_response(system_prompt, history, user_message):
    api_key = None
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
    elif "general" in st.secrets and "GEMINI_API_KEY" in st.secrets["general"]:
        api_key = st.secrets["general"]["GEMINI_API_KEY"]

    if not api_key:
        raise ValueError("APIキーが設定されていません。StreamlitのSecretsを確認してください。")

    try:
        client = genai.Client(api_key=api_key)

        # 履歴の構築
        formatted_history = []
        for m in history[-15:]: # 直近15件に制限して安定化
            r = "user" if m["role"] == "user" else "model"
            formatted_history.append(
                types.Content(
                    role=r,
                    parts=[types.Part.from_text(text=m["content"])]
                )
            )

        # チャットセッション開始
        chat = client.chats.create(
            model="gemini-2.5-flash",
            history=formatted_history,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
            )
        )

        response = chat.send_message(user_message)
        return response.text

    except Exception as e:
        raise RuntimeError(f"API通信エラー: {str(e)}")

# ==========================================
# サイドバー
# ==========================================
with st.sidebar:
    st.header("⚙ 設定")
    
    chat_names = list(st.session_state.histories.keys())
    selected_chat = st.selectbox("チャットを選ぶ", chat_names, index=chat_names.index(current_chat_name) if current_chat_name in chat_names else 0)
    
    if selected_chat != st.session_state.current_chat:
        st.session_state.current_chat = selected_chat
        st.rerun()
        
    new_name = st.text_input("新しいチャット名")
    if st.button("作成"):
        if new_name and new_name not in st.session_state.histories:
            st.session_state.histories[new_name] = []
            st.session_state.chat_settings[new_name] = {
                "character_setting": "あなたは聖川真斗です。俺・お前口調で、小説形式で答えてください。( )は心の中、《 》は行動や光景、〈 〉は効果音。語尾に「よ」は使わない。「そっか」ではなく「そうか」を使う。"
            }
            save_data(HISTORY_FILE, st.session_state.histories)
            save_data(SETTINGS_FILE, st.session_state.chat_settings)
            st.session_state.current_chat = new_name
            st.rerun()

    st.subheader("キャラクター設定")
    current_setting = st.session_state.chat_settings[current_chat_name].get("character_setting", "")
    new_setting = st.text_area("口調・設定", value=current_setting, height=120)
    if st.button("設定を保存"):
        st.session_state.chat_settings[current_chat_name]["character_setting"] = new_setting
        save_data(SETTINGS_FILE, st.session_state.chat_settings)
        st.success("保存しました！")

    if st.button("🗑️ 履歴をクリア"):
        st.session_state.histories[current_chat_name] = []
        save_data(HISTORY_FILE, st.session_state.histories)
        st.rerun()

# ==========================================
# メイン画面
# ==========================================
st.title("💬 自分専用・AIチャット")
st.caption(f"現在のチャット: **{current_chat_name}**")

if current_chat_name not in st.session_state.histories:
    st.session_state.histories[current_chat_name] = []

messages = st.session_state.histories[current_chat_name]

# 履歴の表示
for msg in messages:
    avatar = "👤" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])

st.divider()

# チャット入力欄（スマホでの改行・複数行入力対応のフォーム）
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_area(
        "メッセージを入力（改行可能・送信ボタンを押してください）",
        height=100,
        placeholder="ここに文章を入力..."
    )
    submit_btn = st.form_submit_button(label="送信")

if submit_btn and user_input.strip():
    prompt = user_input.strip()
    messages.append({"role": "user", "content": prompt})
    save_data(HISTORY_FILE, st.session_state.histories)
    
    with st.spinner("思考中..."):
        try:
            system_prompt = st.session_state.chat_settings[current_chat_name].get("character_setting", "")
            reply = generate_ai_response(system_prompt, messages[:-1], prompt)
            messages.append({"role": "assistant", "content": reply})
            save_data(HISTORY_FILE, st.session_state.histories)
            st.rerun()
        except Exception as e:
            messages.pop() # エラー時はユーザー入力を戻す
            st.error(str(e))
