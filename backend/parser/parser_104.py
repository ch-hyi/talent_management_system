import re
import urllib.parse
from typing import Optional
from dataclasses import asdict
from ..models.talent import Talent  # 假設你的 Talent 定義在 models.py
from ..services.code_translator import search
import pandas as pd

class Resume104Parser:
    """104 履歷解析器 - 直接返回 Talent 物件"""
    
    def __init__(self):
        self.supported_senders = {
            "jobbank@104.com.tw": "轉寄履歷",
            "jobbank@ms1.104.com.tw": "自訂配對"
        }
    
    def parse(self, mail_body: str, html_body: str, subject: str, sender: str) -> Optional[Talent]:
        """
        解析 104 履歷郵件，直接返回 Talent 物件
        
        Args:
            mail_body: 純文字郵件內容
            html_body: HTML 格式郵件內容
            subject: 郵件主旨
            sender: 寄件者信箱
        
        Returns:
            Talent: 解析後的人才物件，失敗返回 None
        """
        
        # 1️⃣ 驗證來源
        if not self._is_valid_104_mail(sender, subject):
            return None
        
        # 2️⃣ 清理文字內容
        clean_body = self._clean_body(mail_body)
        
        # 3️⃣ 判斷履歷類型
        resume_type = self._detect_type(subject, sender)
        
        # 4️⃣ 提取姓名 (需要先取得才能解析 URL)
        name = self._extract_name(html_body, resume_type)
        
        if "104應徵履歷" not in subject:
            clean_body = "".join(clean_body.split(name)[1:])
        location = self._extract_location(clean_body)

        city , district = search (location)
        # 5️⃣ 建立 Talent 物件
        talent = Talent(
            # 來源資訊
            source="104",
            source_id=self._extract_source_id(clean_body),
            source_link=self._extract_url(html_body, name),
            
            # 基本資訊
            name=name,
            age=self._safe_int(self._extract_age(clean_body)),
            gender=self._extract_gender(clean_body),
            
            # 聯絡資訊
            email=self._extract_email(clean_body),
            phone=self._extract_phone(clean_body),
            
            # 地點資訊
            city=city,
            district=district,
            
            # 教育背景 (原始完整字串)
            education_school=self._extract_education(clean_body),
            
            # 推薦人與職缺
            recommender=self._extract_recommender(html_body, resume_type),
            
        )
        
        return talent
    
    # ==================== 私有方法 ====================
    
    def _is_valid_104_mail(self, sender: str, subject: str) -> bool:
        """驗證是否為有效的 104 履歷郵件"""
        valid_subjects = ["透過104轉寄履歷給您", "104自訂配對人選", "104應徵履歷"]
        return any(s in subject for s in valid_subjects)
    
    def _clean_body(self, body: str) -> str:
        """清理郵件文字內容"""
        body = re.sub(r"<https://.*?>", "", body)
        if "本人同意本履歷僅供符合104人力銀行規範之" in body:
            body = body.split("本人同意本履歷僅供符合104人力銀行規範之")[0]
        return body.strip()
    
    def _detect_type(self, subject: str, sender: str) -> str:
        """判斷履歷類型"""
        if "透過104轉寄履歷給您" in subject:
            return "轉寄履歷"
        elif "104自訂配對人選" in subject:
            return "自訂配對"
        elif "104應徵履歷" in subject:
            return "應徵履歷"
        return "未知"
    
    def _extract_source_id(self, body: str) -> str:
        """提取求職者代碼"""
        match = re.search(r"代碼：(\d+)", body)
        return match.group(1) if match else ""
    
    def _extract_name(self, html_body: str, resume_type: str) -> str:
        """提取姓名"""
        try:
            if resume_type == "轉寄履歷":
                pattern = r'style="color: #3f66bf[^"]*"><b[^>]*>([^<]+)</b>'
            else:
                pattern = r'<span style="font-size:20px">([^<]+)</span>'
            
            match = re.search(pattern, html_body)
            return match.group(1).strip() if match else "未知"
        except:
            return "未知"
    
    def _extract_age(self, body: str) -> str:
        """提取年齡"""
        match = re.search(r"(\d+)歲", body)
        return match.group(1) if match else ""
    
    def _extract_gender(self, body: str) -> str:
        """提取性別"""
        match = re.search(r"(男|女)", body)
        return match.group(1) if match else ""
    
    def _extract_email(self, body: str) -> str:
        """提取 Email"""
        match = re.search(r"E-mail\s+([\w\.-]+@[\w\.-]+)", body)
        return match.group(1) if match else ""
    
    def _extract_phone(self, body: str) -> str:
        """提取電話"""
        match = re.search(r"聯絡電話\s+([0-9\-]+)", body)
        return match.group(1) if match else ""
    def match_postcode_vectorized(self,full_address: str) -> dict:
        """
        向量化匹配郵遞區號
        
        Args:
            full_address: "桃園市桃園區春日路123號"
            postcode_df: DataFrame with columns ['postcode', 'zip_code', ...]
        
        Returns:
            匹配的郵遞區號資料
        """
        full_address = full_address.replace(" ", "").replace("　", "")  # 移除空格
        full_address = full_address.replace("台", "臺")  # 統一用「臺」
        # 向量化檢查
        postcode_df = pd.read_excel("C:/Users/rchang4/talent_system/backend/data/1050429_行政區經緯度.ods")
        mask = postcode_df['行政區名'].apply(lambda x: full_address.startswith(x))
        matches = postcode_df[mask]
        
        if matches.empty:
            return None
        
        # 返回最長匹配
        longest_match = matches.loc[matches['行政區名'].str.len().idxmax()]
        return longest_match["3碼郵遞區號"]
    
    def _extract_location(self, body: str) -> str:
        """提取居住地"""
        match = re.search(r"居住地\s+(.*)", body)
        location = match.group(1) if match else ""
        try: 
            postcode = location.split(" ")[0]
            int(postcode)
        except:
            postcode = self.match_postcode_vectorized(location)
        return postcode 
    
    def _extract_education(self, body: str) -> str:
        """提取最高學歷 (完整字串)"""
        match = re.search(r"最高學歷\s+(.*)", body)
        return match.group(1).strip() if match else ""
    
    def _extract_recommender(self, html_body: str, resume_type: str) -> str:
        """提取推薦人"""
        if resume_type == "轉寄履歷":
            match = re.search(r'mailto:([^"]+)', html_body)
            return match.group(1) if match else ""
        elif resume_type == "自訂配對":
            return "104"
        elif resume_type == "應徵履歷":
            return "self"
        return ""
    
    
    def _extract_url(self, html_body: str, name: str) -> str:
        """提取履歷連結"""
        if not name or name == "未知":
            return ""
        
        try:
            pattern = r'href="([^"]+)"[^>]*>(?:(?!<\/a>).)*?' + re.escape(name)
            match = re.search(pattern, html_body, re.DOTALL)
            
            if match:
                raw_url = match.group(1)
                clean_url = raw_url.replace("&amp;", "&")
                return urllib.parse.unquote(clean_url)
        except:
            pass
        
        return ""
    
    def _safe_int(self, value: str) -> Optional[int]:
        """安全轉換為整數"""
        try:
            return int(value) if value else None
        except:
            return None


# ==================== 便捷函數 ====================

def parse_104_resume(mail_body: str, html_body: str, subject: str, sender: str) -> Optional[Talent]:
    """
    快速解析 104 履歷 (函數式調用)
    
    Example:
        talent = parse_104_resume(
            mail_body=mail.Body,
            html_body=mail.HTMLBody,
            subject=mail.Subject,
            sender=mail.SenderEmailAddress
        )
        
        if talent:
            print(f"姓名: {talent.name}")
            print(f"代碼: {talent.source_id}")
    """
    parser = Resume104Parser()
    return parser.parse(mail_body, html_body, subject, sender)