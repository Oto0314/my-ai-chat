import streamlit as st
import requests

st.title("Gemini接続テスト")

api_key = st.secrets["GEMINI_API_KEY"]

if st.button("テスト送信"):
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }

        data = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": "Hello. Reply with OK."
                        }
                    ]
                }
            ]
        }

        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=30
        )

        if response.status_code != 200:
            st.error(f"Gemini APIエラー: HTTP {response.status_code}")
            st.code(response.text)
        else:
            result = response.json()
            text = result["candidates"][0]["content"]["parts"][0]["text"]

            st.success("Gemini APIから返答がありました")
            st.write(text)

    except Exception as e:
        st.error("通信エラーが発生しました")
        st.exception(e)
