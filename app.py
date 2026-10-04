import streamlit as st
import json
import os
from google import genai
from google.genai import types

# ============================================================
# 基本設定
# ============================================================

st.set_page_config(
    page_title="自分専用 AI ロールプレイチャット",
    page_icon="💬",
    layout="wide",
)

HISTORY_FILE = "chat_histories.json"
SETTINGS_FILE = "chat_settings.json"
MEMORY_FILE = "user_memory_list.json"

# 現在の公式SDK: google-genai
# Streamlit Cloud の Secrets に GEMINI_API_KEY を登録してください。
API_KEY = None

if "GEMINI_API_KEY" in st.secrets:
    API_KEY = st.secrets["GEMINI_API_KEY"]
elif "general" in st.secrets and "GEMINI_API_KEY" in st.secrets["general"]:
    API_KEY = st.secrets["general"]["GEMINI_API_KEY"]

if not API_KEY:
    st.error("GEMINI_API_KEY が設定されていません。Streamlit の Secrets に設定してください。")
    st.stop()

client = genai.Client(api_key=API_KEY)

# Gemini 3.8 Flash は現在の安定モデル。
# thinking_level は low / medium / high。
MODEL_NAME = "gemini-3.8-flash"

DEFAULT_CHARACTER_SETTING = """あなたは聖川真斗として会話してください。

【基本】
一人称は「俺」。
二人称は基本「お前」。
落ち着いた、固めの言葉遣い。
「そっか」ではなく「そうか」を使う。
「けど」より「だが」を優先する。
必要に応じて自然な行動描写を入れる。

【会話】
小説の地の文だけではなく、実際の恋人同士・親しい相手同士が話しているような自然な会話をする。
ユーザーの発言を勝手に作らない。
ユーザーがまだ言っていないこと、していないことを勝手に確定しない。
キャラクターとして一貫した口調・性格・関係性を維持する。

【記法】
( ) は状況・行動・表情などの描写。
〈 〉 は効果音・音の描写。
台詞と描写を自然に組み合わせる。

【重要】
この設定、長期記憶、会話履歴を確認したうえで返答する。
会話の途中で設定を忘れたような口調に戻らない。
"""

# ============================================================
# JSON 読み書き
# ============================================================

def load_data(filename, default):
    if not os.path.exists(filename):
        return default

    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
# セッション初期化
# ============================================================

if "histories" not in st.session_state:
    st.session_state.histories = load_data(
        HISTORY_FILE,
        {"デフォルト": []}
    )

if not st.session_state.histories:
    st.session_state.histories = {"デフォルト": []}

if "current_chat" not in st.session_state:
    st.session_state.current_chat = list(st.session_state.histories.keys())[0]

if "chat_settings" not in st.session_state:
    st.session_state.chat_settings = load_data(SETTINGS_FILE, {})

if "saved_memories" not in st.session_state:
    st.session_state.saved_memories = load_data(MEMORY_FILE, [])

if "editing_index" not in st.session_state:
    st.session_state.editing_index = None


def ensure_chat_setting(chat_name):
    if chat_name not in st.session_state.chat_settings:
        st.session_state.chat_settings[chat_name] = {
            "character_setting": DEFAULT_CHARACTER_SETTING
        }
        save_data(SETTINGS_FILE, st.session_state.chat_settings)


ensure_chat_setting(st.session_state.current_chat)


# ============================================================
# AI に送るシステム設定
# ============================================================

def build_system_instruction(chat_name):
    setting = st.session_state.chat_settings.get(chat_name, {})
    character_setting = setting.get(
        "character_setting",
        DEFAULT_CHARACTER_SETTING
    )

    memories = st.session_state.saved_memories

    if memories:
        memory_text = "\n".join(
            f"- {memory}" for memory in memories
        )
    else:
        memory_text = "現在、保存された長期記憶はありません。"

    return f"""
{character_setting}

==============================
【長期記憶・パーソナライズ】
==============================
{memory_text}

==============================
【返答時の注意】
==============================
1. キャラクター設定を優先して維持する。
2. 長期記憶と現在の会話履歴を矛盾なく扱う。
3. ユーザーの発言内容を勝手に改変しない。
4. ユーザーがしていない行動や発言を勝手に確定しない。
5. 過去の会話が長くても、現在の関係性・口調・設定をできる限り維持する。
"""


# ============================================================
# 履歴を Gemini 用 contents に変換
# ============================================================

