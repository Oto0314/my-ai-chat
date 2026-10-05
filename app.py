import streamlit as st
import requests
import json
import os
import uuid

# =========================================================
# 基本設定
# =========================================================

st.set_page_config(
    page_title="My AI Chat",
    page_icon="💬",
    layout="centered"
)

MODEL = "gemini-3.8-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

CHAT_FILE = "chat_histories.json"
SETTING_FILE = "chat_settings.json"
MEMORY_FILE = "user_memory.json"


# =========================================================
# ファイル保存
# =========================================================

def load_json(filename, default):
    try:
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =========================================================
# 初期データ
# =========================================================

if "chats" not in st.session_state:
    st.session_state.chats = load_json(CHAT_FILE, {})

if "settings" not in st.session_state:
    st.session_state.settings = load_json(
        SETTING_FILE,
        {
            "character_name": "AI",
            "character_setting": (
                "あなたはユーザーと自然な会話をするキャラクターです。"
                "ユーザーとの会話を大切にし、設定されたキャラクター性を維持してください。"
            )
        }
    )

if "memory" not in st.session_state:
    st.session_state.memory = load_json(MEMORY_FILE, [])

if "current_chat" not in st.session_state:
    if st.session_state.chats:
        st.session_state.current_chat = list(st.session_state.chats.keys())[0]
    else:
        chat_id = str(uuid.uuid4())
        st.session_state.chats[chat_id] = {
            "title": "新しいチャット",
            "messages": []
        }
        st.session_state.current_chat = chat_id
        save_json(CHAT_FILE, st.session_state.chats)


# =========================================================
# API
# =========================================================

def get_api_key():
    try:
        key = st.secrets["GEMINI_API_KEY"]
        return key.strip()
    except Exception:
        return ""


def call_gemini(messages, character_setting, memories):
    api_key = get_api_key()

    if not api_key:
        return None, "GEMINI_API_KEY が設定されていません。"

    # システム指示
    memory_text = ""

    if memories:
        memory_text = (
            "\n\n【長期記憶】\n"
            + "\n".join(f"- {m}" for m in memories)
        )

    system_text = character_setting + memory_text

    # Gemini用の会話履歴
    contents = []

    for message in messages:
        role = message.get("role")

        if role == "user":
            gemini_role = "user"
        elif role == "assistant":
            gemini_role = "model"
        else:
            continue

        contents.append(
            {
                "role": gemini_role,
                "parts": [
                    {
                        "text": message.get("content", "")
                    }
                ]
            }
        )

    if not contents:
        return None, "会話内容がありません。"

    payload = {
        "system_instruction": {
            "parts": [
                {
                    "text": system_text
                }
            ]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.9,
            "maxOutputTokens": 4096
        }
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }

    try:
        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

        if response.status_code != 200:
            try:
                error_data = response.json()
                return None, (
                    f"Gemini APIエラー\n"
                    f"HTTP {response.status_code}\n\n"
                    f"{json.dumps(error_data, ensure_ascii=False, indent=2)}"
                )
            except Exception:
                return None, (
                    f"Gemini APIエラー\n"
                    f"HTTP {response.status_code}\n\n"
                    f"{response.text}"
                )

        data = response.json()

        candidates = data.get("candidates", [])

        if not candidates:
            return None, "Geminiから回答候補が返ってきませんでした。"

        candidate = candidates[0]

        content = candidate.get("content", {})
        parts = content.get("parts", [])

        text_parts = []

        for part in parts:
            if "text" in part:
                text_parts.append(part["text"])

        answer = "".join(text_parts).strip()

        if not answer:
            return None, "Geminiから空の回答が返ってきました。"

        return answer, None

    except requests.exceptions.Timeout:
        return None, "Geminiへの通信が60秒以内に完了しませんでした。"

    except requests.exceptions.RequestException as e:
        return None, f"通信エラー:\n{str(e)}"

    except Exception as e:
        return None, f"予期しないエラー:\n{str(e)}"


# =========================================================
# 保存
# =========================================================

def save_all():
    save_json(CHAT_FILE, st.session_state.chats)
    save_json(SETTING_FILE, st.session_state.settings)
    save_json(MEMORY_FILE, st.session_state.memory)


