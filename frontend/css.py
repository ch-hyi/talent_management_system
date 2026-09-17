import streamlit as st
from api_client import SettingsAPI

def load_custom_css():
    """載入自訂 CSS 樣式 - 顏色統一從 config.py 讀取"""
    color = SettingsAPI.get_theme().data
    primary = color["primary"]
    secondary = color["secondary"]
    hover = color["hover"]
    text_dark = color["text_dark"]
    text_light =  color["text_gray"]  # 請確認 theme API 有回傳此欄位
    footer = color["footer"]

    st.markdown(f"""
<style>

/* =====================================================
Global Background
===================================================== */

.stApp {{
    background-color: {secondary};
}}

[data-testid="stMain"] {{
    background-color: {secondary};
    color: {text_dark};
}}

section[data-testid="stSidebar"] {{
    background-color: {hover};
}}

section[data-testid="stSidebar"] * {{
    color: {text_dark} !important;
}}

/* =====================================================
Typography (頁面文字)
===================================================== */

[data-testid="stMain"] p,
[data-testid="stMain"] label,
[data-testid="stMain"] li,
[data-testid="stMain"] span,
[data-testid="stMain"] div {{
    color: {text_dark};
}}

[data-testid="stMain"] h1,
[data-testid="stMain"] h2,
[data-testid="stMain"] h3,
[data-testid="stMain"] h4,
[data-testid="stMain"] h5,
[data-testid="stMain"] h6 {{
    color: {text_dark};
    font-weight: 600;
}}

small {{
    color: {text_light};
}}

/* =====================================================
Buttons (元件)
===================================================== */

.stButton > button,
.stButton > button *,
.stDownloadButton > button,
.stDownloadButton > button * {{
    background-color: {primary};
    color: {text_light} !important;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.2s ease;
}}

.stButton > button:hover,
.stButton > button:hover *,
.stDownloadButton > button:hover,
.stDownloadButton > button:hover * {{
    background-color: {hover};
    color: {text_light} !important;
    transform: translateY(-2px);
}}

.stButton > button:focus,
.stButton > button:focus *,
.stDownloadButton > button:focus,
.stDownloadButton > button:focus * {{
    color: {text_light} !important;
}}

/* =====================================================
Inputs 
===================================================== */

.stTextInput input,
.stTextArea textarea,
.stNumberInput input,
.stDateInput input,
.stTimeInput input {{
    color: #000000 !important;
    background-color: {hover} !important;
    border: 1px solid #d1d5db !important;
}}

.stSelectbox > div > div,
.stMultiSelect > div > div {{
    background-color: {hover} !important;
}}

.stSelectbox *,
.stMultiSelect [data-baseweb="tag"] span {{
    color: {text_light} !important;
}}
.stRadio *,
.stCheckbox * {{
    color: {text_dark} !important;
}}



/* =====================================================
Tabs (元件)
===================================================== */

.stTabs [data-baseweb="tab"] {{
    color: {text_light} !important;
    background-color: transparent;
}}

/* =====================================================
Tabs
===================================================== */

.stTabs [data-baseweb="tab"] {{
    background-color: transparent;
}}


.stTabs [aria-selected="true"] {{
    background-color: {primary} !important;
    border-radius: 8px 8px 0 0;
}}

.stTabs [aria-selected="true"] p {{
    color: {text_light} !important;
    font-weight: 700 !important;
}}

/* =====================================================
Metric (元件)
===================================================== */

[data-testid="metric-container"] {{
    background: {primary};
    border-radius: 12px;
    border-left: 4px solid {hover};
}}

[data-testid="metric-container"] label {{
    color: {text_light} !important;
}}

[data-testid="stMetricValue"] {{
    color: {text_light} !important;
}}

/* =====================================================
Progress (元件)
===================================================== */

.stProgress > div > div > div {{
    background-color: {primary} !important;
}}

/* =====================================================
Links
===================================================== */

a {{
    color: {primary};
}}

a:hover {{
    color: {hover};
}}

/* =====================================================
Form Submit Button
===================================================== */

[data-testid="stFormSubmitButton"] button,
[data-testid="stFormSubmitButton"] button * {{
    background-color: {primary} !important;
    color: white !important;
    border: none;
    border-radius: 8px;
    font-weight: 600;
}}

[data-testid="stFormSubmitButton"] button:hover,
[data-testid="stFormSubmitButton"] button:hover * {{
    background-color: {hover} !important;
    color: white !important;
    transform: translateY(-2px);
}}

[data-testid="stFormSubmitButton"] button:focus,
[data-testid="stFormSubmitButton"] button:focus * {{
    color: white !important;
}}

/* =====================================================
Alerts (維持原本顏色，不受影響)
===================================================== */

.stSuccess {{
    border-left: 4px solid #22c55e;
}}

.stWarning {{
    border-left: 4px solid #f59e0b;
}}

.stError {{
    border-left: 4px solid #ef4444;
}}

.stInfo {{
    border-left: 4px solid {primary};
    background-color: {primary}20;
}}

""", unsafe_allow_html=True)
    return footer

