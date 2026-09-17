"""
資料庫連線管理器（讀寫分離 + 連接池）
"""
import sqlite3
import threading
import time
from typing import Optional
from contextlib import contextmanager

from .pool import ConnectionPool
from .config import DatabaseConfig


class DatabaseManager:
    """資料庫連線管理器"""
    
    def __init__(self):
        """初始化（不建立連線）"""
        
        # ==================== 人才資料庫 ====================
        self.talent_read_pool: Optional[ConnectionPool] = None
        # ✅ 改：寫入也用連接池
        self.talent_write_pool: Optional[ConnectionPool] = None
        
        # ==================== 日誌資料庫 ====================
        self.log_read_pool: Optional[ConnectionPool] = None
        # ✅ 改：寫入也用連接池
        self.log_write_pool: Optional[ConnectionPool] = None
        
        # ==================== 使用者資料庫 ====================
        self.user_read_pool: Optional[ConnectionPool] = None
        self.user_write_pool: Optional[ConnectionPool] = None

        # ==================== 配置 ====================
        self.config = DatabaseConfig()
    
    def connect(self):
        """建立所有資料庫連線"""
        print("=" * 60)
        print("🚀 初始化資料庫連線")
        print("=" * 60)
        
        # 驗證配置
        try:
            self.config.validate()
        except Exception as e:
            print(f"❌ 配置驗證失敗: {e}")
            raise
        
        # ==================== 人才資料庫 ====================
        print("\n📊 人才資料庫")
        print("-" * 60)
        
        # 讀取連線池（10 個連接）
        self.talent_read_pool = ConnectionPool(
            db_path=self.config.TALENT_DB_PATH,
            pool_size=self.config.READ_POOL_SIZE,  # 10
            timeout=self.config.POOL_TIMEOUT,
            enable_wal=self.config.ENABLE_WAL,
            enable_foreign_keys=self.config.ENABLE_FOREIGN_KEYS,
            busy_timeout=self.config.BUSY_TIMEOUT
        )
        
        # ✅ 新增：寫入連線池（1 個連接）
        print(f"🔌 正在建立寫入連線池: {self.config.TALENT_DB_PATH}")
        print(f"   連線數量: 1")
        
        self.talent_write_pool = ConnectionPool(
            db_path=self.config.TALENT_DB_PATH,
            pool_size=1,  # ← 只有 1 個連接
            timeout=60.0,  # ← 增加超時時間
            enable_wal=self.config.ENABLE_WAL,
            enable_foreign_keys=self.config.ENABLE_FOREIGN_KEYS,
            busy_timeout=60000  # 60 秒
        )
        
        print("✅ 寫入連線池已建立完成\n")
        
        # ==================== 日誌資料庫 ====================
        print("📝 日誌資料庫")
        print("-" * 60)
        
        # 讀取連線池
        self.log_read_pool = ConnectionPool(
            db_path=self.config.LOG_DB_PATH,
            pool_size=self.config.READ_POOL_SIZE,
            timeout=self.config.POOL_TIMEOUT,
            enable_wal=self.config.ENABLE_WAL,
            enable_foreign_keys=self.config.ENABLE_FOREIGN_KEYS,
            busy_timeout=self.config.BUSY_TIMEOUT
        )
        
        # ✅ 新增：寫入連線池（1 個連接）
        print(f"🔌 正在建立日誌寫入連線池: {self.config.LOG_DB_PATH}")
        print(f"   連線數量: 1")
        
        self.log_write_pool = ConnectionPool(
            db_path=self.config.LOG_DB_PATH,
            pool_size=1,
            timeout=60.0,
            enable_wal=self.config.ENABLE_WAL,
            enable_foreign_keys=self.config.ENABLE_FOREIGN_KEYS,
            busy_timeout=60000
        )
        
        print("使用者資料庫")
        print("-" * 60)
        
        # 讀取連線池
        self.user_read_pool = ConnectionPool(
            db_path=self.config.USER_DB_PATH,
            pool_size=self.config.READ_POOL_SIZE,
            timeout=self.config.POOL_TIMEOUT,
            enable_wal=self.config.ENABLE_WAL,
            enable_foreign_keys=self.config.ENABLE_FOREIGN_KEYS,
            busy_timeout=self.config.BUSY_TIMEOUT
        )
        
        # ✅ 新增：寫入連線池（1 個連接）
        print(f"🔌 正在建立使用者寫入連線池: {self.config.USER_DB_PATH}")
        print(f"   連線數量: 1")
        
        self.user_write_pool = ConnectionPool(
            db_path=self.config.USER_DB_PATH,
            pool_size=1,
            timeout=60.0,
            enable_wal=self.config.ENABLE_WAL,
            enable_foreign_keys=self.config.ENABLE_FOREIGN_KEYS,
            busy_timeout=60000
        )
        print("✅ 使用者寫入連線池已建立完成\n")
        
        # ==================== 完成 ====================
        print("=" * 60)
        print("✅ 資料庫連線初始化完成")
        print("=" * 60)
        print()
    
    # ==================== 人才資料庫操作 ====================
    
    @contextmanager
    def talent_read(self):
        """取得人才資料庫的讀取連線"""
        if not self.talent_read_pool:
            raise RuntimeError("資料庫未初始化，請先呼叫 connect()")
        
        with self.talent_read_pool.connection() as conn:
            yield conn
    
    @contextmanager
    def talent_write(self):
        """
        取得人才資料庫的寫入連線
        
        ✅ 從連接池借用（pool_size=1）
        ✅ 用完自動歸還
        ✅ 立即獲取寫鎖
        """
        if not self.talent_write_pool:
            raise RuntimeError("資料庫未初始化，請先呼叫 connect()")
        
        import logging
        import os
        import time
        
        pid = os.getpid()
        start_time = time.time()
        
        logging.debug(f"[PID {pid}] 🔒 請求寫入連接...")
        
        # ✅ 從池中借用連接
        with self.talent_write_pool.connection() as conn:
            try:
                lock_acquired_time = time.time()
                wait_time = lock_acquired_time - start_time
                
                if wait_time > 1:
                    logging.warning(f"[PID {pid}] ⏱️ 等待連接 {wait_time:.2f} 秒")
                
                logging.debug(f"[PID {pid}] ✅ 獲取寫入連接")
                
                cursor = conn.cursor()
                
                # ✅ 立即獲取寫鎖
                cursor.execute("BEGIN IMMEDIATE")
                
                logging.debug(f"[PID {pid}] 🔐 BEGIN IMMEDIATE 完成")
                
                yield conn
                
                # ✅ 顯式 commit
                conn.commit()
                
                commit_time = time.time()
                total_time = commit_time - start_time
                
                logging.debug(f"[PID {pid}] ✅ COMMIT 完成，總耗時 {total_time:.2f} 秒")
                
            except sqlite3.OperationalError as e:
                logging.error(f"[PID {pid}] ❌ 數據庫鎖定錯誤: {e}")
                if conn.in_transaction:
                    conn.rollback()
                raise
                
            except sqlite3.DatabaseError as e:
                logging.error(f"[PID {pid}] ❌ 數據庫錯誤: {e}")
                if conn.in_transaction:
                    conn.rollback()
                raise
                
            except Exception as e:
                logging.error(f"[PID {pid}] ❌ 未知錯誤: {e}")
                if conn.in_transaction:
                    conn.rollback()
                raise
        # ← 離開 with，連接自動歸還到池中
    
    # ==================== 日誌資料庫操作 ====================
    
    @contextmanager
    def log_read(self):
        """取得日誌資料庫的讀取連線"""
        if not self.log_read_pool:
            raise RuntimeError("資料庫未初始化，請先呼叫 connect()")
        
        with self.log_read_pool.connection() as conn:
            yield conn
    
    @contextmanager
    def log_write(self):
        """取得日誌資料庫的寫入連線"""
        if not self.log_write_pool:
            raise RuntimeError("資料庫未初始化，請先呼叫 connect()")
        
        import logging
        import os
        
        pid = os.getpid()
        
        logging.debug(f"[PID {pid}] 🔒 請求日誌寫入連接...")
        
        with self.log_write_pool.connection() as conn:
            try:
                logging.debug(f"[PID {pid}] ✅ 獲取日誌寫入連接")
                
                cursor = conn.cursor()
                cursor.execute("BEGIN IMMEDIATE")
                
                yield conn
                
                conn.commit()
                
                logging.debug(f"[PID {pid}] ✅ 日誌 COMMIT 完成")
                
            except Exception as e:
                logging.error(f"[PID {pid}] ❌ 日誌寫入錯誤: {e}")
                if conn.in_transaction:
                    conn.rollback()
                raise



    @contextmanager
    def user_read(self):
        """取得使用者資料庫的讀取連線"""
        if not self.user_read_pool:
            raise RuntimeError("資料庫未初始化，請先呼叫 connect()")
        
        with self.user_read_pool.connection() as conn:
            yield conn
    
    @contextmanager
    def user_write(self):
        """取得使用者資料庫的寫入連線"""
        if not self.user_write_pool:
            raise RuntimeError("資料庫未初始化，請先呼叫 connect()")
        
        import logging
        import os
        
        pid = os.getpid()
        
        logging.debug(f"[PID {pid}] 🔒 請求使用者寫入連接...")
        
        with self.user_write_pool.connection() as conn:
            try:
                logging.debug(f"[PID {pid}] ✅ 獲取使用者寫入連接")
                
                cursor = conn.cursor()
                cursor.execute("BEGIN IMMEDIATE")
                
                yield conn
                
                conn.commit()
                
                logging.debug(f"[PID {pid}] ✅ 使用者 COMMIT 完成")
                
            except Exception as e:
                logging.error(f"[PID {pid}] ❌ 使用者寫入錯誤: {e}")
                if conn.in_transaction:
                    conn.rollback()
                raise
    
    # ==================== 工具方法 ====================
    
    def close(self):
        """關閉所有資料庫連線"""
        print("=" * 60)
        print("🔌 關閉資料庫連線")
        print("=" * 60)
        print()
        
        errors = []
        
        # 關閉人才資料庫讀取池
        if self.talent_read_pool:
            try:
                self.talent_read_pool.close_all()
            except Exception as e:
                errors.append(f"人才讀取池關閉失敗: {e}")
        
        # ✅ 改：關閉人才資料庫寫入池
        if self.talent_write_pool:
            try:
                self.talent_write_pool.close_all()
            except Exception as e:
                errors.append(f"人才寫入池關閉失敗: {e}")
        
        # 關閉日誌資料庫讀取池
        if self.log_read_pool:
            try:
                self.log_read_pool.close_all()
            except Exception as e:
                errors.append(f"日誌讀取池關閉失敗: {e}")
        
        # ✅ 改：關閉日誌資料庫寫入池
        if self.log_write_pool:
            try:
                self.log_write_pool.close_all()
            except Exception as e:
                errors.append(f"日誌寫入池關閉失敗: {e}")

        if self.user_read_pool:
            try:
                self.user_read_pool.close_all()
            except Exception as e:
                errors.append(f"使用者讀取池關閉失敗: {e}")
        
        # ✅ 改：關閉日誌資料庫寫入池
        if self.user_write_pool:
            try:
                self.user_write_pool.close_all()
            except Exception as e:
                errors.append(f"使用者寫入池關閉失敗: {e}")
        
        print("=" * 60)
        if errors:
            print("⚠️ 部分連線關閉時發生錯誤:")
            for error in errors:
                print(f"   - {error}")
        else:
            print("✅ 所有資料庫連線已關閉")
        print("=" * 60)
        print()
    
    def get_stats(self) -> dict:
        """取得所有連線池的統計資訊"""
        return {
            "talent_read_pool": self.talent_read_pool.get_stats() if self.talent_read_pool else None,
            "talent_write_pool": self.talent_write_pool.get_stats() if self.talent_write_pool else None,
            "log_read_pool": self.log_read_pool.get_stats() if self.log_read_pool else None,
            "log_write_pool": self.log_write_pool.get_stats() if self.log_write_pool else None,
            "user_read_pool": self.user_read_pool.get_stats() if self.user_read_pool else None,
            "user_write_pool": self.user_write_pool.get_stats() if self.user_write_pool else None
        }
    
    def health_check(self) -> dict:
        """健康檢查"""
        result = {
            "healthy": True,
            "talent_db": "unknown",
            "log_db": "unknown",
            "user_db": "unknown",
            "errors": []
        }
        
        # 檢查人才資料庫
        try:
            with self.talent_read() as conn:
                conn.execute("SELECT 1")
            result["talent_db"] = "healthy"
        except Exception as e:
            result["healthy"] = False
            result["talent_db"] = "unhealthy"
            result["errors"].append(f"人才資料庫錯誤: {e}")
        
        # 檢查日誌資料庫
        try:
            with self.log_read() as conn:
                conn.execute("SELECT 1")
            result["log_db"] = "healthy"
        except Exception as e:
            result["healthy"] = False
            result["log_db"] = "unhealthy"
            result["errors"].append(f"日誌資料庫錯誤: {e}")

        try:
            with self.user_read() as conn:
                conn.execute("SELECT 1")
            result["user_db"] = "healthy"
        except Exception as e:
            result["healthy"] = False
            result["user_db"] = "unhealthy"
            result["errors"].append(f"使用者資料庫錯誤: {e}")
        
        return result


# ==================== 全域單例 ====================
db_manager = DatabaseManager()