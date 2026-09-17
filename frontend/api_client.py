"""
前端 API 客戶端 - 統一管理所有後端 API 呼叫
"""
import requests
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import json
import streamlit as st
from config import API_URL



# ==========================================
# API Response 解析器
# ==========================================

@dataclass
class APIResponse:
    """API 回應解析類別"""
    success: bool
    data: Any = None
    message: Optional[str] = None
    error: Optional[str] = None
    
    @classmethod
    def from_dict(cls, response_dict: Optional[Dict]) -> 'APIResponse':
        """從 dict 建立 APIResponse"""
        if not response_dict:
            return cls(success=False, error="API 無回應")
        
        return cls(
            success=response_dict.get("success", False),
            data=response_dict.get("data"),
            message=response_dict.get("message"),
            error=response_dict.get("error")
        )
    
    def is_success(self) -> bool:
        return self.success
    
    def get_data(self, default=None):
        return self.data if self.data is not None else default
    
    def get_error_message(self) -> str:
        return self.error or self.message or "未知錯誤"

# ==========================================
# API 基礎設定
# ==========================================

class APIConfig:
    """API 設定"""
    BASE_URL = API_URL
    TIMEOUT = 30  # 秒

# ==========================================
# 統一 API 呼叫函數
# ==========================================

def api_call(method: str, endpoint: str, **kwargs) -> APIResponse:
    """統一的 API 呼叫函數"""
    url = f"{APIConfig.BASE_URL}{endpoint}"
    
    # 設定預設 timeout
    if 'timeout' not in kwargs:
        kwargs['timeout'] = APIConfig.TIMEOUT
    
    if 'json' in kwargs:
        try:
            json_data = kwargs.pop('json')
            kwargs['data'] = json.dumps(json_data, ensure_ascii=False)
            kwargs['headers'] = kwargs.get('headers', {})
            kwargs['headers']['Content-Type'] = 'application/json; charset=utf-8'
        except (TypeError, ValueError) as e:
            st.error(f"JSON 序列化失敗: {e}")
            return APIResponse(success=False, error=f"JSON 序列化失敗: {e}")

    try:
        if method == "GET":
            response = requests.get(url, **kwargs)
        elif method == "POST":
            response = requests.post(url, **kwargs)
        elif method == "PUT":
            response = requests.put(url, **kwargs)
        elif method == "DELETE":
            response = requests.delete(url, **kwargs)
        else:
            return APIResponse(success=False, error=f"不支援的 HTTP 方法: {method}")
        
        response.raise_for_status()
        return APIResponse.from_dict(response.json())
    
    except requests.exceptions.ConnectionError:
        return APIResponse(
            success=False,
            error="無法連線到後端 API，請確認服務是否啟動"
        )
    except requests.exceptions.Timeout:
        return APIResponse(success=False, error="請求超時")
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP 錯誤 {e.response.status_code}"
        try:
            error_detail = e.response.json().get("detail", "")
            if error_detail:
                error_msg += f": {error_detail}"
        except:
            pass
        return APIResponse(success=False, error=error_msg)
    except Exception as e:
        return APIResponse(success=False, error=f"未預期的錯誤: {e}")

# ==========================================
# 人才相關 API
# ==========================================

