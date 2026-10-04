import os
import streamlit as st

st.title("環境チェック")

names = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
]

for name in names:
    value = os.environ.get(name)

    if value is None:
        st.write(f"{name}: 設定なし")
    else:
        try:
            value.encode("ascii")
            st.write(f"{name}: 設定あり・ASCIIのみ")
        except UnicodeEncodeError:
            st.error(f"{name}: ASCII以外の文字が含まれています")
