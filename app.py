import streamlit as st
from google import genai

st.title("Gemini接続テスト")

api_key = st.secrets["GEMINI_API_KEY"]

client = genai.Client(api_key=api_key)

if st.button("テスト送信"):
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Hello. Reply with OK."
        )

        st.success("Gemini APIから返答がありました")
        st.write(response.text)

    except Exception as e:
        st.error("Gemini APIでエラーが発生しました")
        st.exception(e)
