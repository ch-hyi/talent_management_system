"""
職缺業務邏輯層
"""

import json
import traceback
import uuid

from datetime import datetime
from typing import Dict, Any, Optional

from ..repositories.vacancy_repository import VacancyRepository
from ..repositories.log_repository import LogRepository

from ..models.response import APIResponse
from ..models.vacancy import (
    Vacancy,
    VacancyFilter,
    VacancyUpdateRequest,
)
from ..models.log import LogEntry


class VacancyService:
    """職缺管理業務邏輯"""

    def __init__(
        self,
        vacancy_repo: VacancyRepository,
        log_repo: LogRepository
    ):
        self.vacancy_repo = vacancy_repo
        self.log_repo = log_repo

    # =========================================================
    # 查詢職缺
    # =========================================================

    def query_vacancies(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 30,
        offset: int = 0
    ) -> APIResponse:
        """查詢職缺資料"""

        try:
            vacancy_filter = (
                VacancyFilter(**filters)
                if filters
                else None
            )

            data = self.vacancy_repo.query_vacancies(
                vacancy_filter,
                limit,
                offset
            )

            return APIResponse(
                success=True,
                data=data,
                message=f"成功查詢 {len(data)} 筆職缺資料"
            )

        except TypeError as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="職缺篩選條件格式錯誤"
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="查詢職缺失敗"
            )

    # =========================================================
    # 取得職缺總數
    # =========================================================

    def get_vacancy_count(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> APIResponse:
        """取得符合條件的職缺數量"""

        try:
            vacancy_filter = (
                VacancyFilter(**filters)
                if filters
                else None
            )

            count = self.vacancy_repo.get_vacancy_count(
                vacancy_filter
            )

            if count is None:
                return APIResponse(
                    success=False,
                    error="count 為 None",
                    message="取得職缺數量失敗"
                )

            return APIResponse(
                success=True,
                data=count,
                message="取得職缺數量成功"
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="取得職缺數量失敗"
            )

    # =========================================================
    # 根據 vacancy_id 查詢
    # =========================================================

    def get_vacancy_by_id(
        self,
        vacancy_id: str
    ) -> APIResponse:
        """根據 vacancy_id 取得單一職缺"""

        try:
            if not vacancy_id:
                return APIResponse(
                    success=False,
                    message="vacancy_id 不能為空"
                )

            data = self.vacancy_repo.get_vacancy_by_id(
                vacancy_id
            )

            if not data:
                return APIResponse(
                    success=False,
                    message="找不到該職缺"
                )

            return APIResponse(
                success=True,
                data=data,
                message="取得職缺資料成功"
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="取得職缺資料失敗"
            )

    # =========================================================
    # 建立職缺
    # =========================================================

    def create_vacancy(
        self,
        vacancy: Vacancy,
        created_by: str
    ) -> APIResponse:
        """建立新職缺並記錄日誌"""

        try:
            if not created_by:
                return APIResponse(
                    success=False,
                    message="created_by 不能為空"
                )

            if not vacancy.position_title:
                return APIResponse(
                    success=False,
                    message="position_title 不能為空"
                )

            if not str(vacancy.position_title).strip():
                return APIResponse(
                    success=False,
                    message="position_title 不能只包含空白"
                )

            # 如果沒有 vacancy_id，由 Service 產生 UUID
            if not vacancy.vacancy_id:
                vacancy.vacancy_id = str(uuid.uuid4())

            current_time = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            vacancy.position_title = (
                vacancy.position_title.strip()
            )

            vacancy.created_at = current_time
            vacancy.updated_at = current_time

            vacancy.status = (
                str(vacancy.status).upper()
                if vacancy.status
                else "ACTIVE"
            )

            # 建立 CREATE Log
            log_entry = LogEntry.create_new(
                # 通用 Log 對應
                source="vacancy_management",
                source_id=vacancy.vacancy_id,
                name=vacancy.position_title,

                version=1,
                operator=created_by,

                # CREATE 保存建立後的完整資料
                snapshot_json="",

                status=vacancy.status,
                action="CREATE",
                previous_version=None,
                changed_info="",
                raw_text=(
                    f"{created_by} created vacancy "
                    f"{vacancy.position_title}"
                ),
                vacancy= vacancy.position_title,
                meeting="",
                note=""
            )

            # 建立職缺
            self.vacancy_repo.create_vacancy(vacancy)

            # 建立 Log
            self.log_repo.create_log(log_entry)

            return APIResponse(
                success=True,
                data={
                    "vacancy_id": vacancy.vacancy_id
                },
                message=(
                    f"成功建立職缺 "
                    f"{vacancy.position_title}"
                )
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="建立職缺失敗"
            )

    # =========================================================
    # 基礎更新職缺
    # =========================================================

    def update_vacancy(
        self,
        request: VacancyUpdateRequest
    ) -> APIResponse:
        """
        更新職缺資料。

        此方法只負責驗證及更新，
        不會建立 Log。

        正式 API 建議呼叫 update_vacancy_with_log()。
        """

        try:
            is_valid, error_message = request.validate()

            if not is_valid:
                return APIResponse(
                    success=False,
                    message=error_message
                )

            original_vacancy = (
                self.vacancy_repo.get_vacancy_by_id(
                    request.vacancy_id
                )
            )

            if not original_vacancy:
                return APIResponse(
                    success=False,
                    message="找不到該職缺"
                )

            # 避免直接修改 request 傳入的原始 dict
            updates = request.updates.copy()

            updates["updated_at"] = (
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )

            if "position_title" in updates:
                updates["position_title"] = str(
                    updates["position_title"]
                ).strip()

            if "status" in updates:
                updates["status"] = str(
                    updates["status"]
                ).upper()

            affected_rows = (
                self.vacancy_repo.update_vacancy(
                    request.vacancy_id,
                    updates
                )
            )

            return APIResponse(
                success=True,
                data={
                    "vacancy_id": request.vacancy_id,
                    "affected_rows": affected_rows
                },
                message="成功更新職缺資料"
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="更新職缺失敗"
            )

    # =========================================================
    # 更新職缺並建立 Log
    # =========================================================

    def get_template(self,vacancy_name,candidate_name,username)->APIResponse:
        pass

    def update_vacancy_with_log(
        self,
        vacancy_id: str,
        vacancy_name : str,
        updates: Dict[str, Any],
        operator: str
    ) -> APIResponse:
        """
        更新職缺並記錄日誌。

        Log 的 snapshot_json 保存更新前的完整資料，
        方便未來進行 rollback。
        """

        try:
            if not vacancy_id:
                return APIResponse(
                    success=False,
                    message="vacancy_id 不能為空"
                )

            if not updates:
                return APIResponse(
                    success=False,
                    message="updates 不能為空"
                )

            if not operator:
                return APIResponse(
                    success=False,
                    message="operator 不能為空"
                )

            # 1. 取得更新前資料
            original_vacancy = (
                self.vacancy_repo.get_vacancy_by_id(
                    vacancy_id
                )
            )

            if not original_vacancy:
                return APIResponse(
                    success=False,
                    message="找不到該職缺"
                )

            # 2. 建立更新請求並驗證
            update_request = VacancyUpdateRequest(
                vacancy_id=vacancy_id,
                updates=updates.copy(),
                operator=operator
            )

            is_valid, error_message = (
                update_request.validate()
            )

            if not is_valid:
                return APIResponse(
                    success=False,
                    message=error_message
                )

            # 3. 加入系統更新時間
            update_request.updates["updated_at"] = (
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )

            if "position_title" in update_request.updates:
                update_request.updates[
                    "position_title"
                ] = str(
                    update_request.updates[
                        "position_title"
                    ]
                ).strip()

            if "status" in update_request.updates:
                update_request.updates["status"] = str(
                    update_request.updates["status"]
                ).upper()

            # 4. 取得版本資訊
            previous_version = (
                self.log_repo.get_latest_version(
                    "vacancy_management",
                    vacancy_id
                )
            )

            max_version = self.log_repo.get_max_version(
                "vacancy_management",
                vacancy_id
            )

            new_version = (
                max_version + 1
                if max_version is not None
                else 1
            )

            # 5. 建立 UPDATE Log
            detailed_note = (
                f"{operator} updated vacancy "
                f"{vacancy_id}; fields: "
                f"{list(update_request.updates.keys())}"
            )

            log_entry = LogEntry.create_new(
                # 通用 Log 對應
                source="vacancy_management",
                source_id=vacancy_id,
                name = operator,

                version=new_version,
                operator=operator,

                # 保存更新前 Snapshot
                snapshot_json=json.dumps(
                    original_vacancy,
                    ensure_ascii=False
                ),
                vacancy=vacancy_name,
                note = "",
                meeting= None,
                status=update_request.updates.get(
                    "status",
                    original_vacancy.get("status")
                ),

                action="UPDATE",
                previous_version=previous_version,

                changed_info=json.dumps(
                    update_request.updates,
                    ensure_ascii=False
                ),

                raw_text=detailed_note
            )

            # 6. 執行更新
            affected_rows = (
                self.vacancy_repo.update_vacancy(
                    vacancy_id,
                    update_request.updates
                )
            )

            if affected_rows == 0:
                return APIResponse(
                    success=False,
                    data={
                        "vacancy_id": vacancy_id,
                        "affected_rows": 0
                    },
                    message="沒有職缺資料被更新"
                )

            # 7. 寫入 Log
            self.log_repo.create_log(log_entry)

            return APIResponse(
                success=True,
                data={
                    "vacancy_id": vacancy_id,
                    "affected_rows": affected_rows,
                    "version": new_version,
                    "updated_fields": list(
                        update_request.updates.keys()
                    )
                },
                message="成功更新職缺並記錄日誌"
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=(
                    str(e)
                    + "\n\n"
                    + traceback.format_exc()
                ),
                message="更新職缺失敗"
            )

    # =========================================================
    # 軟刪除職缺
    # =========================================================

    def delete_vacancy(
        self,
        vacancy_id: str,
        deleted_by: str
    ) -> APIResponse:
        """
        軟刪除職缺。

        不會真正刪除 vacancy 資料，
        而是將 status 更新為 DELETED。
        """

        try:
            if not vacancy_id:
                return APIResponse(
                    success=False,
                    message="vacancy_id 不能為空"
                )

            if not deleted_by:
                return APIResponse(
                    success=False,
                    message="deleted_by 不能為空"
                )

            # 1. 取得刪除前資料
            original_vacancy = (
                self.vacancy_repo.get_vacancy_by_id(
                    vacancy_id
                )
            )

            if not original_vacancy:
                return APIResponse(
                    success=False,
                    message="找不到該職缺"
                )

            if (
                str(
                    original_vacancy.get("status", "")
                ).upper()
                == "DELETED"
            ):
                return APIResponse(
                    success=False,
                    message="該職缺已經被刪除"
                )

            delete_time = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            updates = {
                "status": "DELETED",
                "updated_at": delete_time
            }

            # 2. 取得版本
            previous_version = (
                self.log_repo.get_latest_version(
                    "vacancy_management",
                    vacancy_id
                )
            )

            max_version = self.log_repo.get_max_version(
                "vacancy_management",
                vacancy_id
            )

            new_version = (
                max_version + 1
                if max_version is not None
                else 1
            )

            # 3. 建立 DELETE Log
            log_entry = LogEntry.create_new(
                # 通用 Log 對應
                source= "vacancy_management",
                source_id=vacancy_id,
                name=original_vacancy.get(
                    "position_title"
                ),

                version=new_version,
                operator=deleted_by,

                # 保存刪除前 Snapshot
                snapshot_json=json.dumps(
                    original_vacancy,
                    ensure_ascii=False
                ),

                status="DELETED",
                action="DELETE",
                previous_version=previous_version,

                changed_info=json.dumps(
                    updates,
                    ensure_ascii=False
                ),

                raw_text=(
                    f"{deleted_by} deleted vacancy "
                    f"{vacancy_id}"
                ),
                vacancy= original_vacancy.get(
                    "position_title"
                ),
                note = "",
                meeting=""
            )

            # 4. 軟刪除
            affected_rows = (
                self.vacancy_repo.update_vacancy(
                    vacancy_id,
                    updates
                )
            )

            if affected_rows == 0:
                return APIResponse(
                    success=False,
                    data={
                        "vacancy_id": vacancy_id,
                        "affected_rows": 0
                    },
                    message="沒有職缺資料被刪除"
                )

            # 5. 寫入 Log
            self.log_repo.create_log(log_entry)

            return APIResponse(
                success=True,
                data={
                    "vacancy_id": vacancy_id,
                    "affected_rows": affected_rows,
                    "version": new_version
                },
                message=f"成功刪除職缺 {vacancy_id}"
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="刪除職缺失敗"
            )

    # =========================================================
    # 恢復已刪除職缺
    # =========================================================

    def restore_vacancy(
        self,
        vacancy_id: str,
        operator: str
    ) -> APIResponse:
        """將已軟刪除的職缺恢復為 ACTIVE"""

        try:
            if not vacancy_id:
                return APIResponse(
                    success=False,
                    message="vacancy_id 不能為空"
                )

            if not operator:
                return APIResponse(
                    success=False,
                    message="operator 不能為空"
                )

            original_vacancy = (
                self.vacancy_repo.get_vacancy_by_id(
                    vacancy_id
                )
            )

            if not original_vacancy:
                return APIResponse(
                    success=False,
                    message="找不到該職缺"
                )

            current_status = str(
                original_vacancy.get("status", "")
            ).upper()

            if current_status != "DELETED":
                return APIResponse(
                    success=False,
                    message="該職缺目前不是刪除狀態"
                )

            updates = {
                "status": "ACTIVE",
                "updated_at": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            }

            previous_version = (
                self.log_repo.get_latest_version(
                    "vacancy_management",
                    vacancy_id
                )
            )

            max_version = self.log_repo.get_max_version(
                "vacancy_management",
                vacancy_id
            )

            new_version = (
                max_version + 1
                if max_version is not None
                else 1
            )

            log_entry = LogEntry.create_new(
                user_id=vacancy_id,
                user_account=vacancy_id,
                user_name=original_vacancy.get(
                    "position_title"
                ),

                version=new_version,
                operator=operator,

                # 保存恢復前的 DELETED 狀態
                snapshot_json=json.dumps(
                    original_vacancy,
                    ensure_ascii=False
                ),

                status="ACTIVE",
                action="RESTORE",
                previous_version=previous_version,

                changed_info=json.dumps(
                    updates,
                    ensure_ascii=False
                ),

                raw_text=(
                    f"{operator} restored vacancy "
                    f"{vacancy_id}"
                )
            )

            affected_rows = (
                self.vacancy_repo.update_vacancy(
                    vacancy_id,
                    updates
                )
            )

            if affected_rows == 0:
                return APIResponse(
                    success=False,
                    data={
                        "vacancy_id": vacancy_id,
                        "affected_rows": 0
                    },
                    message="沒有職缺資料被恢復"
                )

            self.log_repo.create_log(log_entry)

            return APIResponse(
                success=True,
                data={
                    "vacancy_id": vacancy_id,
                    "affected_rows": affected_rows,
                    "version": new_version
                },
                message="成功恢復職缺"
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="恢復職缺失敗"
            )

    # =========================================================
    # 取得欄位的不重複值
    # =========================================================

    def get_distinct_values(
        self,
        column_name: str
    ) -> APIResponse:
        """取得職缺欄位的不重複值"""

        try:
            allowed_columns = {
                "position_title",
                "work_location",
                "senior",
                "lab",
                "status"
            }

            if column_name not in allowed_columns:
                return APIResponse(
                    success=False,
                    message=(
                        f"不允許取得此欄位的不重複值："
                        f"{column_name}"
                    )
                )

            values = (
                self.vacancy_repo.get_distinct_values(
                    column_name
                )
            )

            return APIResponse(
                success=True,
                data=values,
                message=(
                    f"成功取得 {len(values)} 個"
                    f"{column_name} 不重複值"
                )
            )

        except ValueError as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="取得欄位值失敗"
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="取得欄位值失敗"
            )

    # =========================================================
    # 取得職缺篩選選項
    # =========================================================

    def get_vacancy_options(self) -> APIResponse:
        """取得前端職缺篩選選項"""

        try:
            options = {
                "statuses": [
                    "ACTIVE",
                    "INACTIVE",
                    "PAUSED",
                    "CLOSED",
                    "DELETED"
                ],

                "labs": (
                    self.vacancy_repo.get_distinct_values(
                        "lab"
                    )
                ),

                "seniors": (
                    self.vacancy_repo.get_distinct_values(
                        "senior"
                    )
                ),

                "work_locations": (
                    self.vacancy_repo.get_distinct_values(
                        "work_location"
                    )
                )
            }

            return APIResponse(
                success=True,
                data=options,
                message="成功取得職缺篩選選項"
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="取得職缺篩選選項失敗"
            )

    # =========================================================
    # 取得統計資料
    # =========================================================

    def get_statistics(self) -> APIResponse:
        """取得職缺統計資料"""

        try:
            stats = self.vacancy_repo.get_statistics()

            return APIResponse(
                success=True,
                data=stats,
                message="取得職缺統計資料成功"
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="取得職缺統計資料失敗"
            )