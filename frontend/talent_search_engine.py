"""
人才搜尋引擎 + 分批載入器 - 完全修正版
完全匹配您的 API 格式
"""

import httpx
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import json
import hashlib
from config import API_URL 

# ==========================================
# 篩選條件資料類別 (完全匹配 TalentFilter)
# ==========================================

@dataclass
class FilterConditions:
    """
    篩選條件集合 - 完全匹配後端 TalentFilter
    
    對應: backend/models/talent.py 的 TalentFilter
    """
    
    # ✅ 列表型篩選
    current_status: Optional[List[str]] = None
    city: Optional[List[str]] = None
    source: Optional[List[str]] = None
    vacancy: Optional[List[str]] = None
    education_degree: Optional[List[str]] = None
    education_mode: Optional[List[str]] = None
    gender: Optional[List[str]] = None
    
    # ✅ 範圍型篩選
    score_min: Optional[float] = None
    score_max: Optional[float] = None
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    exp_years_min: Optional[float] = None
    exp_years_max: Optional[float] = None
    expected_salary_min: Optional[int] = None
    expected_salary_max: Optional[int] = None
    
    # ✅ 時間範圍篩選
    received_time_start: Optional[str] = None  # "YYYY-MM-DD"
    received_time_end: Optional[str] = None
    update_time_start: Optional[str] = None
    update_time_end: Optional[str] = None
    
    # ✅ 布林型篩選
    exclude_blocked: bool = False  # 排除黑名單
    only_scored: bool = False      # 僅顯示已評分
    
    # ✅ 關鍵字搜尋
    search_keyword: Optional[str] = None
    
    # ✅ 排序 (在 TalentFilter 裡)
    sort_by: str = "update_time"
    sort_order: str = "DESC"
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典,移除 None 值和空列表"""
        data = asdict(self)
        return {
            k: v for k, v in data.items() 
            if v is not None and (not isinstance(v, list) or len(v) > 0)
        }

@dataclass
class PaginationConfig:
    """分頁配置"""
    page: int = 1
    page_size: int = 50
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
    
    @property
    def limit(self) -> int:
        return self.page_size
    
    def to_dict(self) -> Dict[str, int]:
        return {
            "limit": self.limit,
            "offset": self.offset
        }

@dataclass
class APIConfig:
    """API 配置"""
    base_url: str = API_URL
    timeout: float = 30.0
    
    @property
    def talents_url(self) -> str:
        return f"{self.base_url}/api/talents/query"
    @property
    def talents_len(self) -> str:
        return f"{self.base_url}/api/talents/get-len"

    @property
    def options_url(self) -> str:
        return f"{self.base_url}/api/options"
    
    @property
    def statistics_url(self) -> str:
        return f"{self.base_url}/api/talents/statistics"


@dataclass
class SearchResult:
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    statistics: dict = None
    @property
    def has_next(self):
        return self.page * self.page_size < self.total

    @property
    def total_pages(self):
        if self.total == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size

class TalentSearchEngine:
    """人才資料庫搜尋引擎 - 使用 API"""
    
    def __init__(self, api_config: APIConfig = None):
        self.config = api_config or APIConfig()
        self.client = httpx.Client(timeout=self.config.timeout)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def get_len(self,request):
        response = self.client.post(self.config.talents_len,json = request)
        print(response.status_code)
        print(response.text)
        result = response.json()
        if result["success"]:
            length =result["data"]
        else:
            length = None

        return length

    def close(self):
        """關閉 HTTP 客戶端"""
        self.client.close()

    def search(
        self,
        username:str,
        filters: FilterConditions = None,
        page: int = 1,
        page_size: int = 30
    ) -> SearchResult:

        filters = filters or FilterConditions()

        request_body = {
            "username":username,
            "filters": filters.to_dict(),
            "limit": page_size,
            "offset": (page - 1) * page_size
        }

        response = self.client.post(
            self.config.talents_url,
            json=request_body
        )

        request_len = {
            "username":username,
            "filters": filters.to_dict()}
        
        response.raise_for_status()
        length = self.get_len(request_len)
        result = response.json()
        
        if not result.get("success"):
            raise Exception(result.get("message", "API Error"))

        data = result.get("data")
        return SearchResult(
            items=data,
            total=length,
            page=page,
            page_size=page_size,
            statistics=None
        )
    
    def get_by_id(self, source: str, source_id: str) -> Optional[Dict[str, Any]]:
        """根據 source 和 source_id 查詢單筆資料"""
        url = f"{self.config.base_url}/api/talents/{source}/{source_id}"
        
        try:
            response = self.client.get(url)
            
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            result = response.json()
            
            if not result.get("success"):
                return None
            
            return result.get("data")
            
        except httpx.HTTPError:
            return None
    
    def get_by_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        """根據關鍵字搜尋"""
        filters = FilterConditions(search_keyword=keyword)
        results, _ = self.search(filters)
        return results
    
    def get_statistics(self, filters: FilterConditions = None) -> Dict[str, Any]:
        """取得統計資訊"""
        if filters is None:
            filters = FilterConditions()
        
        request_body = {
            "filters": filters.to_dict(),
            "group_by": None
        }
        
        try:
            response = self.client.post(
                self.config.statistics_url,
                json=request_body
            )
            response.raise_for_status()
            
            result = response.json()
            
            if not result.get("success"):
                raise Exception(result.get("error", "統計資料取得失敗"))
            
            return result.get("data", {})
            
        except httpx.HTTPError as e:
            raise Exception(f"統計 API 請求錯誤: {str(e)}")
    
    def get_status_distribution(self, filters: FilterConditions = None) -> List[Dict[str, Any]]:
        """取得狀態分佈"""
        if filters is None:
            filters = FilterConditions()
        
        request_body = {
            "filters": filters.to_dict(),
            "group_by": "current_status"
        }
        
        try:
            response = self.client.post(
                self.config.statistics_url,
                json=request_body
            )
            response.raise_for_status()
            result = response.json()
            
            if not result.get("success"):
                return []
            
            data = result.get("data", {})
            return data.get("current_status_distribution", [])
            
        except httpx.HTTPError:
            return []
    
    def get_city_distribution(self, filters: FilterConditions = None) -> List[Dict[str, Any]]:
        """取得城市分佈"""
        if filters is None:
            filters = FilterConditions()
        
        request_body = {
            "filters": filters.to_dict(),
            "group_by": "city"
        }
        
        try:
            response = self.client.post(
                self.config.statistics_url,
                json=request_body
            )
            response.raise_for_status()
            result = response.json()
            
            if not result.get("success"):
                return []
            
            data = result.get("data", {})
            return data.get("city_distribution", [])
            
        except httpx.HTTPError:
            return []
    
    def get_source_distribution(self, filters: FilterConditions = None) -> List[Dict[str, Any]]:
        """取得來源分佈"""
        if filters is None:
            filters = FilterConditions()
        
        request_body = {
            "filters": filters.to_dict(),
            "group_by": "source"
        }
        
        try:
            response = self.client.post(
                self.config.statistics_url,
                json=request_body
            )
            response.raise_for_status()
            result = response.json()
            
            if not result.get("success"):
                return []
            
            data = result.get("data", {})
            return data.get("source_distribution", [])
            
        except httpx.HTTPError:
            return []
    
    def get_filter_options(self) -> Dict[str, List[str]]:
        """取得篩選選項"""
        try:
            response = self.client.get(self.config.options_url)
            response.raise_for_status()
            
            result = response.json()
            return result if isinstance(result, dict) else {}
            
        except httpx.HTTPError:
            return {}

# ==========================================
# 分批載入器
# ==========================================

# ==========================================
# 自動載入管理器
# ==========================================

# ==========================================
# 非同步版本
# ==========================================
