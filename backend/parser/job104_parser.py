"""
104 人力銀行郵件解析器
處理三種類型：轉寄履歷、自訂配對、應徵履歷
"""
import re
import urllib.parse
from typing import Optional
from bs4 import BeautifulSoup

from .base_parser import BaseMailParser, ParsedMail, ParsedInstruction

MAIL_SENDERS = {
    "104_forward":"jobbank@104.com.tw",
    "104_match":"jobbank@ms1.104.com.tw",
}


class Job104Parser(BaseMailParser):
    """104 人力銀行郵件解析器"""
    
    MAIL_TYPES = {
        "forward": ("透過104轉寄履歷給您", MAIL_SENDERS["104_forward"]),
        "match": ("104自訂配對人選", MAIL_SENDERS["104_match"]),
        "apply": ("104應徵履歷", MAIL_SENDERS["104_forward"])
    }
    
    def can_parse(self, mail) -> bool:
        """判斷是否為 104 郵件"""
        sender = mail.SenderEmailAddress
        subject = mail.Subject
        
        for mail_type, (keyword, expected_sender) in self.MAIL_TYPES.items():
            if sender == expected_sender and keyword in subject:
                return True
        return False
    
    def parse(self, mail) -> ParsedMail:
        """解析 104 郵件"""
        subject = mail.Subject
        body = mail.Body
        html_body = mail.HTMLBody
        
        # 判斷郵件類型
        mail_type = self._detect_mail_type(subject, mail.SenderEmailAddress)
        
        # 解析基本資訊
        source_id = self.safe_regex(r"代碼：(\d+)", body)
        
        # 解析指令
        instruction_str = self.safe_regex(r"###(.*?)###", body)
        instruction = ParsedInstruction.from_string(instruction_str)
        
        # 解析推薦人
        recommender = self._parse_recommender(mail_type, html_body, subject)
        
        # 解析職缺
        vacancy = self._parse_vacancy(mail_type, subject, instruction)
        
        # 清理 body（移除 URL 和隱私條款）
        clean_body = self._clean_body(body, mail_type)
        
        # 解析姓名
        name = self._parse_name(html_body, clean_body, mail_type)
        
        # 解析個人資訊
        age = self._parse_age(clean_body)
        gender = self.safe_regex(r"(男|女)", clean_body)
        email = self.safe_regex(r"E-mail\s+([\w\.-]+@[\w\.-]+)", clean_body)
        phone = self.safe_regex(r"聯絡電話\s+([0-9\-]+)", clean_body)
        location = self._parse_location(clean_body)
        education = self.safe_regex(r"最高學歷\s+(.*)", clean_body).strip()
        
        # 解析履歷連結
        source_link = self._parse_source_link(html_body, name)
        
        # 解析發件人列表
        senders = self._parse_senders(mail_type, html_body, recommender)
        
        return ParsedMail(
            source="104",
            source_id=source_id,
            name=name,
            vacancy=vacancy,
            instruction=instruction,
            recommender=recommender,
            age=age,
            gender=gender,
            email=email,
            phone=phone,
            location=location,
            education=education,
            source_link=source_link,
            body=clean_body,
            html_body=html_body,
            received_time=mail.ReceivedTime.strftime("%Y-%m-%d %H:%M:%S"),
            senders=senders
        )
    
    def _detect_mail_type(self, subject: str, sender: str) -> str:
        """偵測郵件類型"""
        for mail_type, (keyword, expected_sender) in self.MAIL_TYPES.items():
            if sender == expected_sender and keyword in subject:
                return mail_type
        return "unknown"
    
    def _parse_recommender(self, mail_type: str, html_body: str, subject: str) -> str:
        """解析推薦人"""
        if mail_type == "forward":
            return self.safe_regex(r'mailto:([^"]+)', html_body)
        elif mail_type == "match":
            return "104"
        elif mail_type == "apply":
            return "自己"
        return "未知"
    
    def _parse_vacancy(self, mail_type: str, subject: str, instruction: ParsedInstruction) -> str:
        """解析職缺"""
        if mail_type in ["match", "apply"]:
            # 從主旨解析
            match = re.search(r"【(.+?)】", subject)
            return match.group(1).strip() if match else ""
        else:
            # 從指令解析
            return instruction.vacancy
    
    def _clean_body(self, body: str, mail_type: str) -> str:
        """清理郵件內文"""
        # 移除 URL
        body = re.sub(r"<https://.*?>", "", body)
        
        # 根據類型切分內容
        if mail_type == "forward":
            body = body.split("本人同意本履歷僅供符合104人力銀行規範之")[0]
            body = body.split("轉寄此履歷表給您。")[-1]
        elif mail_type == "match":
            body = body.split("本人同意本履歷僅供符合104人力銀行規範之")[0]
            body = body.split("自訂配對：")[-1]
        elif mail_type == "apply":
            body = body.split("本人同意本履歷僅供符合104人力銀行規範之")[0]
            body = body.split("應徵職務：")[-1]
        
        return body
    
    def _parse_name(self, html_body: str, body: str, mail_type: str) -> str:
        """解析姓名"""
        if mail_type == "forward":
            pattern = r'style="color: #3f66bf; text-decoration: none;"><b style="color: #1654b9;font-size:22px;"> (.+?)</b></a>'
        else:
            pattern = r'<span style="font-size:20px">(.+?)</span>'
        
        match = re.search(pattern, html_body)
        if match:
            return match.group(1).strip()
        
        # Fallback: 從 body 取第一個詞
        return body.split()[0] if body.split() else "未知"
    
    def _parse_age(self, body: str) -> Optional[int]:
        """解析年齡"""
        match = re.search(r"(\d+)歲", body)
        return int(match.group(1)) if match else None
    
    def _parse_location(self, body: str) -> str:
        """解析居住地"""
        match = re.search(r"居住地\s+(.*)", body)
        if match:
            return match.group(1).split(" ")[0]
        return ""
    
    def _parse_source_link(self, html_body: str, name: str) -> str:
        """解析履歷連結"""
        # 建立正則模式
        pattern = r'href="([^"]+)"[^>]*>(?:(?!<\/a>).)*?' + re.escape(name)
        
        match = re.search(pattern, html_body, re.DOTALL)
        if match:
            raw_url = match.group(1)
            # 清理 URL
            clean_url = raw_url.replace("&amp;", "&")
            return urllib.parse.unquote(clean_url)
        
        return ""
    
    def _parse_senders(self, mail_type: str, html_body: str, recommender: str) -> list:
        """解析發件人列表"""
        senders = []
        
        if mail_type == "forward":
            email = self.safe_regex(r'mailto:([^"]+)', html_body)
            if email:
                senders.append(email)
        
        return senders