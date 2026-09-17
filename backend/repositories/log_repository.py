"""
日誌資料存取層 (完整版)
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from ..database.connection import db_manager
from ..models.log import LogEntry, LogFilter, LogStatistics
import traceback

class LogRepository:
    """日誌資料庫操作"""
    
    def __init__(self):
        """初始化 (不需要 db_path，直接使用全域 db_manager)"""
        pass
    
    # ==========================================
    # 輔助方法
    # ==========================================
    
    def _row_to_dict(self, row) -> Dict[str, Any]:
        """將 sqlite3.Row 轉換為字典"""
        return dict(row) if row else None
    
    def _rows_to_dicts(self, rows) -> List[Dict[str, Any]]:
        """將多個 sqlite3.Row 轉換為字典列表"""
        return [dict(row) for row in rows]
    
    # ==========================================
    # 建立 (Create)
    # ==========================================
    
    def create_log(self, log_entry: LogEntry) -> int:
        """建立日誌記錄"""
        query = """
            INSERT INTO log (
                log_id, source, source_id, name, version, 
                operator, timestamp, snapshot_json, 
                status, action, previous_version, vacancy, note, 
                meeting, operate_status, changed_info, raw_text, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            log_entry.log_id,
            log_entry.source,
            log_entry.source_id,
            log_entry.name,  # ← 新增
            log_entry.version,
            log_entry.operator,
            log_entry.timestamp,
            log_entry.snapshot_json,
            log_entry.status,
            log_entry.action,
            log_entry.previous_version,
            log_entry.vacancy,
            log_entry.note,
            log_entry.meeting,
            log_entry.operate_status,
            log_entry.changed_info,
            log_entry.raw_text,
            log_entry.error_message
        )
        
        with db_manager.log_write() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid
    
    # ==========================================
    # 讀取 (Read)
    # ==========================================
    
    def query_logs(
        self,
        filters: Optional[LogFilter] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """查詢日誌"""
        query = "SELECT * FROM log WHERE 1=1"
        params = []
        
        if filters:
            filter_dict = filters.to_dict()
            
            # 列表型篩選
            for field in ['operator', 'action', 'status', 'source','source_id', 'operate_status', 'vacancy']:
                if field in filter_dict and filter_dict[field]:
                    placeholders = ','.join('?' * len(filter_dict[field]))
                    query += f" AND {field} IN ({placeholders})"
                    params.extend(filter_dict[field])
            
            # 時間範圍篩選
            if 'timestamp_start' in filter_dict:
                query += " AND timestamp >= ?"
                params.append(filter_dict['timestamp_start'])
            
            if 'timestamp_end' in filter_dict:
                query += " AND timestamp < datetime(?, '+1 day')"
                params.append(filter_dict['timestamp_end'])
            
            # 版本範圍篩選
            if 'version_min' in filter_dict:
                query += " AND version >= ?"
                params.append(filter_dict['version_min'])
            
            if 'version_max' in filter_dict:
                query += " AND version <= ?"
                params.append(filter_dict['version_max'])
            
            # 關鍵字搜尋 (加入 name)
            if 'search_keyword' in filter_dict and filter_dict['search_keyword']:
                keyword = f"%{filter_dict['search_keyword']}%"
                query += """ AND (
                    raw_text LIKE ? OR 
                    note LIKE ? OR 
                    changed_info LIKE ? OR
                    name LIKE ?
                )"""
                params.extend([keyword] * 4)  # ← 改為 4 次
            
            # 排序
            sort_by = filter_dict.get('sort_by', 'timestamp')
            sort_order = filter_dict.get('sort_order', 'DESC')
            query += f" ORDER BY {sort_by} {sort_order}"
        else:
            query += " ORDER BY timestamp DESC"
        
        # 分頁
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        with db_manager.log_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            return self._rows_to_dicts(cursor.fetchall())

    def get_distinct_values(self, column_name: str) -> List[str]:
        """
        取得欄位的不重複值列表
        
        Args:
            column_name: 欄位名稱
            
        Returns:
            不重複值列表
        """
        # 安全性檢查
        allowed_columns = [
            'operator', 'action', 'status', 'timestamp',
            'vacancy', 'operate_status', 'source_id',
            'source'
        ]
        
        if column_name not in allowed_columns:
            raise ValueError(f"欄位 '{column_name}' 不允許查詢")
        
        query = f"""
            SELECT DISTINCT {column_name} 
            FROM log
            WHERE {column_name} IS NOT NULL 
            ORDER BY {column_name}
        """
        if column_name =="timestamp":
            query = """
                        SELECT
                            MIN(timestamp) AS min_timestamp,
                            MAX(timestamp) AS max_timestamp
                        FROM log
                        WHERE timestamp IS NOT NULL
                    """

        # ✅ 改用 db_manager.talent_read() (讀取操作)
        with db_manager.log_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query)

            if column_name == "timestamp":
                min_ts, max_ts = cursor.fetchone()

                return {
                    "min_timestamp": min_ts,
                    "max_timestamp": max_ts
                }

            results = cursor.fetchall()

            return [
                str(row[0]).strip()
                for row in results
                if row[0] is not None
                and str(row[0]).strip()
                and str(row[0]).strip().lower() != "nan"
            ]

    def get_log_by_id(self, log_id: str) -> Optional[Dict[str, Any]]:
        """根據 log_id 取得單一日誌"""
        query = "SELECT * FROM log WHERE log_id = ?"
        
        with db_manager.log_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (log_id,))
            row = cursor.fetchone()
            return self._row_to_dict(row)
    
    def query_logs_by_ids(self, log_ids: List[str]) -> List[Dict[str, Any]]:
        """根據 log_id 列表查詢完整日誌"""
        if not log_ids:
            return []
        
        placeholders = ','.join('?' * len(log_ids))
        query = f"""
            SELECT * FROM log 
            WHERE log_id IN ({placeholders}) 
            ORDER BY timestamp DESC
        """
        
        with db_manager.log_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(log_ids))
            return self._rows_to_dicts(cursor.fetchall())

    def get_status_log(self,        
        filters: Optional[LogFilter] = None,
        limit: int = 20,
        offset: int = 0):
        params = []
        query = """
                SELECT *
                FROM log
                WHERE (action = 'CREATE' AND source = '104') OR (changed_info LIKE '%"current_status"%' AND source = '104') 
            """
        if filters:
            try:
                filter_dict = filters.to_dict()
            except:
                filter_dict = filters
            
            # 列表型篩選
            for field in ['operator', 'action', 'status', 'source','source_id', 'operate_status', 'vacancy']:
                if field in filter_dict and filter_dict[field]:
                    placeholders = ','.join('?' * len(filter_dict[field]))
                    query += f" AND {field} IN ({placeholders})"
                    params.extend(filter_dict[field])
            
            # 時間範圍篩選
            if 'timestamp_start' in filter_dict:
                query += " AND timestamp >= ?"
                params.append(filter_dict['timestamp_start'])
            
            if 'timestamp_end' in filter_dict:
                query += " AND timestamp < datetime(?, '+1 day')"
                params.append(filter_dict['timestamp_end'])

            
            # 排序
            sort_by = filter_dict.get('sort_by', 'timestamp')
            sort_order = filter_dict.get('sort_order', 'DESC')
            query += f" ORDER BY {sort_by} {sort_order}"
        else:
            query += " ORDER BY timestamp DESC"

        try:
            with db_manager.log_read() as conn:
                cursor = conn.cursor()
                cursor.execute(query,params)
                result = cursor.fetchall()
                return result
        except Exception as e:
            print(e,traceback.format_exc())

            
    def get_latest_version(self, source: str, source_id: str) -> Optional[int]:
        """取得最新版本號"""
        query = """
            SELECT version 
            FROM log 
            WHERE source = ? AND source_id = ?
            ORDER BY timestamp DESC 
            LIMIT 1
        """
        
        with db_manager.log_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (source, source_id))
            row = cursor.fetchone()
            return int(row['version']) if row and row['version'] is not None else None
    
    def get_max_version(self, source: str, source_id: str) -> int:
        """取得最大版本號"""
        query = """
            SELECT version 
            FROM log 
            WHERE source = ? AND source_id = ?
            ORDER BY version DESC 
            LIMIT 1
        """
        
        with db_manager.log_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (source, source_id))
            row = cursor.fetchone()
            return int(row['version']) if row and row['version'] is not None else 0
    
    def get_log_metadata(self) -> List[Dict[str, Any]]:
        """取得日誌元資料 (不含大欄位)"""
        query = """
            SELECT 
                log_id, timestamp, operator, version, action, 
                source, source_id, name, vacancy, operate_status, status
            FROM log 
            ORDER BY timestamp DESC
        """
        
        with db_manager.log_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return self._rows_to_dicts(cursor.fetchall())
    
    def get_logs_by_talent(
        self,
        source: str,
        source_id: str,
        limit: int = 50,
        success : bool =False 
    ) -> List[Dict[str, Any]]:
        """取得特定候選人的所有日誌"""
        if success:
            query = """
                SELECT * FROM log 
                WHERE source = ? AND source_id = ? AND status =?
                ORDER BY version DESC
                LIMIT ?
            """
            
            with db_manager.log_read() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (source, source_id, limit,"SUCCESS"))
                return self._rows_to_dicts(cursor.fetchall())
        if success:
            query = """
                SELECT * FROM log 
                WHERE source = ? AND source_id = ? 
                ORDER BY version DESC
                LIMIT ?
            """
            
            with db_manager.log_read() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (source, source_id, limit))
                return self._rows_to_dicts(cursor.fetchall())
    
    def get_logs_by_name(
        self,
        name: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """根據姓名取得日誌 (模糊搜尋)"""
        query = """
            SELECT * FROM log 
            WHERE name LIKE ?
            ORDER BY timestamp DESC
            LIMIT ?
        """
        
        with db_manager.log_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (f"%{name}%", limit))
            return self._rows_to_dicts(cursor.fetchall())
    
    def get_log_by_talent_version(self , source:str,source_id:str,version:int) ->LogEntry:
        """透過版本與使用者查詢Log"""
        query = "SELECT * FROM log WHERE source = ? AND source_id = ? AND version = ?"
        with db_manager.log_write() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (source,source_id,version))
            result = cursor.fetchone()
            log = LogEntry.from_dict(result)
            return log

    # ==========================================
    # 刪除 (Delete)
    # ==========================================
    
    def delete_logs_by_ids(self, log_ids: List[str]) -> int:
        """根據 log_id 列表刪除日誌"""
        if not log_ids:
            return 0
        
        placeholders = ','.join('?' * len(log_ids))
        query = f"DELETE FROM log WHERE log_id IN ({placeholders})"
        
        with db_manager.log_write() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(log_ids))
            conn.commit()
            return cursor.rowcount
    
    def delete_logs_before_date(self, cutoff_date: str) -> int:
        """刪除指定日期之前的日誌"""
        query = "DELETE FROM log WHERE timestamp < ?"
        
        with db_manager.log_write() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (cutoff_date,))
            conn.commit()
            return cursor.rowcount
    
    def get_deletable_logs(
        self,
        retention_days: int = 180,
        filters: Optional[LogFilter] = None
    ) -> List[Dict[str, Any]]:
        """
        取得可刪除的日誌列表
        
        Args:
            retention_days: 保留天數
            filters: 額外篩選條件
        """
        cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d %H:%M:%S")
        
        query = "SELECT log_id, timestamp, operator, action, source, source_id, name FROM log WHERE timestamp < ?"
        params = [cutoff_date]
        
        # 加入額外篩選條件
        if filters:
            filter_dict = filters.to_dict()
            
            for field in ['operator', 'action', 'status', 'source']:
                if field in filter_dict and filter_dict[field]:
                    placeholders = ','.join('?' * len(filter_dict[field]))
                    query += f" AND {field} IN ({placeholders})"
                    params.extend(filter_dict[field])
        
        query += " ORDER BY timestamp ASC"
        
        with db_manager.log_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            return self._rows_to_dicts(cursor.fetchall())
    
    def count_deletable_logs(self, retention_days: int = 180) -> int:
        """計算可刪除的日誌數量"""
        cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d %H:%M:%S")
        query = "SELECT COUNT(*) as count FROM log WHERE timestamp < ?"
        
        with db_manager.log_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (cutoff_date,))
            row = cursor.fetchone()
            return row['count'] if row else 0
    
    # ==========================================
    # 統計 (Statistics)
    # ==========================================
    
    def get_statistics(self, filters: Optional[LogFilter] = None) -> LogStatistics:
        """取得日誌統計資料"""
        stats = LogStatistics()
        
        # 建立基礎查詢
        base_query = "SELECT * FROM log WHERE 1=1"
        params = []
        
        # TODO: 加入篩選條件邏輯 (可參考 query_logs 的實作)
        
        with db_manager.log_read() as conn:
            cursor = conn.cursor()
            
            # 總數
            cursor.execute(f"SELECT COUNT(*) as count FROM ({base_query})", params)
            stats.total_count = cursor.fetchone()['count']
            
            # 操作者分布
            cursor.execute(f"""
                SELECT operator, COUNT(*) as count 
                FROM ({base_query}) 
                GROUP BY operator
            """, params)
            stats.operator_distribution = {row['operator']: row['count'] for row in cursor.fetchall()}
            
            # 動作分布
            cursor.execute(f"""
                SELECT action, COUNT(*) as count 
                FROM ({base_query}) 
                GROUP BY action
            """, params)
            stats.action_distribution = {row['action']: row['count'] for row in cursor.fetchall()}
            
            # 狀態分布
            cursor.execute(f"""
                SELECT operate_status, COUNT(*) as count 
                FROM ({base_query}) 
                GROUP BY operate_status
            """, params)
            stats.operate_status_distribution = {row['operate_status']: row['count'] for row in cursor.fetchall()}
            
            # 成功率
            success_count = stats.operate_status_distribution.get('SUCCESS', 0)
            if stats.total_count > 0:
                stats.success_rate = (success_count / stats.total_count) * 100
            
            # 平均版本號
            cursor.execute(f"SELECT AVG(version) as avg_version FROM ({base_query})", params)
            result = cursor.fetchone()
            stats.avg_version = result['avg_version'] if result['avg_version'] else 0.0
            
            # 最舊/最新日誌
            cursor.execute(f"SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest FROM ({base_query})", params)
            result = cursor.fetchone()
            stats.oldest_log_date = result['oldest']
            stats.newest_log_date = result['newest']
            
            # 可刪除數量
            stats.deletable_count = self.count_deletable_logs()

            #受被影響的id數量
            cursor.execute(f"""
                SELECT COUNT(DISTINCT source_id)
                FROM log WHERE previous_version IS NOT NULL
                """, params)
            stats.distinct_id_count = cursor.fetchone()[0]
        
        return stats
    
    # ==========================================
    # 維護 (Maintenance)
    # ==========================================
    
    def vacuum_database(self) -> None:
        """壓縮資料庫（刪除後執行）"""
        with db_manager.log_write() as conn:
            conn.execute("VACUUM")