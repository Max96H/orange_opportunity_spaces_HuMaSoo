import base64
import json
import sqlite3
from pathlib import Path

import streamlit as st


@st.cache_data
def load_opportunity_spaces(path: Path) -> list[dict]: #replace to load db instead of json
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data.get("opportunity_space", [])


def load_css(path: Path) -> None:
    with path.open("r", encoding="utf-8") as file:
        st.markdown(f"<style>{file.read()}</style>", unsafe_allow_html=True)


@st.cache_data
def image_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")
