"""
解析器基底類別
定義統一的解析介面
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class ParsedInstruction:
    """解析後的指令"""
    vacancy: str = ""
    status: str = ""
    action: str = ""
    note: str = ""
    
    @classmethod
    def from_string(cls, instruction_str: str) -> 'ParsedInstruction':
        """從字串解析指令（格式：###職缺,狀態,動作,備註###）"""
        parts = instruction_str.split(",")
        return cls(
            vacancy=parts[0].strip() if len(parts) > 0 else "",
            status=parts[1].strip() if len(parts) > 1 else "",
            action=parts[2].strip() if len(parts) > 2 else "",
            note=parts[3].strip() if len(parts) > 3 else ""
        )


@dataclass
class ParsedMail:
    """解析後的郵件資料"""
    source: str
    source_id: str
    name: str
    vacancy: str
    instruction: ParsedInstruction
    
    # 可選欄位
    recommender: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    education: Optional[str] = None
    source_link: Optional[str] = None
    body: Optional[str] = None
    html_body: Optional[str] = None
    received_time: Optional[str] = None
    senders: List[str] = None
    
    def __post_init__(self):
        if self.senders is None:
            self.senders = []


class BaseMailParser(ABC):
    """郵件解析器基底類別"""
    
    @abstractmethod
    def can_parse(self, mail) -> bool:
        """判斷是否能解析此郵件"""
        pass
    
    @abstractmethod
    def parse(self, mail) -> ParsedMail:
        """解析郵件"""
        pass
    
    def safe_regex(self, pattern: str, text: str, default: str = "") -> str:
        """安全的正則表達式匹配"""
        import re
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else default