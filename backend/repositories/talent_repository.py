"""
人才資料存取層
"""
from typing import List, Dict, Any, Optional, Tuple

# ✅ 改成導入 db_manager
from ..database.connection import db_manager

# ✅ 導入 Models
from ..models.talent import TalentFilter, Talent, TalentStatistics ,OCRDraft
import pandas as pd

class TalentRepository:   
    """人才資料庫操作"""
    
    def query_talents(
        self,
        filters: Optional[TalentFilter] = None,
        limit: int = 30,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        查詢人才資料
        
        Args:
            filters: 篩選條件
            limit: 每頁筆數
            offset: 偏移量
            
        Returns:
            人才資料列表
        """
        query = "SELECT * FROM talent WHERE 1=1"
        params = []
        
        # 動態建立篩選條件
        if filters:
            filter_dict = filters.to_dict()
            
            # 列表型篩選
            for field in ['current_status', 'city', 'source', 'vacancy', 'education_degree']:

                # 欄位不存在 => 不篩選
                if field not in filter_dict:
                    continue

                value = filter_dict[field]

                # vacancy = [] => 查不到任何資料
                if field == "vacancy" and value == []:
                    query += " AND 1 = 0"
                    continue

                # 其他空值直接忽略
                if not value:
                    continue

                placeholders = ",".join("?" * len(value))
                query += f" AND {field} IN ({placeholders})"
                params.extend(value)
            
            # 範圍型篩選
            range_filters = {
                'score_min': ('score', '>='),
                'score_max': ('score', '<='),
                'age_min': ('age', '>='),
                'age_max': ('age', '<='),
                'exp_years_min': ('total_exp_years', '>='),
                'exp_years_max': ('total_exp_years', '<=')
            }
            
            for filter_key, (db_field, operator) in range_filters.items():
                if filter_key in filter_dict:
                    query += f" AND {db_field} {operator} ?"
                    params.append(filter_dict[filter_key])
            
            # 排除黑名單
            if filter_dict.get('exclude_blocked'):
                query += " AND current_status != '黑名單'"
            
            # 關鍵字搜尋
            if 'search_keyword' in filter_dict and filter_dict['search_keyword']:
                keyword = f"%{filter_dict['search_keyword']}%"
                query += """ AND (
                    name LIKE ? OR 
                    current_company LIKE ? OR 
                    vacancy LIKE ? OR
                    education_school LIKE ? OR 
                    source_id LIKE ? OR
                    description LIKE ? OR
                    education_department LIKE ? OR
                    note LIKE ?
                )"""
                params.extend([keyword] * 8)
        
        # 排序與分頁
        query += " ORDER BY update_time DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        # ✅ 改用 db_manager.talent_read() (讀取操作)
        with db_manager.talent_read() as conn:
            cursor = conn.cursor()  
            cursor.execute(query, tuple(params))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_len(self,filters: Optional[TalentFilter] = None):
        query = "SELECT COUNT(*) as total FROM talent WHERE 1=1"
        params = []
        if filters:
            try:
                filter_dict = filters.to_dict()
            except:
                filter_dict = filters
            
            # 列表型篩選
            for field in ['current_status', 'city', 'source', 'vacancy', 'education_degree']:

                # 欄位不存在 => 不篩選
                if field not in filter_dict:
                    continue

                value = filter_dict[field]

                # vacancy = [] => 查不到任何資料
                if field == "vacancy" and value == []:
                    query += " AND 1 = 0"
                    continue

                # 其他空值直接忽略
                if not value:
                    continue

                placeholders = ",".join("?" * len(value))
                query += f" AND {field} IN ({placeholders})"
                params.extend(value)
            
            # 範圍型篩選
            range_filters = {
                'score_min': ('score', '>='),
                'score_max': ('score', '<='),
                'age_min': ('age', '>='),
                'age_max': ('age', '<='),
                'exp_years_min': ('total_exp_years', '>='),
                'exp_years_max': ('total_exp_years', '<=')
            }
            
            for filter_key, (db_field, operator) in range_filters.items():
                if filter_key in filter_dict:
                    query += f" AND {db_field} {operator} ?"
                    params.append(filter_dict[filter_key])
            
            # 排除黑名單
            if filter_dict.get('exclude_blocked'):
                query += " AND block != '1'"
            
            # 關鍵字搜尋
            if 'search_keyword' in filter_dict and filter_dict['search_keyword']:
                keyword = f"%{filter_dict['search_keyword']}%"
                query += """ AND (
                    name LIKE ? OR 
                    current_company LIKE ? OR 
                    vacancy LIKE ? OR
                    education_school LIKE ? OR
                    source_id LIKE ? OR 
                    description LIKE ? OR
                    education_department LIKE ? OR
                    note LIKE ?
                )"""
                params.extend([keyword] * 8)

        with db_manager.talent_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            result = cursor.fetchone()
            total_count = result[0]
            if total_count is None:
                return 0
            else :
                return total_count
            

    def share(self,source, source_id, username) -> str:
        from datetime import datetime, timedelta
        import secrets
        # 權限檢查
        with db_manager.user_read() as user_conn:
            cursor = user_conn.cursor()

            cursor.execute(
                "SELECT user_role FROM user WHERE user_account = ?",
                (username,)
            )

            result = cursor.fetchone()

            if not result or result[0] != "admin":
                return ""

        now = datetime.now()

        with db_manager.talent_write() as conn:
            cursor = conn.cursor()

            # 查既有 token
            cursor.execute("""
                SELECT share_id, expired_time
                FROM share
                WHERE source = ?
                AND source_id = ?
            """, (source, source_id))

            result = cursor.fetchone()

            # 有 token 且未過期
            if result:
                share_id, expired_time = result

                if datetime.fromisoformat(expired_time) > now:
                    return share_id

            # 沒有 token 或已過期
            share_id = secrets.token_urlsafe(32)

            created_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            expired_time = (
            datetime.now() + timedelta(days=7)
            ).strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                INSERT INTO share (
                    source,
                    source_id,
                    share_id,
                    created_time,
                    expired_time
                )
                VALUES (?, ?, ?, ?, ?)

                ON CONFLICT(source, source_id)
                DO UPDATE SET
                    share_id = excluded.share_id,
                    created_time = excluded.created_time,
                    expired_time = excluded.expired_time
            """, (
                source,
                source_id,
                share_id,
                created_time,
                expired_time
            ))

            conn.commit()

            return share_id




    def upload_ocr_result(
        self,
        file_path: str,
        username: str,
        result_json: dict
    ):
        import json
        import uuid
        with db_manager.talent_write() as talent_conn:

            cursor = talent_conn.cursor()
            draft = OCRDraft(
                draft_id=str(uuid.uuid4()),
                creator=username,
                file_path=file_path,
                status="SUCCESS",
                result_json=result_json
            )

            cursor.execute(
                """
                INSERT INTO ocr_draft (
                    draft_id,
                    creator,
                    file_path,
                    status,
                    result_json,
                    error_msg
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    draft.draft_id,
                    draft.creator,
                    draft.file_path,
                    draft.status,
                    json.dumps(
                        draft.result_json,
                        ensure_ascii=False
                    ),
                    draft.error_msg
                )
            )

            talent_conn.commit()

            return True

    def get_ocr_result(self,file_path):
        with db_manager.talent_read() as talent_conn:
            cursor = talent_conn.cursor()

            cursor.execute(
                "SELECT result_json FROM ocr_draft WHERE file_path = ?",
                (file_path,)
            )

            result = cursor.fetchone()

            if not result :
                return None
            return result

    def get_textfile(self,path):
        with open(path, "r", encoding="utf-8") as f:

            file = f.read()

            return file

    def get_talent_by_share_id(self,share_id)->Optional[Talent]:
        query = "SELECT source, source_id FROM share WHERE share_id = ? AND expired_time > datetime('now')"
        with db_manager.talent_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query,(share_id,))
            result = cursor.fetchone()
        if not result:
            return None
        source = result[0]
        source_id = result[1]
        
        return  self.get_one_talent(source,source_id)
        
    def get_one_talent(self, source: str, source_id: str) -> Talent:
        """取得單一人才資料"""
        query = "SELECT * FROM talent WHERE source = ? AND source_id = ?"
        
        # ✅ 改用 db_manager.talent_read() (讀取操作)
        with db_manager.talent_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (source, source_id))
            result = cursor.fetchone()
            talent = Talent.from_db_row(result)
            return talent if result else None
    
    def create_talent(self,talent:Talent):
        query = ("""
                            INSERT INTO talent (
                                source, source_id, source_link, mail_id, update_time, 
                                recommender, name, score, score_distance, score_experience, 
                                score_education, score_age, gender,education_department, education_school, education_degree, 
                                education_discipline, education_mode, education_status, description, age, 
                                vacancy, city, district, phone, email, 
                                received_time, current_status, current_company, current_job_title, total_exp_years, 
                                expected_salary, note, msg_backup_path, interview_time, meeting, 
                                block, block_reason, onboarding_date
                            ) VALUES (
                                ?, ?, ?, ?, ?, ?,
                                ?, ?, ?, ?, ?, 
                                ?, ?, ?, ?, ?, 
                                ?, ?, ?, ?, ?, 
                                ?, ?, ?, ?, ?, 
                                ?, ?, ?, ?, ?, 
                                ?, ?, ?, ?, ?, 
                                ?, ?, ?
                            )
                            ON CONFLICT(source_id) DO UPDATE SET
                                source = excluded.source,
                                source_link = excluded.source_link,
                                mail_id = excluded.mail_id,
                                update_time = excluded.update_time,
                                recommender = excluded.recommender,
                                name = excluded.name,
                                score = excluded.score,
                                score_distance = excluded.score_distance,
                                score_experience = excluded.score_experience,
                                score_education = excluded.score_education,
                                score_age = excluded.score_age,
                                gender = excluded.gender,
                                education_department = excluded.education_department,
                                education_school = excluded.education_school,
                                education_degree = excluded.education_degree,
                                education_discipline = excluded.education_discipline,
                                education_mode = excluded.education_mode,
                                education_status = excluded.education_status,
                                description = excluded.description,
                                age = excluded.age,
                                vacancy = excluded.vacancy,
                                city = excluded.city,
                                district = excluded.district,
                                phone = excluded.phone,
                                email = excluded.email,
                                received_time = excluded.received_time,
                                current_status = excluded.current_status,
                                current_company = excluded.current_company,
                                current_job_title = excluded.current_job_title,
                                total_exp_years = excluded.total_exp_years,
                                expected_salary = excluded.expected_salary,
                                note = excluded.note,
                                msg_backup_path = excluded.msg_backup_path,
                                interview_time = excluded.interview_time,
                                meeting = excluded.meeting,
                                block = excluded.block,
                                block_reason = excluded.block_reason,
                                onboarding_date = excluded.onboarding_date
                            """)
        conditions =                             (
                                talent.source, talent.source_id, talent.source_link, talent.mail_id, talent.update_time, \
                                talent.recommender, talent.name, talent.score, talent.score_distance, talent.score_experience, \
                                talent.score_education, talent.score_age, talent.gender, talent.education_department, talent.education_school, talent.education_degree, \
                                talent.education_discipline, talent.education_mode, talent.education_status, talent.description, talent.age, \
                                talent.vacancy, talent.city, talent.district, talent.phone, talent.email, \
                                talent.received_time, talent.current_status, talent.current_company, talent.current_job_title, talent.total_exp_years, \
                                talent.expected_salary, talent.note, talent.msg_backup_path, talent.interview_time, talent.meeting, \
                                talent.block, talent.block_reason, talent.onboarding_date
                            )
        with db_manager.talent_write() as conn:
            cursor = conn.cursor()
            cursor.execute(query,conditions)
            return cursor.rowcount
    
    def delete_talent(self,
        source: str,
        source_id: str,) -> bool :
        """
        刪除人才資料
        """
        query = f"""
            DELETE FROM talent
            WHERE source = ?
            AND source_id = ?
            AND (
                lock_status IS NULL
                OR lock_status != 'locked'
            )
        """
        with db_manager.talent_write() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (source,source_id))
            return cursor.rowcount > 0  

    def update_talent(
        self,
        source: str,
        source_id: str,
        updates: Dict[str, Any]
    ) -> int:
        """
        更新人才資料
        
        Returns:
            影響行數
        """
        if not updates:
            return 0
        
        # 動態建立 UPDATE 語句
        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])    
        values = list(updates.values()) + [source, source_id]
        
        query = f"""
            UPDATE talent 
            SET {set_clause}
            WHERE source = ? AND source_id = ?
        """
        
        # ✅ 改用 db_manager.talent_write() (寫入操作)
        with db_manager.talent_write() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(values))

            return cursor.rowcount
    
    def update_status(self, source: str, source_id: str, status: str) -> int:
        """更新人才狀態"""
        query = """
            UPDATE talent 
            SET current_status = ?
            WHERE source = ? AND source_id = ?
        """
        
        # ✅ 改用 db_manager.talent_write() (寫入操作)
        with db_manager.talent_write() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (status, source, source_id))

            return cursor.rowcount
        
    def update_lock_status(self, source: str, source_id: str, lock_status: str) -> int:
        """更新人才狀態"""
        query = """
            UPDATE talent 
            SET lock_status = ?
            WHERE source = ? AND source_id = ?
        """
        
        # ✅ 改用 db_manager.talent_write() (寫入操作)
        with db_manager.talent_write() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (lock_status, source, source_id))

            return cursor.rowcount
    
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
            'city', 'current_status', 'source', 'vacancy', 
            'education_degree', 'education_mode', 'education_status',
            'gender', 'district'
        ]
        
        if column_name not in allowed_columns:
            raise ValueError(f"欄位 '{column_name}' 不允許查詢")
        
        query = f"""
            SELECT DISTINCT {column_name} 
            FROM talent 
            WHERE {column_name} IS NOT NULL 
            ORDER BY {column_name}
        """
        
        # ✅ 改用 db_manager.talent_read() (讀取操作)
        with db_manager.talent_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            
            # ✅ 用索引 [0] 取第一個欄位
            return [
                    str(row[0]).strip() 
                    for row in results 
                    if row[0] is not None 
                    and str(row[0]).strip() 
                    and str(row[0]).strip().lower() != 'nan'
                    ]
    
    def get_options(self) -> Dict:
        """
        取得欄位顯示選項
        returns:欄位顯示選項
        """
        dic = {}
        df_taiwan = pd.read_excel("C:/Users/rchang4/talent_system/backend/data/taiwan_zipcode_clean.xlsx")
        city = list(set(df_taiwan["縣市"]))
        district = df_taiwan["區"].tolist()
        discipline = pd.read_excel("C:/Users/rchang4/talent_system/backend/data/學門.xlsx")["名稱"].tolist()
        

        dic["city"] = city 
        dic["district"] = district
        dic["discipline"] = discipline
        dic["gender"] = ["男","女"]
        dic["source"] = ["104"]
        dic["status"] = ["AI REVIEW","AI REVIEW-NOT PASS","感興趣","感興趣-NOT PASS", "電邀","電邀-NOT PASS", "電訪","電訪-NOT PASS", "面邀","面邀-NOT PASS", "面試","面試-NOT PASS","OFFER","OFFER-NOT PASS", "報到"]
        dic["education_status"] = ["畢業", "修業", "肄業","就學中"]
        dic["education_mode"] = ["日間部", "進修部", "在職專班", "學分班"]
        dic["education_degree"] = ["博士", "碩士", "學士", "二技", "五專", "高職", "高中", "國中以下"]

        query = """
SELECT DISTINCT position_title 
FROM vacancy WHERE status = 'ACTIVE'
"""

        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, )
            dic["vacancies"] = [row["position_title"]for row in cursor.fetchall()]
        
        return dic

    def count_total(self, filters: Optional[TalentFilter] = None) -> int:
        """計算符合條件的總筆數"""
        query = "SELECT COUNT(*) as count FROM talent WHERE 1=1"
        params = []
        
        # 複用 query_talents 的篩選邏輯
        if filters:
            filter_dict = filters.to_dict()
            
            for field in ['current_status', 'city', 'source', 'vacancy', 'education_degree']:
                if field in filter_dict and filter_dict[field]:
                    placeholders = ','.join('?' * len(filter_dict[field]))
                    query += f" AND {field} IN ({placeholders})"
                    params.extend(filter_dict[field])
            
            range_filters = {
                'score_min': ('score', '>='),
                'score_max': ('score', '<='),
                'age_min': ('age', '>='),
                'age_max': ('age', '<='),
                'exp_years_min': ('total_exp_years', '>='),
                'exp_years_max': ('total_exp_years', '<=')
            }
            
            for filter_key, (db_field, operator) in range_filters.items():
                if filter_key in filter_dict:
                    query += f" AND {db_field} {operator} ?"
                    params.append(filter_dict[filter_key])
            
            if filter_dict.get('exclude_blocked'):
                query += " AND current_status != '黑名單'"
            
            if 'search_keyword' in filter_dict and filter_dict['search_keyword']:
                keyword = f"%{filter_dict['search_keyword']}%"
                query += """ AND (
                    name LIKE ? OR 
                    current_company LIKE ? OR 
                    vacancy LIKE ? OR
                    education_school LIKE ?
                )"""
                params.extend([keyword] * 4)
        
        # ✅ 改用 db_manager.talent_read() (讀取操作)
        with db_manager.talent_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            result = cursor.fetchone()
            return result['count'] if result else 0
    
    def get_talent_by_id(self, source: str, source_id: str) -> Optional[Talent]:
        """取得單一人才資料 (回傳 Talent 物件)"""
        query = "SELECT * FROM talent WHERE source = ? AND source_id = ?"
        
        # ✅ 改用 db_manager.talent_read() (讀取操作)
        with db_manager.talent_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (source, source_id))
            result = cursor.fetchone()
            
            if not result:
                return None
            
            return Talent.from_db_row(dict(result))
    
    def get_talents(
        self,
        filters: Optional[TalentFilter] = None,
        limit: int = 30,
        offset: int = 0
    ) -> List[Talent]:
        """查詢人才資料 (回傳 Talent 物件列表)"""
        rows = self.query_talents(filters, limit, offset)
        return [Talent.from_db_row(row) for row in rows]
    
    def get_statistics(self, filters: Optional[TalentFilter] = None) -> TalentStatistics:
        """取得統計資料"""
        stats = TalentStatistics()
        
        # 基礎查詢條件
        base_query = "SELECT * FROM talent WHERE 1=1"
        params = []
        
        # TODO: 加入篩選條件邏輯 (複用 query_talents 的邏輯)
        if filters:
            filter_dict = filters.to_dict()
            
            # 列表型篩選
            for field in ['current_status', 'city', 'source', 'vacancy', 'education_degree']:
                if field in filter_dict and filter_dict[field]:
                    placeholders = ','.join('?' * len(filter_dict[field]))
                    base_query += f" AND {field} IN ({placeholders})"
                    params.extend(filter_dict[field])
            
            # 範圍型篩選
            range_filters = {
                'score_min': ('score', '>='),
                'score_max': ('score', '<='),
                'age_min': ('age', '>='),
                'age_max': ('age', '<='),
                'exp_years_min': ('total_exp_years', '>='),
                'exp_years_max': ('total_exp_years', '<=')
            }
            
            for filter_key, (db_field, operator) in range_filters.items():
                if filter_key in filter_dict:
                    base_query += f" AND {db_field} {operator} ?"
                    params.append(filter_dict[filter_key])
            
            if filter_dict.get('exclude_blocked'):
                base_query += " AND current_status != '黑名單'"
            
            if 'search_keyword' in filter_dict and filter_dict['search_keyword']:
                keyword = f"%{filter_dict['search_keyword']}%"
                base_query += """ AND (
                    name LIKE ? OR 
                    current_company LIKE ? OR 
                    vacancy LIKE ? OR
                    education_school LIKE ?
                )"""
                params.extend([keyword] * 4)
        
        # ✅ 改用 db_manager.talent_read() (讀取操作)
        with db_manager.talent_read() as conn:
            cursor = conn.cursor()
            
            # 總數
            cursor.execute(
                f"SELECT COUNT(*) as count FROM ({base_query})",
                tuple(params)
            )
            stats.total_count = cursor.fetchone()['count']
            
            # 狀態分布
            cursor.execute(
                f"""
                SELECT current_status, COUNT(*) as count 
                FROM ({base_query}) 
                GROUP BY current_status
                """,
                tuple(params)
            )
            stats.status_distribution = {
                row['current_status']: row['count'] 
                for row in cursor.fetchall()
            }
            
            # 平均分數
            cursor.execute(
                f"SELECT AVG(score) as avg_score FROM ({base_query})",
                tuple(params)
            )
            result = cursor.fetchone()
            stats.avg_score = result['avg_score'] if result['avg_score'] else None
            
            # 黑名單數量
            cursor.execute(
                f"SELECT COUNT(*) as count FROM ({base_query}) WHERE block = 1",
                tuple(params)
            )
            stats.blocked_count = cursor.fetchone()['count']
        
        return stats