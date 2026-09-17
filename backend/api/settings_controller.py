"""
FastAPI 系統設定管理端點
"""


from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    UploadFile,
)
from pydantic import BaseModel, Field
from ..models.settings import MessageContent ,ThemeConfig
from ..repositories.log_repository import LogRepository
from ..repositories.settings_repository import SettingsRepository
from ..services.settings_service import SettingsService


# ============================================================
# 路由初始化
# ============================================================

router = APIRouter(
    prefix="/api/settings",
    tags=["settings"]
)


# ============================================================
# Dependency Injection
# ============================================================

def get_settings_service() -> SettingsService:
    """取得 SettingsService 實例"""

    settings_repo = SettingsRepository()
    log_repo = LogRepository()

    return SettingsService(
        settings_repo=settings_repo,
        log_repo=log_repo
    )


# ============================================================
# Request Models
# ============================================================

class ThemeUpdateRequest(BaseModel):
    """更新系統主題請求"""

    theme: ThemeConfig

    operator: str = Field(
        ...,
        min_length=1,
        description="操作者"
    )


class EmailTemplateUpdateRequest(BaseModel):
    """更新信件模板請求"""

    settings : MessageContent
    operator: str = Field(
        ...,
        min_length=1,
        description="操作者"
    )


class RestartRequest(BaseModel):
    """重新啟動系統請求"""

    operator: str = Field(
        ...,
        min_length=1,
        description="操作者"
    )



# ============================================================
# 共用 Response 處理
# ============================================================



# ============================================================
# 取得完整設定
# ============================================================

@router.get("/all")
async def get_all_settings(
    service: SettingsService = Depends(
        get_settings_service
    )
):
    """取得所有系統設定"""

    result = service.get_all_settings()

    return result.to_dict()


# ============================================================
# Theme
# ============================================================

@router.get("/theme")
async def get_theme(
    service: SettingsService = Depends(
        get_settings_service
    )
):
    """取得系統主題"""

    result = service.get_theme()

    return result.to_dict()


@router.put("/theme")
async def update_theme(
    request: ThemeUpdateRequest,
    service: SettingsService = Depends(
        get_settings_service
    )
):
    """更新系統主題"""

    result = service.update_theme(
        theme=request.theme,
        operator=request.operator
    )

    return result.to_dict()


# ============================================================
# Logo
# ============================================================

@router.get("/logo")
async def get_logo(
    service: SettingsService = Depends(
        get_settings_service
    )
):
    """取得系統 Logo"""

    result = service.get_logo()

    return result.to_dict()


@router.put("/logo")
async def update_logo(
    logo: UploadFile = File(...),
    operator: str = Form(...),
    service: SettingsService = Depends(
        get_settings_service
    )
):
    """更新系統 Logo"""

    file_content = await logo.read()

    try:
        result = service.update_logo(
            filename=logo.filename,
            content_type=logo.content_type,
            file_content=file_content,
            operator=operator
        )

        return result.to_dict()

    finally:
        await logo.close()


# ============================================================
# External Email Template
# ============================================================

@router.get("/template/external")
async def get_ex_temp(
    service: SettingsService = Depends(
        get_settings_service
    )
):
    """取得外部信件模板"""

    result = service.get_external_template()

    return result.to_dict()

@router.put("/template/external")
async def update_ex_temp(
    request: EmailTemplateUpdateRequest,
    service: SettingsService = Depends(
        get_settings_service
    )
):
    """更新外部信件模板"""

    result = service.update_external_template(
        settings = request.settings,
        operator=request.operator
    )

    return result.to_dict()

# ============================================================
# Internal Email Template
# ============================================================

@router.get("/template/internal")
async def get_in_temp(
    service: SettingsService = Depends(
        get_settings_service
    )
):
    """取得內部信件模板"""

    result = service.get_internal_template()

    return result.to_dict()

@router.put("/score_threshold")
async def update_score_threshold(threshold, operator,   service: SettingsService = Depends(
        get_settings_service
    )):
    result = service.update_score_threshold(threshold,operator)
    return result.to_dict()

@router.put("/template/internal")
async def update_in_temp(
    request: EmailTemplateUpdateRequest,
    service: SettingsService = Depends(
        get_settings_service
    )
):
    """更新內部信件模板"""

    result = service.update_internal_template(
        settings = request.settings,
        operator=request.operator
    )

    return result.to_dict()


# ============================================================
# 系統重新啟動
# ============================================================

@router.post("/restart")
async def restart(
    request: RestartRequest,
    service: SettingsService = Depends(
        get_settings_service
    )
):
    """重新啟動系統"""

    result = service.restart(
        operator=request.operator
    )
    return result.to_dict()