class TalentAPI:
    """人才管理 API 客戶端"""
    
    @staticmethod
    def create_talent(talent:Dict,body:str) -> APIResponse:
        """查詢人才列表"""
        return api_call(
            "POST",
            "/api/talents/create",
            json={
                "talent":talent,
                "body":body
            }
        )
    
    @staticmethod
    def query_talents(username,filters: Dict = None, limit: int = 30, offset: int = 0) -> APIResponse:
        """查詢人才列表"""
        return api_call(
            "POST",
            "/api/talents/query",
            json={
                "username":username,
                "filters": filters or {},
                "limit": limit,
                "offset": offset
            }
        )
    
    @staticmethod
    def get_taiwan_location():
        return api_call("GET","/api/talents/location")

    @staticmethod
    def get_talent_detail(source: str, source_id: str) -> APIResponse:
        """取得單一人才詳細資料"""
        return api_call("GET", f"/api/talents/{source}/{source_id}")
    
    @staticmethod
    def share(source: str, source_id: str,username:str) -> APIResponse:
        """取得單一人才詳細資料"""
        return api_call("GET", f"/api/talents/share",json={
            "source":source,
            "source_id":source_id,
            "username":username
        })

    @staticmethod
    def msg(source: str, source_id: str,username:str) -> APIResponse:
        """取得單一人才詳細資料"""
        return api_call("GET", f"/api/talents/resume",json={
            "source":source,
            "source_id":source_id,
            "username":username
        })

    @staticmethod
    def ocr(file_path,username:str) -> APIResponse:
        """取得單一人才詳細資料"""
        return api_call("GET", f"/api/talents/ocr",json={
            "file_path":file_path,
            "username":username
        })

    @staticmethod
    def get_ocr_result(file_path,username:str) -> APIResponse:
        """取得單一人才詳細資料"""
        return api_call("GET", f"/api/talents/ocr/result",json={
            "file_path":file_path,
            "username":username
        })

    @staticmethod
    def get_talent_by_share_id(share_id:str) -> APIResponse:
        """取得單一人才詳細資料"""
        return api_call("GET", f"/api/talents/share/{share_id}")
    
    @staticmethod
    def update_talent(source: str, source_id: str, updates: Dict, operator: str) -> APIResponse:
        """更新人才資料"""
        return api_call(
            "PUT",
            "/api/talents/update",
            json={
                "source": source,
                "source_id": source_id,
                "updates": updates,
                "operator": operator
            }
        )

    
    @staticmethod
    def check_if_locked(source: str,source_id: str,):
        """確認人才是否鎖定"""
        return api_call(
            "GET",
            f"/api/talents/check-lock/{source}/{source_id}")
    
    @staticmethod
    def lock_talent(source: str, source_id: str) -> APIResponse:
        """鎖定人才(待修改)"""
        return api_call(
            "POST",
            "/api/talents/lock")
    
    @staticmethod
    def unlock_talent(source: str, source_id: str) -> APIResponse:
        """解鎖人才(待修改)"""
        return api_call(
            "POST",
            "/api/talents/unlock",
            params={"source": source, "source_id": source_id}
        )
    
    @staticmethod
    def get_distinct_values(column_name: str) -> APIResponse:
        """取得欄位的不重複值"""
        return api_call("GET", f"/api/talents/options/{column_name}")
    
    @staticmethod
    def update_talent_with_log(request:Dict)->APIResponse:
        """更新人才與LOGS"""
        return api_call(
        "PUT",
        "/api/talents/update" ,
        json =request
        )

    @staticmethod
    def get_options() -> APIResponse:
        """取得所有篩選選項（快取版）"""
        return api_call("GET", "/api/talents/options")
    
    @staticmethod
    def submit_scoring(source: str, source_id: str, row_data: Dict) -> APIResponse:
        """提交評分任務"""
        return api_call(
            "POST",
            "/api/talents/scoring",
            json={
                "source": source,
                "source_id": source_id,
                "row_data": row_data
            }
        )

    @staticmethod
    def delete_talent(source:str ,source_id:str,operator:str) ->APIResponse:
            return api_call(
                "POST",
                "/api/talents/delete",
                json={
                    "source": source,
                    "source_id": source_id,
                    "operator":operator
                }
            )

# ==========================================
# 日誌相關 API
# ==========================================

class LogAPI:
    """日誌管理 API 客戶端"""
    
    @staticmethod
    def query_logs(filters: Dict = None, limit: int = 20, offset: int = 0) -> APIResponse:
        """查詢日誌"""
        return api_call(
            "POST",
            "/api/logs/query",
            json={
                "filters": filters or {},
                "limit": limit,
                "offset": offset
            }
        )
    
    @staticmethod
    def get_log_by_id(log_id: str) -> APIResponse:
        """取得單一日誌"""
        return api_call("GET", f"/api/logs/{log_id}")
    
    @staticmethod
    def get_talent_logs(source: str, source_id: str, limit: int = 50) -> APIResponse:
        """取得特定候選人的操作歷史"""
        return api_call(
            "GET",
            f"/api/logs/talent/{source}/{source_id}",
            params={"limit": limit}
        )

    @staticmethod
    def get_status_logs(filters: Dict = None, limit: int = 20, offset: int = 0) -> APIResponse:
        """取得欄位的不重複值"""
        return api_call("GET", f"/api/logs/status",json = {
                "filters": filters or {},
                "limit": limit,
                "offset": offset
            })

    @staticmethod
    def get_distinct_values(column_name: str) -> APIResponse:
        """取得欄位的不重複值"""
        return api_call("GET", f"/api/logs/options/{column_name}")
    
    @staticmethod
    def get_log_metadata() -> APIResponse:
        """取得日誌元資料（輕量化列表）"""
        return api_call("GET", "/api/logs/metadata/all")
    
    @staticmethod
    def query_logs_by_ids(log_ids: List[str]) -> APIResponse:
        """根據 log_id 列表查詢完整日誌"""
        return api_call(
            "POST",
            "/api/logs/query-by-ids",
            json=log_ids
        )
    
    @staticmethod
    def get_statistics() -> APIResponse:
        """取得日誌統計"""
        return api_call("GET", "/api/logs/statistics")
    
    @staticmethod
    def delete_logs(log_ids: List[str], operator: str, retention_days: int = 180, force_delete: bool = False) -> APIResponse:
        """刪除指定日誌"""
        return api_call(
            "DELETE",
            "/api/logs/delete",
            json={
                "log_ids": log_ids,
                "operator": operator,
                "retention_days": retention_days,
                "force_delete": force_delete
            }
        )
