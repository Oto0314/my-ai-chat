import streamlit as st
import requests
import json
import os

st.set_page_config(page_title="自分専用・無制限AIチャット", page_icon="💬", layout="wide")

st.markdown("""
<style>
.stChatMessage { padding: 0.8rem 1rem; border-radius: 12px; margin-bottom: 0.8rem; }
div[data-testid="stChatMessage"]:has(div[aria-label="Chat message from user"]) { background-color: #f0f4f9; border-left: 4px solid #4a90e2; }
div[data-testid="stChatMessage"]:has(div[aria-label="Chat message from assistant"]) { background-color: #ffffff; border-left: 4px solid #2c3e50; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
</style>
""", unsafe_allow_html=True)

# 履歴保存用のファイルパス
HISTORY_FILE = "chat_histories.json"
MEMORY_FILE = "user_memory.json"

def load_data(filename, default_value):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default_value
    return default_value

def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if "histories" not in st.session_state:
    st.session_state.histories = load_data(HISTORY_FILE, {"デフォルト": []})

if "current_chat" not in st.session_state:
    chat_keys = list(st.session_state.histories.keys())
    st.session_state.current_chat = chat_keys[0] if chat_keys else "デフォルト"

if "saved_memory" not in st.session_state:
    st.session_state.saved_memory = load_data(MEMORY_FILE, {"memory": ""})

st.title("💬 自分専用・無制限AIチャット")

with st.sidebar:
    st.header("⚙️ 設定・履歴管理")
    api_key = st.text_input("OpenRouter API Key", type="password")
    model_name = st.text_input("モデル名", value="openrouter/free")
    
    st.subheader("📁 チャット履歴の切り替え")
    chat_names = list(st.session_state.histories.keys())
    selected_chat = st.selectbox("会話を選ぶ", chat_names, index=chat_names.index(st.session_state.current_chat) if st.session_state.current_chat in chat_names else 0)
    
    if selected_chat != st.session_state.current_chat:
        st.session_state.current_chat = selected_chat
        st.rerun()
        
    new_chat_name = st.text_input("新しいチャット名")
    if st.button("新規チャット作成"):
        if new_chat_name and new_chat_name not in st.session_state.histories:
            st.session_state.histories[new_chat_name] = []
            save_data(HISTORY_FILE, st.session_state.histories)
            st.session_state.current_chat = new_chat_name
            st.rerun()
            
    if st.button("現在のチャットを削除"):
        if len(st.session_state.histories) > 1:
            del st.session_state.histories[st.session_state.current_chat]
            save_data(HISTORY_FILE, st.session_state.histories)
            st.session_state.current_chat = list(st.session_state.histories.keys())[0]
            st.rerun()
        else:
            st.warning("最後のチャットは削除できません。")

    st.subheader("キャラクター設定")
    system_prompt = st.text_area("キャラ付け・口調など", value="", height=100)
    
    st.subheader("長期記憶・パーソナライズ保存")
    current_memory_text = st.session_state.saved_memory.get("memory", "")
    updated_memory = st.text_area("随時追加できる思い出・設定", value=current_memory_text, height=120)
    if st.button("記憶を保存する"):
        st.session_state.saved_memory["memory"] = updated_memory
        save_data(MEMORY_FILE, st.session_state.saved_memory)
        st.success("記憶を保存しました！")

if st.session_state.current_chat not in st.session_state.histories:
    st.session_state.histories[st.session_state.current_chat] = []

current_messages = st.session_state.histories[st.session_state.current_chat]

full_system_instruction = ""
if system_prompt:
    full_system_instruction += f"【キャラクター設定】\n{system_prompt}\n\n"
if st.session_state.saved_memory.get("memory"):
    full_system_instruction += f"【長期記憶・パーソナライズ】\n{st.session_state.saved_memory['memory']}\n\n"

def generate_response():
    api_messages = []
    if full_system_instruction:
        api_messages.append({"role": "system", "content": full_system_instruction})
    for m in current_messages:
        api_messages.append({"role": m["role"], "content": m["content"]})
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model_name,
        "messages": api_messages
    }
    
    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        res_json = response.json()
        if "choices" in res_json and len(res_json["choices"]) > 0:
            return res_json["choices"][0]["message"]["content"]
        elif "error" in res_json:
            return f"エラーが発生しました: {res_json['error'].get('message', '不明なエラー')}"
        else:
            return "応答を取得できませんでした。"
    except Exception as e:
        return f"通信エラーが発生しました: {e}"

for msg in current_messages:
    avatar = "👤" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])

if len(current_messages) > 0:
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🔄 最後の返答を再試行"):
            if current_messages[-1]["role"] == "assistant":
                current_messages.pop()
            if len(current_messages) > 0 and current_messages[-1]["role"] == "user":
                with st.spinner("思考中..."):
                    new_reply = generate_response()
                    current_messages.append({"role": "assistant", "content": new_reply})
                    save_data(HISTORY_FILE, st.session_state.histories)
                st.rerun()
    with col2:
        if st.button("↩️ 1つのやり取りを取消"):
            if len(current_messages) >= 2:
                current_messages.pop()
                current_messages.pop()
                save_data(HISTORY_FILE, st.session_state.histories)
                st.rerun()
            elif len(current_messages) == 1:
                current_messages.pop()
                save_data(HISTORY_FILE, st.session_state.histories)
                st.rerun()

if prompt := st.chat_input("メッセージを入力..."):
    if not api_key:
        st.error("サイドバーで OpenRouter API Key を入力してください。")
    else:
        current_messages.append({"role": "user", "content": prompt})
        save_data(HISTORY_FILE, st.session_state.histories)
        st.rerun()

if len(current_messages) > 0 and current_messages[-1]["role"] == "user":
    with st.spinner("思考中..."):
        reply = generate_response()
        current_messages.append({"role": "assistant", "content": reply})
        save_data(HISTORY_FILE, st.session_state.histories)
    st.rerun()


if len(st.session_state.messages) > 0 and st.session_state.messages[-1]["role"] == "user":
    with st.spinner("思考中..."):
        reply = generate_response()
        st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()

