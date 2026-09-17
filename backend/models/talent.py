"""
人才資料模型
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
import sqlite3
# ==========================================
# Talent 完整資料模型
# ==========================================

@dataclass
class Talent:
    """人才完整資料結構 (對應資料庫 talent 表)"""
    
    # 主鍵與來源資訊
    id: Optional[int] = None
    source: Optional[str] = None
    source_id: Optional[str] = None
    source_link: Optional[str] = None
    mail_id: Optional[str] = None
    
    # 時間戳記
    update_time: Optional[str] = None  # DATETIME 格式: "YYYY-MM-DD HH:MM:SS"
    received_time: Optional[str] = None
    interview_time: Optional[str] = None
    onboarding_date: Optional[str] = None
    
    # 推薦與基本資訊
    recommender: Optional[str] = None
    name: Optional[str] = ""
    gender: Optional[str] = None
    age: Optional[int] = None
    
    # 評分資訊
    score: Optional[float] = None
    score_distance: Optional[float] = None
    score_experience: Optional[float] = None
    score_education: Optional[float] = None
    score_age: Optional[float] = None
    review_status : Optional[str] = ""
    review_reason: Optional[str] = ""
    invitation :Optional[str] = None
    
    # 教育背景
    education_department: Optional[str] = None
    education_school: Optional[str] = ""
    education_degree: Optional[str] = None
    education_discipline: Optional[str] = None
    education_mode: Optional[str] = None
    education_status: Optional[str] = None
    
    # 職位與地點
    vacancy: Optional[str] = ""
    city: Optional[str] = None
    district: Optional[str] = None
    
    # 聯絡資訊
    phone: Optional[str] = None
    email: Optional[str] = ""
    
    # 工作經歷
    current_company: Optional[str] = ""
    current_job_title: Optional[str] = ""
    total_exp_years: Optional[float] = None
    
    # 期望薪資與狀態
    expected_salary: Optional[int] = None
    current_status: Optional[str] = "AI REVIEW"
    
    # 備註與會議記錄
    note: Optional[str] = None
    meeting: Optional[str] = None
    description: Optional[str] = ""
    
    # 檔案路徑
    msg_backup_path: Optional[str] = None
    
    # 黑名單管理
    block: int = 0
    lock_status: str = "unlocked"
    block_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Talent':
        """從字典建立實例"""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Talent':
        if row is None:
            return None
        
        # 🔑 關鍵：將 sqlite3.Row 轉換為 dict
        if isinstance(row, sqlite3.Row):
            # 方法 A: 使用 dict()
            data = dict(row)
            
            # 或方法 B: 手動轉換
            # data = {key: row[key] for key in row.keys()}
        elif isinstance(row, dict):
            data = row
        else:
            raise TypeError(f"不支援的資料類型: {type(row)}")
        
        return cls.from_dict(data)
        return cls.from_dict(row)
    
    def get_display_name(self) -> str:
        """取得顯示用名稱"""
        return self.name or f"{self.source}-{self.source_id}"
    
    def is_blocked(self) -> bool:
        """是否被封鎖"""
        return self.block == 1
    
    def is_locked(self) -> bool:
        """是否被鎖定"""
        return self.current_status == "鎖定"
    
    def get_score_summary(self) -> Dict[str, float]:
        """取得評分摘要"""
        return {
            "total": self.score or 0.0,
            "distance": self.score_distance or 0.0,
            "experience": self.score_experience or 0.0,
            "education": self.score_education or 0.0,
            "age": self.score_age or 0.0
        }

class OCRDraft(BaseModel):

    draft_id: str

    creator: str 

    file_path: str

    status: str 

    result_json: Optional[dict] = None

    error_msg: Optional[str] = None

    created_time: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return asdict(self)

@dataclass
class TalentOCRRequest:
    """人才資料更新請求"""
    file_path:str
    username: str
    

# ==========================================
# Talent 更新請求模型
# ==========================================

@dataclass
class TalentUpdateRequest:
    """人才資料更新請求"""
    source: str
    source_id: str
    updates: Dict[str, Any]
    operator: str
    
    # 禁止更新的欄位
    FORBIDDEN_FIELDS = ["id", "source", "source_id", "mail_id"]
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """驗證請求參數"""
        if not self.source or not self.source_id:
            return False, "source 和 source_id 不能為空"
        
        if not self.updates:
            return False, "updates 不能為空"
        
        # 檢查禁止更新的欄位
        invalid_fields = [f for f in self.updates.keys() if f in self.FORBIDDEN_FIELDS]
        
        if invalid_fields:
            return False, f"禁止更新欄位: {', '.join(invalid_fields)}"
        
        # 檢查欄位是否存在於 Talent 模型中
        valid_fields = Talent.__annotations__.keys()
        unknown_fields = [f for f in self.updates.keys() if f not in valid_fields]
        
        if unknown_fields:
            return False, f"未知欄位: {', '.join(unknown_fields)}"
        
        return True, None
    
    def get_valid_updates(self) -> Dict[str, Any]:
        """取得有效的更新欄位"""
        return {
            k: v for k, v in self.updates.items() 
            if k not in self.FORBIDDEN_FIELDS
        }

# ==========================================
# Talent 批量更新請求
# ==========================================

class TalentUpdateItem(BaseModel):
    source: str
    source_id: str
    error_message:str =None
    updates: Dict[str, Any]

class TalentBatchUpdateRequest(BaseModel):
    """
    統一的更新請求 (支援單筆或批次)
    
    批次更新範例:
    {"edit":[
         {
            "source":"104",
            "source_id":"123456",
            "updates": {"current_status": "面試中"}},
        },
        {
            "source":"104",
            "source_id":"123457",
            "error_message":"缺少信箱",
            "updates": {"score": "90","name":"張五"}},
        }]
        ,
        "operator":"張三"
    }
    """
    edit: List[TalentUpdateItem]
    operator: str

    @staticmethod
    def create_batch_request(
    talent: Talent,
    operator: str
    ) -> TalentBatchUpdateRequest:

        return TalentBatchUpdateRequest(
            edit=[
                TalentUpdateItem(
                    source=talent.source,
                    source_id=talent.source_id,
                    updates=talent.to_dict()
                )
            ],
            operator=operator
        )

# ==========================================
# Talent 篩選條件模型
# ==========================================

@dataclass
class TalentFilter:
    """人才篩選條件"""
    
    # 列表型篩選
    current_status: Optional[List[str]] = None
    city: Optional[List[str]] = None
    source: Optional[List[str]] = None
    vacancy: Optional[List[str]] = None
    education_degree: Optional[List[str]] = None
    education_mode: Optional[List[str]] = None
    gender: Optional[List[str]] = None
    
    # 範圍型篩選
    score_min: Optional[float] = None
    score_max: Optional[float] = None
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    exp_years_min: Optional[float] = None
    exp_years_max: Optional[float] = None
    expected_salary_min: Optional[int] = None
    expected_salary_max: Optional[int] = None
    
    # 時間範圍篩選
    received_time_start: Optional[str] = None  # "YYYY-MM-DD"
    received_time_end: Optional[str] = None
    update_time_start: Optional[str] = None
    update_time_end: Optional[str] = None
    
    # 布林型篩選
    exclude_blocked: bool = False  # 排除黑名單
    only_scored: bool = False  # 僅顯示已評分
    
    # 關鍵字搜尋
    search_keyword: Optional[str] = None
    
    # 排序
    sort_by: str = "update_time"  # 可選: score, age, received_time, update_time
    sort_order: str = "DESC"  # ASC 或 DESC
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典（過濾 None 值）"""
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    def has_filters(self) -> bool:
        """是否有任何篩選條件"""
        return any([
            self.current_status,
            self.city,
            self.source,
            self.vacancy,
            self.education_degree,
            self.score_min is not None,
            self.score_max is not None,
            self.age_min is not None,
            self.age_max is not None,
            self.search_keyword,
            self.exclude_blocked,
            self.only_scored
        ])

