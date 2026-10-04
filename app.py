import streamlit as st
import json
import os
import google.generativeai as genai

st.set_page_config(page_title="自分専用・無制限AIチャット", page_icon="💬", layout="wide")

st.markdown("""
<style>
.stChatMessage { padding: 0.8rem 1rem; border-radius: 12px; margin-bottom: 0.8rem; }
div[data-testid="stChatMessage"]:has(div[aria-label="Chat message from user"]) { background-color: #f0f4f9; border-left: 4px solid #4a90e2; }
div[data-testid="stChatMessage"]:has(div[aria-label="Chat message from assistant"]) { background-color: #ffffff; border-left: 4px solid #2c3e50; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
</style>
""", unsafe_allow_html=True)

HISTORY_FILE = "chat_histories.json"
MEMORY_FILE = "user_memory_list.json"

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

if "saved_memories" not in st.session_state:
    st.session_state.saved_memories = load_data(MEMORY_FILE, [])

st.title("💬 自分専用・無制限AIチャット")

with st.sidebar:
    st.header("⚙ 設定・履歴管理")
    api_key = st.text_input("Google AI Studio API Key", type="password")
    model_name = st.selectbox("モデル選択", ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"])
    
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
    
    st.subheader("🧠 パーソナライズ・長期記憶")
    new_memory_input = st.text_input("新しい記憶・設定を追加")
    if st.button("記憶を追加する"):
        if new_memory_input.strip():
            st.session_state.saved_memories.append(new_memory_input.strip())
            save_data(MEMORY_FILE, st.session_state.saved_memories)
            st.success("記憶を追加しました！")
            st.rerun()
            
    if st.session_state.saved_memories:
        st.write("【保存されている記憶一覧】")
        for i, mem in enumerate(st.session_state.saved_memories):
            cols = st.columns([4, 1])
            with cols[0]:
                st.markdown(f"- {mem}")
            with cols[1]:
                if st.button("削除", key=f"del_mem_{i}"):
                    st.session_state.saved_memories.pop(i)
                    save_data(MEMORY_FILE, st.session_state.saved_memories)
                    st.rerun()

if st.session_state.current_chat not in st.session_state.histories:
    st.session_state.histories[st.session_state.current_chat] = []

current_messages = st.session_state.histories[st.session_state.current_chat]

full_system_instruction = ""
if system_prompt:
    full_system_instruction += f"【キャラクター設定】\n{system_prompt}\n\n"
if st.session_state.saved_memories:
    full_system_instruction += f"【長期記憶・パーソナライズ】\n" + "\n".join([f"- {m}" for m in st.session_state.saved_memories]) + "\n\n"

def generate_response():
    try:
        genai.configure(api_key=api_key)
        
        gemini_history = []
        for m in current_messages:
            role = "user" if m["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [m["content"]]})
            
        history_part = gemini_history[:-1] if len(gemini_history) > 0 else []
        latest_user_message = gemini_history[-1]["parts"][0] if len(gemini_history) > 0 else ""
        
        generation_config = {}
        if full_system_instruction:
            generation_config["system_instruction"] = full_system_instruction
            
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=full_system_instruction if full_system_instruction else None
        )
        
        chat = model.start_chat(history=history_part)
        response = chat.send_message(latest_user_message)
        return response.text
    except Exception as e:
        return f"エラーが発生しました: {e}"

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

with st.form(key="chat_form", clear_on_submit=True):
    prompt = st.text_area("メッセージを入力...", placeholder="Shift+Enter等で改行できます", height=80)
    submit_button = st.form_submit_button("送信")

if submit_button and prompt:
    if not api_key:
        st.error("サイドバーで Google AI Studio API Key を入力してください。")
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
    
    st.subheader("🧠 パーソナライズ・長期記憶")
    new_memory_input = st.text_input("新しい記憶・設定を追加")
    if st.button("記憶を追加する"):
        if new_memory_input.strip():
            st.session_state.saved_memories.append(new_memory_input.strip())
            save_data(MEMORY_FILE, st.session_state.saved_memories)
            st.success("記憶を追加しました！")
            st.rerun()
            
    if st.session_state.saved_memories:
        st.write("【保存されている記憶一覧】")
        for i, mem in enumerate(st.session_state.saved_memories):
            cols = st.columns([4, 1])
            with cols[0]:
                st.markdown(f"- {mem}")
            with cols[1]:
                if st.button("削除", key=f"del_mem_{i}"):
                    st.session_state.saved_memories.pop(i)
                    save_data(MEMORY_FILE, st.session_state.saved_memories)
                    st.rerun()

if st.session_state.current_chat not in st.session_state.histories:
    st.session_state.histories[st.session_state.current_chat] = []

current_messages = st.session_state.histories[st.session_state.current_chat]

full_system_instruction = ""
if system_prompt:
    full_system_instruction += f"【キャラクター設定】\n{system_prompt}\n\n"
if st.session_state.saved_memories:
    full_system_instruction += f"【長期記憶・パーソナライズ】\n" + "\n".join([f"- {m}" for m in st.session_state.saved_memories]) + "\n\n"

def generate_response():
    try:
        genai.configure(api_key=api_key)
        
        # 履歴を変換
        gemini_history = []
        for m in current_messages:
            role = "user" if m["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [m["content"]]})
            
        # 最新のメッセージを除いたものを履歴とする
        history_part = gemini_history[:-1] if len(gemini_history) > 0 else []
        latest_user_message = gemini_history[-1]["parts"][0] if len(gemini_history) > 0 else ""
        
        generation_config = {}
        if full_system_instruction:
            generation_config["system_instruction"] = full_system_instruction
            
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=full_system_instruction if full_system_instruction else None
        )
        
        chat = model.start_chat(history=history_part)
        response = chat.send_message(latest_user_message)
        return response.text
    except Exception as e:
        return f"エラーが発生しました: {e}"

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

with st.form(key="chat_form", clear_on_submit=True):
    prompt = st.text_area("メッセージを入力...", placeholder="Shift+Enter等で改行できます", height=80)
    submit_button = st.form_submit_button("送信")

if submit_button and prompt:
    if not api_key:
        st.error("サイドバーで Google AI Studio API Key を入力してください。")
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

