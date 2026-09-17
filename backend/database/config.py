# backend/database/config.py
"""
資料庫配置
"""
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class DatabaseConfig:
    """資料庫配置類別"""
    
    # ==================== 資料庫路徑 ====================
    
    # 人才資料庫路徑
    TALENT_DB_PATH: str = "C:/Users/rchang4/talent_system/backend/data/104_talent.db"
    
    # 日誌資料庫路徑
    LOG_DB_PATH: str = "C:/Users/rchang4/talent_system/backend/data/log.db"

    # 使用者資料庫路徑
    USER_DB_PATH: str = "C:/Users/rchang4/talent_system/backend/data/user.db"
    # ==================== 連線池配置 ====================
    
    # 讀取連線池大小（建議 5-20）
    READ_POOL_SIZE: int = 10
    
    # 寫入連線數量（SQLite 只需要 1 個）
    WRITE_POOL_SIZE: int = 1
    
    # 等待連線的超時時間（秒）
    POOL_TIMEOUT: float = 60.0
    
    # ==================== SQLite 參數 ====================
    
    # 是否啟用 WAL 模式（Write-Ahead Logging）
    # ✅ 建議開啟：讀寫可以並行
    ENABLE_WAL: bool = True
    
    # 連線超時時間（秒）
    CONNECTION_TIMEOUT: float = 10.0
    
    # 資料庫忙碌時的等待時間（毫秒）
    # 當資料庫被鎖定時，會等待這段時間再重試
    BUSY_TIMEOUT: int = 5000
    
    # ==================== 進階參數 ====================
    
    # 是否啟用外鍵約束
    ENABLE_FOREIGN_KEYS: bool = False
    
    # 快取大小（KB）
    # -2000 表示 2MB（負數表示 KB）
    CACHE_SIZE: int = -2000
    
    # 同步模式
    # NORMAL: 平衡安全性和效能
    # FULL: 最安全但最慢
    # OFF: 最快但有資料遺失風險
    SYNCHRONOUS: str = "NORMAL"
    
    # 日誌模式
    # WAL: Write-Ahead Logging（推薦）
    # DELETE: 傳統模式
    # TRUNCATE: 截斷模式
    JOURNAL_MODE: str = "WAL"
    
    # ==================== 環境變數支援 ====================
    
    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """從環境變數讀取配置"""
        return cls(
            TALENT_DB_PATH=os.getenv("TALENT_DB_PATH", cls.TALENT_DB_PATH),
            LOG_DB_PATH=os.getenv("LOG_DB_PATH", cls.LOG_DB_PATH),
            READ_POOL_SIZE=int(os.getenv("READ_POOL_SIZE", cls.READ_POOL_SIZE)),
            ENABLE_WAL=os.getenv("ENABLE_WAL", "true").lower() == "true",
        )
    
    def validate(self) -> None:
        """驗證配置是否合法"""
        if self.READ_POOL_SIZE < 1:
            raise ValueError("READ_POOL_SIZE 必須 >= 1")
        
        if self.READ_POOL_SIZE > 100:
            raise ValueError("READ_POOL_SIZE 不應該 > 100（太多連線會降低效能）")
        
        if self.POOL_TIMEOUT <= 0:
            raise ValueError("POOL_TIMEOUT 必須 > 0")
        
        if not os.path.exists(os.path.dirname(self.TALENT_DB_PATH)):
            raise ValueError(f"資料庫目錄不存在: {os.path.dirname(self.TALENT_DB_PATH)}")

# 建立全域配置實例
config = DatabaseConfig()