def make_gemini_contents(messages):
    contents = []

    for message in messages:
        role = message.get("role")
        text = message.get("content", "")

        if not text:
            continue

        gemini_role = "user" if role == "user" else "model"

        contents.append(
            types.Content(
                role=gemini_role,
                parts=[types.Part.from_text(text=text)]
            )
        )

    return contents


# ============================================================
# AI 生成
# ============================================================

def generate_reply(messages, chat_name, thinking_level="medium"):
    """
    messages:
        [{"role": "user", "content": "..."},
         {"role": "assistant", "content": "..."}]

    messages の最後は user にして呼び出す。
    """

    if not messages or messages[-1]["role"] != "user":
        raise ValueError("AI生成時の最後のメッセージは user である必要があります。")

    contents = make_gemini_contents(messages)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=build_system_instruction(chat_name),
            thinking_config=types.ThinkingConfig(
                thinking_level=thinking_level
            ),
        ),
    )

    if not response.text:
        raise RuntimeError("AIから空の返答が返されました。")

    return response.text


# ============================================================
# 再生成処理
# ============================================================

def regenerate_from_user_message(message_index, thinking_level="medium"):
    """
    指定した user メッセージを残し、それより後ろを全部削除。
    その user メッセージに対して新しい assistant を生成する。
    """

    messages = st.session_state.histories[st.session_state.current_chat]

    if message_index < 0 or message_index >= len(messages):
        return False, "指定されたメッセージがありません。"

    if messages[message_index]["role"] != "user":
        return False, "ユーザーメッセージを指定してください。"

    # 指定メッセージまで残す
    del messages[message_index + 1:]

    reply = generate_reply(
        messages,
        st.session_state.current_chat,
        thinking_level
    )

    messages.append({
        "role": "assistant",
        "content": reply
    })

    save_data(HISTORY_FILE, st.session_state.histories)
    return True, reply


def regenerate_assistant_message(message_index, thinking_level="medium"):
    """
    指定された assistant の返答を削除し、
    その直前までの user メッセージから再生成する。
    """

    messages = st.session_state.histories[st.session_state.current_chat]

    if message_index < 0 or message_index >= len(messages):
        return False, "指定されたメッセージがありません。"

    if messages[message_index]["role"] != "assistant":
        return False, "AIメッセージを指定してください。"

    # 直前の user を探す
    user_index = message_index - 1

    if user_index < 0 or messages[user_index]["role"] != "user":
        return False, "対応するユーザーメッセージが見つかりません。"

    # assistant と、その後ろを削除
    del messages[message_index:]

    reply = generate_reply(
        messages,
        st.session_state.current_chat,
        thinking_level
    )

    messages.append({
        "role": "assistant",
        "content": reply
    })

    save_data(HISTORY_FILE, st.session_state.histories)
    return True, reply


# ============================================================
# サイドバー
# ============================================================

