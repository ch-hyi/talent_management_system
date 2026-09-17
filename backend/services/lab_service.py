"""
Lab 業務邏輯層
"""

import traceback

from typing import Dict, Any,Optional

from ..repositories.lab_repository import LabRepository
from ..models.response import APIResponse
from geopy.exc import (
    GeocoderServiceError,
    GeocoderTimedOut,
    GeocoderUnavailable,
)
from geopy.geocoders import Nominatim


class LabService:
    """Lab 管理業務邏輯"""

    def __init__(
        self,
        lab_repo: LabRepository
    ):
        self.lab_repo = lab_repo

    # =========================================================
    # 建立 Lab
    # =========================================================

    def geocode_address(
        self,
        address: str,
    ) -> Optional[tuple[float, float, str]]:
        """
        將地址轉換成經緯度。

        Returns:
            (latitude, longitude, matched_address)

            找不到地址時回傳 None。
        """
        geolocator = Nominatim(
        user_agent="talent-management-system/1.0",
        timeout=10,
        )
        cleaned_address = address.strip()

        if not cleaned_address:
            return None

        # 加上 Taiwan 通常能提升台灣地址的辨識準確度
        query = f"{cleaned_address}, Taiwan"

        try:
            location = geolocator.geocode(
                query,
                exactly_one=True,
                country_codes="tw",
                language="zh-TW",
            )

            if location is None:
                return None

            return (
                float(location.latitude),
                float(location.longitude),
                location.address,
            )

        except (
            GeocoderTimedOut,
            GeocoderUnavailable,
            GeocoderServiceError,
        ) as error:
            raise RuntimeError(
                f"Address geocoding failed: {error}"
            ) from error
        
    def create_lab(
        self,
        lab_data: Dict[str, Any]
    ) -> APIResponse:
        """
        建立新的 Lab。

        Args:
            lab_data:
                Lab 資料，可包含：

                - name
                - address
                - latitude
                - longitude
                - template
                - contact

        Returns:
            APIResponse
        """

        try:
            if not lab_data:
                return APIResponse(
                    success=False,
                    message="Lab 資料不能為空"
                )

            name = str(
                lab_data.get("name", "")
            ).strip()

            address = str(
                lab_data.get("address", "")
            ).strip()

            if not name:
                return APIResponse(
                    success=False,
                    message="Lab 名稱不能為空"
                )

            if not address:
                return APIResponse(
                    success=False,
                    message="Lab 地址不能為空"
                )

            # 檢查 Lab 名稱是否重複
            if self.lab_repo.check_lab_name_exists(name):
                return APIResponse(
                    success=False,
                    message=f"Lab 名稱「{name}」已經存在"
                )
            if not lab_data.get("latitude") or not lab_data.get("longitude"):
                lat ,lon , _ = self.geocode_address(lab_data.get("address"))
                lab_data["latitude"] = lat
                lab_data["longitude"] = lon


            normalized_data = lab_data.copy()

            normalized_data["name"] = name
            normalized_data["address"] = address

            # 正規化選填文字欄位
            for field in (
                "template",
                "contact",
            ):
                if field in normalized_data:
                    value = normalized_data[field]

                    if value is not None:
                        normalized_data[field] = str(
                            value
                        ).strip()

            # 經緯度轉成 float
            for field in (
                "latitude",
                "longitude",
            ):
                if field in normalized_data:
                    value = normalized_data[field]

                    if value in (
                        None,
                        "",
                    ):
                        normalized_data[field] = None

                    else:
                        normalized_data[field] = float(value)

            self._validate_coordinates(
                normalized_data.get("latitude"),
                normalized_data.get("longitude")
            )

            lab_id = self.lab_repo.create_lab(
                normalized_data
            )

            return APIResponse(
                success=True,
                data={
                    "lab_id": lab_id
                },
                message=f"成功建立 Lab「{name}」"
            )

        except ValueError as e:
            return APIResponse(
                success=False,
                error=str(e),
                message=str(e)
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="建立 Lab 失敗"
            )

    # =========================================================
    # 更新 Lab
    # =========================================================

    def update_lab(
        self,
        lab_id: str,
        updates: Dict[str, Any]
    ) -> APIResponse:
        """
        更新指定 Lab。

        Args:
            lab_id:
                Lab ID。

            updates:
                要更新的欄位。

        Returns:
            APIResponse
        """

        try:
            if not lab_id:
                return APIResponse(
                    success=False,
                    message="lab_id 不能為空"
                )

            if not updates:
                return APIResponse(
                    success=False,
                    message="updates 不能為空"
                )

            original_lab = self.lab_repo.get_lab_by_id(
                lab_id
            )

            if not original_lab:
                return APIResponse(
                    success=False,
                    message="找不到該 Lab"
                )

            normalized_updates = updates.copy()

            if "name" in normalized_updates:
                normalized_updates["name"] = str(
                    normalized_updates["name"]
                ).strip()

                if not normalized_updates["name"]:
                    return APIResponse(
                        success=False,
                        message="Lab 名稱不能為空"
                    )

                name_exists = (
                    self.lab_repo.check_lab_name_exists(
                        normalized_updates["name"],
                        exclude_lab_id=lab_id
                    )
                )

                if name_exists:
                    return APIResponse(
                        success=False,
                        message=(
                            f"Lab 名稱「"
                            f"{normalized_updates['name']} 已經存在"
                        )
                    )

            if "address" in normalized_updates:
                normalized_updates["address"] = str(
                    normalized_updates["address"]
                ).strip()

                if not normalized_updates["address"]:
                    return APIResponse(
                        success=False,
                        message="Lab 地址不能為空"
                    )

            for field in (
                "template",
                "contact",
            ):
                if field in normalized_updates:
                    value = normalized_updates[field]

                    if value is not None:
                        normalized_updates[field] = str(
                            value
                        ).strip()

            for field in (
                "latitude",
                "longitude",
            ):
                if field in normalized_updates:
                    value = normalized_updates[field]

                    if value in (
                        None,
                        "",
                    ):
                        normalized_updates[field] = None

                    else:
                        normalized_updates[field] = float(
                            value
                        )

            # 使用更新後的值驗證經緯度
            latitude = normalized_updates.get(
                "latitude",
                original_lab.get("latitude")
            )

            longitude = normalized_updates.get(
                "longitude",
                original_lab.get("longitude")
            )

            self._validate_coordinates(
                latitude,
                longitude
            )

            # 過濾沒有實際改變的欄位
            changed_updates = {
                field: value
                for field, value in normalized_updates.items()
                if original_lab.get(field) != value
            }

            if not changed_updates:
                return APIResponse(
                    success=True,
                    data={
                        "lab_id": lab_id,
                        "affected_rows": 0,
                        "updated_fields": []
                    },
                    message="Lab 資料沒有變更"
                )

            affected_rows = self.lab_repo.update_lab(
                lab_id,
                changed_updates
            )

            if affected_rows == 0:
                return APIResponse(
                    success=False,
                    data={
                        "lab_id": lab_id,
                        "affected_rows": 0
                    },
                    message="沒有 Lab 資料被更新"
                )

            return APIResponse(
                success=True,
                data={
                    "lab_id": lab_id,
                    "affected_rows": affected_rows,
                    "updated_fields": list(
                        changed_updates.keys()
                    )
                },
                message="成功更新 Lab"
            )
        except ValueError as e:
            return APIResponse(
                success=False,
                error=str(e),
                message=str(e)
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="更新 Lab 失敗"
            )

    # =========================================================
    # 硬刪除 Lab
    # =========================================================

    def delete_lab(
        self,
        lab_id: str
    ) -> APIResponse:
        """
        永久刪除指定 Lab。

        注意：
            此方法為硬刪除，不保留歷史資料。

            若 vacancy.lab 儲存的是 Lab 名稱，
            刪除 Lab 不會自動修改既有 Vacancy。
        """

        try:
            if not lab_id:
                return APIResponse(
                    success=False,
                    message="lab_id 不能為空"
                )

            original_lab = self.lab_repo.get_lab_by_id(
                lab_id
            )

            if not original_lab:
                return APIResponse(
                    success=False,
                    message="找不到該 Lab"
                )

            affected_rows = self.lab_repo.delete_lab(
                lab_id
            )

            if affected_rows == 0:
                return APIResponse(
                    success=False,
                    data={
                        "lab_id": lab_id,
                        "affected_rows": 0
                    },
                    message="沒有 Lab 資料被刪除"
                )

            return APIResponse(
                success=True,
                data={
                    "lab_id": lab_id,
                    "name": original_lab.get("name"),
                    "affected_rows": affected_rows
                },
                message=(
                    f"成功刪除 Lab「"
                    f"{original_lab.get('name', lab_id)}」"
                ))
        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="刪除 Lab 失敗"
            )

    # =========================================================
    # 依 ID 取得單一 Lab
    # =========================================================

    def get_lab_by_id(
        self,
        lab_id: str
    ) -> APIResponse:
        """
        根據 lab_id 取得單一 Lab。
        """

        try:
            if not lab_id:
                return APIResponse(
                    success=False,
                    message="lab_id 不能為空"
                )

            data = self.lab_repo.get_lab_by_id(
                lab_id
            )

            if not data:
                return APIResponse(
                    success=False,
                    message="找不到該 Lab"
                )

            return APIResponse(
                success=True,
                data=data,
                message="取得 Lab 資料成功"
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="取得 Lab 資料失敗"
            )

    # =========================================================
    # 依名稱取得 Lab
    # =========================================================

    def get_lab_by_name(
        self,
        name: str
    ) -> APIResponse:
        """
        根據名稱取得單一 Lab。
        """

        try:
            normalized_name = str(name).strip()

            if not normalized_name:
                return APIResponse(
                    success=False,
                    message="Lab 名稱不能為空"
                )

            data = self.lab_repo.get_lab_by_name(
                normalized_name
            )

            if not data:
                return APIResponse(
                    success=False,
                    message=f"找不到 Lab「{normalized_name}」"
                )

            return APIResponse(
                success=True,
                data=data,
                message="取得 Lab 資料成功"
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="取得 Lab 資料失敗"
            )

    # =========================================================
    # 取得全部 Lab
    # =========================================================

    def get_all_labs(
        self
    ) -> APIResponse:
        """
        取得全部 Lab。

        Lab 數量不多，因此不使用分頁。
        """

        try:
            data = self.lab_repo.get_all_labs()

            return APIResponse(
                success=True,
                data=data,
                message=f"成功取得 {len(data)} 筆 Lab 資料"
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="取得 Lab 列表失敗"
            )

    # =========================================================
    # 取得 Lab 數量
    # =========================================================

    def get_lab_count(
        self
    ) -> APIResponse:
        """取得 Lab 總數"""

        try:
            count = self.lab_repo.get_lab_count()

            return APIResponse(
                success=True,
                data=count,
                message="取得 Lab 數量成功"
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="取得 Lab 數量失敗"
            )

    # =========================================================
    # 取得 Lab 下拉選項
    # =========================================================

    def get_lab_options(
        self
    ) -> APIResponse:
        """
        取得前端 Lab 下拉選單資料。

        每筆資料包含：

        - lab_id
        - name
        """

        try:
            options = self.lab_repo.get_lab_options()

            return APIResponse(
                success=True,
                data=options,
                message=(
                    f"成功取得 {len(options)} 個 "
                    f"Lab 選項"
                )
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="取得 Lab 選項失敗"
            )

    # =========================================================
    # 檢查 Lab 是否存在
    # =========================================================

    def check_lab_exists(
        self,
        lab_id: str
    ) -> APIResponse:
        """檢查 Lab 是否存在"""

        try:
            if not lab_id:
                return APIResponse(
                    success=False,
                    message="lab_id 不能為空"
                )

            exists = self.lab_repo.check_lab_exists(
                lab_id
            )

            return APIResponse(
                success=True,
                data=exists,
                message=(
                    "Lab 存在"
                    if exists
                    else "Lab 不存在"
                )
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="檢查 Lab 是否存在失敗"
            )

    # =========================================================
    # 檢查 Lab 名稱是否重複
    # =========================================================

    def check_lab_name_exists(
        self,
        name: str,
        exclude_lab_id: str | None = None
    ) -> APIResponse:
        """
        檢查 Lab 名稱是否重複。

        Args:
            name:
                Lab 名稱。

            exclude_lab_id:
                更新時排除目前的 Lab ID。
        """

        try:
            normalized_name = str(name).strip()

            if not normalized_name:
                return APIResponse(
                    success=False,
                    message="Lab 名稱不能為空"
                )

            exists = (
                self.lab_repo.check_lab_name_exists(
                    normalized_name,
                    exclude_lab_id=exclude_lab_id
                )
            )

            return APIResponse(
                success=True,
                data=exists,
                message=(
                    "Lab 名稱已存在"
                    if exists
                    else "Lab 名稱可以使用"
                )
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e),
                message="檢查 Lab 名稱失敗"
            )

    # =========================================================
    # 經緯度驗證
    # =========================================================

    @staticmethod
    def _validate_coordinates(
        latitude: Any,
        longitude: Any
    ) -> None:
        """
        驗證經緯度範圍。

        Latitude:
            -90 到 90。

        Longitude:
            -180 到 180。

        Raises:
            ValueError:
                經緯度格式或範圍錯誤。
        """

        if latitude is not None:
            try:
                latitude = float(latitude)

            except (
                TypeError,
                ValueError,
            ) as e:
                raise ValueError(
                    "latitude 必須是有效數字"
                ) from e

            if not -90 <= latitude <= 90:
                raise ValueError(
                    "latitude 必須介於 -90 到 90"
                )

        if longitude is not None:
            try:
                longitude = float(longitude)

            except (
                TypeError,
                ValueError,
            ) as e:
                raise ValueError(
                    "longitude 必須是有效數字"
                ) from e

            if not -180 <= longitude <= 180:
                raise ValueError(
                    "longitude 必須介於 -180 到 180"
                )