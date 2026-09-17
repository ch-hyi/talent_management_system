"""
統一 API 回應格式
"""
from dataclasses import dataclass
from typing import Optional, Any

@dataclass
class APIResponse:
    """統一 API 響應格式"""
    success: bool
    data: Optional[Any] = None
    message: str = ""
    error: Optional[str] = None
    
    def to_dict(self):
        """轉換為字典"""
        return {
            "success": self.success,
            "data": self.data,
            "message": self.message,
            "error": self.error
        }