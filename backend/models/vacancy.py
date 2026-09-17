# models/vacancy.py

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class Vacancy:
    """職缺資料模型"""

    vacancy_id: str
    position_title: str

    introduction: Optional[str] = None
    compensation: Optional[str] = None
    requirements: Optional[str] = None
    work_location: Optional[str] = None
    manager: Optional[str] = None
    senior: Optional[str] = None
    lab: Optional[str] = None
    weight: Optional[float] = None

    education_score_error: Optional[float] = None
    education_score_5: Optional[float] = None
    education_score_4: Optional[float] = None
    education_score_3: Optional[float] = None
    education_score_2: Optional[float] = None
    education_score_1: Optional[float] = None
    education_score_0: Optional[float] = None

    status: str = "ACTIVE"

    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """轉換成字典"""

        return {
            "vacancy_id": self.vacancy_id,
            "position_title": self.position_title,
            "introduction": self.introduction,
            "compensation": self.compensation,
            "requirements": self.requirements,
            "work_location": self.work_location,
            "manager": self.manager,
            "senior": self.senior,
            "lab": self.lab,
            "weight": self.weight,
            "education_score_error": self.education_score_error,
            "education_score_5": self.education_score_5,
            "education_score_4": self.education_score_4,
            "education_score_3": self.education_score_3,
            "education_score_2": self.education_score_2,
            "education_score_1": self.education_score_1,
            "education_score_0": self.education_score_0,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class VacancyFilter:
    """職缺篩選條件"""

    vacancy_id: Optional[str] = None
    position_title: Optional[str] = None
    position_title_authority : Optional[list] = None
    work_location: Optional[str] = None
    senior: Optional[str] = None
    lab: Optional[str] = None
    status: Optional[str] = None

    # 查詢某位使用者負責的職缺
    incharge_user_id: Optional[str] = None

    # 通用關鍵字搜尋
    search_keyword: Optional[str] = None

    # 預設排除軟刪除職缺
    exclude_deleted: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vacancy_id": self.vacancy_id,
            "position_title": self.position_title,
            "position_title_authority": self.position_title_authority,
            "work_location": self.work_location,
            "senior": self.senior,
            "lab": self.lab,
            "status": self.status,
            "incharge_user_id": self.incharge_user_id,
            "search_keyword": self.search_keyword,
            "exclude_deleted": self.exclude_deleted,
        }


@dataclass
class VacancyUpdateRequest:
    """職缺更新請求"""

    vacancy_id: str
    updates: Dict[str, Any]
    operator: str

    def validate(self) -> tuple[bool, str]:
        """驗證更新請求"""

        if not self.vacancy_id:
            return False, "vacancy_id 不能為空"

        if not self.updates:
            return False, "updates 不能為空"

        if not self.operator:
            return False, "operator 不能為空"

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
        }

        invalid_fields = set(self.updates) - allowed_fields

        if invalid_fields:
            return False, (
                f"不允許更新以下欄位："
                f"{', '.join(sorted(invalid_fields))}"
            )

        if "position_title" in self.updates:
            position_title = self.updates["position_title"]

            if (
                position_title is None
                or not str(position_title).strip()
            ):
                return False, "position_title 不能為空"

        if "status" in self.updates:
            valid_statuses = {
                "ACTIVE",
                "INACTIVE",
                "PAUSED",
                "CLOSED",
                "DELETED",
            }

            status = str(self.updates["status"]).upper()

            if status not in valid_statuses:
                return False, (
                    f"無效的職缺狀態：{status}"
                )

        return True, ""
    
@dataclass
class VacancyCreateRequest:
    """建立職缺請求"""

    position_title: str

    introduction: Optional[str] = None
    compensation: Optional[str] = None
    requirements: Optional[str] = None
    work_location: Optional[str] = None

    senior: Optional[str] = None
    lab: Optional[str] = None
    weight: Optional[float] = None

    education_score_error: Optional[float] = None
    education_score_5: Optional[float] = None
    education_score_4: Optional[float] = None
    education_score_3: Optional[float] = None
    education_score_2: Optional[float] = None
    education_score_1: Optional[float] = None
    education_score_0: Optional[float] = None

    status: str = "ACTIVE"
    operator: Optional[str] = None

    def validate(self) -> tuple[bool, str]:
        """驗證新增職缺請求"""

        if not self.position_title:
            return False, "position_title 不能為空"

        if not self.position_title.strip():
            return False, "position_title 不能只包含空白"

        if not self.operator:
            return False, "operator 不能為空"

        valid_statuses = {
            "ACTIVE",
            "INACTIVE",
            "PAUSED",
            "CLOSED",
            "DELETED",
        }

        if self.status.upper() not in valid_statuses:
            return False, f"無效的職缺狀態：{self.status}"

        return True, ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position_title": self.position_title.strip(),
            "introduction": self.introduction,
            "compensation": self.compensation,
            "requirements": self.requirements,
            "work_location": self.work_location,
            "senior": self.senior,
            "lab": self.lab,
            "weight": self.weight,
            "education_score_error": self.education_score_error,
            "education_score_5": self.education_score_5,
            "education_score_4": self.education_score_4,
            "education_score_3": self.education_score_3,
            "education_score_2": self.education_score_2,
            "education_score_1": self.education_score_1,
            "education_score_0": self.education_score_0,
            "status": self.status.upper(),
        }