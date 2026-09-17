"""
用戶資料存取層
"""
from typing import List, Dict, Any, Optional
from ..database.connection import db_manager
from ..models.user import UserFilter, User
import pandas as pd
from datetime import datetime
import uuid

class UserRepository:   
    """用戶資料庫操作"""
    
    def auth(self):
        query = """
                SELECT user_account, user_name, user_email, password_hash, user_role
                FROM user
                WHERE status = 'ACTIVE'
                """
        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query,())
            fetch = [dict(row) for row in cursor.fetchall()]
            return fetch
    
    def login(self,user_account):

        time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query_login = """
                UPDATE user SET last_login = ?  WHERE user_account = ?
                """
            
        with db_manager.user_write() as conn:
            cursor = conn.cursor()
            cursor.execute(query_login,(time,user_account))
            return time
        

    def query_users(
        self,
        filters: Optional[UserFilter] = None,
        limit: int = 30,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        查詢用戶資料
        
        Args:
            filters: 篩選條件
            limit: 每頁筆數
            offset: 偏移量
            
        Returns:
            用戶資料列表
        """
        query = "SELECT * FROM user WHERE 1=1"
        params = []
        
        # 動態建立篩選條件
        if filters:
            filter_dict = filters.to_dict() if hasattr(filters, 'to_dict') else filters
            
            # 精確匹配篩選
            for field in ['user_role', 'status',"user_account"]:
                if field in filter_dict and filter_dict[field]:
                    query += f" AND {field} = ?"
                    params.append(filter_dict[field])
            
            # 關鍵字搜尋
            if 'search_keyword' in filter_dict and filter_dict['search_keyword']:
                keyword = f"%{filter_dict['search_keyword']}%"
                query += """ AND (
                    user_account LIKE ? OR 
                    user_name LIKE ? OR 
                    user_email LIKE ?
                )"""
                params.extend([keyword] * 3)
            
            # 排除已刪除用戶
            if filter_dict.get('exclude_deleted', True):
                query += " AND status != 'DELETED'"
        else:
            # 預設排除已刪除用戶
            query += " AND status != 'DELETED'"
        
        # 排序與分頁
        query += " ORDER BY create_time DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_user_count(self, filters: Optional[Dict] = None) -> int:
        """
        取得符合條件的用戶總數
        
        Args:
            filters: 篩選條件
            
        Returns:
            用戶總數
        """
        query = "SELECT COUNT(*) as total FROM user WHERE 1=1"
        params = []
        
        if filters:
            filter_dict = filters.to_dict() if hasattr(filters, 'to_dict') else filters
            
            # 精確匹配篩選
            for field in ['user_role', 'status']:
                if field in filter_dict and filter_dict[field]:
                    query += f" AND {field} = ?"
                    params.append(filter_dict[field])
            
            # 關鍵字搜尋
            if 'search_keyword' in filter_dict and filter_dict['search_keyword']:
                keyword = f"%{filter_dict['search_keyword']}%"
                query += """ AND (
                    user_account LIKE ? OR 
                    user_name LIKE ? OR 
                    user_email LIKE ?
                )"""
                params.extend([keyword] * 3)
            
            # 排除已刪除用戶
            if filter_dict.get('exclude_deleted', True):
                query += " AND status != 'DELETED'"
        else:
            # 預設排除已刪除用戶
            query += " AND status != 'DELETED'"
        
        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            result = cursor.fetchone()
            total_count = result[0] if result else 0
            return total_count
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        根據 user_id 取得單一用戶資料
        
        Args:
            user_id: 用戶 ID
            
        Returns:
            用戶資料字典，若不存在則回傳 None
        """
        query = "SELECT * FROM user WHERE user_id = ? AND status != 'DELETED'"
        
        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id,))
            result = cursor.fetchone()

        result = dict(result) if result else None 
        query_vacancy_incharge = """
        SELECT
            vi.*,
            v.position_title
        FROM vacancy_incharge vi
        JOIN vacancy v
            ON vi.vacancy_id = v.vacancy_id
        WHERE vi.user_id = ?
        AND vi.unassigned_at IS NULL
        """
        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query_vacancy_incharge, (result["user_id"],))
            result_vacancy_incharge = [row["position_title"]for row in cursor.fetchall()]

        result["vacancy_incharge"] = result_vacancy_incharge

        return  result
    
    def get_user_by_account(self, username: str) -> Optional[Dict[str, Any]]:
        """
        根據帳號取得用戶資料
        
        Args:
            user_account: 用戶帳號
            
        Returns:
            用戶資料字典，若不存在則回傳 None
        """
        query = "SELECT * FROM user WHERE user_account = ? AND status != 'DELETED'"
        
        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (username,))
            result = cursor.fetchone()

        result = dict(result) if result else None 
        query_vacancy_incharge = """
        SELECT
            vi.*,
            v.position_title
        FROM vacancy_incharge vi
        JOIN vacancy v
            ON vi.vacancy_id = v.vacancy_id
        WHERE vi.user_id = ?
        AND vi.unassigned_at IS NULL
        """
        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query_vacancy_incharge, (result["user_id"],))
            result_vacancy_incharge = [row["position_title"]for row in cursor.fetchall()]

        result["vacancy_incharge"] = result_vacancy_incharge

        return  result
    
    def get_user_by_email(self, user_email: str) -> Optional[Dict[str, Any]]:
        """
        根據郵箱取得用戶資料
        
        Args:
            user_email: 用戶郵箱
            
        Returns:
            用戶資料字典，若不存在則回傳 None
        """
        query = "SELECT * FROM user WHERE user_email = ? AND status != 'DELETED'"
        
        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_email,))
            result = cursor.fetchone()
            return dict(result) if result else None
    
    def create_user(self, user: User) -> int:
        """
        創建新用戶
        
        Args:
            user: User 物件
            
        Returns:
            影響行數
        """
        query = """
            INSERT INTO user (
                user_id, user_account, user_name, user_email, password_hash,
                user_role, create_time, created_by, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            user.user_id,
            user.user_account,
            user.user_name,
            user.user_email,
            user.password_hash,
            user.user_role,
            user.create_time,
            user.created_by,
            user.status,
        )
        
        with db_manager.user_write() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.rowcount
    
    def update_user(
        self,
        user_id: str,
        updates: Dict[str, Any]
    ) -> int:
        """
        更新用戶資料
        
        Args:
            user_id: 用戶 ID
            updates: 更新欄位字典
            
        Returns:
            影響行數
        """
        if not updates:
            return 0
        
        # 動態建立 UPDATE 語句
        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values()) + [user_id]
        
        query = f"""
            UPDATE user 
            SET {set_clause}
            WHERE user_id = ?
        """
        
        with db_manager.user_write() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(values))
            return cursor.rowcount



    def update_vacancy_incharge(
        self,
        user_id: str,
        vacancy_incharge: list[str]
    ) -> None:
        """
        更新使用者負責職缺

        Args:
            user_id:
                使用者 ID

            vacancy_incharge:
                最新職缺名稱列表
        """

        with db_manager.user_write() as conn:
            cursor = conn.cursor()

            # 目前有效關聯
            cursor.execute(
                """
                SELECT vacancy_id
                FROM vacancy_incharge
                WHERE user_id = ?
                AND unassigned_at IS NULL
                """,
                (user_id,)
            )

            current_vacancy_ids = {
                row["vacancy_id"]
                for row in cursor.fetchall()
            }

            # 前端職缺名稱轉 vacancy_id
            new_vacancy_ids = set()

            if vacancy_incharge:
                placeholders = ",".join(
                    ["?"] * len(vacancy_incharge)
                )

                cursor.execute(
                    f"""
                    SELECT vacancy_id
                    FROM vacancy
                    WHERE position_title IN ({placeholders})
                    """,
                    vacancy_incharge
                )

                new_vacancy_ids = {
                    row["vacancy_id"]
                    for row in cursor.fetchall()
                }

            # 差集
            to_add = new_vacancy_ids - current_vacancy_ids
            to_remove = current_vacancy_ids - new_vacancy_ids

            # 新增關聯
            for vacancy_id in to_add:
                cursor.execute(
                    """
                    INSERT INTO vacancy_incharge (
                        relation_id,
                        vacancy_id,
                        user_id,
                        assigned_at
                    )
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        str(uuid.uuid4()),
                        vacancy_id,
                        user_id
                    )
                )

            # 關閉關聯(保留歷史)
            for vacancy_id in to_remove:
                cursor.execute(
                    """
                    UPDATE vacancy_incharge
                    SET
                        unassigned_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE vacancy_id = ?
                    AND user_id = ?
                    AND unassigned_at IS NULL
                    """,
                    (
                        vacancy_id,
                        user_id
                    )
                )

            conn.commit()
    
    def update_user_status(self, user_id: str, status: str) -> int:
        """
        更新用戶狀態
        
        Args:
            user_id: 用戶 ID
            status: 新狀態 ('ACTIVE', 'INACTIVE', 'DELETED')
            
        Returns:
            影響行數
        """
        query = """
            UPDATE user 
            SET status = ?
            WHERE user_id = ?
        """
        
        with db_manager.user_write() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (status, user_id))
            return cursor.rowcount
    
    def update_password(self, user_id: str, password_hash: str, updated_by: str) -> int:
        """
        更新用戶密碼
        
        Args:
            user_id: 用戶 ID
            password_hash: 新密碼雜湊值
            updated_by: 更新者
            
        Returns:
            影響行數
        """
        from datetime import datetime
        
        query = """
            UPDATE user 
            SET password_hash = ?, update_time = ?, updated_by = ?
            WHERE user_id = ?
        """
        
        update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with db_manager.user_write() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (password_hash, update_time, updated_by, user_id))
            return cursor.rowcount
    
    def update_last_login(self, user_id: str) -> int:
        """
        更新最後登錄時間
        
        Args:
            user_id: 用戶 ID
            
        Returns:
            影響行數
        """
        from datetime import datetime
        
        query = """
            UPDATE user 
            SET last_login = ?
            WHERE user_id = ?
        """
        
        last_login = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with db_manager.user_write() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (last_login, user_id))
            return cursor.rowcount

    def get_distinct_values(self, column_name: str) -> List[str]:
        """
        取得欄位的不重複值列表
        
        Args:
            column_name: 欄位名稱
            
        Returns:
            不重複值列表
        """
        # 安全性檢查 - 只允許特定欄位
        allowed_columns = [
            'user_role', 'status'
        ]
        
        if column_name not in allowed_columns:
            raise ValueError(f"欄位 '{column_name}' 不允許查詢")
        
        query = f"""
            SELECT DISTINCT {column_name} 
            FROM user 
            WHERE {column_name} IS NOT NULL 
            AND status != 'deleted'
            ORDER BY {column_name}
        """
        
        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            
            return [
                str(row[0]).strip() 
                for row in results 
                if row[0] is not None 
                and str(row[0]).strip()
            ]
    
    def get_users_by_role(self, user_role: str) -> List[Dict[str, Any]]:
        """
        根據角色取得所有用戶
        
        Args:
            user_role: 用戶角色
            
        Returns:
            用戶資料列表
        """
        query = """
            SELECT * FROM user 
            WHERE user_role = ? AND status != 'DELETED'
            ORDER BY create_time DESC
        """
        
        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_role,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_active_users(self) -> List[Dict[str, Any]]:
        """
        取得所有活躍用戶
        
        Returns:
            活躍用戶列表
        """
        query = """
            SELECT * FROM user 
            WHERE status = 'ACTIVE'
            ORDER BY create_time DESC
        """
        
        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        取得用戶統計資訊
        
        Returns:
            統計資訊字典
        """
        stats = {}
        
        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            
            # 總用戶數
            cursor.execute("SELECT COUNT(*) as count FROM user WHERE status != 'DELETED'")
            stats['total_users'] = cursor.fetchone()[0]
            
            # 活躍用戶數
            cursor.execute("SELECT COUNT(*) as count FROM user WHERE status = 'ACTIVE'")
            stats['active_users'] = cursor.fetchone()[0]
            
            # 非活躍用戶數
            cursor.execute("SELECT COUNT(*) as count FROM user WHERE status = 'INACTIVE'")
            stats['inactive_users'] = cursor.fetchone()[0]
            
            # 按角色分布
            cursor.execute("""
                SELECT user_role, COUNT(*) as count 
                FROM user 
                WHERE status != 'DELETED'
                GROUP BY user_role
            """)
            stats['by_role'] = {
                row[0]: row[1] 
                for row in cursor.fetchall()
            }
            
            # 最近登錄的用戶
            cursor.execute("""
                SELECT user_id, user_account, user_name, last_login 
                FROM user 
                WHERE status = 'ACTIVE' AND last_login IS NOT NULL
                ORDER BY last_login DESC 
                LIMIT 5
            """)
            stats['recent_logins'] = [dict(row) for row in cursor.fetchall()]

        
        return stats
    
    def check_user_exists(self, user_account: str) -> bool:
        """
        檢查帳號是否存在
        
        Args:
            user_account: 用戶帳號
            
        Returns:
            是否存在
        """
        query = "SELECT COUNT(*) as count FROM user WHERE user_account = ? AND status != 'DELETED'"
        
        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_account,))
            result = cursor.fetchone()
            return result[0] > 0 if result else False
    
    def check_email_exists(self, user_email: str, exclude_user_id: Optional[str] = None) -> bool:
        """
        檢查郵箱是否存在
        
        Args:
            user_email: 用戶郵箱
            exclude_user_id: 排除的用戶 ID（用於更新時檢查）
            
        Returns:
            是否存在
        """
        if exclude_user_id:
            query = """
                SELECT COUNT(*) as count FROM user 
                WHERE user_email = ? AND user_id != ? AND status != 'DELETED'
            """
            params = (user_email, exclude_user_id)
        else:
            query = "SELECT COUNT(*) as count FROM user WHERE user_email = ? AND status != 'DELETED'"
            params = (user_email,)
        
        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result[0] > 0 if result else False