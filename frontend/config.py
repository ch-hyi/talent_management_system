from dotenv import load_dotenv
import os

load_dotenv()

API_HOST = os.getenv(
    "API_HOST",
    "localhost"
)

API_PORT = os.getenv(
    "API_PORT",
    "8000"
)

API_URL = f"http://{API_HOST}:{API_PORT}"

CI_COLORS = {
    "primary": "#0204a0",     # 企業識別主色
    "secondary": "#ffffff",   # 企業識別次色
}

# 輔助色（依附識別色延伸出的效果色，非官方色票本身）
SUPPORT_COLORS = {
    "hover": "#0305c5",        # 主色 hover 加深效果
    "text_dark": "#2d2d2d",    # 進度條深色文字
    "text_gray": "#666666",    # 說明文字灰色
}