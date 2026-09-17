"""
FastAPI 用戶管理端點
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse
import traceback
from fastapi import Query
from ..repositories.user_repository import UserRepository
from ..repositories.log_repository import LogRepository 
from ..services.user_service import UserService
from ..services.log_service import LogService
from ..models.response import APIResponse
from ..models.user import User, UserUpdateRequest

# ==========================================
# 路由初始化
# ==========================================

router = APIRouter(prefix="/api/user", tags=["user"])

# ==========================================
# 依賴注入
# ==========================================

def get_user_service() -> UserService:
    """取得 UserService 實例"""
    user_repo = UserRepository()
    log_repo = LogRepository()
    return UserService(user_repo, log_repo)


# ==========================================
# 請求模型
# ==========================================

class UserQueryRequest(BaseModel):
    """查詢用戶請求"""
    filters: Optional[Dict[str, Any]] = None
    limit: int = Field(30, ge=1, le=1000000000000000000000000)
    offset: int = Field(0, ge=0)

class UserCountRequest(BaseModel):
    """用戶計數請求"""
    filters: Optional[Dict[str, Any]] = None

class UserCreateRequest(BaseModel):
    """創建用戶請求"""
    user_id: str = Field(default=None, description="用戶 ID")
    user_account: str = Field(..., description="用戶帳號")
    user_name: str = Field(..., description="用戶名稱")
    user_email: str = Field(..., description="用戶郵箱")
    password_hash: str = Field(..., description="密碼雜湊值")
    user_role: Optional[str] = Field(None, description="用戶角色")
    vacancies_in_charge: Optional[str] = Field(None, description="負責職位 (JSON)")
    created_by: str = Field(..., description="創建者")

class UserUpdateRequestModel(BaseModel):
    """更新用戶請求"""
    user_id: str = Field(..., description="用戶 ID")
    updates: Dict[str, Any] = Field(..., description="更新欄位")
    operator: str = Field(..., description="操作者")

class UserPasswordUpdateRequest(BaseModel):
    """更新密碼請求"""
    user_id: str = Field(..., description="用戶 ID")
    password_hash: str = Field(..., description="新密碼雜湊值")
    operator: str = Field(..., description="操作者")

class UserStatusUpdateRequest(BaseModel):
    """更新用戶狀態請求"""
    user_ids: List[str] = Field(..., description="用戶 ID 列表")
    status: str = Field(..., description="新狀態")
    operator: str = Field(..., description="操作者")

class UserVacanciesUpdateRequest(BaseModel):
    """更新負責職位請求"""
    user_id: str = Field(..., description="用戶 ID")
    vacancies: str = Field(..., description="職位列表 (JSON)")
    operator: str = Field(..., description="操作者")

# ==========================================
# API 端點 - 查詢
# ==========================================

@router.get("/statistics")
async def get_statistics(
    service: UserService = Depends(get_user_service)
):
    """
    取得用戶統計資訊
    
    返回:
    - total_users: 總用戶數
    - active_users: 活躍用戶數
    - inactive_users: 非活躍用戶數
    - by_role: 按角色分布
    - recent_logins: 最近登錄用戶
    """
    try:
        stat = service.get_statistics()
        result = APIResponse(
            success=True,
            data=stat,
            message="統計資料取得成功"
        )
        
        return result.to_dict()
    
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# API 端點 - 驗證
# ==========================================

@router.post("/check/account-exists")
async def check_account_exists(
    user_account: str = Body(..., description="用戶帳號"),
    service: UserService = Depends(get_user_service)
):
    """
    檢查帳號是否已存在
    
    範例:
    {
        "user_account": "john.doe"
    }
    """
    try:
        user_repo = UserRepository()
        exists = user_repo.check_user_exists(user_account)
        
        return APIResponse(
            success=True,
            data={"exists": exists},
            message="檢查完成"
        ).to_dict()
    
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check/email-exists")
async def check_email_exists(
    user_email: str = Body(..., description="用戶郵箱"),
    exclude_user_id: Optional[str] = Body(None, description="排除的用戶 ID"),
    service: UserService = Depends(get_user_service)
):
    """
    檢查郵箱是否已存在
    
    範例:
    {
        "user_email": "john@example.com",
        "exclude_user_id": "USR001"
    }
    """
    try:
        user_repo = UserRepository()
        exists = user_repo.check_email_exists(user_email, exclude_user_id)
        
        return APIResponse(
            success=True,
            data={"exists": exists},
            message="檢查完成"
        ).to_dict()
    
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post("/query")
async def query_users(
    request: UserQueryRequest,
    service: UserService = Depends(get_user_service)
):
    """
    查詢用戶資料
    
    範例:
    {
        "filters": {
            "user_role": "recruiter",
            "status": "ACTIVE",
            "search_keyword": "張"
        },
        "limit": 30,
        "offset": 0
    }
    """

    result = service.query_users(
        filters=request.filters,
        limit=request.limit,
        offset=request.offset
    )

    
    if not result.success:
        print(result.error)
        print(result.message)
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.to_dict()


@router.post("/count")
async def get_user_count(
    request: UserCountRequest,
    service: UserService = Depends(get_user_service)
):
    """
    取得符合條件的用戶總數
    
    範例:
    {
        "filters": {
            "user_role": "recruiter",
            "status": "ACTIVE"
        }
    }
    """
    result = service.get_user_count(request.filters)
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.to_dict()




@router.get("/id/{user_id}")
async def get_user_by_id(
    user_id: str,
    service: UserService = Depends(get_user_service)
):
    """
    根據帳號取得用戶資料
    
    範例: GET /api/user/account/john.doe
    """
    result = service.get_user_by_id(user_id)
    
    if not result.success:
        raise HTTPException(status_code=404, detail=result.message)
    
    return result.to_dict()


# ==========================================
# API 端點 - 創建
# ==========================================

@router.get("/auth")
async def auth( service: UserService = Depends(get_user_service)):
    auth = service.auth()
    return auth.to_dict()

@router.put("/auth/{user_account}")
async def login( user_account,service: UserService = Depends(get_user_service)):
    login = service.login(user_account)
    return login.to_dict()

@router.post("/create")
async def create_user(
    request: UserCreateRequest,
    service: UserService = Depends(get_user_service)
):
    """
    創建新用戶
    
    範例:
    {
        "user_id": "USR001",
        "user_account": "john.doe",
        "user_name": "John Doe",
        "user_email": "john@example.com",
        "password_hash": "$2b$12$...",
        "user_role": "recruiter",
        "created_by": "admin"
    }
    """
    try:
        user = User(
            user_id="",
            user_account=request.user_account,
            user_name=request.user_name,
            user_email=request.user_email,
            password_hash=request.password_hash,
            user_role=request.user_role,
            created_by=request.created_by,
            status="ACTIVE"
        )
        
        result = service.create_user(user, request.created_by)
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)
        
        return result.to_dict()
    
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# API 端點 - 更新
# ==========================================


@router.put("/status/batch")
async def update_user_status_batch(
    request: UserStatusUpdateRequest,
    service: UserService = Depends(get_user_service)
):
    """
    批量更新用戶狀態
    
    範例:
    {
        "user_ids": ["USR001", "USR002", "USR003"],
        "status": "INACTIVE",
        "operator": "admin"
    }
    """
    results = []
    
    for user_id in request.user_ids:
        result = service.update_user_with_log(
            user_id=user_id,
            updates={"status": request.status},
            operator=request.operator
        )
        
        results.append({
            "user_id": user_id,
            "success": result.success,
            "message": result.message
        })
    
    success_count = sum(1 for r in results if r["success"])
    
    return APIResponse(
        success=True,
        data={
            "total": len(results),
            "success": success_count,
            "failed": len(results) - success_count,
            "details": results
        },
        message=f"狀態更新完成: {success_count}/{len(results)} 成功"
    ).to_dict()


# ==========================================
# API 端點 - 刪除
# ==========================================

@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    operator: str = Query(..., description="操作者ID"),
    service: UserService = Depends(get_user_service)
):
    """
    刪除用戶（軟刪除）
    
    範例:
    DELETE /api/user/USR001
    Body: {"operator": "admin"}
    """
    try:
        result = service.delete_user(user_id, operator)
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)
        
        return result.to_dict()
    
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/batch")
async def delete_users_batch(
    user_ids: List[str] = Body(..., description="用戶 ID 列表"),
    operator: str = Body(..., description="操作者"),
    service: UserService = Depends(get_user_service)
):
    """
    批量刪除用戶（軟刪除）
    
    範例:
    {
        "user_ids": ["USR001", "USR002", "USR003"],
        "operator": "admin"
    }
    """
    results = []
    
    for user_id in user_ids:
        result = service.delete_user(user_id, operator)
        
        results.append({
            "user_id": user_id,
            "success": result.success,
            "message": result.message
        })
    
    success_count = sum(1 for r in results if r["success"])
    
    return APIResponse(
        success=True,
        data={
            "total": len(results),
            "success": success_count,
            "failed": len(results) - success_count,
            "details": results
        },
        message=f"刪除完成: {success_count}/{len(results)} 成功"
    ).to_dict()


# ==========================================
# API 端點 - 登錄相關
# ==========================================


# ==========================================
# API 端點 - 查詢選項
# ==========================================

@router.get("/options/all")
async def get_user_options(
    service: UserService = Depends(get_user_service)
):
    """
    取得用戶相關的所有選項
    
    返回: 角色、狀態等選項
    """
    result = service.get_user_options()
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.to_dict()


@router.put("/update")
async def update_user_with_log(
    request: UserUpdateRequestModel,
    service: UserService = Depends(get_user_service)
):
    """
    更新用戶資料並記錄日誌
    
    範例:
    {
        "user_id": "USR001",
        "updates": {
            "user_name": "Jane Doe",
            "user_role": "manager"
        },
        "operator": "admin"
    }
    """
    try:
        result = service.update_user_with_log(
            user_id=request.user_id,
            updates=request.updates,
            operator=request.operator
        )
        print(result)
        print(result.message,result.error)

        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)
        
        return result.to_dict()
    
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/options/{column_name}")
async def get_distinct_values(
    column_name: str,
    service: UserService = Depends(get_user_service)
):
    """
    取得欄位的不重複值列表
    
    支援的欄位:
    - user_role: 用戶角色
    - status: 用戶狀態
    
    範例: GET /api/user/options/user_role
    """
    result = service.get_distinct_values(column_name)
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.to_dict()

@router.put("/{user_id}/last-login")
async def update_last_login(
    user_id: str,
    service: UserService = Depends(get_user_service)
):
    """
    更新用戶最後登錄時間
    
    範例: PUT /api/user/USR001/last-login
    """
    try:
        result = service.update_last_login(user_id)
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)
        
        return result.to_dict()
    
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/account/{username}")
async def get_user_by_account(
    username: str,
    service: UserService = Depends(get_user_service)
):
    """
    根據 user_id 取得用戶資料
    
    範例: GET /api/user/USR001
    """
    result = service.get_user_by_account(username)
    
    if not result.success:
        raise HTTPException(status_code=404, detail=result.message)
    
    return result.to_dict()

@router.get("/id/{user_id}")
async def get_user_by_id(
    user_id: str,
    service: UserService = Depends(get_user_service)
):
    """
    根據 user_id 取得用戶資料
    
    範例: GET /api/user/USR001
    """
    result = service.get_user_by_id(user_id)
    
    if not result.success:
        raise HTTPException(status_code=404, detail=result.message)
    
    return result.to_dict()


@router.put("/{user_id}/password")
async def update_password(
    user_id: str,
    request: UserPasswordUpdateRequest,
    service: UserService = Depends(get_user_service)
):
    """
    更新用戶密碼
    
    範例:
    {
        "user_id": "USR001",
        "password_hash": "$2b$12$...",
        "operator": "admin"
    }
    """
    try:
        result = service.update_user_with_log(
            user_id=user_id,
            updates={"password_hash": request.password_hash},
            operator=request.operator
        )
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)
        
        return result.to_dict()
    
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
# ==========================================
# API 端點 - 統計
# ==========================================
