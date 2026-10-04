import streamlit as st
import requests

st.set_page_config(page_title="自分専用・無制限AIチャット", page_icon="💬", layout="wide")

st.markdown("""
<style>
.stChatMessage { padding: 0.8rem 1rem; border-radius: 12px; margin-bottom: 0.8rem; }
div[data-testid="stChatMessage"]:has(div[aria-label="Chat message from user"]) { background-color: #f0f4f9; border-left: 4px solid #4a90e2; }
div[data-testid="stChatMessage"]:has(div[aria-label="Chat message from assistant"]) { background-color: #ffffff; border-left: 4px solid #2c3e50; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
</style>
""", unsafe_allow_html=True)

st.title("💬 自分専用・無制限AIチャット")

if "chats" not in st.session_state:
    st.session_state.chats = {"新しいチャット": []}
if "current_chat" not in st.session_state:
    st.session_state.current_chat = "新しいチャット"

with st.sidebar:
    st.header("⚙️ 設定 & 履歴")
    api_key = st.text_input("OpenRouter API Key", type="password")
    model_name = st.text_input("モデル名", value="nousresearch/hermes-3-llama-3.1-70b:free")
    
    st.subheader("キャラクター設定")
    system_prompt = st.text_area("キャラ付け・口調など", value="", height=120)
    
    st.subheader("長期記憶・コンテキスト")
    long_term_memory = st.text_area("ユーザー設定や思い出など", value="", height=120)
    
    st.divider()
    chat_titles = list(st.session_state.chats.keys())
    selected_chat = st.selectbox("会話を選ぶ", chat_titles, index=chat_titles.index(st.session_state.current_chat))
    if selected_chat != st.session_state.current_chat:
        st.session_state.current_chat = selected_chat
        st.rerun()
        
    new_chat_title = st.text_input("新しいチャット名", placeholder="例：甘い時間")
    if st.button("➕ 新規チャット作成"):
        if new_chat_title and new_chat_title not in st.session_state.chats:
            st.session_state.chats[new_chat_title] = []
            st.session_state.current_chat = new_chat_title
            st.rerun()
            
    if st.button("🗑️ 現在の履歴をクリア"):
        st.session_state.chats[st.session_state.current_chat] = []
        st.rerun()

messages = st.session_state.chats[st.session_state.current_chat]

full_system_instruction = ""
if system_prompt:
    full_system_instruction += f"【キャラクター設定】\n{system_prompt}\n\n"
if long_term_memory:
    full_system_instruction += f"【長期記憶・コンテキスト】\n{long_term_memory}\n\n"

def generate_response():
    api_messages = []
    if full_system_instruction:
        api_messages.append({"role": "system", "content": full_system_instruction})
    for m in messages:
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

for msg in messages:
    avatar = "👤" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])

if "editing" not in st.session_state:
    st.session_state.editing = False

if len(messages) > 0:
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("🔄 再試行"):
            if messages[-1]["role"] == "assistant":
                messages.pop()
            if len(messages) > 0 and messages[-1]["role"] == "user":
                with st.spinner("思考中..."):
                    new_reply = generate_response()
                    messages.append({"role": "assistant", "content": new_reply})
                st.rerun()
    with col2:
        if st.button("↩️ 取消"):
            if len(messages) >= 2:
                messages.pop()
                messages.pop()
                st.rerun()
            elif len(messages) == 1:
                messages.pop()
                st.rerun()
    with col3:
        if st.button("✏️ 直前を編集"):
            if len(messages) > 0:
                st.session_state.editing = True
                st.rerun()

if st.session_state.editing and len(messages) > 0:
    st.markdown("---")
    st.write("**直前のメッセージを編集する**")
    last_user_idx = -1
    for i in range(len(messages)-1, -1, -1):
        if messages[i]["role"] == "user":
            last_user_idx = i
            break
    
    if last_user_idx != -1:
        edit_text = st.text_area("修正内容", value=messages[last_user_idx]["content"])
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            if st.button("更新して送信"):
                while len(messages) > last_user_idx:
                    messages.pop()
                messages.append({"role": "user", "content": edit_text})
                st.session_state.editing = False
                with st.spinner("思考中..."):
                    reply = generate_response()
                    messages.append({"role": "assistant", "content": reply})
                st.rerun()
        with col_e2:
            if st.button("キャンセル"):
                st.session_state.editing = False
                st.rerun()

if not st.session_state.editing:
    if prompt := st.chat_input("メッセージを入力..."):
        if not api_key:
            st.error("サイドバーで OpenRouter API Key を入力してください。")
        else:
            messages.append({"role": "user", "content": prompt})
            st.rerun()

    if len(messages) > 0 and messages[-1]["role"] == "user":
        with st.spinner("思考中..."):
            reply = generate_response()
            messages.append({"role": "assistant", "content": reply})
        st.rerun()

    st.rerun()
