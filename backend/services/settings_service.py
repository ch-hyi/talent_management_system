"""系統設定業務邏輯層（Service）"""

import os
import uuid
from pathlib import Path
from typing import Optional

from ..models.settings import MessageContent, ThemeConfig
from ..repositories.log_repository import LogRepository
from ..repositories.settings_repository import (
    SettingsRepository,
    SettingsRepositoryError,
)
from ..models.response import APIResponse

ALLOWED_LOGO_TYPES = {"image/png", "image/jpeg", "image/svg+xml", "image/webp"}
MAX_LOGO_SIZE = 5 * 1024 * 1024  # 5MB


class SettingsService:
    """系統設定業務邏輯層"""

    def __init__(
        self,
        settings_repo: SettingsRepository,
        log_repo: LogRepository,
        logo_storage_dir: Optional[str] = None,
    ):
        self.settings_repo = settings_repo
        self.log_repo = log_repo
        self.logo_storage_dir = Path(
            logo_storage_dir or os.getenv("LOGO_STORAGE_DIR", "./static/logo")
        )
        self.logo_public_prefix = os.getenv("LOGO_PUBLIC_PREFIX", "/static/logo")

    # --------------------------------------------------------
    # 內部工具
    # --------------------------------------------------------

    def _log(self, action: str, operator: str, detail: str = "") -> None:
        """寫入操作紀錄，失敗不影響主流程"""
        try:
            self.log_repo.add_log(action=action, operator=operator, detail=detail)
        except Exception:
            pass  # 建議改用 logger.warning 記錄失敗事件

    # --------------------------------------------------------
    # 完整設定
    # --------------------------------------------------------

    def get_all_settings(self) -> APIResponse:
        try:
            settings = self.settings_repo.load()
            return APIResponse(success=True,data=settings,message="Success")
        except SettingsRepositoryError as e:
            return APIResponse(success=False,message = "取得系統設定失敗", error=str(e))

    # --------------------------------------------------------
    # Theme
    # --------------------------------------------------------

    def get_theme(self) -> APIResponse:
        try:
            theme = self.settings_repo.get_theme()
            return APIResponse(success=True,data=theme,message="Success")
        except SettingsRepositoryError as e:
            return APIResponse(success=False,message = "取得主題失敗", error=str(e))

    def update_theme(self, theme: ThemeConfig, operator: str) -> APIResponse:
        try:
            self.settings_repo.update_theme(theme)
            self._log("update_theme", operator, theme.model_dump_json())
            return APIResponse(success=True,data=theme,message="Success")
        except SettingsRepositoryError as e:
            return APIResponse(success=False,message = "更新主題失敗", error=str(e))


    def update_score_threshold(self,threshold:int,operator:str) ->APIResponse:
        try:
            self.settings_repo.update_threshold(threshold)
            self._log("update_theme", operator,threshold)
            return APIResponse(success=True,data=threshold,message="Success")
        except SettingsRepositoryError as e:
            return APIResponse(success=False,message = "更新主題失敗", error=str(e))


    # --------------------------------------------------------
    # Logo
    # --------------------------------------------------------

    def get_logo(self) -> APIResponse:
        try:
            theme = self.settings_repo.get_theme()
            return APIResponse(success=True,data=theme.logo_address,message="Success")
        except SettingsRepositoryError as e:
            return APIResponse(success=False,message = "取得主題失敗", error=str(e))

    def update_logo(
        self,
        filename: str,
        content_type: str,
        file_content: bytes,
        operator: str,
    ) -> APIResponse:
        if content_type not in ALLOWED_LOGO_TYPES:
            return APIResponse(success = False,
                message = "不支援的檔案格式",
                error=f"content_type={content_type} 不在允許清單: {ALLOWED_LOGO_TYPES}",
            )

        if len(file_content) > MAX_LOGO_SIZE:
            return APIResponse(success=False,
                message="檔案過大",
                error=f"檔案大小 {len(file_content)} bytes 超過上限 {MAX_LOGO_SIZE} bytes",
            )

        try:
            self.logo_storage_dir.mkdir(parents=True, exist_ok=True)

            ext = Path(filename).suffix or ".png"
            safe_name = f"logo_{uuid.uuid4().hex}{ext}"
            save_path = self.logo_storage_dir / safe_name

            with open(save_path, "wb") as f:
                f.write(file_content)

            logo_address = f"{self.logo_public_prefix}/{safe_name}"
            settings = self.settings_repo.update_logo_address(logo_address)

            self._log(
                "update_logo", operator, f"filename={filename}, size={len(file_content)}"
            )

            return APIResponse(
                success= True,
                data=settings.theme.logo_address,
                message="Logo 更新成功",
            )
        except (OSError, SettingsRepositoryError) as e:
            return APIResponse(success=False,message="更新 Logo 失敗", error=str(e))

    # --------------------------------------------------------
    # External Email Template
    # --------------------------------------------------------

    def get_external_template(self) -> APIResponse:
        try:
            content = self.settings_repo.get_external_template()
            return APIResponse(success=True,data=content,message="Success")
        except SettingsRepositoryError as e:
            return APIResponse(success=False,message = "取得外部信件模板失敗", error=str(e))

    def update_external_template(self, settings: MessageContent, operator: str) -> APIResponse:
        try:
            self.settings_repo.update_external_template(settings)
            self._log("update_external_template", operator, settings.model_dump_json())
            return APIResponse(success=True,data=True,message="Success")
        except SettingsRepositoryError as e:
            return APIResponse(success=False,message = "更新外部信件模板失敗", error=str(e))

    # --------------------------------------------------------
    # Internal Email Template
    # --------------------------------------------------------

    def get_internal_template(self) -> APIResponse:
        try:
            content = self.settings_repo.get_internal_template()
            return APIResponse(success=True,data=content,message="Success")
        except SettingsRepositoryError as e:
            return APIResponse(success=False,message = "取得內部信件模板失敗", error=str(e))

    def update_internal_template(self, settings: MessageContent, operator: str) -> APIResponse:
        try:
            self.settings_repo.update_internal_template(settings)
            self._log("update_internal_template", operator, settings.model_dump_json())
            return APIResponse(success=True,data=True,message="Success")
        except SettingsRepositoryError as e:
            return APIResponse(success=False,message = "更新內部信件模板失敗", error=str(e))

    # --------------------------------------------------------
    # 系統重新啟動
    # --------------------------------------------------------

    def restart(self, operator: str) -> APIResponse:
        import subprocess
        import uuid

        try:
            self._log("restart", operator, "系統重新啟動請求")

            project_root = Path(__file__).resolve().parents[2]
            restart_script = project_root / "start.bat"

            if not restart_script.exists():
                raise FileNotFoundError(f"找不到重新啟動腳本：{restart_script}")

            task_name = f"TalentSystemRestart_{uuid.uuid4().hex[:8]}"
            command = f"timeout /t 3 /nobreak >nul && call {restart_script}"

            # 建立一個「立即執行一次」的排程任務。
            # 這個新行程由 Windows Task Scheduler 服務啟動，
            # 完全脫離目前 API 行程的 Job Object / process tree，
            # 因此關閉 API 的 Terminal 不會影響到它。
            create_result = subprocess.run(
                [
                    "schtasks", "/create",
                    "/tn", task_name,
                    "/tr", f'cmd.exe /c "{command}"',
                    "/sc", "once",
                    "/st", "00:00",  # 佔位時間，實際靠 /ru 立即觸發
                    "/f",
                ],
                cwd=str(project_root),
                capture_output=True,
                text=True,
            )

            if create_result.returncode != 0:
                raise RuntimeError(f"建立排程任務失敗: {create_result.stderr}")

            # 立即執行剛建立的任務
            run_result = subprocess.run(
                ["schtasks", "/run", "/tn", task_name],
                capture_output=True,
                text=True,
            )

            if run_result.returncode != 0:
                raise RuntimeError(f"觸發排程任務失敗: {run_result.stderr}")

            return APIResponse(
                success=True,
                message="系統重新啟動指令已送出，預計數秒後開始重新啟動。",
            )

        except Exception as exc:
            self._log("restart_failed", operator, f"系統重新啟動失敗：{exc}")
            return APIResponse(success=False, message=f"系統重新啟動失敗：{exc}")