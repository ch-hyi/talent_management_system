"""
用戶業務邏輯層
"""
import json
from typing import Dict, Any, Optional
from ..repositories.user_repository import UserRepository
from ..repositories.log_repository import LogRepository
from ..models.response import APIResponse
from ..models.user import UserFilter, UserUpdateRequest, User
from ..models.log import LogEntry
import traceback
from datetime import datetime
import streamlit_authenticator as stauth
import uuid

class UserService:
    """用戶管理邏輯"""
    
    def __init__(self, user_repo: UserRepository, log_repo: LogRepository):
        self.user_repo = user_repo
        self.log_repo = log_repo
    
    def auth(self,):
        auth = self.user_repo.auth()
        return APIResponse(success=True,
                           data = auth,
                           message= f"USER LIST ")
    def login(self,user_account):

        time = self.user_repo.login(user_account)
        return APIResponse(success=True,
                           data = time,
                           message= f"USER LIST ")

    def query_users(
        self,
        filters: Optional[Dict] = None,
        limit: int = 30,
        offset: int = 0
    ) -> APIResponse:
        """查詢用戶資料"""
        try:
            # 轉換篩選條件
            user_filter = UserFilter(**filters) if filters else None
            
            # 執行查詢
            data = self.user_repo.query_users(user_filter, limit, offset)
            
            return APIResponse(
                success=True,
                data=data,
                message=f"成功查詢 {len(data)} 筆資料"
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="查詢失敗"
            )
        
    def get_user_count(self, filters: Optional[Dict] = None) -> APIResponse:
        """取得用戶總數"""
        try:
            count = self.user_repo.get_user_count(filters)
            
            if count is not None:
                return APIResponse(success=True, data=count, message="查詢成功")
            else:
                return APIResponse(success=False, error="count為None", message="查詢失敗")
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="查詢失敗"
            )
    
    def get_user_by_account(self, username: str) -> APIResponse:
        """取得單一用戶資料"""
        try:
            data = self.user_repo.get_user_by_account(username)
            
            if not data:
                return APIResponse(
                    success=False,
                    message="找不到該用戶資料"
                )
            
            return APIResponse(
                success=True,
                data=data
            )
        except Exception as e:
            print(traceback.format_exc())
            return APIResponse(
                success=False,
                error=str(e),
                message="查詢失敗"
            )
    
    def get_user_by_id(self, user_id: str) -> APIResponse:
        """根據帳號取得用戶"""
        try:
            data = self.user_repo.get_user_by_id(user_id)
            
            if not data:
                return APIResponse(
                    success=False,
                    message="找不到該用戶帳號"
                )
            
            return APIResponse(
                success=True,
                data=data
            )
        except Exception as e:
            print(traceback.format_exc())
            return APIResponse(
                success=False,
                error=str(e),
                message="查詢失敗"
            )
    
    def create_user(self, user: User, created_by: str) -> APIResponse:
        """創建新用戶"""
        try:
            user.create_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            user.created_by = created_by
            user.status = "ACTIVE"
            user.user_id = str(uuid.uuid4())
            # 記錄日誌
            log_entry = LogEntry.create_new(
                source="user_management",
                source_id=user.user_id,
                name=user.user_name,
                version=1,
                operator=created_by,
                snapshot_json=json.dumps(user.to_dict(), ensure_ascii=False),
                status=user.status,
                action="UPDATE",
                vacancy="",
                note="",
                meeting="",
                previous_version=None,
                changed_info=json.dumps(user.to_dict(), ensure_ascii=False),
                raw_text=created_by+" Created " +user.user_name
            )
            if user.user_role=="admin":
                user.vacancy_incharge=[]
            user.password_hash = stauth.Hasher.hash(user.password_hash)
            self.user_repo.create_user(user)
            self.user_repo.update_vacancy_incharge(user.user_id,user.vacancy_incharge)
            self.log_repo.create_log(log_entry)
            
            return APIResponse(
                success=True,
                data={"user_id": user.user_id},
                message=f"成功創建用戶 {user.user_account}"
            )
        except Exception as e:
            print(e, traceback.format_exc())
            return APIResponse(
                success=False,
                error=str(e),
                message="創建失敗"
            )
    
    def update_user(self, request: UserUpdateRequest) -> APIResponse:
        """更新用戶資料"""
        try:
            # 驗證請求
            is_valid, error_msg = request.validate()
            if not is_valid:
                return APIResponse(
                    success=False,
                    message=error_msg
                )
            
            # 更新時間戳
            request.updates["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            request.updates["updated_by"] = request.operator
            if "vacancy_incharge" in request.updates:
                vacancy_incharge = request.updates["vacancy_incharge"]
                del request.updates["vacancy_incharge"]
                update_vacancy_incharge = self.user_repo.update_vacancy_incharge(request.user_id,vacancy_incharge)
            # 執行更新
            affected_rows = self.user_repo.update_user(
                request.user_id,
                request.updates
            )


            
            return APIResponse(
                success=True,
                data={"affected_rows": affected_rows},
                message=f"成功更新用戶資料"
            )
        except Exception as e:
            print(traceback.format_exc())
            return APIResponse(
                success=False,
                error=str(e),
                message="更新失敗"
            )
    
    def delete_user(self, user_id: str, deleted_by: str) -> APIResponse:
        """軟刪除用戶（標記為已刪除）"""
        try:
            delete_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            user = self.user_repo.get_user_by_id(user_id)
            affected_rows = self.user_repo.update_user(
                user_id,
                {
                    "status": "DELETED",
                    "deleted_time": delete_time,
                    "deleted_by": deleted_by
                }
            )

            previous_version = self.log_repo.get_latest_version("user_management",user_id)
            new_version = self.log_repo.get_max_version("user_management",user_id) + 1
            log_entry = LogEntry.create_new(
                source="user_management",
                source_id=user_id,
                name=user["user_name"],
                version=new_version,
                operator=deleted_by,
                snapshot_json=json.dumps(user, ensure_ascii=False),
                status=user["status"],
                action="DELETE",
                vacancy="",
                note="",
                meeting="",
                previous_version=previous_version,
                changed_info=json.dumps(user, ensure_ascii=False),
                raw_text=deleted_by+" Deleted " +user["user_name"]
            )
            self.log_repo.create_log(log_entry)

            return APIResponse(
                success=True,
                data={"affected_rows": affected_rows},
                message=f"成功刪除用戶 {user_id}"
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="刪除失敗"
            )
    
    def update_last_login(self, user_id: str) -> APIResponse:
        """更新最後登錄時間"""
        try:
            last_login = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            affected_rows = self.user_repo.update_user(
                user_id,
                {"last_login": last_login}
            )
            
            return APIResponse(
                success=True,
                data={"affected_rows": affected_rows},
                message="登錄時間已更新"
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="更新失敗"
            )
    
    def update_user_with_log(
        self,
        user_id: str,
        updates: Dict,
        operator: str
    ) -> APIResponse:
        """更新用戶資料並記錄日誌"""
        try:
            # 1. 取得原始用戶資料
            original_user = self.user_repo.get_user_by_id(user_id)
            if not original_user:
                return APIResponse(
                    success=False,
                    message="找不到該用戶"
                )
            
            # 2. 添加系統欄位
            updates["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            updates["updated_by"] = operator
            
            # 3. 取得版本號
            previous_version = self.log_repo.get_latest_version("user_management",user_id)
            new_version = self.log_repo.get_max_version("user_management",user_id) + 1
            
            # 4. 建立日誌記錄
            detailed_note = f"{operator} 對以下欄位進行修改: {str(list(updates.keys()))}"
            
            log_entry = LogEntry.create_new(
                source="user_management",
                source_id=user_id,
                name=original_user.get("user_name"),
                version=new_version,
                operator=operator,
                snapshot_json=json.dumps(original_user, ensure_ascii=False),
                status=updates.get("status", original_user.get("status")),
                action="UPDATE",
                vacancy="",
                note="",
                meeting="",
                previous_version=previous_version,
                changed_info=json.dumps(updates, ensure_ascii=False),
                raw_text=detailed_note
            )
            if "password_hash" in updates:
                updates["password_hash"] = stauth.Hasher.hash(updates["password_hash"])
            # 5. 執行更新
            update_request = UserUpdateRequest(
                user_id=user_id,
                updates=updates,
                operator=operator
            )
            
            update_result = self.update_user(update_request)
            if not update_result.success:
                log_entry.error_message = update_result.message
                return update_result
            
            # 6. 記錄日誌
            self.log_repo.create_log(log_entry)
            
            return APIResponse(
                success=True,
                data={
                    "updated_fields": len(updates),
                    "user_id": user_id
                },
                message=f"成功更新用戶資料並記錄日誌"
            )
            
        except Exception as e:
            print(traceback.format_exc())
            return APIResponse(
                success=False,
                error=str(e) + "\n\n" + traceback.format_exc(),
                message="更新失敗"
            )
    
    def get_distinct_values(self, column_name: str) -> APIResponse:
        """取得欄位的不重複值列表"""
        try:
            values = self.user_repo.get_distinct_values(column_name)
            
            return APIResponse(
                success=True,
                data=values,
                message=f"成功取得 {len(values)} 個不重複值"
            )
        except ValueError as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="查詢失敗"
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="查詢失敗"
            )
    
    def get_user_options(self) -> APIResponse:
        """取得用戶選項（用於篩選）"""
        try:
            options = {
                "roles": self.user_repo.get_distinct_values("user_role"),
                "statuses": ["ACTIVE", "INACTIVE", "DELETED"]
            }
            
            return APIResponse(
                success=True,
                data=options,
                message="成功取得用戶選項"
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="查詢失敗"
            )
        
    def get_statistics(self) -> APIResponse:
        """取得使用者統計資料"""

        try:

            stats = self.user_repo.get_statistics()

            return APIResponse(
                success=True,
                data=stats,
                message="取得統計資料成功"
            )

        except Exception as e:

            return APIResponse(
                success=False,
                error=str(e),
                message="取得統計資料失敗"
            )