"""
Outlook 相關工具函式
處理郵件儲存、地址轉換、收件人管理、郵件發送等
"""

import os
import html
import logging
import re
from typing import List, Tuple, Optional, Dict
from bs4 import BeautifulSoup
import pandas as pd
import re
from ..models.talent import Talent

# ==================== 設定 ====================

MSG_BACKUP_DIR = "C:/Users/rchang4/talent_system/frontend/static/msg_backup"
JD_PATH = "C:/Users/rchang4/talent_system/backend/data/jd_fake.xlsx"

# 確保目錄存在
os.makedirs(MSG_BACKUP_DIR, exist_ok=True)


# ==================== Outlook 連線 ====================

def get_unread_messages(outlook) -> Dict:
    """
    取得未讀郵件
    
    Returns:
        dict: {
            "app": Outlook Application 物件,
            "namespace": MAPI namespace,
            "messages": 未讀郵件集合
        }
    """
    try:
        namespace = outlook.GetNamespace("MAPI")
        inbox = namespace.GetDefaultFolder(6)  # 6 = Inbox
        messages = inbox.Items.Restrict("[Unread]=True")
        messages.Sort("[ReceivedTime]", True)
        
        logging.info(f"取得 {messages.Count} 封未讀郵件")
        
        return {
            "namespace": namespace,
            "messages": messages
        }
    except Exception as e:
        logging.error(f"連線 Outlook 失敗: {e}", exc_info=True)
        raise


# ==================== 地址轉換 ====================

def to_smtp(address: str, outlook) -> Optional[str]:
    """
    將 Exchange 地址轉換為 SMTP 格式
    
    Args:
        address: 原始地址 (可能是 EX 格式或已經是 SMTP)
        outlook: Outlook Application 物件
        
    Returns:
        str: SMTP 格式的 email 地址, 失敗返回 None
        
    Example:
        >>> to_smtp("/o=ExchangeLabs/ou=Exchange...", outlook)
        "user@example.com"
        
        >>> to_smtp("user@example.com", outlook)
        "user@example.com"
    """
    if not address:
        return None

    address = str(address).strip()

    # 已經是 email 格式
    if "@" in address:
        return address.lower()

    # EX address → 轉 SMTP
    try:
        recipient = outlook.Session.CreateRecipient(address)
        recipient.Resolve()

        if recipient.Resolved:
            ae = recipient.AddressEntry

            if ae.Type == "EX":
                ex_user = ae.GetExchangeUser()
                if ex_user:
                    return ex_user.PrimarySmtpAddress.lower()
            else:
                return recipient.Address.lower()
    except Exception as e:
        logging.warning(f"地址轉換失敗: {address}, 錯誤: {e}")

    return None


# ==================== 郵件儲存 ====================

