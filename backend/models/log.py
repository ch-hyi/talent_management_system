"""
日誌資料模型 (完整版)
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import uuid
import json

# ==========================================
# Log 完整資料模型
# ==========================================

@dataclass
class LogEntry:
    """日誌記錄結構"""
    log_id: str
    source: str
    source_id: str
    name : str
    version: int
    operator: str
    timestamp: str
    snapshot_json: str
    status: str
    action: str
    previous_version: Optional[int]
    vacancy: str
    note: str
    meeting: str
    operate_status: str
    changed_info: str
    raw_text: str
    error_message: str
    
    @classmethod
    def create_new(
        cls,
        source: str,
        source_id: str,
        name:str,
        version: int,
        operator: str,
        snapshot_json: str,
        status: str,
        action: str,
        previous_version: Optional[int],
        vacancy: str,
        note: str,
        meeting: str,
        changed_info: str,
        raw_text: str,
        error_message: str = None
    ) -> 'LogEntry':
        """建立新日誌記錄"""
        return cls(
            log_id=str(uuid.uuid4()),
            source=source,
            source_id=source_id,
            name = name,
            version=version,
            operator=operator,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            snapshot_json=snapshot_json,
            status=status,
            action=action,
            previous_version=previous_version,
            vacancy=vacancy,
            note=note,
            meeting=meeting,
            operate_status="SUCCESS" if not error_message else "FAILED",
            changed_info=changed_info,
            raw_text=raw_text,
            error_message=error_message
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LogEntry':
        """從字典建立實例"""
        return cls(**data)
    
    def get_timestamp_datetime(self) -> datetime:
        """取得時間戳記的 datetime 物件"""
        return datetime.strptime(self.timestamp, "%Y-%m-%d %H:%M:%S")
    
    def is_deletable(self, retention_days: int = 180) -> bool:
        """
        檢查是否可刪除 (預設保留 180 天)
        
        Args:
            retention_days: 保留天數 (預設 180 天 = 6 個月)
        """
        log_date = self.get_timestamp_datetime()
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        return log_date < cutoff_date
    
    def get_changed_fields(self) -> Dict[str, Any]:
        """解析變更資訊"""
        try:
            return json.loads(self.changed_info)
        except:
            return {}

# ==========================================
# Log 篩選條件模型
# ==========================================

@dataclass
class LogFilter:
    """日誌篩選條件"""
    operator: Optional[List[str]] = None
    action: Optional[List[str]] = None
    status: Optional[List[str]] = None
    source: Optional[List[str]] = None
    source_id : Optional[List[str]] = None
    operate_status: Optional[List[str]] = None
    vacancy: Optional[List[str]] = None
    
    # 時間範圍篩選
    timestamp_start: Optional[str] = None  # "YYYY-MM-DD"
    timestamp_end: Optional[str] = None
    
    # 版本篩選
    version_min: Optional[int] = None
    version_max: Optional[int] = None
    
    # 關鍵字搜尋
    search_keyword: Optional[str] = None
    
    # 排序
    sort_by: str = "timestamp"  # timestamp, version
    sort_order: str = "DESC"  # ASC 或 DESC
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典（過濾 None 值）"""
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    def has_filters(self) -> bool:
        """是否有任何篩選條件"""
        return any([
            self.operator,
            self.action,
            self.status,
            self.source,
            self.timestamp_start,
            self.timestamp_end,
            self.search_keyword
        ])

# ==========================================
# Log 刪除請求模型
# ==========================================

@dataclass
class LogDeleteRequest:
    """日誌刪除請求"""
    log_ids: List[str]
    operator: str
    retention_days: int = 180  # 預設保留 180 天
    force_delete: bool = False  # 強制刪除（跳過時間檢查）
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """驗證刪除請求"""
        if not self.log_ids:
            return False, "log_ids 不能為空"
        
        if not self.operator:
            return False, "operator 不能為空"
        
        if self.retention_days < 0:
            return False, "retention_days 必須大於等於 0"
        
        return True, None

@dataclass
class LogBulkDeleteRequest:
    """日誌批次刪除請求（依條件）"""
    operator: str
    retention_days: int = 180  # 刪除 N 天前的日誌
    filters: Optional[LogFilter] = None  # 額外篩選條件
    dry_run: bool = True  # 預覽模式（不實際刪除）
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """驗證刪除請求"""
        if not self.operator:
            return False, "operator 不能為空"
        
        if self.retention_days < 180:
            return False, "批次刪除至少需保留 180 天 (6 個月)"
        
        return True, None
    
    def get_cutoff_date(self) -> str:
        """取得刪除截止日期"""
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        return cutoff.strftime("%Y-%m-%d %H:%M:%S")

# ==========================================
# Log 統計模型
# ==========================================

@dataclass
class LogStatistics:
    """日誌統計資料"""
    total_count: int = 0
    operator_distribution: Dict[str, int] = field(default_factory=dict)
    action_distribution: Dict[str, int] = field(default_factory=dict)
    status_distribution: Dict[str, int] = field(default_factory=dict)
    operate_status_distribution: Dict[str, int] = field(default_factory=dict)
    
    success_rate: float = 0.0
    avg_version: float = 0.0
    
    oldest_log_date: Optional[str] = None
    newest_log_date: Optional[str] = None
    
    deletable_count: int = 0  # 可刪除的日誌數量
    distinct_id_count :int = 0 
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return asdict(self)

# ==========================================
# Log 匯出模型
# ==========================================

@dataclass
class LogExportRequest:
    """日誌匯出請求"""
    filters: Optional[LogFilter] = None
    fields: Optional[List[str]] = None  # None = 全部欄位
    format: str = "csv"  # csv, excel, json
    include_large_fields: bool = False  # 是否包含大欄位 (snapshot_json, changed_info)
    
    def get_export_fields(self) -> List[str]:
        """取得匯出欄位列表"""
        if self.fields:
            return self.fields
        
        # 預設匯出欄位（排除大欄位）
        base_fields = [
            "log_id", "timestamp", "operator", "version", "action",
            "source", "source_id", "vacancy", "status", "operate_status",
            "raw_text", "error_message"
        ]
        
        if self.include_large_fields:
            base_fields.extend(["snapshot_json", "changed_info", "note"])
        
        return base_fields