class UserAPI:
    """使用者管理 API 客戶端"""
    
    @staticmethod
    def auth()->APIResponse:
        return api_call("GET", f"/api/user/auth")
    
    @staticmethod
    def login(user_account)->APIResponse:
        return api_call("PUT", f"/api/user/auth/{user_account}")

    @staticmethod
    def create_user(request:Dict)->APIResponse:
        return api_call("POST" , "/api/user/create",json = request)

    @staticmethod
    def query_user( filters: Dict = None, limit: int = 20, offset: int = 0 ) -> APIResponse:
        """查詢使用者"""
        return api_call(
            "POST",
            "/api/user/query",
            json={
                "filters": filters or {},
                "limit": limit,
                "offset": offset,
            }
        )
    
    
    @staticmethod
    def update_user( user_id:str ,updates:Dict ,operator:str ) -> APIResponse:
        """查詢使用者"""
        return api_call(
            "PUT",
            "/api/user/update",
            json={
                "user_id": user_id,
                "updates": updates,
                "operator":operator
            }
        )

    @staticmethod
    def get_user_by_id(user_id: str) -> APIResponse:
        """取得單一使用者"""
        return api_call("GET", f"/api/user/id/{user_id}")

    @staticmethod
    def get_user_by_account(username: str) -> APIResponse:
        """取得單一使用者"""
        return api_call("GET", f"/api/user/account/{username}")

    
    @staticmethod
    def get_statistics() -> APIResponse:
        """取得日誌統計"""
        return api_call("GET", "/api/user/statistics")
    
    @staticmethod
    def delete_user(user_id: str, operator: str) -> APIResponse:
        """刪除指定使用者"""
        return api_call(
            "DELETE",
            f"/api/user/{user_id}",
            params={"operator": operator}
        )
    
class VacancyAPI:
    """使用者管理 API 客戶端"""
    
    @staticmethod
    def get_lab_options() -> APIResponse:
        return api_call(
            "POST",
            "/api/vacancy/lab",
        )

    @staticmethod
    def query_vacancy( filters: Dict = None, limit: int = 20, offset: int = 0 ) -> APIResponse:
        """查詢使用者"""
        return api_call(
            "POST",
            "/api/vacancy/query",
            json={
                "filters": filters or {},
                "limit": limit,
                "offset": offset,
            }
        )
    
    @staticmethod
    def create_vacancy(vacancy:Dict, operator:str) -> APIResponse:
        """創建職缺"""
        
        request_data = {
            **vacancy,
            "created_by": operator
        }

        return api_call(
            "POST",
            "/api/vacancy/create",
            json = request_data
        )


    @staticmethod
    def update_vacancy( vacancy_name:str,vacancy_id:str ,updates:Dict,operator:str ) -> APIResponse:
        """查詢使用者"""
        return api_call(
            "PUT",
            f"/api/vacancy/update/{vacancy_id}",
            json={
                "vacancy_name":vacancy_name,
                "updates": updates,
                "operator":operator
            }
        )

    @staticmethod
    def get_vacancy_by_id(vacancy_id: str) -> APIResponse:
        """取得單一使用者"""
        return api_call("GET", f"/api/vacancy/{vacancy_id}")

    @staticmethod
    def get_distinct_values(column_name:str)->APIResponse:
        return api_call(
            "GET",
            f"/api/vacancy/options/{column_name}",
        )
    
    @staticmethod
    def get_statistics() -> APIResponse:
        """取得日誌統計"""
        return api_call("GET", "/api/vacancy/statistics")
    
    @staticmethod
    def delete_vacancy(vacancy_ids: List[str], operator: str, retention_days: int = 180, force_delete: bool = False) -> APIResponse:
        """刪除指定使用者"""
        return api_call(
            "DELETE",
            f"/api/vacancy/{vacancy_ids}",
            json={
                "user_ids": vacancy_ids,
                "operator": operator,
                "retention_days": retention_days,
                "force_delete": force_delete
            }
        )