@dataclass
class TalentBatchDeleteRequest:
    """批次刪除請求"""
    talent_ids: List[tuple[str, str]]  # [(source, source_id), ...]
    operator: str
    soft_delete: bool = True  # True: 標記為黑名單, False: 實際刪除
    delete_reason: Optional[str] = None

# ==========================================
# Talent 統計模型
# ==========================================

@dataclass
class TalentStatistics:
    """人才統計資料"""
    total_count: int = 0
    status_distribution: Dict[str, int] = field(default_factory=dict)
    city_distribution: Dict[str, int] = field(default_factory=dict)
    source_distribution: Dict[str, int] = field(default_factory=dict)
    vacancy_distribution: Dict[str, int] = field(default_factory=dict)
    
    avg_score: Optional[float] = None
    avg_age: Optional[float] = None
    avg_exp_years: Optional[float] = None
    
    blocked_count: int = 0
    scored_count: int = 0
    unscored_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return asdict(self)

# ==========================================
# Talent 匯出模型
# ==========================================

@dataclass
class TalentExportRequest:
    """人才資料匯出請求"""
    filters: Optional[TalentFilter] = None
    fields: Optional[List[str]] = None  # None = 全部欄位
    format: str = "csv"  # csv, excel, json
    
    def get_export_fields(self) -> List[str]:
        """取得匯出欄位列表"""
        if self.fields:
            return self.fields
        
        # 預設匯出欄位（排除敏感資訊）
        return [
            "source", "source_id", "name", "gender", "age",
            "education_school", "education_degree", "education_department",
            "vacancy", "city", "district",
            "current_company", "current_job_title", "total_exp_years",
            "score", "score_distance", "score_experience", "score_education", "score_age",
            "current_status", "received_time", "update_time"
        ]

# ==========================================
# Talent 選項模型
# ==========================================

@dataclass
class TalentOptions:
    """人才篩選選項 (用於前端下拉選單)"""
    cities: List[str] = field(default_factory=list)
    statuses: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    vacancies: List[str] = field(default_factory=list)
    education_degrees: List[str] = field(default_factory=list)
    education_modes: List[str] = field(default_factory=list)
    genders: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, List[str]]:
        """轉換為字典"""
        return asdict(self)
    
    @classmethod
    def from_repository(cls, talent_repo) -> 'TalentOptions':
        """從 Repository 載入選項"""
        return cls(
            cities=talent_repo.get_distinct_values("city"),
            statuses=talent_repo.get_distinct_values("current_status"),
            sources=talent_repo.get_distinct_values("source"),
            vacancies=talent_repo.get_distinct_values("vacancy"),
            education_degrees=talent_repo.get_distinct_values("education_degree"),
            education_modes=talent_repo.get_distinct_values("education_mode"),
            genders=talent_repo.get_distinct_values("gender")
        )