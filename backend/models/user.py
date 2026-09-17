# models/user.py
from dataclasses import dataclass, field,asdict
from typing import Optional, Dict, Any
from datetime import datetime

@dataclass
class User:
    """用戶模型"""
    user_id: str
    user_account: str
    user_name: str
    user_email: str
    password_hash: str
    user_role: Optional[str] = None
    create_time: Optional[str] = None
    created_by: Optional[str] = None
    update_time: Optional[str] = None
    updated_by: Optional[str] = None
    last_login: Optional[str] = None
    status: str = "ACTIVE"
    deleted_time: Optional[str] = None
    deleted_by: Optional[str] = None
    vacancy_incharge :list = None
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            "user_id": self.user_id,
            "user_account": self.user_account,
            "user_name": self.user_name,
            "user_email": self.user_email,
            "password_hash": self.password_hash,
            "user_role": self.user_role,
            "create_time": self.create_time,
            "created_by": self.created_by,
            "update_time": self.update_time,
            "updated_by": self.updated_by,
            "last_login": self.last_login,
            "status": self.status,
            "deleted_time": self.deleted_time,
            "deleted_by": self.deleted_by,
            "vacancy_incharge": self.vacancy_incharge
        }

@dataclass
class VacancyManager:
    """用戶模型"""
    relation_id: str
    vacancy_id: str
    user_id: str
    role: str
    assigned_at: str
    unassigned_at: Optional[str] = None
    note: Optional[str] = None
    created_by: Optional[str] = None
    created_time: Optional[str] = None
    updated_time: Optional[str] = None

    
    def to_dict(self):
        return {
            "relation_id": self.relation_id,
            "vacancy_id": self.vacancy_id,
            "user_id": self.user_id,
            "role": self.role,
            "assigned_at": self.assigned_at,
            "unassigned_at": self.unassigned_at,
            "note": self.note,
            "created_by": self.created_by,
            "created_time": self.created_time,
            "updated_time": self.updated_time,
        }

@dataclass
class UserFilter:
    """用戶篩選條件"""
    user_role: Optional[str] = None
    status: Optional[str] = None
    user_account: Optional[str] = None
    user_name: Optional[str] = None

    def to_dict(self, exclude_none: bool = True) -> Dict[str, Any]:
        """
        轉換為字典
        
        Args:
            exclude_none: 是否排除 None 值
            
        Returns:
            字典形式的篩選條件
        """
        data = asdict(self)
        
        if exclude_none:
            return {k: v for k, v in data.items() if v is not None}
        
        return data

@dataclass
class UserUpdateRequest:
    """用戶更新請求"""
    user_id: str
    updates: Dict[str, Any]
    operator: str
    
    def validate(self) -> tuple[bool, str]:
        """驗證更新請求"""
        if not self.user_id:
            return False, "user_id 不能為空"
        if not self.updates:
            return False, "updates 不能為空"
        if not self.operator:
            return False, "operator 不能為空"
        return True, ""