# =========================================================
# チャット操作
# =========================================================

def create_chat():
    chat_id = str(uuid.uuid4())

    st.session_state.chats[chat_id] = {
        "title": "新しいチャット",
        "messages": []
    }

    st.session_state.current_chat = chat_id

    save_json(CHAT_FILE, st.session_state.chats)


def delete_chat(chat_id):
    if chat_id in st.session_state.chats:
        del st.session_state.chats[chat_id]

    if not st.session_state.chats:
        create_chat()
        return

    if st.session_state.current_chat == chat_id:
        st.session_state.current_chat = list(
            st.session_state.chats.keys()
        )[0]

    save_json(CHAT_FILE, st.session_state.chats)


def clear_current_chat():
    chat = st.session_state.chats[st.session_state.current_chat]
    chat["messages"] = []
    chat["title"] = "新しいチャット"
    save_json(CHAT_FILE, st.session_state.chats)


def regenerate_from(index):
    chat = st.session_state.chats[st.session_state.current_chat]
    messages = chat["messages"]

    # 指定位置より後ろを削除
    messages = messages[:index]

    if not messages:
        return

    # 最後がユーザー発言である状態にする
    if messages[-1]["role"] != "user":
        return

    answer, error = call_gemini(
        messages,
        st.session_state.settings["character_setting"],
        st.session_state.memory
    )

    if error:
        st.error(error)
        return

    messages.append(
        {
            "role": "assistant",
            "content": answer
        }
    )

    chat["messages"] = messages
    save_json(CHAT_FILE, st.session_state.chats)

    st.rerun()


# =========================================================
# サイドバー
# =========================================================

with st.sidebar:

    st.title("チャット")

    if st.button(
        "＋ 新しいチャット",
        use_container_width=True
    ):
        create_chat()
        st.rerun()

    st.divider()

    chat_ids = list(st.session_state.chats.keys())

    for chat_id in chat_ids:

        chat = st.session_state.chats[chat_id]

        title = chat.get("title", "新しいチャット")

        col1, col2 = st.columns([4, 1])

        with col1:
            if st.button(
                title,
                key=f"select_{chat_id}",
                use_container_width=True
            ):
                st.session_state.current_chat = chat_id
                st.rerun()

        with col2:
            if st.button(
                "×",
                key=f"delete_{chat_id}"
            ):
                delete_chat(chat_id)
                st.rerun()

    st.divider()

    st.subheader("キャラクター設定")

    character_name = st.text_input(
        "名前",
        value=st.session_state.settings["character_name"]
    )

    character_setting = st.text_area(
        "キャラクター設定",
        value=st.session_state.settings["character_setting"],
        height=180
    )

    if st.button(
        "設定を保存",
        use_container_width=True
    ):
        st.session_state.settings["character_name"] = character_name
        st.session_state.settings["character_setting"] = character_setting
        save_all()
        st.success("保存しました")

    st.divider()

    st.subheader("長期記憶")

    new_memory = st.text_area(
        "覚えておいてほしいこと",
        height=100,
        key="new_memory"
    )

    if st.button(
        "記憶に追加",
        use_container_width=True
    ):
        if new_memory.strip():
            st.session_state.memory.append(
                new_memory.strip()
            )
            save_all()
            st.rerun()

    if st.session_state.memory:

        st.write("現在の記憶")

        for i, memory in enumerate(
            st.session_state.memory
        ):

            st.write(f"・{memory}")

            if st.button(
                "削除",
                key=f"memory_delete_{i}"
            ):
                st.session_state.memory.pop(i)
                save_all()
                st.rerun()

    st.divider()

    if st.button(
        "このチャットを全消去",
        use_container_width=True
    ):
        clear_current_chat()
        st.rerun()


# =========================================================
# 現在のチャット
# =========================================================

chat = st.session_state.chats[
    st.session_state.current_chat
]

st.title(
    chat.get("title", "新しいチャット")
)

# =========================================================
# メッセージ表示
# =========================================================