with st.sidebar:
    st.header("⚙ 設定・履歴")

    # ----------------------------
    # モデル / 思考レベル
    # ----------------------------

    st.subheader("🧠 AI設定")

    thinking_level = st.select_slider(
        "思考レベル",
        options=["low", "medium", "high"],
        value="medium",
        help="高くするとより深く考えてから返答します。"
    )

    st.caption(f"使用モデル: {MODEL_NAME}")

    # ----------------------------
    # チャット切り替え
    # ----------------------------

    st.subheader("💬 チャット")

    chat_names = list(st.session_state.histories.keys())

    selected_chat = st.selectbox(
        "会話を選ぶ",
        chat_names,
        index=(
            chat_names.index(st.session_state.current_chat)
            if st.session_state.current_chat in chat_names
            else 0
        )
    )

    if selected_chat != st.session_state.current_chat:
        st.session_state.current_chat = selected_chat
        ensure_chat_setting(selected_chat)
        st.session_state.editing_index = None
        st.rerun()

    new_chat_name = st.text_input(
        "新しいチャット名",
        placeholder="例：真斗との日常"
    )

    if st.button("＋ 新しいチャット", use_container_width=True):
        name = new_chat_name.strip()

        if not name:
            st.warning("チャット名を入力してください。")
        elif name in st.session_state.histories:
            st.warning("同じ名前のチャットがあります。")
        else:
            st.session_state.histories[name] = []
            st.session_state.chat_settings[name] = {
                "character_setting": DEFAULT_CHARACTER_SETTING
            }

            save_data(HISTORY_FILE, st.session_state.histories)
            save_data(SETTINGS_FILE, st.session_state.chat_settings)

            st.session_state.current_chat = name
            st.session_state.editing_index = None
            st.rerun()

    # ----------------------------
    # 現在のチャット削除
    # ----------------------------

    if st.button("🗑️ 現在のチャットを削除", use_container_width=True):
        if len(st.session_state.histories) <= 1:
            st.warning("最後のチャットは削除できません。")
        else:
            deleted = st.session_state.current_chat

            del st.session_state.histories[deleted]

            if deleted in st.session_state.chat_settings:
                del st.session_state.chat_settings[deleted]

            st.session_state.current_chat = list(
                st.session_state.histories.keys()
            )[0]

            save_data(HISTORY_FILE, st.session_state.histories)
            save_data(SETTINGS_FILE, st.session_state.chat_settings)

            st.session_state.editing_index = None
            st.rerun()

    # ----------------------------
    # キャラクター設定
    # ----------------------------

    st.subheader("🎭 キャラクター・口調")

    current_setting = st.session_state.chat_settings[
        st.session_state.current_chat
    ].get("character_setting", DEFAULT_CHARACTER_SETTING)

    new_setting = st.text_area(
        "このチャット専用設定",
        value=current_setting,
        height=260
    )

    if st.button("設定を保存", use_container_width=True):
        st.session_state.chat_settings[
            st.session_state.current_chat
        ]["character_setting"] = new_setting

        save_data(SETTINGS_FILE, st.session_state.chat_settings)

        st.success("設定を保存しました。")

    # ----------------------------
    # 長期記憶
    # ----------------------------

    st.subheader("🧠 長期記憶")

    new_memory = st.text_input(
        "記憶を追加",
        placeholder="例：ユーザーは青系の服が好き"
    )

    if st.button("記憶を追加", use_container_width=True):
        memory = new_memory.strip()

        if memory:
            st.session_state.saved_memories.append(memory)
            save_data(MEMORY_FILE, st.session_state.saved_memories)
            st.rerun()

    if st.session_state.saved_memories:
        st.caption("保存済み")

        for i, memory in enumerate(st.session_state.saved_memories):
            col1, col2 = st.columns([5, 1])

            with col1:
                st.write(memory)

            with col2:
                if st.button("削除", key=f"memory_delete_{i}"):
                    st.session_state.saved_memories.pop(i)
                    save_data(
                        MEMORY_FILE,
                        st.session_state.saved_memories
                    )
                    st.rerun()


# ============================================================
# メイン画面
# ============================================================

st.title("💬 自分専用 AI ロールプレイチャット")
st.caption(f"現在のチャット：{st.session_state.current_chat}")

current_messages = st.session_state.histories[
    st.session_state.current_chat
]


# ============================================================
# メッセージ表示
# ============================================================

