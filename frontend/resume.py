# frontend/streamlit_app.py
"""

"""
import streamlit as st
from css import load_custom_css

def msg_backup(html):
    load_custom_css()
    st.components.v1.html(
        html,
        height=700,
        scrolling=True
    )