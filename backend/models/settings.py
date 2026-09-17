import re
from pydantic import BaseModel, HttpUrl, field_validator
from typing import Optional


class MessageContent(BaseModel):
    subject: str = ""
    content: str = ""
    attachments: list[str] = []  # 可放檔案路徑或 URL

    @field_validator("subject")
    @classmethod
    def subject_length(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("subject 長度不可超過 200 字")
        return v


class TempConfig(BaseModel):
    external: MessageContent
    internal: MessageContent


class ThemeConfig(BaseModel):
    primary: str = ""
    secondary: str = ""
    hover: str = ""
    text_dark: str = ""
    text_gray: str = ""
    logo_address: Optional[HttpUrl] = None
    footer : str = ""

    @field_validator("primary", "secondary", "hover", "text_dark", "text_gray")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        if v and not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError(f"顏色格式錯誤，須為 HEX 格式（如 #1A73E8），收到: {v}")
        return v


class Settings(BaseModel):
    temp: TempConfig 
    theme: ThemeConfig
    score_threshold :int