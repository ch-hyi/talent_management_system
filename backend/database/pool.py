"""
資料庫連線池實作
"""
import sqlite3
import threading
from queue import Queue, Empty, Full
from typing import Optional
from contextlib import contextmanager
import time

class ConnectionPool:
    """
    資料庫連線池
    
    功能：
    - 預先建立多個連線
    - 自動管理連線的借用和歸還
    - 連線健康檢查
    - 執行緒安全
    """
    
    def __init__(
        self, 
        db_path: str, 
        pool_size: int = 10,
        timeout: float = 5.0,
        enable_wal: bool = True,
        enable_foreign_keys: bool = True,
        busy_timeout: int = 5000
    ):
        """
        初始化連線池
        
        Args:
            db_path: 資料庫檔案路徑
            pool_size: 連線池大小（預先建立多少個連線）
            timeout: 等待連線的超時時間（秒）
            enable_wal: 是否啟用 WAL 模式
            enable_foreign_keys: 是否啟用外鍵約束
            busy_timeout: 資料庫忙碌時的等待時間（毫秒）
        """
        self.db_path = db_path
        self.pool_size = pool_size
        self.timeout = timeout
        self.enable_wal = enable_wal
        self.enable_foreign_keys = enable_foreign_keys
        self.busy_timeout = busy_timeout
        
        # 連線池（使用 Queue 管理）
        self.pool = Queue(maxsize=pool_size)
        
        # 統計資訊
        self.total_connections = 0      # 已建立的連線總數
        self.active_connections = 0     # 當前使用中的連線數
        self.stats_lock = threading.Lock()  # 統計資訊的鎖
        
        # 初始化連線池
        self._initialize_pool()
    
    def _initialize_pool(self):
        """初始化連線池（預先建立所有連線）"""
        print(f"🔌 正在建立連線池: {self.db_path}")
        print(f"   連線數量: {self.pool_size}")
        
        for i in range(self.pool_size):
            try:
                conn = self._create_connection()
                self.pool.put(conn, block=False)
                self.total_connections += 1
                print(f"   ✅ 連線 {i+1}/{self.pool_size} 已建立")
            except Exception as e:
                print(f"   ❌ 連線 {i+1} 建立失敗: {e}")
                raise
        
        print(f"✅ 連線池已建立完成（{self.total_connections} 個連線）\n")
    
    def _create_connection(self) -> sqlite3.Connection:
        """
        建立新的資料庫連線
        
        Returns:
            sqlite3.Connection 物件
        """
        # 建立連線
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,  # 允許多執行緒使用
            timeout=self.timeout
        )
        
        # 設定 Row Factory（讓查詢結果可以用欄位名稱存取）
        conn.row_factory = sqlite3.Row
        
        # 設定 busy_timeout（資料庫忙碌時等待的時間）
        conn.execute(f"PRAGMA busy_timeout = {self.busy_timeout}")
        
        # 啟用 WAL 模式（Write-Ahead Logging）
        if self.enable_wal:
            conn.execute("PRAGMA journal_mode=WAL")
        
        # 啟用外鍵約束
        if self.enable_foreign_keys:
            conn.execute("PRAGMA foreign_keys=ON")
        
        return conn
    
    def get_connection(self, timeout: Optional[float] = None) -> sqlite3.Connection:
        """
        從連線池取得一個連線
        
        Args:
            timeout: 等待超時時間（秒），None 使用預設值
            
        Returns:
            資料庫連線
            
        Raises:
            TimeoutError: 等待連線超時
        """
        timeout = timeout or self.timeout
        
        try:
            # 從池中取得連線（如果沒有可用連線會等待）
            conn = self.pool.get(block=True, timeout=timeout)
            
            # 更新統計資訊
            with self.stats_lock:
                self.active_connections += 1
            
            # 檢查連線是否有效
            try:
                conn.execute("SELECT 1")
            except sqlite3.Error:
                # 連線已失效，建立新連線
                print("⚠️ 檢測到失效連線，正在重建...")
                conn = self._create_connection()
            
            return conn
            
        except Empty:
            # 等待超時
            raise TimeoutError(
                f"等待資料庫連線超時（{timeout} 秒）。"
                f"當前活躍連線：{self.active_connections}/{self.pool_size}"
            )
    
    def return_connection(self, conn: sqlite3.Connection):
        """
        歸還連線到連線池
        
        Args:
            conn: 要歸還的連線
        """
        try:
            # 確保沒有未完成的事務
            if conn.in_transaction:
                conn.rollback()
                print("⚠️ 歸還連線時發現未完成的事務，已自動回滾")
            
            # 歸還到池中
            self.pool.put(conn, block=False)
            
            # 更新統計資訊
            with self.stats_lock:
                self.active_connections -= 1
                
        except Full:
            # 池已滿（不應該發生）
            print("⚠️ 連線池已滿，關閉多餘連線")
            conn.close()
    
    @contextmanager
    def connection(self):
        """
        上下文管理器：自動取得和歸還連線
        
        使用方式:
            with pool.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT ...")
        """
        conn = self.get_connection()
        try:
            yield conn
        finally:
            self.return_connection(conn)
    
    def close_all(self):
        """關閉所有連線"""
        print(f"🔌 正在關閉連線池: {self.db_path}")
        
        closed_count = 0
        while not self.pool.empty():
            try:
                conn = self.pool.get(block=False)
                conn.close()
                closed_count += 1
            except Empty:
                break
        
        print(f"   ✅ 已關閉 {closed_count} 個連線\n")
    
    def get_stats(self) -> dict:
        """
        取得連線池統計資訊
        
        Returns:
            統計資訊字典
        """
        with self.stats_lock:
            return {
                "pool_size": self.pool_size,
                "total_connections": self.total_connections,
                "active_connections": self.active_connections,
                "available_connections": self.pool.qsize(),
                "db_path": self.db_path
            }