for i, message in enumerate(chat["messages"]):

    role = message["role"]
    content = message["content"]

    if role == "user":

        with st.chat_message("user"):
            st.markdown(content)

            edit_key = f"edit_user_{i}"

            if st.button(
                "編集",
                key=edit_key
            ):
                st.session_state.editing_index = i
                st.session_state.editing_role = "user"
                st.rerun()

    else:

        with st.chat_message("assistant"):

            st.markdown(content)

            col1, col2 = st.columns(2)

            with col1:
                if st.button(
                    "編集",
                    key=f"edit_ai_{i}"
                ):
                    st.session_state.editing_index = i
                    st.session_state.editing_role = "assistant"
                    st.rerun()

            with col2:
                if st.button(
                    "再生成",
                    key=f"regen_{i}"
                ):
                    if i > 0:
                        # このAI回答より前まで戻す
                        previous_messages = chat["messages"][:i]

                        if (
                            previous_messages
                            and previous_messages[-1]["role"] == "user"
                        ):
                            answer, error = call_gemini(
                                previous_messages,
                                st.session_state.settings[
                                    "character_setting"
                                ],
                                st.session_state.memory
                            )

                            if error:
                                st.error(error)
                            else:
                                chat["messages"] = (
                                    previous_messages
                                    + [
                                        {
                                            "role": "assistant",
                                            "content": answer
                                        }
                                    ]
                                )

                                save_json(
                                    CHAT_FILE,
                                    st.session_state.chats
                                )

                                st.rerun()


# =========================================================
# メッセージ編集
# =========================================================

if "editing_index" in st.session_state:

    index = st.session_state.editing_index
    role = st.session_state.editing_role

    if index < len(chat["messages"]):

        old_content = chat["messages"][index]["content"]

        st.divider()

        st.subheader("メッセージを編集")

        edited = st.text_area(
            "内容",
            value=old_content,
            height=180,
            key="editing_text"
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                "保存",
                type="primary",
                use_container_width=True
            ):

                if edited.strip():

                    chat["messages"][index]["content"] = edited

                    # ユーザー発言を編集した場合、
                    # そこから後ろを消してAIを再生成
                    if role == "user":

                        chat["messages"] = (
                            chat["messages"][:index + 1]
                        )

                        answer, error = call_gemini(
                            chat["messages"],
                            st.session_state.settings[
                                "character_setting"
                            ],
                            st.session_state.memory
                        )

                        if error:
                            st.error(error)
                        else:
                            chat["messages"].append(
                                {
                                    "role": "assistant",
                                    "content": answer
                                }
                            )

                    save_json(
                        CHAT_FILE,
                        st.session_state.chats
                    )

                    del st.session_state.editing_index
                    del st.session_state.editing_role

                    st.rerun()

        with col2:
            if st.button(
                "キャンセル",
                use_container_width=True
            ):
                del st.session_state.editing_index
                del st.session_state.editing_role
                st.rerun()


# =========================================================
# 新規メッセージ入力
# =========================================================

st.divider()

with st.form("message_form", clear_on_submit=True):

    user_message = st.text_area(
        "メッセージ",
        placeholder="ここにメッセージを入力\n改行もできます。",
        height=140
    )

    send = st.form_submit_button(
        "送信",
        type="primary",
        use_container_width=True
    )

if send:

    text = user_message.strip()

    if text:

        # ユーザー発言を追加
        chat["messages"].append(
            {
                "role": "user",
                "content": text
            }
        )

        # 最初の発言をチャット名にする
        if len(chat["messages"]) == 1:

            title = text.replace("\n", " ").strip()

            if len(title) > 25:
                title = title[:25] + "…"

            chat["title"] = title

        save_json(
            CHAT_FILE,
            st.session_state.chats
        )

        # AIに送信
        with st.spinner("考え中…"):

            answer, error = call_gemini(
                chat["messages"],
                st.session_state.settings[
                    "character_setting"
                ],
                st.session_state.memory
            )

        if error:

            st.error(error)

        else:

            chat["messages"].append(
                {
                    "role": "assistant",
                    "content": answer
                }
            )

            save_json(
                CHAT_FILE,
                st.session_state.chats
            )

            st.rerun()

    else:

        st.warning("メッセージを入力してください。")
