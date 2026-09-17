    # =========================================================
    # 建立 Lab
    # =========================================================
import uuid
from ..database.connection import db_manager
from typing import List, Dict, Any, Optional

class LabRepository:

    
    def create_lab(
        self,
        lab_data: Dict[str, Any]
    ) -> str:
        """
        建立新的 Lab。

        Args:
            lab_data:
                Lab 資料，可包含以下欄位：

                - name
                - address
                - latitude
                - longitude
                - template
                - contact

        Returns:
            新建立的 lab_id。

        Raises:
            ValueError:
                name 或 address 為空。
        """

        name = str(
            lab_data.get("name", "")
        ).strip()

        address = str(
            lab_data.get("address", "")
        ).strip()

        if not name:
            raise ValueError("Lab 名稱不可為空")

        if not address:
            raise ValueError("Lab 地址不可為空")

        lab_id = str(uuid.uuid4())

        query = """
            INSERT INTO lab (
                lab_id,
                name,
                address,
                latitude,
                longitude,
                template,
                contact
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            lab_id,
            name,
            address,
            lab_data.get("latitude"),
            lab_data.get("longitude"),
            lab_data.get("template"),
            lab_data.get("contact"),
        )

        with db_manager.user_write() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)

            if cursor.rowcount <= 0:
                raise RuntimeError("建立 Lab 失敗")

        return lab_id

    # =========================================================
    # 動態更新 Lab
    # =========================================================

    def update_lab(
        self,
        lab_id: str,
        updates: Dict[str, Any]
    ) -> int:
        """
        更新指定 Lab。

        Args:
            lab_id:
                Lab ID。

            updates:
                要更新的欄位字典。

                允許更新：

                - name
                - address
                - latitude
                - longitude
                - template
                - contact

        Returns:
            影響行數。

        Raises:
            ValueError:
                包含不允許更新的欄位，或必填欄位為空。
        """

        if not updates:
            return 0

        allowed_fields = {
            "name",
            "address",
            "latitude",
            "longitude",
            "template",
            "contact",
        }

        invalid_fields = (
            set(updates.keys()) - allowed_fields
        )

        if invalid_fields:
            raise ValueError(
                "不允許更新以下 Lab 欄位："
                + ", ".join(sorted(invalid_fields))
            )

        normalized_updates = updates.copy()

        if "name" in normalized_updates:
            normalized_updates["name"] = str(
                normalized_updates["name"]
            ).strip()

            if not normalized_updates["name"]:
                raise ValueError("Lab 名稱不可為空")

        if "address" in normalized_updates:
            normalized_updates["address"] = str(
                normalized_updates["address"]
            ).strip()

            if not normalized_updates["address"]:
                raise ValueError("Lab 地址不可為空")

        set_clause = ", ".join(
            f"{field} = ?"
            for field in normalized_updates.keys()
        )

        values = list(normalized_updates.values())
        values.append(lab_id)

        query = f"""
            UPDATE lab
            SET {set_clause}
            WHERE lab_id = ?
        """

        with db_manager.user_write() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                tuple(values)
            )

            return cursor.rowcount

    # =========================================================
    # 硬刪除 Lab
    # =========================================================

    def delete_lab(
        self,
        lab_id: str
    ) -> int:
        """
        永久刪除指定 Lab。

        注意：
            此方法為硬刪除，不保留 Lab 資料。

        Args:
            lab_id:
                Lab ID。

        Returns:
            影響行數。
        """

        query = """
            DELETE FROM lab
            WHERE lab_id = ?
        """

        with db_manager.user_write() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (lab_id,)
            )

            return cursor.rowcount

    # =========================================================
    # 依 ID 取得單一 Lab
    # =========================================================

    def get_lab_by_id(
        self,
        lab_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        根據 lab_id 取得單一 Lab。

        Args:
            lab_id:
                Lab ID。

        Returns:
            Lab 資料字典，不存在時回傳 None。
        """

        query = """
            SELECT
                lab_id,
                name,
                address,
                latitude,
                longitude,
                template,
                contact,
                created_time
            FROM lab
            WHERE lab_id = ?
        """

        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (lab_id,)
            )

            result = cursor.fetchone()

            return dict(result) if result else None

    # =========================================================
    # 依名稱取得 Lab
    # =========================================================

    def get_lab_by_name(
        self,
        name: str
    ) -> Optional[Dict[str, Any]]:
        """
        根據名稱取得單一 Lab。

        Args:
            name:
                Lab 名稱。

        Returns:
            Lab 資料字典，不存在時回傳 None。
        """

        normalized_name = str(name).strip()

        if not normalized_name:
            return None

        query = """
            SELECT
                lab_id,
                name,
                address,
                latitude,
                longitude,
                template,
                contact,
                created_time
            FROM lab
            WHERE name = ?
            LIMIT 1
        """

        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (normalized_name,)
            )

            result = cursor.fetchone()

            return dict(result) if result else None

    # =========================================================
    # 取得全部 Lab
    # =========================================================

    def get_all_labs(
        self
    ) -> List[Dict[str, Any]]:
        """
        取得全部 Lab。

        Returns:
            Lab 資料列表。

        Notes:
            Lab 數量不多，因此不使用分頁。
        """

        query = """
            SELECT
                lab_id,
                name,
                address,
                latitude,
                longitude,
                template,
                contact,
                created_time
            FROM lab
            ORDER BY name ASC
        """

        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query)

            return [
                dict(row)
                for row in cursor.fetchall()
            ]

    # =========================================================
    # 取得 Lab 數量
    # =========================================================

    def get_lab_count(
        self
    ) -> int:
        """
        取得 Lab 總數。

        Returns:
            Lab 總數。
        """

        query = """
            SELECT COUNT(*) AS total
            FROM lab
        """

        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query)

            result = cursor.fetchone()

            return result[0] if result else 0

    # =========================================================
    # 檢查 Lab 是否存在
    # =========================================================

    def check_lab_exists(
        self,
        lab_id: str
    ) -> bool:
        """
        檢查 lab_id 是否存在。

        Args:
            lab_id:
                Lab ID。

        Returns:
            Lab 是否存在。
        """

        query = """
            SELECT EXISTS(
                SELECT 1
                FROM lab
                WHERE lab_id = ?
            )
        """

        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (lab_id,)
            )

            result = cursor.fetchone()

            return bool(result[0]) if result else False

    # =========================================================
    # 檢查 Lab 名稱是否重複
    # =========================================================

    def check_lab_name_exists(
        self,
        name: str,
        exclude_lab_id: Optional[str] = None
    ) -> bool:
        """
        檢查 Lab 名稱是否已存在。

        Args:
            name:
                Lab 名稱。

            exclude_lab_id:
                更新 Lab 時，排除目前的 lab_id。

        Returns:
            名稱是否已存在。
        """

        normalized_name = str(name).strip()

        if not normalized_name:
            return False

        if exclude_lab_id:
            query = """
                SELECT EXISTS(
                    SELECT 1
                    FROM lab
                    WHERE name = ?
                      AND lab_id != ?
                )
            """

            params = (
                normalized_name,
                exclude_lab_id,
            )

        else:
            query = """
                SELECT EXISTS(
                    SELECT 1
                    FROM lab
                    WHERE name = ?
                )
            """

            params = (normalized_name,)

        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                params
            )

            result = cursor.fetchone()

            return bool(result[0]) if result else False

    # =========================================================
    # 取得 Lab 下拉選單資料
    # =========================================================

    def get_lab_options(
        self
    ) -> List[Dict[str, Any]]:
        """
        取得 Lab 下拉選單所需資料。

        Returns:
            僅包含 lab_id 與 name 的 Lab 列表。
        """

        query = """
            SELECT
                lab_id,
                name
            FROM lab
            ORDER BY name ASC
        """

        with db_manager.user_read() as conn:
            cursor = conn.cursor()
            cursor.execute(query)

            return [
                dict(row)
                for row in cursor.fetchall()
            ]