def save_mail_to_html(mail_item, name: str, source_id: str) -> Optional[str]:
    """
    將 Outlook 郵件儲存為 HTML 格式
    
    Args:
        mail_item: win32com MailItem 物件
        name: 求職者姓名
        source_id: 來源 ID
        
    Returns:
        str: 儲存的檔案路徑, 失敗返回 None
        
    Example:
        >>> save_mail_to_html(mail, "王小明", "12345678")
        "C:/Users/.../msg_backup/王小明_12345678_ABC...XYZ.html"
    """
    try:
        # 1️⃣ 抽取郵件中繼資料
        subject = mail_item.Subject if mail_item.Subject else "(無主旨)"
        
        try:
            outlook = mail_item.Application
            sender_email = to_smtp(mail_item.SenderEmailAddress, outlook)
            sender = f"{mail_item.SenderName} ({sender_email})" if sender_email else mail_item.SenderName
        except:
            sender = mail_item.SenderName if mail_item.SenderName else "(未知寄件者)"
        
        try:
            date_str = mail_item.ReceivedTime.strftime("%Y-%m-%d %H:%M:%S")
        except:
            date_str = str(mail_item.ReceivedTime)
            
        # 2️⃣ 獲取 HTML 內文
        html_body = mail_item.HTMLBody
        if not html_body:
            html_body = f"<pre style='font-family: sans-serif;'>{mail_item.Body}</pre>"
            
        # 3️⃣ 注入郵件表頭
        header_html = f"""
        <div style="
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background-color: #f8f9fa;
            padding: 20px;
            margin-bottom: 20px;
            border-bottom: 2px solid #e9ecef;
            border-radius: 6px;
        ">
            <h2 style="margin: 0 0 12px 0; color: #212529; font-size: 20px; font-weight: 600;">Subject: {html.escape(subject)}</h2>
            <div style="font-size: 14px; color: #495057; line-height: 1.6;">
                <strong>From:</strong> <span style="color: #0d6efd;">{html.escape(sender)}</span><br>
                <strong>Date:</strong> {date_str}
            </div>
        </div>
        """
        
        # 4️⃣ 插入表頭到 HTML
        if "<body>" in html_body:
            final_html = html_body.replace("<body>", f"<body>\n{header_html}")
        elif "<body " in html_body:
            final_html = html_body.replace("<body ", f"<body>\n{header_html} ", 1)
        elif "<BODY>" in html_body:
            final_html = html_body.replace("<BODY>", f"<BODY>\n{header_html}")
        else:
            final_html = f"<html><body>{header_html}{html_body}</body></html>"
            
        # 5️⃣ 安全處理 EntryID (防止路徑過長)
        raw_entry_id = mail_item.EntryID if mail_item.EntryID else "no_id"
        if len(raw_entry_id) > 30:
            safe_entry_id = f"{raw_entry_id[:10]}...{raw_entry_id[-10:]}"
        else:
            safe_entry_id = raw_entry_id

        # 清理檔名中的非法字元
        clean_name = "".join([c for c in str(name) if c.isalnum() or c in " _-"])
        clean_source_id = "".join([c for c in str(source_id) if c.isalnum() or c in " _-"])

        # 6️⃣ 組合檔案路徑
        output_html_path = os.path.join(
            MSG_BACKUP_DIR, 
            f"{clean_name}_{clean_source_id}_{safe_entry_id}.html"
        )
        
        # 7️⃣ 寫入檔案
        with open(output_html_path, "w", encoding="utf-8") as f:
            f.write(final_html)
            
        logging.info(f"郵件已儲存: {output_html_path}")
        return output_html_path
        
    except Exception as e:
        logging.error(f"郵件轉存 HTML 失敗: {e}", exc_info=True)
        return None


# ==================== 收件人管理 ====================

def get_senders(talent:Talent, outlook) -> List[str]:
    """
    取得應發送郵件的收件者清單
    
    Args:
        talent: Talent 物件 (包含 vacancy, recommender 等資訊)
        outlook: Outlook Application 物件
        
    Returns:
        list: SMTP 格式的 email 清單
        
    Example:
        >>> get_sender_list(talent, outlook)
        ["hr@company.com", "manager@company.com", "recommender@company.com"]
    """
    sender_list = []
    
    try:
        # 1️⃣ 從 JD 取得主管清單
        jd = pd.read_excel(JD_PATH)
        row = jd[jd["職位"] == talent.vacancy]
        
        if not row.empty:
            supervisors_str = row["主管"].iloc[0]
            if pd.notna(supervisors_str):
                supervisors = [x.strip() for x in str(supervisors_str).split(",")]
                sender_list.extend(supervisors)
        
        # 2️⃣ 加入推薦人
        if talent.recommender and talent.recommender not in sender_list:
            sender_list.append(talent.recommender)
        
        # 3️⃣ 轉換為 SMTP 格式並去重
        clean_senders = []
        for s in sender_list:
            smtp = to_smtp(s, outlook)
            if smtp and smtp not in clean_senders:
                clean_senders.append(smtp)
        
        logging.info(f"收件人清單: {clean_senders}")
        return clean_senders
        
    except Exception as e:
        logging.error(f"取得收件人清單失敗: {e}", exc_info=True)
        return []


# ==================== HTML 內容提取 ====================

