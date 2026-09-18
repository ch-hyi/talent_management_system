"""
系統設定檔存取層（Repository）

設定資料以 JSON 檔案儲存於本地端，非資料庫儲存。
檔案路徑透過環境變數 SETTINGS_JSON_PATH 指定。
"""

import json
import os
import shutil
import threading
from pathlib import Path
from typing import Any, Dict

from ..models.settings import Settings, ThemeConfig, MessageContent


class SettingsRepositoryError(Exception):
    """設定檔讀寫發生錯誤時拋出"""
    pass


class SettingsRepository:
    """系統設定 JSON 檔案存取層"""

    _lock = threading.Lock()

    # 此檔案位於 backend/app/repositories/settings_repository.py
    # parents[2] = backend/
    _BACKEND_DIR = Path(__file__).resolve().parents[1]
    _FRONTEND_DIR = Path(__file__).resolve().parents[2] /"frontend"
    _DEFAULT_SETTINGS_PATH = _BACKEND_DIR / "data" / "settings.json"

    def __init__(self):
        self.settings_path = Path(str(self._DEFAULT_SETTINGS_PATH))
        self._ensure_file_exists()


    # --------------------------------------------------------
    # 內部工具方法
    # --------------------------------------------------------

    def _ensure_file_exists(self) -> None:
        """若設定檔不存在，建立預設檔案"""
        if not self.settings_path.exists():
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_raw(Settings().model_dump())

    def _read_raw(self) -> Dict[str, Any]:
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            raise SettingsRepositoryError(f"讀取設定檔失敗: {e}") from e

    def _write_raw(self, data: Dict[str, Any]) -> None:
        """寫入暫存檔後再覆蓋正式檔，避免寫入過程中中斷造成檔案損毀"""
        tmp_path = self.settings_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            shutil.move(str(tmp_path), str(self.settings_path))
        except OSError as e:
            raise SettingsRepositoryError(f"寫入設定檔失敗: {e}") from e

    # --------------------------------------------------------
    # 對外方法
    # --------------------------------------------------------

    def load(self) -> Settings:
        """讀取完整設定"""
        with self._lock:
            raw = self._read_raw()
        return Settings(**raw)

    def save(self, settings: Settings) -> None:
        """儲存完整設定"""
        with self._lock:
            self._write_raw(settings.model_dump())

    def get_theme(self) -> ThemeConfig:
        return self.load().theme

    def update_theme(self, theme: ThemeConfig) -> Settings:
        settings = self.load()
        settings.theme = theme
        self.save(settings)
        return settings

    def get_external_template(self) -> MessageContent:
        return self.load().temp.external

    def update_external_template(self, content: MessageContent) -> Settings:
        settings = self.load()
        content.attachments = [f.name for f in Path(self._FRONTEND_DIR / "static" /"settings" /"external_attachments" ).iterdir() if f.is_file()]
        print(content.attachments)
        settings.temp.external = content
        self.save(settings)
        return settings

    def get_internal_template(self) -> MessageContent:
        return self.load().temp.internal

    def update_internal_template(self, content: MessageContent) -> Settings:
        settings = self.load()
        content.attachments = [f.name for f in Path(self._FRONTEND_DIR / "static" /"settings" /"internal_attachments" ).iterdir() if f.is_file()]
        settings.temp.internal = content
        self.save(settings)
        return settings

    def update_logo_address(self, logo_address: str) -> Settings:
        settings = self.load()
        settings.theme.logo_address = logo_address
        self.save(settings)
        return settings

    def update_score_threshold(self,threshold:int)->Settings:
        settings = self.load()
        settings.score_threshold = threshold
        self.save(settings)
        return settings

    def get_current_info(self,) ->str:
        json_dir = self._BACKEND_DIR / "info.json"
        with open(json_dir, "r", encoding="utf-8") as f:
            return f.read()
        