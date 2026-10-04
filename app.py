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
    st.header("⚙ 設定・履歴管理")
    
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

# 操作ボタンエリア（1個戻る・再思考・全削除など）
col_b1, col_b2, col_b3 = st.columns(3)
with col_b1:
    if st.button("↩ 1個戻る") and current_messages:
        current_messages.pop()
        if current_messages and current_messages[-1]["role"] == "assistant":
            current_messages.pop()
        save_data(HISTORY_FILE, st.session_state.histories)
        st.rerun()
with col_b2:
    if st.button("🔄 再思考（直前やり直し）") and len(current_messages) >= 2:
        current_messages.pop() # アシスタントの返答を削除
        save_data(HISTORY_FILE, st.session_state.histories)
        st.rerun()
with col_b3:
    if st.button("🗑️ 履歴を全クリア"):
        current_messages.clear()
        save_data(HISTORY_FILE, st.session_state.histories)
        st.rerun()

st.divider()

for i, msg in enumerate(current_messages):
    avatar = "👤" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])
        
        # 編集機能
        if st.button("✏️ 編集", key=f"edit_btn_{i}"):
            st.session_state[f"is_editing_{i}"] = True
            
        if st.session_state.get(f"is_editing_{i}", False):
            new_text = st.text_area("内容を修正", value=msg["content"], key=f"edit_text_{i}")
            if st.button("保存して更新", key=f"save_edit_{i}"):
                current_messages[i]["content"] = new_text
                # 以降の履歴を切り詰める場合などの処理
                save_data(HISTORY_FILE, st.session_state.histories)
                st.session_state[f"is_editing_{i}"] = False
                st.rerun()

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
