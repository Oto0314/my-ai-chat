import streamlit as st
import json
import os

st.set_page_config(page_title="自分専用・無制限AIチャット", page_icon="💬", layout="wide")

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
    st.header("📁 チャット履歴の管理")
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

    st.subheader("🧠 長期記憶・パーソナライズ")
    new_memory_input = st.text_input("新しい記憶を追加")
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

for msg in current_messages:
    avatar = "👤" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])

if prompt := st.chat_input("メッセージを入力..."):
    current_messages.append({"role": "user", "content": prompt})
    save_data(HISTORY_FILE, st.session_state.histories)
    
    with st.chat_message("user", avatar="👤"):
        st.write(prompt)
        
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("思考中..."):
            reply = f"「{prompt}」だな。しっかり受け止めたぞ、詩音。"
            st.write(reply)
            current_messages.append({"role": "assistant", "content": reply})
            save_data(HISTORY_FILE, st.session_state.histories)

    else:
        current_messages.append({"role": "user", "content": prompt})
        save_data(HISTORY_FILE, st.session_state.histories)
        
        with st.chat_message("user", avatar="👤"):
            st.write(prompt)
            
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("思考中..."):
                try:
                    genai.configure(api_key=api_key)
                    
                    gemini_history = []
                    for m in current_messages[:-1]:
                        role = "user" if m["role"] == "user" else "model"
                        gemini_history.append({"role": role, "parts": [m["content"]]})
                        
                    model = genai.GenerativeModel(
                        model_name=model_name,
                        system_instruction=full_system_instruction if full_system_instruction else None
                    )
                    
                    chat = model.start_chat(history=gemini_history)
                    response = chat.send_message(prompt)
                    reply = response.text
                except Exception as e:
                    reply = f"エラーが発生しました: {e}"
                
                st.write(reply)
                current_messages.append({"role": "assistant", "content": reply})
                save_data(HISTORY_FILE, st.session_state.histories)