class LabAPI:
    """Lab 管理 API 客戶端"""

    # =========================================================
    # 取得全部 Lab
    # =========================================================

    @staticmethod
    def get_all_labs() -> APIResponse:
        """取得全部 Lab 資料"""

        return api_call(
            "GET",
            "/api/lab/all"
        )

    # =========================================================
    # 取得 Lab 數量
    # =========================================================

    @staticmethod
    def get_lab_count() -> APIResponse:
        """取得 Lab 總數"""

        return api_call(
            "GET",
            "/api/lab/count"
        )

    # =========================================================
    # 取得 Lab 下拉選項
    # =========================================================

    @staticmethod
    def get_lab_options() -> APIResponse:
        """
        取得 Lab 下拉選單資料。

        回傳欄位：
        - lab_id
        - name
        """

        return api_call(
            "GET",
            "/api/lab/options"
        )

    # =========================================================
    # 依 ID 取得單一 Lab
    # =========================================================

    @staticmethod
    def get_lab_by_id(
        lab_id: str
    ) -> APIResponse:
        """根據 lab_id 取得單一 Lab"""

        return api_call(
            "GET",
            f"/api/lab/{lab_id}"
        )

    # =========================================================
    # 依名稱取得單一 Lab
    # =========================================================

    @staticmethod
    def get_lab_by_name(
        name: str
    ) -> APIResponse:
        """根據名稱取得單一 Lab"""

        return api_call(
            "GET",
            f"/api/lab/by-name/{name}"
        )

    # =========================================================
    # 檢查 Lab 名稱是否存在
    # =========================================================

    @staticmethod
    def check_lab_name_exists(
        name: str,
        exclude_lab_id: Optional[str] = None
    ) -> APIResponse:
        """
        檢查 Lab 名稱是否已存在。

        Args:
            name:
                要檢查的 Lab 名稱。

            exclude_lab_id:
                更新 Lab 時，排除目前 Lab ID。
        """

        params: Dict[str, Any] = {}

        if exclude_lab_id:
            params["exclude_lab_id"] = exclude_lab_id

        return api_call(
            "GET",
            f"/api/lab/check-name/{name}",
            params=params
        )

    # =========================================================
    # 建立 Lab
    # =========================================================

    @staticmethod
    def create_lab(
        lab_data: Dict[str, Any]
    ) -> APIResponse:
        """
        建立新的 Lab。

        lab_data 可包含：
        - name
        - address
        - latitude
        - longitude
        - template
        - contact
        """

        return api_call(
            "POST",
            "/api/lab/create",
            json=lab_data
        )

    # =========================================================
    # 更新 Lab
    # =========================================================

    @staticmethod
    def update_lab(
        lab_id: str,
        updates: Dict[str, Any]
    ) -> APIResponse:
        """
        更新指定 Lab。

        僅需在 updates 中傳入實際要修改的欄位。
        """

        return api_call(
            "PUT",
            f"/api/lab/update/{lab_id}",
            json=updates
        )

    # =========================================================
    # 硬刪除 Lab
    # =========================================================

    @staticmethod
    def delete_lab(
        lab_id: str
    ) -> APIResponse:
        """永久刪除指定 Lab"""

        return api_call(
            "DELETE",
            f"/api/lab/{lab_id}"
        )
    
class SettingsAPI:

    BASE = "/api/settings"

    def get_all_settings():
        return api_call("GET", f"{SettingsAPI.BASE}/all")

    def get_theme():
        return api_call("GET", f"{SettingsAPI.BASE}/theme")

    def update_theme(theme: dict, operator: str):
        return api_call("PUT", f"{SettingsAPI.BASE}/theme", json={
            "theme": theme,
            "operator": operator
        })

    def update_score_threshold(threshold:int,operator:str):
        return api_call("PUT", f"{SettingsAPI.BASE}/score_threshold", json={
            "threshold": threshold,
            "operator": operator
        })

    def get_logo():
        return api_call("GET", f"{SettingsAPI.BASE}/logo")

    def update_logo(file, operator: str):
        return api_call("PUT", f"{SettingsAPI.BASE}/logo",
            files={"logo": file},
            data={"operator": operator}
        )

    def update_ex_temp(settings: dict, operator: str):
        return api_call("PUT", f"{SettingsAPI.BASE}/template/external", json={
            "settings": settings,
            "operator": operator
        })

    def update_in_temp(settings: dict, operator: str):
        return api_call("PUT", f"{SettingsAPI.BASE}/template/internal", json={
            "settings": settings,
            "operator": operator
        })

    def get_ex_temp():
        return api_call("GET", f"{SettingsAPI.BASE}/template/external")

    def get_in_temp():
        return api_call("GET", f"{SettingsAPI.BASE}/template/internal")

    def restart(operator: str):
        return api_call("POST", f"{SettingsAPI.BASE}/restart", json={
            "operator": operator
        })