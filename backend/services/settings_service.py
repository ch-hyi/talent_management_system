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

    def get_currnet_info(self,operator)->APIResponse:
        info = self.settings_repo.get_current_info()
        return APIResponse(success=True,data=info,message="Current Information")
        
    
    def get_update_info(self, operator) -> APIResponse:
        import subprocess, json, logging
        from datetime import datetime

        logger = logging.getLogger("system_update")

        def ensure_remote_configured(repo_path: str, remote_url: str, remote_name: str = "origin"):
            """確保 git remote 有正確設定"""
            import subprocess

            try:
                # 檢查目前 remote
                result = subprocess.run(
                    ["git", "remote", "get-url", remote_name],
                    cwd=repo_path, capture_output=True, text=True, timeout=5
                )
                current_url = result.stdout.strip()

                if result.returncode != 0:
                    # remote 不存在，新增
                    subprocess.run(
                        ["git", "remote", "add", remote_name, remote_url],
                        cwd=repo_path, check=True, timeout=5
                    )
                    logger.info(f"新增 remote {remote_name} → {remote_url}")
                elif current_url != remote_url:
                    # remote 存在但 URL 不對，修正
                    subprocess.run(
                        ["git", "remote", "set-url", remote_name, remote_url],
                        cwd=repo_path, check=True, timeout=5
                    )
                    logger.info(f"修正 remote {remote_name}: {current_url} → {remote_url}")
                else:
                    logger.info(f"remote {remote_name} 已正確設定: {current_url}")

            except subprocess.CalledProcessError as e:
                logger.error(f"設定 remote 失敗: {e}")

        def fetch_tags():
            """先同步遠端 tag，失敗不致命"""
            try:
                subprocess.run(
                    ["git", "fetch", "--tags"],
                    check=True, timeout=10,
                    capture_output=True, text=True
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                logger.warning(f"git fetch --tags failed: {e}")

        def get_current_tag() -> str | None:
            try:
                return subprocess.check_output(
                    ["git", "describe", "--tags", "--abbrev=0"],
                    text=True, timeout=5, stderr=subprocess.DEVNULL
                ).strip()
            except subprocess.CalledProcessError:
                return None

        def get_all_tags() -> list[str]:
            output = subprocess.check_output(
                ["git", "tag", "--sort=version:refname"], text=True, timeout=5
            ).strip()
            return output.split("\n") if output else []

        def get_tag_content(tag: str) -> str:
            return subprocess.check_output(
                ["git", "tag", "-l", "--format=%(contents)", tag],
                text=True, timeout=5
            ).strip()

        def get_tag_date(tag: str) -> str:
            return subprocess.check_output(
                ["git", "for-each-ref", f"refs/tags/{tag}", "--format=%(creatordate:iso)"],
                text=True, timeout=5
            ).strip()

        def parse_tag(tag: str) -> dict:
            raw_msg = get_tag_content(tag)
            date = get_tag_date(tag)
            try:
                data = json.loads(raw_msg)
            except json.JSONDecodeError:
                data = {"summary": raw_msg}
            return {
                "version": tag,
                "name": data.get("name", ""),
                "summary": data.get("summary", ""),
                "date": date,
            }

        # ---- 主流程 ----
        logger.info(f"[{operator}] 觸發檢查更新")
        ensure_remote_configured(
            repo_path=".",  # ← 這裡要換成你實際的路徑，見下方
            remote_url="https://github.com/ch-hyi/talent_management_system.git",
            remote_name="origin"
        )
        fetch_tags()
        current_tag = get_current_tag()
        all_tags = get_all_tags()

        if not all_tags:
            return APIResponse(
                success=False,
                message="No version tags found in repository",
                data=None
            )

        latest_tag = all_tags[-1]

        # 沒有目前版本（本地從未打過 tag），視為需要更新
        if current_tag is None:
            latest_info = parse_tag(latest_tag)
            logger.info(f"[{operator}] No local tag allowed ,Found New Version: {latest_tag}")
            return APIResponse(
                success=True,
                message="Update available",
                data={
                    "has_update": True,
                    "current_version": None,
                    **latest_info,
                }
            )

        # 目前版本已經是最新
        if current_tag == latest_tag:
            logger.info(f"[{operator}] Already Latest {current_tag}")
            return APIResponse(
                success=True,
                message="Already up to date",
                data={
                    "has_update": False,
                    "current_version": current_tag,
                }
            )

        # 有更新可用
        latest_info = parse_tag(latest_tag)
        logger.info(f"[{operator}] Found New Version :{current_tag} → {latest_tag}")

        return APIResponse(
            success=True,
            message="Update available",
            data={
                "has_update": True,
                "current_version": current_tag,
                **latest_info,
            }
        )

    def update(self,operator) -> APIResponse:
        import subprocess, json, os, shutil, hashlib, logging
        from datetime import datetime
        import requests

        logging.basicConfig(
            filename="update_history.log",
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            encoding="utf-8",
        )
        logger = logging.getLogger("system_update")

        PROTECTED_DIRS = ["backend/data", "frontend/static"]
        REPO_ROOT = os.path.abspath(os.getcwd())
        BACKUP_ROOT = os.path.join(os.path.dirname(REPO_ROOT), "system_backups")

        # ---------------- Git helpers ----------------

        def fetch_all() -> bool:
            try:
                subprocess.run(
                    ["git", "fetch", "--all", "--tags"],
                    check=True, timeout=10, capture_output=True, text=True
                )
                return True
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                logger.error(f"git fetch failed: {e}")
                return False

        def get_current_tag() -> str | None:
            try:
                return subprocess.check_output(
                    ["git", "describe", "--tags", "--abbrev=0"],
                    text=True, timeout=5, stderr=subprocess.DEVNULL
                ).strip()
            except subprocess.CalledProcessError:
                return None

        def get_all_tags() -> list[str]:
            output = subprocess.check_output(
                ["git", "tag", "--sort=version:refname"], text=True, timeout=5
            ).strip()
            return output.split("\n") if output else []

        def get_latest_tag() -> str | None:
            tags = get_all_tags()
            return tags[-1] if tags else None

        def get_tag_content(tag: str) -> str:
            return subprocess.check_output(
                ["git", "tag", "-l", "--format=%(contents)", tag], text=True, timeout=5
            ).strip()

        def get_tag_date(tag: str) -> str:
            return subprocess.check_output(
                ["git", "for-each-ref", f"refs/tags/{tag}", "--format=%(creatordate:iso)"],
                text=True, timeout=5
            ).strip()

        def parse_tag(tag: str) -> dict:
            raw_msg = get_tag_content(tag)
            date = get_tag_date(tag)
            try:
                data = json.loads(raw_msg)
            except json.JSONDecodeError:
                data = {"summary": raw_msg}
            return {
                "version": tag,
                "name": data.get("name", ""),
                "summary": data.get("summary", ""),
                "date": date,
            }

        def rollback_to(tag: str) -> bool:
            try:
                subprocess.run(
                    ["git", "reset", "--hard", tag],
                    check=True, timeout=15, capture_output=True, text=True
                )
                logger.info(f"已回滾至 {tag}")
                return True
            except subprocess.CalledProcessError as e:
                logger.critical(f"回滾失敗！伺服器可能處於不一致狀態：{e}")
                return False

        # ---------------- Backup helpers ----------------

        def compute_file_hash(filepath: str) -> str:
            h = hashlib.sha256()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()

        def compute_dir_manifest(dir_path: str) -> dict:
            manifest = {}
            if not os.path.exists(dir_path):
                return manifest
            for root, _, filenames in os.walk(dir_path):
                for fname in filenames:
                    full_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(full_path, dir_path)
                    manifest[rel_path] = compute_file_hash(full_path)
            return manifest

        def backup_protected_dirs() -> str:
            """備份到系統外部資料夾，附時間戳記，並寫入 manifest.json 記錄雜湊值"""
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = os.path.join(BACKUP_ROOT, f"backup_{timestamp}")
            os.makedirs(backup_dir, exist_ok=True)

            manifest_record = {
                "backup_time": datetime.now().isoformat(),
                "dirs": {}
            }

            for protected in PROTECTED_DIRS:
                dir_name = os.path.basename(protected.rstrip("/"))
                dest = os.path.join(backup_dir, dir_name)

                if os.path.exists(protected):
                    shutil.copytree(protected, dest)
                    file_manifest = compute_dir_manifest(protected)
                else:
                    os.makedirs(dest, exist_ok=True)
                    file_manifest = {}
                    logger.warning(f"備份時發現目錄不存在：{protected}")

                manifest_record["dirs"][protected] = {
                    "backup_path": dest,
                    "file_count": len(file_manifest),
                    "files": file_manifest,
                }

            manifest_path = os.path.join(backup_dir, "manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_record, f, indent=2, ensure_ascii=False)

            logger.info(f"已備份保護目錄至：{backup_dir}（備份時間：{manifest_record['backup_time']}）")
            return backup_dir

        def verify_against_backup(backup_dir: str) -> dict:
            """比對目前保護目錄內容是否與備份完全一致（新增檔案不算異常，遺失/改變才算）"""
            manifest_path = os.path.join(backup_dir, "manifest.json")
            if not os.path.exists(manifest_path):
                logger.error(f"找不到備份 manifest.json：{manifest_path}")
                return {"ok": False, "error": "manifest not found"}

            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_record = json.load(f)

            result = {
                "ok": True,
                "backup_time": manifest_record["backup_time"],
                "backup_dir": backup_dir,
                "dirs": {}
            }

            for protected, info in manifest_record["dirs"].items():
                backed_up_files = info["files"]
                current_files = compute_dir_manifest(protected)

                missing = [f for f in backed_up_files if f not in current_files]
                extra = [f for f in current_files if f not in backed_up_files]
                changed = [
                    f for f in backed_up_files
                    if f in current_files and backed_up_files[f] != current_files[f]
                ]

                dir_ok = not (missing or changed)

                result["dirs"][protected] = {
                    "identical": dir_ok,
                    "missing_files": missing,
                    "changed_files": changed,
                    "extra_files": extra,
                }

                if not dir_ok:
                    result["ok"] = False
                    logger.warning(
                        f"⚠️ 保護目錄 {protected} 與備份（{manifest_record['backup_time']}）不一致："
                        f"遺失 {len(missing)} 個、改變 {len(changed)} 個檔案"
                    )
                else:
                    logger.info(f"✅ 保護目錄 {protected} 內容與備份一致")

            return result

        def finalize(success: bool, message: str, result_data: dict, backup_dir: str) -> APIResponse:
            """更新結束（無論成功失敗）都執行備份比對，確保保護目錄未被動到"""
            verify_result = verify_against_backup(backup_dir)
            result_data["backup_verification"] = verify_result

            if not verify_result.get("ok", False):
                logger.critical(
                    f"🚨 保護目錄在本次更新（success={success}）後與備份不一致！請檢查：{backup_dir}"
                )
                message += "（⚠️ 警告：保護目錄內容與備份不一致，請檢查 log）"

            return APIResponse(success=success, message=message, data=result_data)

        # ---------------- 主流程 ----------------

        backup_dir = backup_protected_dirs()
        result_data = {
            "backup_dir": backup_dir,
            "backup_time": datetime.now().isoformat(),
        }

        try:
            if not fetch_all():
                logger.error("update failed: cannot fetch remote")
                return finalize(False, "無法連線至遠端倉庫，更新中止", result_data, backup_dir)

            old_tag = get_current_tag()
            latest_tag = get_latest_tag()
            result_data["previous_version"] = old_tag

            if latest_tag is None:
                return finalize(False, "遠端沒有任何版本標籤", result_data, backup_dir)

            if old_tag == latest_tag:
                result_data["current_version"] = old_tag
                result_data["updated"] = False
                return finalize(True, "目前已是最新版本", result_data, backup_dir)

            logger.info(f"開始更新：{old_tag} → {latest_tag}")

            try:
                subprocess.run(
                    ["git", "pull"], check=True, timeout=30,
                    capture_output=True, text=True
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                logger.error(f"git pull 失敗：{e}，嘗試回滾")
                rollback_to(old_tag)
                result_data["current_version"] = old_tag
                return finalize(False, "更新失敗（git pull 失敗），已自動回滾至前一版本", result_data, backup_dir)

            new_tag = get_current_tag()
            if new_tag != latest_tag:
                logger.error(f"pull 後版本不符（預期 {latest_tag}，實際 {new_tag}），回滾")
                rollback_to(old_tag)
                result_data["current_version"] = old_tag
                return finalize(False, "更新後版本異常，已自動回滾至前一版本", result_data, backup_dir)

            result_data["current_version"] = new_tag

            try:
                changed_files = subprocess.check_output(
                    ["git", "diff", "--name-only", old_tag, new_tag], text=True, timeout=5
                )
                if "requirements.txt" in changed_files:
                    subprocess.run(["pip", "install", "-r", "requirements.txt"], check=True, timeout=120)
            except Exception as e:
                logger.warning(f"Update failed {e}")

            new_info = parse_tag(new_tag)
            result_data["update_summary"] = new_info["summary"]
            logger.info(f"Update successful {old_tag} → {new_tag}")
            self.restart("System Update")

        except Exception as e:
            logger.critical(f"update() 發生未預期例外：{e}")
            return finalize(False, f"更新過程發生未預期錯誤：{e}", result_data, backup_dir)