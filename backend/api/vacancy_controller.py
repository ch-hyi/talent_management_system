"""
FastAPI 職缺管理端點
"""

import traceback
from typing import Dict, Any, Optional, List
import pandas as pd
from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
)
from pydantic import BaseModel, Field

from ..repositories.vacancy_repository import VacancyRepository
from ..repositories.log_repository import LogRepository

from ..services.vacancy_service import VacancyService

from ..models.response import APIResponse
from ..models.vacancy import (
    Vacancy,
    VacancyUpdateRequest,
)


# ============================================================
# 路由初始化
# ============================================================

router = APIRouter(
    prefix="/api/vacancy",
    tags=["vacancy"]
)


# ============================================================
# Dependency Injection
# ============================================================

def get_vacancy_service() -> VacancyService:
    """取得 VacancyService 實例"""

    vacancy_repo = VacancyRepository()
    log_repo = LogRepository()

    return VacancyService(
        vacancy_repo=vacancy_repo,
        log_repo=log_repo
    )


# ============================================================
# Request Models
# ============================================================

class VacancyQueryRequest(BaseModel):
    """查詢職缺請求"""

    filters: Optional[Dict[str, Any]] = None

    limit: int = Field(
        default=30,
        ge=1,
        le=1000000000000000000000
    )

    offset: int = Field(
        default=0,
        ge=0
    )


class VacancyCountRequest(BaseModel):
    """職缺計數請求"""

    filters: Optional[Dict[str, Any]] = None


class VacancyCreateRequest(BaseModel):
    """建立職缺請求"""

    vacancy_id: Optional[str] = Field(
        default=None,
        description="職缺 ID；未提供時由後端產生 UUID"
    )

    position_title: str = Field(
        ...,
        min_length=1,
        description="職位名稱"
    )

    introduction: Optional[str] = Field(
        default=None,
        description="職缺介紹"
    )

    compensation: Optional[str] = Field(
        default=None,
        description="待遇"
    )

    requirements: Optional[str] = Field(
        default=None,
        description="職缺條件"
    )

    work_location: Optional[str] = Field(
        default=None,
        description="上班地點"
    )

    senior: Optional[str] = Field(
        default=None,
        description="Senior 欄位"
    )

    lab: Optional[str] = Field(
        default=None,
        description="Lab"
    )

    weight: Optional[str] = Field(
        default=None,
        description="職缺權重"
    )

    education_score_error: Optional[str] = Field(
        default=None,
        description="學歷要求錯誤分數"
    )

    education_score_5: Optional[str] = Field(
        default=None,
        description="學歷要求 5 分對應分數"
    )

    education_score_4: Optional[str] = Field(
        default=None,
        description="學歷要求 4 分對應分數"
    )

    education_score_3: Optional[str] = Field(
        default=None,
        description="學歷要求 3 分對應分數"
    )

    education_score_2: Optional[str] = Field(
        default=None,
        description="學歷要求 2 分對應分數"
    )

    education_score_1: Optional[str] = Field(
        default=None,
        description="學歷要求 1 分對應分數"
    )

    education_score_0: Optional[str] = Field(
        default=None,
        description="學歷要求 0 分對應分數"
    )

    status: str = Field(
        default="ACTIVE",
        description="職缺狀態"
    )

    created_by: str = Field(
        ...,
        min_length=1,
        description="建立者 user_id 或帳號"
    )


class VacancyUpdateRequestModel(BaseModel):
    """更新職缺請求"""
    vacancy_name:str
    updates: Dict[str, Any] = Field(
        ...,
        description="要更新的欄位"
    )

    operator: str = Field(
        ...,
        min_length=1,
        description="操作者"
    )


class VacancyStatusUpdateRequest(BaseModel):
    """批次更新職缺狀態請求"""

    vacancy_ids: List[str] = Field(
        ...,
        min_length=1,
        description="職缺 ID 列表"
    )

    status: str = Field(
        ...,
        description="新狀態"
    )

    operator: str = Field(
        ...,
        min_length=1,
        description="操作者"
    )


class VacancyDeleteRequest(BaseModel):
    """刪除職缺請求"""

    operator: str = Field(
        ...,
        min_length=1,
        description="操作者"
    )


class VacancyBatchDeleteRequest(BaseModel):
    """批次刪除職缺請求"""

    vacancy_ids: List[str] = Field(
        ...,
        min_length=1,
        description="職缺 ID 列表"
    )

    operator: str = Field(
        ...,
        min_length=1,
        description="操作者"
    )


