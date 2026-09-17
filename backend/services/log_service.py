"""
日誌業務邏輯層 (完整版)
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from ..repositories.log_repository import LogRepository
from ..models.response import APIResponse 
from ..models.log import    LogEntry, LogFilter, LogDeleteRequest,LogBulkDeleteRequest,LogStatistics
import traceback

class LogService:
    """日誌管理業務邏輯"""
    
    def __init__(self, log_repo: LogRepository):
        self.log_repo = log_repo
    
    # ==========================================
    # 建立 (Create)
    # ==========================================
    
    def create_log(self, log_entry: LogEntry) -> APIResponse:
        """建立日誌記錄"""
        try:
            self.log_repo.create_log(log_entry)
            
            return APIResponse(
                success=True,
                message="日誌記錄成功"
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="日誌記錄失敗"
            )
    
    # ==========================================
    # 讀取 (Read)
    # ==========================================
    
    def query_logs(
        self,
        filters: Optional[Dict] = None,
        limit: int = 20,
        offset: int = 0
    ) -> APIResponse:
        """查詢日誌"""
        try:
            log_filter = LogFilter(**filters) if filters else None
            
            data = self.log_repo.query_logs(log_filter, limit, offset)
            
            return APIResponse(
                success=True,
                data=data,
                message=f"成功查詢 {len(data)} 筆日誌"
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="查詢失敗"
            )
        
    def get_distinct_values(self, column_name: str) -> APIResponse:
        """取得欄位的不重複值列表"""
        try:
            values = self.log_repo.get_distinct_values(column_name)
            
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

        
    def get_log_by_id(self, log_id: str) -> APIResponse:
        """取得單一日誌"""
        try:
            data = self.log_repo.get_log_by_id(log_id)
            
            if not data:
                return APIResponse(
                    success=False,
                    message="找不到該日誌"
                )
            
            return APIResponse(
                success=True,
                data=data
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="查詢失敗"
            )

    def get_status_log(self,      
        filters: Optional[Dict] = None,
        limit: int = 30,
        offset: int = 0):
        try:
            data = self.log_repo.get_status_log(filters,limit,offset)

            return APIResponse(
                success=True,
                data=data,
                message=f"成功查詢 {len(data)} 筆日誌"
            )
        except Exception as e:
            print(traceback.format_exc(),e)
            return APIResponse(
                success=False,
                error=str(e),
                message="查詢失敗"
            )
    
    def get_logs_by_talent(
        self,
        source: str,
        source_id: str,
        limit: int = 50,
        success : bool =False
    ) -> APIResponse:
        """取得特定候選人的所有日誌"""
        try:
            data = self.log_repo.get_logs_by_talent(source, source_id, limit,success)

            return APIResponse(
                success=True,
                data=data,
                message=f"成功查詢 {len(data)} 筆日誌"
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="查詢失敗"
            )

    def get_latest_version(self, source: str, source_id: str) -> APIResponse:
        """取得最新版本號"""
        try:
            version = self.log_repo.get_latest_version(source, source_id)
            
            return APIResponse(
                success=True,
                data={"version": version if version is not None else 0}
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e)
            )
    
    def get_max_version(self, source: str, source_id: str) -> APIResponse:
        """取得最大版本號"""
        try:
            version = self.log_repo.get_max_version(source, source_id)
            
            return APIResponse(
                success=True,
                data={"version": version}
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e)
            )
    
    def get_log_metadata(self) -> APIResponse:
        """取得日誌元資料"""
        try:
            data = self.log_repo.get_log_metadata()
            
            return APIResponse(
                success=True,
                data=data,
                message=f"成功取得 {len(data)} 筆日誌元資料"
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="查詢失敗"
            )
    
    def query_logs_by_ids(self, log_ids: List[str]) -> APIResponse:
        """根據 log_id 列表查詢完整日誌"""
        try:
            if not log_ids:
                return APIResponse(
                    success=True,
                    data=[],
                    message="無查詢目標"
                )
            
            data = self.log_repo.query_logs_by_ids(log_ids)
            
            return APIResponse(
                success=True,
                data=data,
                message=f"成功查詢 {len(data)} 筆完整日誌"
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="查詢失敗"
            )
    
    def get_previous_log(self,source:str,source_id:str) -> APIResponse:
        try:
            latest_log = self.get_logs_by_talent(source,source_id,1,True).data
            previous_version = int(latest_log["previous_version"])
            log = self.log_repo.get_log_by_talent_version(source,source_id,previous_version)
            return APIResponse(
                    success=True,
                    data = log.to_dict(),
                    message="取得上版本Log成功"
                )
        except Exception as e :
            return APIResponse(
                    success=True,
                    error=str(e),
                    message="取得上版本Log失敗"
                )

    # ==========================================
    # 刪除 (Delete)
    # ==========================================
    
    def delete_logs(self, request: LogDeleteRequest) -> APIResponse:
        """
        刪除指定的日誌記錄
        
        Args:
            request: LogDeleteRequest 包含 log_ids, operator, retention_days, force_delete
        """
        try:
            # 驗證請求
            is_valid, error_msg = request.validate()
            if not is_valid:
                return APIResponse(
                    success=False,
                    message=error_msg
                )
            
            # 如果不是強制刪除，需檢查日誌是否可刪除
            if not request.force_delete:
                # 取得日誌資料
                logs = self.log_repo.query_logs_by_ids(request.log_ids)
                
                undeletable_logs = []
                for log in logs:
                    log_entry = LogEntry.from_dict(log)
                    if not log_entry.is_deletable(request.retention_days):
                        undeletable_logs.append(log_entry.log_id)
                
                if undeletable_logs:
                    return APIResponse(
                        success=False,
                        data={"undeletable_logs": undeletable_logs},
                        message=f"有 {len(undeletable_logs)} 筆日誌未達保留期限，無法刪除"
                    )
            
            # 執行刪除
            deleted_count = self.log_repo.delete_logs_by_ids(request.log_ids)
            
            # 壓縮資料庫
            self.log_repo.vacuum_database()
            
            # 記錄刪除操作 (建立刪除日誌)
            delete_log = LogEntry.create_new(
                source="system",
                source_id="log_deletion",
                version=1,
                operator=request.operator,
                snapshot_json="{}",
                status="completed",
                action="DeleteLogs",
                previous_version=None,
                vacancy="N/A",
                note=f"刪除了 {deleted_count} 筆日誌",
                meeting="",
                changed_info=f'{{"deleted_count": {deleted_count}, "log_ids": {request.log_ids}}}',
                raw_text=f"管理員 {request.operator} 刪除了 {deleted_count} 筆日誌"
            )
            self.log_repo.create_log(delete_log)
            
            return APIResponse(
                success=True,
                data={"deleted_count": deleted_count},
                message=f"成功刪除 {deleted_count} 筆日誌"
            )
            
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="刪除失敗"
            )
    
    def bulk_delete_logs(self, request: LogBulkDeleteRequest) -> APIResponse:
        """
        批次刪除日誌（依時間條件）
        
        Args:
            request: LogBulkDeleteRequest 包含 operator, retention_days, filters, dry_run
        """
        try:
            # 驗證請求
            is_valid, error_msg = request.validate()
            if not is_valid:
                return APIResponse(
                    success=False,
                    message=error_msg
                )
            
            # 取得可刪除的日誌
            deletable_logs = self.log_repo.get_deletable_logs(
                retention_days=request.retention_days,
                filters=request.filters
            )
            
            if not deletable_logs:
                return APIResponse(
                    success=True,
                    data={"deleted_count": 0},
                    message="沒有符合條件的日誌可刪除"
                )
            
            # 預覽模式：只回傳可刪除的日誌列表
            if request.dry_run:
                return APIResponse(
                    success=True,
                    data={
                        "preview": True,
                        "deletable_count": len(deletable_logs),
                        "deletable_logs": deletable_logs[:100],  # 最多顯示 100 筆
                        "cutoff_date": request.get_cutoff_date()
                    },
                    message=f"預覽模式：共 {len(deletable_logs)} 筆日誌可刪除"
                )
            
            # 實際刪除
            cutoff_date = request.get_cutoff_date()
            deleted_count = self.log_repo.delete_logs_before_date(cutoff_date)
            
            # 壓縮資料庫
            self.log_repo.vacuum_database()
            
            # 記錄批次刪除操作
            delete_log = LogEntry.create_new(
                source="system",
                source_id="bulk_log_deletion",
                version=1,
                operator=request.operator,
                snapshot_json="{}",
                status="completed",
                action="BulkDeleteLogs",
                previous_version=None,
                vacancy="N/A",
                note=f"批次刪除 {request.retention_days} 天前的日誌",
                meeting="",
                changed_info=f'{{"deleted_count": {deleted_count}, "retention_days": {request.retention_days}, "cutoff_date": "{cutoff_date}"}}',
                raw_text=f"管理員 {request.operator} 批次刪除了 {deleted_count} 筆日誌 (保留期限: {request.retention_days} 天)"
            )
            self.log_repo.create_log(delete_log)
            
            return APIResponse(
                success=True,
                data={
                    "deleted_count": deleted_count,
                    "cutoff_date": cutoff_date
                },
                message=f"成功刪除 {deleted_count} 筆日誌"
            )
            
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="批次刪除失敗"
            )
    
    def preview_deletable_logs(self, retention_days: int = 180) -> APIResponse:
        """
        預覽可刪除的日誌
        
        Args:
            retention_days: 保留天數
        """
        try:
            deletable_logs = self.log_repo.get_deletable_logs(retention_days)
            deletable_count = len(deletable_logs)
            
            return APIResponse(
                success=True,
                data={
                    "deletable_count": deletable_count,
                    "preview_logs": deletable_logs[:50],  # 最多顯示 50 筆
                    "retention_days": retention_days,
                    "cutoff_date": (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d")
                },
                message=f"共有 {deletable_count} 筆日誌可刪除"
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="預覽失敗"
            )
    
    # ==========================================
    # 統計 (Statistics)
    # ==========================================
    
    def get_statistics(self, filters: Optional[Dict] = None) -> APIResponse:
        """取得日誌統計資料"""
        try:
            log_filter = LogFilter(**filters) if filters else None
            stats = self.log_repo.get_statistics(log_filter)
            
            return APIResponse(
                success=True,
                data=stats.to_dict(),
                message="統計資料取得成功"
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="統計失敗"
            )