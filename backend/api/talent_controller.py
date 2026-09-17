"""
FastAPI 人才管理端點 (簡化版)
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse
import traceback
from ..models.talent import  Talent ,TalentOCRRequest
from ..repositories.talent_repository import TalentRepository
from ..repositories.log_repository import LogRepository 
from ..repositories.user_repository import UserRepository 
from ..services.talent_service import TalentService

from ..services.local_llm import ScoringService
from ..models.response import APIResponse
from ..models.talent import TalentBatchUpdateRequest

# ==========================================
# 路由初始化
# ==========================================

router = APIRouter(prefix="/api/talents", tags=["talents"])

# ==========================================
# 依賴注入
# ==========================================

def get_talent_service() -> TalentService:
    """取得 TalentService 實例"""
    talent_repo = TalentRepository()
    log_repo = LogRepository()
    user_repo = UserRepository()
    return TalentService(talent_repo, log_repo,user_repo)

def get_scoring_service() -> ScoringService:
    """取得 ScoringService 實例"""
    talent_repo = TalentRepository()
    log_repo = LogRepository()
    return ScoringService(talent_repo, log_repo)

# ==========================================
# 請求模型
# ==========================================

class TalentCreateRequest(BaseModel):
    """查詢請求"""
    talent:Optional[Dict[str,Any]] 
    body:str


class TalentShareRequest(BaseModel):
    """查詢請求"""
    source:str
    source_id:str
    username:str


class TalentQueryRequest(BaseModel):
    """查詢請求"""
    username: str 
    filters: Optional[Dict[str, Any]] = None
    limit: int = 30
    offset: int = 0

class TalentDeleteRequest(BaseModel):
    """查詢請求"""
    source:str
    source_id:str
    operator:str

class TalentLength(BaseModel):
    username:str
    filters: Optional[Dict[str, Any]] = None

class ScoringRequest(BaseModel):
    """評分請求"""
    source: str
    source_id: str
    row_data: Dict[str, Any]

class StatisticsRequest(BaseModel):
    """統計請求"""
    filters: Optional[Dict[str, Any]] = None
    group_by: Optional[str] = None  # 'status', 'city', 'source' 等

# ==========================================
# API 端點
# ==========================================
@router.post("/create")
async def create_talent(
    request: TalentCreateRequest,
    service: TalentService = Depends(get_talent_service)
):
    """查詢人才資料"""
    talent = Talent(**request.talent)
    result = service.create_talent(
            talent,request.body
    )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.to_dict()


@router.post("/query")
async def query_talents(
    request: TalentQueryRequest,
    service: TalentService = Depends(get_talent_service)
):
    """查詢人才資料"""
    result = service.query_talents(
        username=request.username,
        filters=request.filters,
        limit=request.limit,
        offset=request.offset
    )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.to_dict()

@router.get("/share")
async def share(
    request:TalentShareRequest,
    service: TalentService = Depends(get_talent_service)):
    result = service.share(request.source,request.source_id,request.username)
    
    return result.to_dict()

@router.get("/resume")
async def msg(
    request:TalentShareRequest,
    service: TalentService = Depends(get_talent_service)):
    result = service.msg(request.source,request.source_id,request.username)
    
    return result.to_dict()

@router.get("/ocr")
async def ocr(
    request:TalentOCRRequest,
    service: TalentService = Depends(get_talent_service)):
    result = service.ocr(request)
    
    return result.to_dict()

@router.get("/ocr/result")
async def get_ocr_result(
    request:TalentOCRRequest,
    service: TalentService = Depends(get_talent_service)):
    result = service.get_ocr_result(request)
    
    return result.to_dict()


@router.get("/share/{share_id}")
async def get_talent_by_share_id(
    share_id,
    service: TalentService = Depends(get_talent_service)):
    result = service.get_talent_by_share_id(share_id)
    
    return result.to_dict()

@router.get("/location")
async def get_tawiwan_location(service: TalentService = Depends(get_talent_service)):
    result = service.get_taiwan_location()
    
    return result.to_dict()



@router.post("/get-len")
async def get_len(
    request: TalentLength,
    service: TalentService = Depends(get_talent_service)
):
    print(request.filters)
    result = service.get_len(request.username,request.filters)
    
    # if not result.success:
    #     raise HTTPException(status_code=400, detail=result.error)
    
    return result

@router.put("/update")
async def update_talents(
    request: TalentBatchUpdateRequest,
    service: TalentService = Depends(get_talent_service)
):
    """
    更新人才資料 (統一端點,支援單筆或批次)
    
    所有更新都會記錄日誌
    單筆更新 = batch_size 為 1
    """

    result = service.update_talent_with_log(
            request= request
    )
    
    return result.to_dict()
        


@router.post("/lock")
async def lock_talents(
    talent_ids: List[Dict[str, str]] = Body(
        ..., 
        description="格式: [{'source': '104', 'source_id': '123'}]"
    ),
    operator: str = Body(..., description="操作者名稱"),
    service: TalentService = Depends(get_talent_service)
):
    """
    鎖定人才 (統一批次處理)
    
    單筆鎖定範例:
    {
        "talent_ids": [{"source": "104", "source_id": "123"}],
        "operator": "張三"
    }
    
    批次鎖定範例:
    {
        "talent_ids": [
            {"source": "104", "source_id": "123"},
            {"source": "104", "source_id": "456"}
        ],
        "operator": "張三"
    }
    """
    results = []
    
    for item in talent_ids:
        result = service.lock_talent(item["source"], item["source_id"])
        results.append({
            "source": item["source"],
            "source_id": item["source_id"],
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
        message=f"鎖定完成: {success_count}/{len(results)} 成功"
    ).to_dict()

@router.post("/unlock")
async def unlock_talents(
    talent_ids: List[Dict[str, str]] = Body(...),
    operator: str = Body(...),
    service: TalentService = Depends(get_talent_service)
):
    """
    解鎖人才 (統一批次處理)
    """
    results = []
    
    for item in talent_ids:
        result = service.unlock_talent(item["source"], item["source_id"])
        results.append({
            "source": item["source"],
            "source_id": item["source_id"],
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
        message=f"解鎖完成: {success_count}/{len(results)} 成功"
    ).to_dict()

@router.get("/options")
def get_options( service: TalentService = Depends(get_talent_service)) -> APIResponse:
    """取得所有選項"""
    result = service.get_options()
    return result

@router.post("/scoring")
async def submit_scoring(
    request: ScoringRequest,
    service: ScoringService = Depends(get_scoring_service)
):
    """提交評分任務"""
    result = service.submit_scoring_task(
        source=request.source,
        source_id=request.source_id,
        row_data=request.row_data
    )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.to_dict()

@router.post("/statistics")
async def get_statistics(
    request: StatisticsRequest,
    service: TalentService = Depends(get_talent_service)
):
    """
    取得統計資訊
    
    支援的 group_by 選項:
    - 'current_status': 按狀態分組
    - 'city': 按城市分組
    - 'source': 按來源分組
    - None: 總體統計
    """

    result = service.query_talents(
        filters=request.filters,
        limit=10000,
        offset=0
    )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    data = result.data
    
    # 計算統計資訊
    stats = {
        "total_count": len(data),
        "avg_score": sum(d.get("score", 0) for d in data) / len(data) if data else 0,
        "max_score": max((d.get("score", 0) for d in data), default=0),
        "min_score": min((d.get("score", 0) for d in data), default=0),
        "avg_age": sum(d.get("age", 0) for d in data) / len(data) if data else 0,
        "avg_exp_years": sum(d.get("total_exp_years", 0) for d in data) / len(data) if data else 0,
    }
    
    # 如果有 group_by,進行分組統計
    if request.group_by:
        from collections import defaultdict
        groups = defaultdict(list)
        
        for item in data:
            key = item.get(request.group_by, "未分類")
            groups[key].append(item)
        
        distribution = []
        for key, items in groups.items():
            distribution.append({
                request.group_by: key,
                "count": len(items),
                "avg_score": sum(d.get("score", 0) for d in items) / len(items) if items else 0
            })
        
        stats[f"{request.group_by}_distribution"] = sorted(
            distribution, 
            key=lambda x: x["count"], 
            reverse=True
        )
    
    return APIResponse(
        success=True,
        data=stats,
        message="統計資料取得成功"
    ).to_dict()

@router.post("/delete")
async def delete_talent(
    request:TalentDeleteRequest,
    service: TalentService = Depends(get_talent_service)
):
    result = service.delete_talent(request.source,request.source_id,request.operator)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return result.to_dict()
    
@router.get("/options/{column_name}")
async def get_distinct_values(
    column_name: str,
    service: TalentService = Depends(get_talent_service)
):
    """取得欄位的不重複值列表"""
    result = service.get_distinct_values(column_name)
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.to_dict()

@router.get("/check-lock/{source}/{source_id}")
async def check_if_locked(
    source: str,
    source_id: str,
    service: TalentService = Depends(get_talent_service)
):
    """檢查人才是否被鎖定"""
    result = service.check_if_locked(source, source_id)
    
    if not result.success:
        raise HTTPException(status_code=404, detail=result.message)
    
    return result.to_dict()

@router.get("/{source}/{source_id}")
async def get_one_talent(
    source: str,
    source_id: str,
    service: TalentService = Depends(get_talent_service)
):
    """取得單一人才資料"""
    result = service.get_one_talent(source, source_id)
    
    if not result.success:
        raise HTTPException(status_code=404, detail=result.message)
    
    return result.to_dict()





