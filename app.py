import streamlit as st

st.title("APIキー確認")

api_key = st.secrets["GEMINI_API_KEY"]

try:
    api_key.encode("ascii")
    st.success("APIキーはASCII文字だけです")
except UnicodeEncodeError:
    st.error("APIキーにASCII以外の文字が入っています")

st.write("APIキーの文字数:", len(api_key))
st.write("先頭5文字:", api_key[:5])
st.write("末尾5文字:", api_key[-5:])
