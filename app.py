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

with st.sidebar:
    st.header("⚙️ 設定")
    api_key = st.text_input("OpenRouter API Key", type="password")
    model_name = st.text_input("モデル名", value="nousresearch/hermes-3-llama-3.1-70b:free")
    
    st.subheader("キャラクター設定")
    system_prompt = st.text_area("キャラ付け・口調など", value="", height=120)
    
    st.subheader("長期記憶・コンテキスト")
    long_term_memory = st.text_area("ユーザー設定や思い出など", value="", height=120)
    
    if st.button("チャット履歴を全消去"):
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

full_system_instruction = ""
if system_prompt:
    full_system_instruction += f"【キャラクター設定】\n{system_prompt}\n\n"
if long_term_memory:
    full_system_instruction += f"【長期記憶・コンテキスト】\n{long_term_memory}\n\n"

def generate_response():
    api_messages = []
    if full_system_instruction:
        api_messages.append({"role": "system", "content": full_system_instruction})
    for m in st.session_state.messages:
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

for msg in st.session_state.messages:
    avatar = "👤" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])

if len(st.session_state.messages) > 0:
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🔄 最後の返答を再試行"):
            if st.session_state.messages[-1]["role"] == "assistant":
                st.session_state.messages.pop()
            if len(st.session_state.messages) > 0 and st.session_state.messages[-1]["role"] == "user":
                with st.spinner("思考中..."):
                    new_reply = generate_response()
                    st.session_state.messages.append({"role": "assistant", "content": new_reply})
                st.rerun()
    with col2:
        if st.button("↩️ 1つのやり取りを取消"):
            if len(st.session_state.messages) >= 2:
                st.session_state.messages.pop()
                st.session_state.messages.pop()
                st.rerun()
            elif len(st.session_state.messages) == 1:
                st.session_state.messages.pop()
                st.rerun()

if prompt := st.chat_input("メッセージを入力..."):
    if not api_key:
        st.error("サイドバーで OpenRouter API Key を入力してください。")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.rerun()

if len(st.session_state.messages) > 0 and st.session_state.messages[-1]["role"] == "user":
    with st.spinner("思考中..."):
        reply = generate_response()
        st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()


if len(st.session_state.messages) > 0 and st.session_state.messages[-1]["role"] == "user":
    with st.spinner("思考中..."):
        reply = generate_response()
        st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()