class VacancyRestoreRequest(BaseModel):
    """恢復職缺請求"""

    operator: str = Field(
        ...,
        min_length=1,
        description="操作者"
    )


# ============================================================
# 統計
# ============================================================

@router.get("/statistics")
async def get_statistics(
    service: VacancyService = Depends(
        get_vacancy_service
    )
):
    """
    取得職缺統計資料。

    回傳內容包括：

    - total_vacancies
    - active_vacancies
    - inactive_vacancies
    - paused_vacancies
    - closed_vacancies
    - deleted_vacancies
    - total_labs
    - by_status
    - by_lab
    - by_senior
    - recent_vacancies
    """

    result = service.get_statistics()

    if not result.success:
        raise HTTPException(
            status_code=500,
            detail=result.error or result.message
        )

    return result.to_dict()


# ============================================================
# 查詢職缺
# ============================================================

@router.post("/lab")
async def get_lab_options():
    lab = pd.read_excel("c:/Users/rchang4/talent_system/backend/data/公司經緯度.xlsx")["實驗室"].tolist()
    result = APIResponse(True,lab,"","")
    return result

@router.post("/query")
async def query_vacancies(
    request: VacancyQueryRequest,
    service: VacancyService = Depends(
        get_vacancy_service
    )
):
    """
    查詢職缺。

    範例：

    {
        "filters": {
            "position_title": "Engineer",
            "lab": "RF",
            "status": "ACTIVE",
            "work_location": "Taipei"
        },
        "limit": 30,
        "offset": 0
    }

    查某位使用者負責的職缺：

    {
        "filters": {
            "incharge_user_id": "使用者 UUID"
        },
        "limit": 30,
        "offset": 0
    }
    """

    result = service.query_vacancies(
        filters=request.filters,
        limit=request.limit,
        offset=request.offset
    )
    print(result.error,result.message)
    if not result.success:
        raise HTTPException(
            status_code=400,
            detail=result.error or result.message
        )

    return result.to_dict()


@router.post("/count")
async def get_vacancy_count(
    request: VacancyCountRequest,
    service: VacancyService = Depends(
        get_vacancy_service
    )
):
    """
    取得符合條件的職缺數量。

    範例：

    {
        "filters": {
            "status": "ACTIVE",
            "lab": "RF"
        }
    }
    """

    result = service.get_vacancy_count(
        request.filters
    )

    if not result.success:
        raise HTTPException(
            status_code=400,
            detail=result.error or result.message
        )

    return result.to_dict()


# ============================================================
# 查詢選項
# 注意：固定路由必須放在 /{vacancy_id} 前面
# ============================================================

@router.get("/options/all")
async def get_vacancy_options(
    service: VacancyService = Depends(
        get_vacancy_service
    )
):
    """
    取得職缺頁面的篩選選項。

    包括：

    - statuses
    - labs
    - seniors
    - work_locations
    """

    result = service.get_vacancy_options()

    if not result.success:
        raise HTTPException(
            status_code=400,
            detail=result.error or result.message
        )

    return result.to_dict()


@router.get("/options/{column_name}")
async def get_distinct_values(
    column_name: str,
    service: VacancyService = Depends(
        get_vacancy_service
    )
):
    """
    取得指定欄位的不重複值。

    支援：

    - position_title
    - work_location
    - senior
    - lab
    - status
    """

    result = service.get_distinct_values(
        column_name
    )

    if not result.success:
        raise HTTPException(
            status_code=400,
            detail=result.error or result.message
        )

    return result.to_dict()


# ============================================================
# 透過使用者查詢負責職缺
# ============================================================