def extract_html_content_between_markers(html_body: str) -> str:
    """
    提取 ### 標記之間的 HTML 內容
    
    用於從回信中提取使用者輸入的會議邀請內容
    
    Args:
        html_body: HTML 格式的郵件內容
        
    Returns:
        str: 提取出的 HTML 內容
        
    Example:
        郵件內容:
        ```
        <p>回覆:</p>
        <span>###</span>
        <p>會議時間: 2024/01/15 14:00</p>
        <p>地點: 線上</p>
        <span>###</span>
        ```
        
        返回:
        ```
        <p>會議時間: 2024/01/15 14:00</p>
        <p>地點: 線上</p>
        ```
    """
    try:
        # Decode HTML entities
        raw = html_body
        for _ in range(2):
            raw = html.unescape(raw)
        
        soup = BeautifulSoup(raw, "html.parser")
        html_content = ""
        
        # 找 start marker
        start_node = None
        for span in soup.find_all("span"):
            if span.get_text(strip=True) == "###":
                start_node = span
                break
        
        # 抓後面所有 sibling
        if start_node:
            for sibling in start_node.parent.next_siblings:
                # 遇到下一個 ###
                if isinstance(sibling, str) and "###" in sibling:
                    break
                if hasattr(sibling, "get_text"):
                    if sibling.get_text(strip=True) == "###":
                        break
                html_content += str(sibling)
        
        return html_content
        
    except Exception as e:
        logging.error(f"提取 HTML 內容失敗: {e}", exc_info=True)
        return ""


def extract_instruction(body: str) -> str:
    """
    提取 ###...### 指令
    
    Args:
        body: 郵件純文字內容
        
    Returns:
        str: 提取出的指令內容
        
    Example:
        >>> extract_instruction("其他內容\n###軟體工程師,電邀,,2024/01/15 14:00_線上_面試###\n其他內容")
        "軟體工程師,電邀,,2024/01/15 14:00_線上_面試"
    """
    match = re.search(r"###(.*?)###", body, re.DOTALL)
    return match.group(1).strip() if match else ""


# ==================== 主旨解析 ====================

def parse_subject(subject: str) -> Tuple[str, str, str]:
    """
    解析系統回信主旨
    
    Args:
        subject: 郵件主旨
        
    Returns:
        tuple: (source_id, name, vacancy)
        
    Example:
        >>> parse_subject("RE: 系統回信-求職者代碼:12345678,求職者名稱:王小明,職缺:軟體工程師,狀態更新信")
        ("12345678", "王小明", "軟體工程師")
    """
    try:
        # 格式: "RE: 系統回信-求職者代碼:XXX,求職者名稱:XXX,職缺:XXX,..."
        parts = subject.split("-")[1].split(",")
        source_id = parts[0].split(":")[1].strip()
        name = parts[1].split(":")[1].strip()
        vacancy = parts[2].split(":")[1].strip()
        return source_id, name, vacancy
    except Exception as e:
        logging.error(f"解析主旨失敗: {subject}, 錯誤: {e}")
        return "", "", ""

def clean_outlook_mail_body(mail_body):
    """
    清理html
    """
    soup = BeautifulSoup(mail_body, 'html.parser')
    
    # 移除噪音标签
    for tag in soup(['script', 'style', 'img', 'meta', 'link']):
        tag.decompose()
    
    # 为重要的结构元素添加明确的分隔
    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        tag.string = f"\n\n## {tag.get_text().strip()} ##\n"
    
    # 段落间加空行
    for p in soup.find_all('p'):
        p.append('\n')
    
    # 移除链接但保留文本
    for a in soup.find_all('a'):
        text = a.get_text().strip()
        if text and not text.startswith('http'):
            a.replace_with(text + ' ')
        else:
            a.decompose()
    
    text = soup.get_text()
    
    # 清理
    text = re.sub(r'https?://\S+', '', text)
    text = text.replace('&nbsp;', ' ')
    
    # 规范化空行:连续空行最多 2 个
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    
    return text.strip()



