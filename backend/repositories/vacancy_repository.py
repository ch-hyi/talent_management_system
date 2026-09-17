"""
職缺資料存取層
"""

from typing import List, Dict, Any, Optional
from ..database.connection import db_manager
from ..models.vacancy import VacancyFilter, Vacancy


class VacancyRepository:
    """職缺資料庫操作"""

    # =========================================================
    # 共用篩選條件
    # =========================================================

    @staticmethod
    def _build_filter_conditions(
        filters: Optional[VacancyFilter | Dict[str, Any]] = None
    ) -> tuple[str, List[Any], bool]:
        """
        建立職缺查詢條件。

        Returns:
            where_clause:
                SQL WHERE 條件，不包含 WHERE 關鍵字

            params:
                SQL 參數

            requires_incharge_join:
                是否需要 JOIN vacancy_incharge
        """

        conditions = ["1 = 1"]
        params: List[Any] = []
        requires_incharge_join = False

        if filters:
            filter_dict = (
                filters.to_dict()
                if hasattr(filters, "to_dict")
                else filters
            )
        else:
            filter_dict = {}

        # -----------------------------------------------------
        # 精確比對
        # -----------------------------------------------------

        exact_fields = [
            "vacancy_id",
            "status",
            "senior",
            "lab",
        ]

        for field in exact_fields:
            value = filter_dict.get(field)

            if value is not None and value != "":
                conditions.append(f"v.{field} = ?")
                params.append(value)

        # -----------------------------------------------------
        # 模糊比對
        # -----------------------------------------------------

        like_fields = [
            "position_title",
            "work_location",
        ]

        for field in like_fields:
            value = filter_dict.get(field)
            print(value)
            if value is not None and str(value).strip():
                conditions.append(f"v.{field} LIKE ?")
                params.append(f"%{str(value).strip()}%")

        # -----------------------------------------------------
        # 通用關鍵字搜尋
        # -----------------------------------------------------

        search_keyword = filter_dict.get("search_keyword")

        if search_keyword:
            keyword = f"%{str(search_keyword).strip()}%"

            conditions.append(
                """
                (
                    v.position_title LIKE ?
                    OR v.introduction LIKE ?
                    OR v.requirements LIKE ?
                    OR v.work_location LIKE ?
                    OR v.senior LIKE ?
                    OR v.lab LIKE ?
                )
                """
            )

            params.extend([keyword] * 6)

        # -----------------------------------------------------
        # 查詢某位使用者目前負責的職缺
        # -----------------------------------------------------

        position_title_authority = filter_dict.get(
            "position_title_authority"
        )

        # [] => 不可看任何職缺
        if position_title_authority == []:
            conditions.append("1 = 0")

        # 有授權職缺 => 只能看這些職缺
        elif position_title_authority:
            placeholders = ",".join(
                ["?"] * len(position_title_authority)
            )

            conditions.append(
                f"v.position_title IN ({placeholders})"
            )

            params.extend(position_title_authority)

        # -----------------------------------------------------
        # 預設排除已刪除職缺
        # -----------------------------------------------------

        exclude_deleted = filter_dict.get(
            "exclude_deleted",
            True
        )

        # 如果明確指定 status=DELETED，就不能又排除 DELETED
        requested_status = filter_dict.get("status")

        if (
            exclude_deleted
            and str(requested_status).upper() != "DELETED"
        ):
            conditions.append("v.status != 'DELETED'")

        where_clause = " AND ".join(conditions)

        return (
            where_clause,
            params,
            requires_incharge_join
        )

    # =========================================================
    # 查詢職缺
    # =========================================================

    def query_vacancies(
        self,
        filters: Optional[VacancyFilter] = None,
        limit: int = 30,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        查詢職缺資料。

        Args:
            filters:
                職缺篩選條件

            limit:
                每頁筆數

            offset:
                偏移量

        Returns:
            職缺資料列表
        """

        (
            where_clause,
            params,
            requires_incharge_join
        ) = self._build_filter_conditions(filters)

        if requires_incharge_join:
            query = f"""
                SELECT DISTINCT v.*
                FROM vacancy AS v

                INNER JOIN vacancy_incharge AS vi
                    ON vi.vacancy_id = v.vacancy_id

                WHERE {where_clause}


                LIMIT ?
                OFFSET ?
            """
        else:
            query = f"""
                SELECT v.*
                FROM vacancy AS v

                WHERE {where_clause}


                LIMIT ?
                OFFSET ?
            """

        params.extend([limit, offset])

        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))

            return [
                dict(row)
                for row in cursor.fetchall()
            ]

    # =========================================================
    # 取得職缺數量
    # =========================================================

    def get_vacancy_count(
        self,
        filters: Optional[VacancyFilter] = None
    ) -> int:
        """
        取得符合條件的職缺總數。

        Args:
            filters:
                職缺篩選條件

        Returns:
            職缺總數
        """

        (
            where_clause,
            params,
            requires_incharge_join
        ) = self._build_filter_conditions(filters)

        if requires_incharge_join:
            query = f"""
                SELECT COUNT(
                    DISTINCT v.vacancy_id
                ) AS total

                FROM vacancy AS v

                INNER JOIN vacancy_incharge AS vi
                    ON vi.vacancy_id = v.vacancy_id

                WHERE {where_clause}
            """
        else:
            query = f"""
                SELECT COUNT(*) AS total
                FROM vacancy AS v
                WHERE {where_clause}
            """

        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))

            result = cursor.fetchone()

            return result[0] if result else 0

    # =========================================================
    # 依 ID 查詢單一職缺
    # =========================================================

    def get_vacancy_by_id(
        self,
        vacancy_id: str,
        include_deleted: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        根據 vacancy_id 取得單一職缺。

        Args:
            vacancy_id:
                職缺 ID

            include_deleted:
                是否允許取得已刪除職缺。
                Log、恢復與刪除功能需要設為 True。

        Returns:
            職缺資料字典，若不存在則回傳 None。
        """

        query = """
            SELECT *
            FROM vacancy
            WHERE vacancy_id = ?
        """

        params: List[Any] = [vacancy_id]

        if not include_deleted:
            query += " AND status != 'DELETED'"

        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))

            result = cursor.fetchone()

            return dict(result) if result else None

    # =========================================================
    # 建立職缺
    # =========================================================

    def create_vacancy(
        self,
        vacancy: Vacancy
    ) -> int:
        """
        建立新職缺。

        Args:
            vacancy:
                Vacancy Model

        Returns:
            影響行數
        """

        query = """
            INSERT INTO vacancy (
                vacancy_id,
                position_title,
                introduction,
                compensation,
                requirements,
                work_location,
                manager,
                senior,
                lab,
                weight,
                education_score_error,
                education_score_5,
                education_score_4,
                education_score_3,
                education_score_2,
                education_score_1,
                education_score_0,
                status,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ? , ?
            )
        """

        params = (
            vacancy.vacancy_id,
            vacancy.position_title,
            vacancy.introduction,
            vacancy.compensation,
            vacancy.requirements,
            vacancy.work_location,
            vacancy.manager,
            vacancy.senior,
            vacancy.lab,
            vacancy.weight,
            vacancy.education_score_error,
            vacancy.education_score_5,
            vacancy.education_score_4,
            vacancy.education_score_3,
            vacancy.education_score_2,
            vacancy.education_score_1,
            vacancy.education_score_0,
            vacancy.status,
            vacancy.created_at,
            vacancy.updated_at,
        )

        with db_manager.user_write() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)

            return cursor.rowcount

    # =========================================================
    # 動態更新職缺
    # =========================================================

    def update_vacancy(
        self,
        vacancy_id: str,
        updates: Dict[str, Any]
    ) -> int:
        """
        更新職缺資料。

        Args:
            vacancy_id:
                職缺 ID

            updates:
                更新欄位字典

        Returns:
            影響行數
        """

        if not updates:
            return 0

        allowed_fields = {
            "position_title",
            "introduction",
            "compensation",
            "requirements",
            "work_location",
            "manager",
            "senior",
            "lab",
            "weight",
            "education_score_error",
            "education_score_5",
            "education_score_4",
            "education_score_3",
            "education_score_2",
            "education_score_1",
            "education_score_0",
            "status",
            "updated_at",
        }

        invalid_fields = (
            set(updates.keys()) - allowed_fields
        )

        if invalid_fields:
            raise ValueError(
                "不允許更新以下 vacancy 欄位："
                + ", ".join(sorted(invalid_fields))
            )

        set_clause = ", ".join(
            f"{field} = ?"
            for field in updates.keys()
        )

        values = list(updates.values())
        values.append(vacancy_id)

        query = f"""
            UPDATE vacancy
            SET {set_clause}
            WHERE vacancy_id = ?
        """

        with db_manager.user_write() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(values))

            return cursor.rowcount

    # =========================================================
    # 更新職缺狀態
    # =========================================================

    def update_vacancy_status(
        self,
        vacancy_id: str,
        status: str,
        updated_at: Optional[str] = None
    ) -> int:
        """
        更新職缺狀態。

        Args:
            vacancy_id:
                職缺 ID

            status:
                新狀態

            updated_at:
                更新時間

        Returns:
            影響行數
        """

        allowed_statuses = {
            "ACTIVE",
            "INACTIVE",
            "PAUSED",
            "CLOSED",
            "DELETED",
        }

        normalized_status = str(status).upper()

        if normalized_status not in allowed_statuses:
            raise ValueError(
                f"不合法的職缺狀態：{status}"
            )

        if updated_at:
            query = """
                UPDATE vacancy
                SET
                    status = ?,
                    updated_at = ?
                WHERE vacancy_id = ?
            """

            params = (
                normalized_status,
                updated_at,
                vacancy_id,
            )

        else:
            query = """
                UPDATE vacancy
                SET
                    status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE vacancy_id = ?
            """

            params = (
                normalized_status,
                vacancy_id,
            )

        with db_manager.user_write() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)

            return cursor.rowcount

    # =========================================================
    # 取得使用者目前負責的職缺
    # =========================================================

    def get_vacancies_by_user_id(
        self,
        user_id: str,
        include_deleted: bool = False
    ) -> List[Dict[str, Any]]:
        """
        取得某位使用者目前負責的職缺。

        Args:
            user_id:
                使用者 ID

            include_deleted:
                是否包含已刪除職缺

        Returns:
            使用者目前負責的職缺列表
        """

        query = """
            SELECT
                v.*,
                vi.relation_id,
                vi.role_type,
                vi.is_primary,
                vi.assigned_at,
                vi.note

            FROM vacancy_incharge AS vi

            INNER JOIN vacancy AS v
                ON v.vacancy_id = vi.vacancy_id

            WHERE vi.user_id = ?
              AND vi.unassigned_at IS NULL
        """

        params: List[Any] = [user_id]

        if not include_deleted:
            query += " AND v.status != 'DELETED'"

        query += """
            ORDER BY
                vi.is_primary DESC,
                vi.assigned_at DESC,
                v.position_title ASC
        """

        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))

            return [
                dict(row)
                for row in cursor.fetchall()
            ]

    # =========================================================
    # 取得職缺目前的負責人
    # =========================================================

    def get_vacancy_incharges(
        self,
        vacancy_id: str,
        include_history: bool = False
    ) -> List[Dict[str, Any]]:
        """
        取得職缺負責人。

        Args:
            vacancy_id:
                職缺 ID

            include_history:
                是否包含歷史負責人

        Returns:
            負責人列表
        """

        query = """
            SELECT
                vi.relation_id,
                vi.vacancy_id,
                vi.user_id,
                vi.role_type,
                vi.is_primary,
                vi.assigned_at,
                vi.unassigned_at,
                vi.note,
                vi.created_by,
                vi.created_at,
                vi.updated_at,

                u.user_account,
                u.user_name,
                u.user_email,
                u.user_role,
                u.status AS user_status

            FROM vacancy_incharge AS vi

            INNER JOIN user AS u
                ON u.user_id = vi.user_id

            WHERE vi.vacancy_id = ?
        """

        params: List[Any] = [vacancy_id]

        if not include_history:
            query += " AND vi.unassigned_at IS NULL"

        query += """
            ORDER BY
                vi.is_primary DESC,
                vi.assigned_at DESC
        """

        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))

            return [
                dict(row)
                for row in cursor.fetchall()
            ]

    # =========================================================
    # 取得不重複欄位值
    # =========================================================

    def get_distinct_values(
        self,
        column_name: str
    ) -> List:
        allowed_columns = {
            "position_title",
            "work_location",
            "senior",
            "lab",
            "status",
        }

        if column_name not in allowed_columns:
            raise ValueError(
                f"欄位 '{column_name}' 不允許查詢"
            )

        query = f"""
            SELECT DISTINCT {column_name}
            FROM vacancy
            WHERE {column_name} IS NOT NULL
              AND TRIM(CAST({column_name} AS TEXT)) != ''
              AND status = 'ACTIVE'
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

    # =========================================================
    # 取得特定狀態的職缺
    # =========================================================

    def get_vacancies_by_status(
        self,
        status: str
    ) -> List[Dict[str, Any]]:
        """
        根據狀態取得職缺。

        Args:
            status:
                職缺狀態

        Returns:
            職缺資料列表
        """

        normalized_status = str(status).upper()

        query = """
            SELECT *
            FROM vacancy
            WHERE status = ?
            ORDER BY updated_at DESC
        """

        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (normalized_status,)
            )

            return [
                dict(row)
                for row in cursor.fetchall()
            ]

    # =========================================================
    # 取得活躍職缺
    # =========================================================

    def get_active_vacancies(
        self
    ) -> List[Dict[str, Any]]:
        """取得所有 ACTIVE 職缺"""

        query = """
            SELECT *
            FROM vacancy
            WHERE status = 'ACTIVE'
            ORDER BY updated_at DESC
        """

        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query)

            return [
                dict(row)
                for row in cursor.fetchall()
            ]

    # =========================================================
    # 職缺統計
    # =========================================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        取得職缺統計資訊。

        Returns:
            統計資訊字典
        """

        stats: Dict[str, Any] = {}

        with db_manager.user_read() as conn:
            cursor = conn.cursor()

            # -------------------------------------------------
            # 職缺總數，不包含 DELETED
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM vacancy
                WHERE status != 'DELETED'
                """
            )

            stats["total_vacancies"] = (
                cursor.fetchone()[0]
            )

            # -------------------------------------------------
            # ACTIVE 職缺
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM vacancy
                WHERE status = 'ACTIVE'
                """
            )

            stats["active_vacancies"] = (
                cursor.fetchone()[0]
            )

            # -------------------------------------------------
            # INACTIVE 職缺
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM vacancy
                WHERE status = 'INACTIVE'
                """
            )

            stats["inactive_vacancies"] = (
                cursor.fetchone()[0]
            )

            # -------------------------------------------------
            # PAUSED 職缺
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM vacancy
                WHERE status = 'PAUSED'
                """
            )

            stats["paused_vacancies"] = (
                cursor.fetchone()[0]
            )

            # -------------------------------------------------
            # CLOSED 職缺
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM vacancy
                WHERE status = 'CLOSED'
                """
            )

            stats["closed_vacancies"] = (
                cursor.fetchone()[0]
            )

            # -------------------------------------------------
            # 已刪除職缺
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM vacancy
                WHERE status = 'DELETED'
                """
            )

            stats["deleted_vacancies"] = (
                cursor.fetchone()[0]
            )

            # -------------------------------------------------
            # Lab 數量
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT COUNT(
                    DISTINCT lab
                )
                FROM vacancy
                WHERE lab IS NOT NULL
                  AND TRIM(lab) != ''
                  AND status != 'DELETED'
                """
            )

            stats["total_labs"] = (
                cursor.fetchone()[0]
            )

            # -------------------------------------------------
            # 按狀態分布
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT
                    status,
                    COUNT(*) AS count

                FROM vacancy

                GROUP BY status

                ORDER BY count DESC
                """
            )

            stats["by_status"] = {
                row[1]
                for row in cursor.fetchall()
            }

            # -------------------------------------------------
            # 按 Lab 分布
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT
                    lab,
                    COUNT(*) AS count

                FROM vacancy

                WHERE lab IS NOT NULL
                  AND TRIM(lab) != ''
                  AND status != 'DELETED'

                GROUP BY lab

                ORDER BY count DESC
                """
            )

            stats["by_lab"] = {
                row[1]
                for row in cursor.fetchall()
            }

            # -------------------------------------------------
            # 按 Senior 分布
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT
                    senior,
                    COUNT(*) AS count

                FROM vacancy

                WHERE senior IS NOT NULL
                  AND TRIM(senior) != ''
                  AND status != 'DELETED'

                GROUP BY senior

                ORDER BY count DESC
                """
            )

            stats["by_senior"] = {
                row[1]
                for row in cursor.fetchall()
            }

            # -------------------------------------------------
            # 最近更新的職缺
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT
                    vacancy_id,
                    position_title,
                    lab,
                    senior,
                    status,
                    updated_at

                FROM vacancy

                WHERE status != 'DELETED'

                ORDER BY updated_at DESC

                LIMIT 5
                """
            )

            stats["recent_vacancies"] = [
                dict(row)
                for row in cursor.fetchall()
            ]

        return stats

    # =========================================================
    # 檢查職缺是否存在
    # =========================================================

    def check_vacancy_exists(
        self,
        vacancy_id: str,
        include_deleted: bool = False
    ) -> bool:
        """
        檢查 vacancy_id 是否存在。

        Args:
            vacancy_id:
                職缺 ID

            include_deleted:
                是否將 DELETED 職缺視為存在

        Returns:
            是否存在
        """

        query = """
            SELECT COUNT(*)
            FROM vacancy
            WHERE vacancy_id = ?
        """

        params: List[Any] = [vacancy_id]

        if not include_deleted:
            query += " AND status != 'DELETED'"

        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                tuple(params)
            )

            result = cursor.fetchone()

            return (
                result[0] > 0
                if result
                else False
            )

    # =========================================================
    # 檢查職位名稱是否重複
    # =========================================================

    def check_position_title_exists(
        self,
        position_title: str,
        exclude_vacancy_id: Optional[str] = None
    ) -> bool:
        """
        檢查職位名稱是否已存在。

        注意：
            同職位名稱可能屬於不同 Lab，
            因此此方法只提供檢查，不代表一定要禁止重複。

        Args:
            position_title:
                職位名稱

            exclude_vacancy_id:
                更新時排除目前職缺

        Returns:
            是否存在
        """

        if exclude_vacancy_id:
            query = """
                SELECT COUNT(*)
                FROM vacancy
                WHERE position_title = ?
                  AND vacancy_id != ?
                  AND status != 'DELETED'
            """

            params = (
                position_title,
                exclude_vacancy_id,
            )

        else:
            query = """
                SELECT COUNT(*)
                FROM vacancy
                WHERE position_title = ?
                  AND status != 'DELETED'
            """

            params = (position_title,)

        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)

            result = cursor.fetchone()

            return (
                result[0] > 0
                if result
                else False
            )