@router.get("/incharge/user/{user_id}")
async def get_vacancies_by_user_id(
    user_id: str,
    include_deleted: bool = False
):
    """
    取得某位使用者目前負責的職缺。

    範例：

    GET /api/vacancy/incharge/user/user-uuid

    包含已刪除職缺：

    GET /api/vacancy/incharge/user/user-uuid?include_deleted=true
    """

    try:
        vacancy_repo = VacancyRepository()

        data = vacancy_repo.get_vacancies_by_user_id(
            user_id=user_id,
            include_deleted=include_deleted
        )

        return APIResponse(
            success=True,
            data=data,
            message=f"成功取得 {len(data)} 筆職缺"
        ).to_dict()

    except Exception as e:
        print(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# 查詢職缺負責人
# ============================================================




# ============================================================
# 建立職缺
# ============================================================

@router.post("/create")
async def create_vacancy(
    request: VacancyCreateRequest,
    service: VacancyService = Depends(
        get_vacancy_service
    )
):
    """
    建立新職缺。

    vacancy_id 未提供時，由後端產生 UUID。

    範例：

    {
        "position_title": "RF Test Engineer",
        "introduction": "負責 RF 測試工作",
        "compensation": "面議",
        "requirements": "具備 RF 測試經驗",
        "work_location": "Taipei",
        "senior": "Yes",
        "lab": "RF Lab",
        "weight": 1.0,
        "education_score_error": 0,
        "education_score_5": 5,
        "education_score_4": 4,
        "education_score_3": 3,
        "education_score_2": 2,
        "education_score_1": 1,
        "education_score_0": 0,
        "status": "ACTIVE",
        "created_by": "user-uuid"
    }
    """

    try:
        vacancy = Vacancy(
            vacancy_id=request.vacancy_id or "",
            position_title=request.position_title,
            introduction=request.introduction,
            compensation=request.compensation,
            requirements=request.requirements,
            work_location=request.work_location,
            senior=request.senior,
            lab=request.lab,
            weight=request.weight,
            education_score_error=(
                request.education_score_error
            ),
            education_score_5=(
                request.education_score_5
            ),
            education_score_4=(
                request.education_score_4
            ),
            education_score_3=(
                request.education_score_3
            ),
            education_score_2=(
                request.education_score_2
            ),
            education_score_1=(
                request.education_score_1
            ),
            education_score_0=(
                request.education_score_0
            ),
            status=request.status
        )

        result = service.create_vacancy(
            vacancy=vacancy,
            created_by=request.created_by
        )

        if not result.success:
            raise HTTPException(
                status_code=400,
                detail=result.error or result.message
            )

        return result.to_dict()

    except HTTPException:
        raise

    except Exception as e:
        print(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# 批次更新狀態
# 固定路由必須放在 /{vacancy_id} 前面
# ============================================================

@router.put("/status/batch")
async def update_vacancy_status_batch(
    request: VacancyStatusUpdateRequest,
    service: VacancyService = Depends(
        get_vacancy_service
    )
):
    """
    批次更新職缺狀態，並為每一筆建立 Log。

    範例：

    {
        "vacancy_ids": [
            "vacancy-001",
            "vacancy-002"
        ],
        "status": "CLOSED",
        "operator": "user-uuid"
    }
    """

    valid_statuses = {
        "ACTIVE",
        "INACTIVE",
        "PAUSED",
        "CLOSED",
        "DELETED"
    }

    normalized_status = request.status.upper()

    if normalized_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                f"不合法的職缺狀態："
                f"{request.status}"
            )
        )

    results = []

    for vacancy_id in request.vacancy_ids:
        result = service.update_vacancy_with_log(
            vacancy_id=vacancy_id,
            updates={
                "status": normalized_status
            },
            operator=request.operator
        )

        results.append({
            "vacancy_id": vacancy_id,
            "success": result.success,
            "message": result.message,
            "error": result.error
        })

    success_count = sum(
        1
        for result in results
        if result["success"]
    )

    failed_count = len(results) - success_count

    return APIResponse(
        success=failed_count == 0,
        data={
            "total": len(results),
            "success": success_count,
            "failed": failed_count,
            "details": results
        },
        message=(
            f"職缺狀態更新完成："
            f"{success_count}/{len(results)} 成功"
        )
    ).to_dict()


