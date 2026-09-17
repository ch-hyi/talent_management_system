"""
FastAPI 日誌管理端點
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

from ..repositories.log_repository import LogRepository
from ..services.log_service import LogService
from ..models.response import APIResponse
from ..models.log import LogDeleteRequest, LogBulkDeleteRequest ,LogFilter

# ==========================================
# 路由初始化
# ==========================================

router = APIRouter(prefix="/api/logs", tags=["logs"])

# ==========================================
# 依賴注入
# ==========================================

def get_log_service() -> LogService:
    """取得 LogService 實例"""
    log_repo = LogRepository()
    return LogService(log_repo)

# ==========================================
# 請求模型
# ==========================================

class LogQueryRequest(BaseModel):
    filters: Optional[Dict[str, Any]] = None
    limit: int = 30
    offset: int = 0

class LogDeleteRequestModel(BaseModel):
    log_ids: List[str]
    operator: str
    retention_days: int = 180
    force_delete: bool = False

class LogBulkDeleteRequestModel(BaseModel):
    operator: str
    retention_days: int = 180
    filters: Optional[Dict[str, Any]] = None
    dry_run: bool = True

# ==========================================
# API 端點
# ==========================================

@router.post("/query")
async def query_logs(
    request: LogQueryRequest,
    service: LogService = Depends(get_log_service)
):
    """查詢日誌"""
    result = service.query_logs(
        filters=request.filters,
        limit=request.limit,
        offset=request.offset
    )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.to_dict()

@router.get("/options/{column_name}")
async def get_distinct_values(
    column_name: str,
    service: LogService = Depends(get_log_service)
):
    """取得欄位的不重複值列表"""
    result = service.get_distinct_values(column_name)
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.to_dict()


@router.get("/talent/{source}/{source_id}")
async def get_logs_by_talent(
    source: str,
    source_id: str,
    limit: int = Query(50, ge=1, le=200),
    service: LogService = Depends(get_log_service)
):
    """取得特定候選人的所有日誌"""
    result = service.get_logs_by_talent(source, source_id, limit)
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.to_dict()

@router.get("/metadata/all")
async def get_log_metadata(
    service: LogService = Depends(get_log_service)
):
    """取得日誌元資料 (輕量化列表)"""
    result = service.get_log_metadata()
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.to_dict()

@router.post("/query-by-ids")
async def query_logs_by_ids(
    log_ids: List[str],
    service: LogService = Depends(get_log_service)
):
    """根據 log_id 列表查詢完整日誌"""
    result = service.query_logs_by_ids(log_ids)
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.to_dict()


@router.get("/status")
async def get_status_log(
    request: LogQueryRequest,
    service: LogService = Depends(get_log_service)
):
    result = service.get_status_log(request.filters,request.limit,request.offset)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.to_dict()
# ==========================================
# 刪除相關端點
# ==========================================

@router.delete("/delete")
async def delete_logs(
    request: LogDeleteRequestModel,
    service: LogService = Depends(get_log_service)
):
    """
    刪除指定的日誌記錄
    
    - **log_ids**: 要刪除的日誌 ID 列表
    - **operator**: 操作者
    - **retention_days**: 保留天數 (預設 180 天)
    - **force_delete**: 是否強制刪除 (跳過時間檢查)
    """
    
    delete_request = LogDeleteRequest(
        log_ids=request.log_ids,
        operator=request.operator,
        retention_days=request.retention_days,
        force_delete=request.force_delete
    )
    
    result = service.delete_logs(delete_request)
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    
    return result.to_dict()

@router.post("/bulk-delete")
async def bulk_delete_logs(
    request: LogBulkDeleteRequestModel,
    service: LogService = Depends(get_log_service)
):
    """
    批次刪除日誌（依時間條件）
    
    - **operator**: 操作者
    - **retention_days**: 刪除 N 天前的日誌 (最少 180 天)
    - **filters**: 額外篩選條件
    - **dry_run**: 預覽模式 (True = 不實際刪除)
    """
    
    bulk_request = LogBulkDeleteRequest(
        operator=request.operator,
        retention_days=request.retention_days,
        filters=LogFilter(**request.filters) if request.filters else None,
        dry_run=request.dry_run
    )
    
    result = service.bulk_delete_logs(bulk_request)
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    
    return result.to_dict()

@router.get("/preview-deletable")
async def preview_deletable_logs(
    retention_days: int = Query(180, ge=180),
    service: LogService = Depends(get_log_service)
):
    """
    預覽可刪除的日誌
    
    - **retention_days**: 保留天數 (最少 180 天)
    """
    result = service.preview_deletable_logs(retention_days)
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.to_dict()

# ==========================================
# 統計端點
# ==========================================

@router.get("/statistics")
async def get_statistics(
    service: LogService = Depends(get_log_service)
):
    """取得日誌統計資料"""
    result = service.get_statistics()
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.to_dict()

@router.get("/version/latest/{source}/{source_id}")
async def get_latest_version(
    source: str,
    source_id: str,
    service: LogService = Depends(get_log_service)
):
    """取得最新版本號"""
    result = service.get_latest_version(source, source_id)
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.to_dict()

@router.get("/version/max/{source}/{source_id}")
async def get_max_version(
    source: str,
    source_id: str,
    service: LogService = Depends(get_log_service)
):
    """取得最大版本號"""
    result = service.get_max_version(source, source_id)
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.to_dict()

@router.get("/{log_id}")
async def get_log_by_id(
    log_id: str,
    service: LogService = Depends(get_log_service)
):
    """取得單一日誌"""
    result = service.get_log_by_id(log_id)
    
    if not result.success:
        raise HTTPException(status_code=404, detail=result.message)
    
    return result.to_dict()