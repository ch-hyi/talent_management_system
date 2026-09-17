"""
FastAPI Lab 管理端點
"""

import traceback

from typing import Optional

from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    status,
)

from pydantic import BaseModel, Field

from ..repositories.lab_repository import LabRepository
from ..services.lab_service import LabService


# ============================================================
# 路由初始化
# ============================================================

router = APIRouter(
    prefix="/api/lab",
    tags=["lab"]
)


# ============================================================
# Dependency Injection
# ============================================================

def get_lab_service() -> LabService:
    """取得 LabService 實例"""

    lab_repo = LabRepository()

    return LabService(
        lab_repo=lab_repo
    )


# ============================================================
# Request Models
# ============================================================

class LabCreateRequest(BaseModel):
    """建立 Lab 請求"""

    name: str = Field(
        ...,
        min_length=1,
        description="Lab 名稱"
    )

    address: str = Field(
        ...,
        min_length=1,
        description="Lab 地址"
    )

    latitude: Optional[float] = Field(
        default=None,
        ge=-90,
        le=90,
        description="緯度，範圍為 -90 到 90"
    )

    longitude: Optional[float] = Field(
        default=None,
        ge=-180,
        le=180,
        description="經度，範圍為 -180 到 180"
    )

    template: Optional[str] = Field(
        default=None,
        description="Lab 使用的郵件模板"
    )

    contact: Optional[str] = Field(
        default=None,
        description="Lab 聯絡資訊"
    )


class LabUpdateRequest(BaseModel):
    """更新 Lab 請求"""

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Lab 名稱"
    )

    address: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Lab 地址"
    )

    latitude: Optional[float] = Field(
        default=None,
        ge=-90,
        le=90,
        description="緯度，範圍為 -90 到 90"
    )

    longitude: Optional[float] = Field(
        default=None,
        ge=-180,
        le=180,
        description="經度，範圍為 -180 到 180"
    )

    template: Optional[str] = Field(
        default=None,
        description="Lab 使用的郵件模板"
    )

    contact: Optional[str] = Field(
        default=None,
        description="Lab 聯絡資訊"
    )


# ============================================================
# 取得全部 Lab
# 固定路由必須放在 /{lab_id} 前面
# ============================================================

@router.get("/all")
async def get_all_labs(
    service: LabService = Depends(
        get_lab_service
    )
):
    """
    取得全部 Lab。

    Lab 數量不多，因此不使用分頁。

    範例：

    GET /api/lab/all
    """

    result = service.get_all_labs()

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error or result.message
        )

    return result.to_dict()


# ============================================================
# 取得 Lab 數量
# ============================================================

@router.get("/count")
async def get_lab_count(
    service: LabService = Depends(
        get_lab_service
    )
):
    """
    取得 Lab 總數。

    範例：

    GET /api/lab/count
    """

    result = service.get_lab_count()

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error or result.message
        )

    return result.to_dict()


# ============================================================
# 取得 Lab 下拉選項
# ============================================================

@router.get("/options")
async def get_lab_options(
    service: LabService = Depends(
        get_lab_service
    )
):
    """
    取得前端下拉選單所需的 Lab 選項。

    回傳欄位：

    - lab_id
    - name

    範例：

    GET /api/lab/options
    """

    result = service.get_lab_options()

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error or result.message
        )

    return result.to_dict()


# ============================================================
# 依名稱取得 Lab
# ============================================================

@router.get("/by-name/{name}")
async def get_lab_by_name(
    name: str,
    service: LabService = Depends(
        get_lab_service
    )
):
    """
    根據名稱取得單一 Lab。

    範例：

    GET /api/lab/by-name/華亞
    """

    result = service.get_lab_by_name(
        name
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error or result.message
        )

    return result.to_dict()


# ============================================================
# 檢查 Lab 名稱是否已存在
# ============================================================

@router.get("/check-name/{name}")
async def check_lab_name_exists(
    name: str,
    exclude_lab_id: Optional[str] = None,
    service: LabService = Depends(
        get_lab_service
    )
):
    """
    檢查 Lab 名稱是否已存在。

    建立時：

    GET /api/lab/check-name/華亞

    更新時排除目前的 Lab：

    GET /api/lab/check-name/華亞
        ?exclude_lab_id=lab-uuid
    """

    result = service.check_lab_name_exists(
        name=name,
        exclude_lab_id=exclude_lab_id
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or result.message
        )

    return result.to_dict()


# ============================================================
# 建立 Lab
# ============================================================

@router.post(
    "/create",
    status_code=status.HTTP_201_CREATED
)
async def create_lab(
    request: LabCreateRequest,
    service: LabService = Depends(
        get_lab_service
    )
):
    """
    建立新的 Lab。

    lab_id 由後端自動產生 UUID。

    範例：

    {
        "name": "華亞",
        "address": "桃園市龜山區華亞二路19號",
        "latitude": 25.05051,
        "longitude": 121.3785,
        "template": null,
        "contact": null
    }
    """

    try:
        lab_data = request.model_dump()

        result = service.create_lab(
            lab_data
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error or result.message
            )

        return result.to_dict()

    except HTTPException:
        raise

    except Exception as e:
        print(traceback.format_exc())

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================
# 更新 Lab
# ============================================================

@router.put("/update/{lab_id}")
async def update_lab(
    lab_id: str,
    request: LabUpdateRequest,
    service: LabService = Depends(
        get_lab_service
    )
):
    """
    更新指定 Lab。

    僅需要提供要修改的欄位。

    範例：

    PUT /api/lab/update/lab-uuid

    {
        "address": "桃園市龜山區華亞二路20號",
        "contact": "HR Department"
    }
    """

    try:
        # exclude_unset=True：
        # 只取得前端實際傳入的欄位
        updates = request.model_dump(
            exclude_unset=True
        )

        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="沒有提供任何要更新的欄位"
            )

        result = service.update_lab(
            lab_id=lab_id,
            updates=updates
        )

        if not result.success:
            if result.message == "找不到該 Lab":
                status_code = status.HTTP_404_NOT_FOUND
            else:
                status_code = status.HTTP_400_BAD_REQUEST

            raise HTTPException(
                status_code=status_code,
                detail=result.error or result.message
            )

        return result.to_dict()

    except HTTPException:
        raise

    except Exception as e:
        print(traceback.format_exc())

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================
# 硬刪除 Lab
# ============================================================

@router.delete("/{lab_id}")
async def delete_lab(
    lab_id: str,
    service: LabService = Depends(
        get_lab_service
    )
):
    """
    永久刪除指定 Lab。

    注意：

    此操作為硬刪除，不會保留 Lab 資料。

    範例：

    DELETE /api/lab/lab-uuid
    """

    try:
        result = service.delete_lab(
            lab_id
        )

        if not result.success:
            if result.message == "找不到該 Lab":
                status_code = status.HTTP_404_NOT_FOUND
            else:
                status_code = status.HTTP_400_BAD_REQUEST

            raise HTTPException(
                status_code=status_code,
                detail=result.error or result.message
            )

        return result.to_dict()

    except HTTPException:
        raise

    except Exception as e:
        print(traceback.format_exc())

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================
# 依 ID 取得單一 Lab
# 動態路由必須放在固定路由後面
# ============================================================

@router.get("/{lab_id}")
async def get_lab_by_id(
    lab_id: str,
    service: LabService = Depends(
        get_lab_service
    )
):
    """
    根據 lab_id 取得單一 Lab。

    範例：

    GET /api/lab/lab-uuid
    """

    result = service.get_lab_by_id(
        lab_id
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error or result.message
        )

    return result.to_dict()