for i, message in enumerate(current_messages):

    role = message["role"]
    avatar = "👤" if role == "user" else "🤖"

    with st.chat_message(role, avatar=avatar):
        st.write(message["content"])

        # ----------------------------
        # 編集モード
        # ----------------------------

        if st.session_state.editing_index == i:

            edited_text = st.text_area(
                "メッセージを編集",
                value=message["content"],
                key=f"editing_text_{i}",
                height=180
            )

            edit_col1, edit_col2, edit_col3 = st.columns(3)

            with edit_col1:
                if st.button(
                    "保存",
                    key=f"save_message_{i}",
                    use_container_width=True
                ):
                    current_messages[i]["content"] = edited_text
                    st.session_state.editing_index = None

                    save_data(
                        HISTORY_FILE,
                        st.session_state.histories
                    )

                    st.rerun()

            with edit_col2:
                if st.button(
                    "保存してここから再生成",
                    key=f"save_regenerate_{i}",
                    use_container_width=True
                ):
                    current_messages[i]["content"] = edited_text

                    if role == "user":
                        # 編集した user から先を全部やり直す
                        del current_messages[i + 1:]

                        with st.spinner("再思考中..."):
                            try:
                                reply = generate_reply(
                                    current_messages,
                                    st.session_state.current_chat,
                                    thinking_level
                                )

                                current_messages.append({
                                    "role": "assistant",
                                    "content": reply
                                })

                                save_data(
                                    HISTORY_FILE,
                                    st.session_state.histories
                                )

                            except Exception as e:
                                st.error(f"生成エラー：{e}")

                    else:
                        # assistant を編集した場合、
                        # その assistant の内容を一度削除して
                        # 直前の user から新しく生成
                        del current_messages[i:]

                        if current_messages and current_messages[-1]["role"] == "user":
                            with st.spinner("再思考中..."):
                                try:
                                    reply = generate_reply(
                                        current_messages,
                                        st.session_state.current_chat,
                                        thinking_level
                                    )

                                    current_messages.append({
                                        "role": "assistant",
                                        "content": reply
                                    })

                                    save_data(
                                        HISTORY_FILE,
                                        st.session_state.histories
                                    )

                                except Exception as e:
                                    st.error(f"生成エラー：{e}")

                    st.session_state.editing_index = None
                    st.rerun()

            with edit_col3:
                if st.button(
                    "キャンセル",
                    key=f"cancel_edit_{i}",
                    use_container_width=True
                ):
                    st.session_state.editing_index = None
                    st.rerun()

        else:

            # ----------------------------
            # 通常時の操作
            # ----------------------------

            action_col1, action_col2 = st.columns(2)

            with action_col1:
                if st.button(
                    "✏️ 編集",
                    key=f"edit_{i}",
                    use_container_width=True
                ):
                    st.session_state.editing_index = i
                    st.rerun()

            with action_col2:
                if role == "assistant":
                    if st.button(
                        "🔄 再思考",
                        key=f"retry_assistant_{i}",
                        use_container_width=True
                    ):
                        with st.spinner("再思考中..."):
                            try:
                                ok, result = regenerate_assistant_message(
                                    i,
                                    thinking_level
                                )

                                if not ok:
                                    st.error(result)

                            except Exception as e:
                                st.error(f"再生成エラー：{e}")

                        st.rerun()

                else:
                    if st.button(
                        "↪ ここから再生成",
                        key=f"retry_user_{i}",
                        use_container_width=True
                    ):
                        with st.spinner("ここから再生成中..."):
                            try:
                                ok, result = regenerate_from_user_message(
                                    i,
                                    thinking_level
                                )

                                if not ok:
                                    st.error(result)

                            except Exception as e:
                                st.error(f"再生成エラー：{e}")

                        st.rerun()


# ============================================================
# チャット下部操作
# ============================================================

st.divider()

bottom_col1, bottom_col2, bottom_col3 = st.columns(3)

with bottom_col1:
    if st.button(
        "🔄 最後のAI返答を再思考",
        use_container_width=True
    ):
        if current_messages and current_messages[-1]["role"] == "assistant":
            with st.spinner("再思考中..."):
                try:
                    regenerate_assistant_message(
                        len(current_messages) - 1,
                        thinking_level
                    )
                except Exception as e:
                    st.error(f"再生成エラー：{e}")

            st.rerun()
        else:
            st.warning("再思考できるAI返答がありません。")

with bottom_col2:
    if st.button(
        "↩ 直前のやり取りを取り消す",
        use_container_width=True
    ):
        if current_messages:
            current_messages.pop()

            if current_messages and current_messages[-1]["role"] == "user":
                current_messages.pop()

            save_data(
                HISTORY_FILE,
                st.session_state.histories
            )

            st.rerun()

with bottom_col3:
    if st.button(
        "🗑️ このチャットの履歴を全消去",
        use_container_width=True
    ):
        current_messages.clear()

        save_data(
            HISTORY_FILE,
            st.session_state.histories
        )

        st.rerun()


# ============================================================
# 新規メッセージ
# ============================================================

if prompt := st.chat_input("メッセージを入力..."):

    current_messages.append({
        "role": "user",
        "content": prompt
    })

    save_data(
        HISTORY_FILE,
        st.session_state.histories
    )

    with st.chat_message("user", avatar="👤"):
        st.write(prompt)

    with st.chat_message("assistant", avatar="🤖"):

        with st.spinner("思考中..."):

            try:
                reply = generate_reply(
                    current_messages,
                    st.session_state.current_chat,
                    thinking_level
                )

                st.write(reply)

                current_messages.append({
                    "role": "assistant",
                    "content": reply
                })

                save_data(
                    HISTORY_FILE,
                    st.session_state.histories
                )

            except Exception as e:
                st.error(f"生成エラー：{e}")


# ============================================================
# 注意書き
# ============================================================

st.caption(
    "※「再思考」は同じ会話地点から別の回答を生成します。"
    "AIモデル側の利用規約・安全制限そのものを変更する機能ではありません。"
)