# ============================================================
# 批次刪除
# 必須放在 DELETE /{vacancy_id} 前面
# ============================================================
@router.put("/update/{vacancy_id}")
async def update_vacancy(

    vacancy_id: str,
    request: VacancyUpdateRequestModel,
    service: VacancyService = Depends(
        get_vacancy_service
    )
):
    """
    更新職缺並建立 Log。

    範例：

    {
        "updates": {
            "position_title": "Senior RF Test Engineer",
            "weight": 1.5,
            "status": "ACTIVE"
        },
        "operator": "user-uuid"
    }
    """
    try:
        result = service.update_vacancy_with_log(
            vacancy_name= request.vacancy_name,
            vacancy_id=vacancy_id,
            updates=request.updates,
            operator=request.operator
        )

        if not result.success:
            print(result.error,result.message)
            raise HTTPException(
                status_code=400,
                detail=result.error or result.message
            )

        return result.to_dict()

    except HTTPException:
        
        raise

    except Exception as e:
        print(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    
@router.delete("/batch")
async def delete_vacancies_batch(
    request: VacancyBatchDeleteRequest,
    service: VacancyService = Depends(
        get_vacancy_service
    )
):
    """
    批次軟刪除職缺。

    範例：

    {
        "vacancy_ids": [
            "vacancy-001",
            "vacancy-002"
        ],
        "operator": "user-uuid"
    }
    """

    results = []

    for vacancy_id in request.vacancy_ids:
        result = service.delete_vacancy(
            vacancy_id=vacancy_id,
            deleted_by=request.operator
        )

        results.append({
            "vacancy_id": vacancy_id,
            "success": result.success,
            "message": result.message,
            "error": result.error
        })

    success_count = sum(
        1
        for result in results
        if result["success"]
    )

    failed_count = len(results) - success_count

    return APIResponse(
        success=failed_count == 0,
        data={
            "total": len(results),
            "success": success_count,
            "failed": failed_count,
            "details": results
        },
        message=(
            f"職缺刪除完成："
            f"{success_count}/{len(results)} 成功"
        )
    ).to_dict()

@router.delete("/{vacancy_id}")
async def delete_vacancy(
    vacancy_id: str,
    request: VacancyDeleteRequest,
    service: VacancyService = Depends(
        get_vacancy_service
    )
):
    """
    軟刪除單一職缺。

    不會真的 DELETE 資料，
    而是將 status 更新為 DELETED。

    範例：

    DELETE /api/vacancy/vacancy-001

    {
        "operator": "user-uuid"
    }
    """

    result = service.delete_vacancy(
        vacancy_id=vacancy_id,
        deleted_by=request.operator
    )

    if not result.success:
        print(result.message,result.error)
        raise HTTPException(
            status_code=400,
            detail=result.error or result.message
        )

    return result.to_dict()


# ============================================================
# 恢復職缺
# ============================================================

@router.put("/{vacancy_id}/restore")
async def restore_vacancy(
    vacancy_id: str,
    request: VacancyRestoreRequest,
    service: VacancyService = Depends(
        get_vacancy_service
    )
):
    """
    將 DELETED 職缺恢復為 ACTIVE。

    範例：

    PUT /api/vacancy/vacancy-001/restore

    {
        "operator": "user-uuid"
    }
    """

    result = service.restore_vacancy(
        vacancy_id=vacancy_id,
        operator=request.operator
    )

    if not result.success:
        raise HTTPException(
            status_code=400,
            detail=result.error or result.message
        )

    return result.to_dict()


# ============================================================
# 軟刪除單一職缺
# ============================================================

@router.get("/{vacancy_id}/incharges")
async def get_vacancy_incharges(
    vacancy_id: str,
    include_history: bool = False
):
    """
    取得某個職缺的負責人。

    預設只回傳目前負責人：

    GET /api/vacancy/{vacancy_id}/incharges

    包含歷史負責人：

    GET /api/vacancy/{vacancy_id}/incharges?include_history=true
    """

    try:
        vacancy_repo = VacancyRepository()

        if not vacancy_repo.check_vacancy_exists(
            vacancy_id=vacancy_id,
            include_deleted=True
        ):
            raise HTTPException(
                status_code=404,
                detail="找不到該職缺"
            )

        data = vacancy_repo.get_vacancy_incharges(
            vacancy_id=vacancy_id,
            include_history=include_history
        )

        return APIResponse(
            success=True,
            data=data,
            message=f"成功取得 {len(data)} 筆負責人資料"
        ).to_dict()

    except HTTPException:
        raise

    except Exception as e:
        print(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )



# ============================================================
# 依 ID 取得職缺
# 動態 GET 路由應放在固定 GET 路由後面
# ============================================================

@router.get("/{vacancy_id}")
async def get_vacancy_by_id(
    vacancy_id: str,
    service: VacancyService = Depends(
        get_vacancy_service
    )
):
    """
    根據 vacancy_id 取得單一職缺。

    範例：

    GET /api/vacancy/vacancy-001
    """

    result = service.get_vacancy_by_id(
        vacancy_id
    )

    if not result.success:
        raise HTTPException(
            status_code=404,
            detail=result.error or result.message
        )

    return result.to_dict()
