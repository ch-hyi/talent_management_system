import logging
from datetime import datetime
from typing import List, Tuple, Optional
from .local_llm import ScoringService
import time
from .send_service import send_status_update
import re
import win32com.client
from ..utils.outlook_helper  import (
    get_unread_messages,
    save_mail_to_html,
    extract_html_content_between_markers,
    get_senders,
    clean_outlook_mail_body
)
from ..parser.parser_104 import parse_104_resume
from ..utils.status_manager import (
    parse_instruction,
    process_status_update,
    process_rollback,
    create_meeting_invitation,
    process_meeting_cancellation
)
from ..models.talent import Talent ,TalentBatchUpdateRequest ,TalentUpdateItem
from ..models.log import LogEntry  # ✅ 直接 import 你的 LogEntry
from ..api.talent_controller import get_talent_service
from ..api.log_controller import get_log_service
import sys
from pathlib import Path
import traceback
from celery.signals import worker_process_init
from celery import Celery
from ..database.connection import db_manager
from ..config import REDIS_URL

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
backend_service = Celery(
    'mail_scoring_system',
    broker=REDIS_URL,
    backend=REDIS_URL
)
db_manager.connect()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
talent_service = get_talent_service()
log_service = get_log_service()
scoring_service = ScoringService()
# ==================== 常數定義 ====================

FLOW = ["AI REVIEW","感興趣", "電邀", "電訪", "面邀", "面試","OFFER", "報到"]
ACTION = ["更新","刪除", "不合格", "取消","復原","查詢","略過"]

WARNING_TEXT = """
<div style="font-family:Segoe UI, Arial; font-size:14px; line-height:1.6;">
<p><b>麻煩按照以下格式回信，否則程式將無法解析：</b></p>
<p><b>回信格式：</b><br>
<span style="color:#d9534f;"><b>###職缺,狀態,動作,備註###</b></span></p>
<hr>
<p><b>欄位說明：</b></p>
<p><b>1. 職缺</b><br>
・只能填一個，名稱需與公司開缺完全相同<br>
・若人才已建立，可留空（不改變職缺）<br>
・若填寫且與原職缺不同，系統會更新職缺</p>
<p><b>2. 狀態</b><br>
・流程：感興趣 → 電邀 → 電訪 → 面邀 → 面試 → 報到<br>
・可填值：<br>
&nbsp;&nbsp;感興趣 / 電邀 / 電訪接受 / 電訪拒絕 / 面邀接受 / 面邀拒絕<br>
&nbsp;&nbsp;面試未到 / 面試完成 / 報到未到 / 報到完成 / 不合格<br><br>
・留空：自動往下一階段<br>
・輸入 y：代表通過（例如電邀 → 電訪接受）<br>
・輸入 n：代表未通過（例如電邀 → 電訪拒絕）<br>
・輸入 skip：代表跳過下流程(如電邀 -> 跳過電訪 -> 面邀))</p>
<p><b>3. 動作</b><br>
・可用值：刪除、更新、鎖定、解鎖、略過、邀請函、查詢<br>
・留空：預設為「更新」</p>
<p><b>4. 備註</b><br>
・可留空<br>
・可填寫：拒絕原因、不合格原因、注意事項等</p>
<hr>
</div>
"""



# ==================== 主要處理函式 ====================



def process_104_resume(mail) -> Tuple[Optional[LogEntry], List[str], bool]:
    """
    處理 104 履歷郵件
    
    Returns:
        (log_entry, errors, skip)
    """
    errors = []
    
    try:
        # 1️⃣ 解析履歷
        sender = mail.SenderEmailAddress
        subject = mail.Subject
        talent = Talent()
        send = ""
        if not((sender == "jobbank@104.com.tw"  and "透過104轉寄履歷給您" in subject) or ( sender =="jobbank@ms1.104.com.tw" and "104自訂配對人選" in subject) or (sender =="jobbank@104.com.tw" and "104應徵履歷" in subject)):
            mail.Unread = False
            return  [], True  # 非 104 履歷，跳過
        
        # 2️⃣ 補充郵件資訊
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(mail.HTMLBody, "html.parser")
        for div in soup.find_all("div"):
            style = (div.get("style") or "").lower()
            if "display:none" in style:
                div.decompose()
        htmlbody = str(soup)
        body = soup.get_text(separator="\n", strip=True)
        # 3️⃣ 解析指令 (如果有)
        if "透過104轉寄履歷給您" in subject:
            match = re.search(r'mailto:([^"]+)', htmlbody, re.DOTALL)
            send = match.group(1).strip() if match else ""
        else:
            send = "104"

        instruction_str = extract_instruction(body)
        print(instruction_str)
        vacancy, status, action, note = parse_instruction(instruction_str)
        print(vacancy,status,action,note)
        if status not in FLOW:
            status = ""
        if action not in ACTION:
            action = ""
        print(vacancy)
        print(status)
        

        if "104自訂配對人選" in subject or "104應徵履歷" in subject :
            vacancy = subject.split("【")[1].split("】")[0].strip()
        body = clean_outlook_mail_body(mail_body=body).split("本人同意本履歷僅供符合")[0]
        talent = parse_104_resume(
            mail_body=body,
            html_body=mail.HTMLBody,
            subject=mail.Subject,
            sender=mail.SenderEmailAddress
        )
        talent.recommender = send
        print(talent.education_school)
        print(note)
        talent.mail_id = mail.EntryID
        talent.received_time = mail.ReceivedTime.strftime("%Y-%m-%d %H:%M:%S")
        if note !="":
            talent.note = f"<p>使用者：{send} 於 {talent.received_time} 留言：" +note +"</p>"
        print(talent.received_time,mail.ReceivedTime.strftime("%Y-%m-%d %H:%M:%S"))
        # 4️⃣ 檢查是否已存在
        existing_talent = talent_service.get_one_talent(talent.source,talent.source_id).data
        talent.mail_id = mail.EntryID
        if action == "略過":
            logging.info("動作為略過，跳過此信件。")
            return  [], True
        talent.msg_backup_path = save_mail_to_html(mail, talent.name, talent.source_id)
        # 5️⃣ 處理職缺與狀態
        if existing_talent:
            if vacancy:
                if vacancy != existing_talent.vacancy:

                    talent.vacancy = vacancy
                    talent = merge_talent_data(existing_talent, talent)
                    if status !="":

                        talent.current_status = status
                    request =TalentBatchUpdateRequest.create_batch_request(talent,send)
                    talent_service.update_talent_with_log(request)
                else:

                    updates = talent.to_dict()
                    updates.pop("vacancy", None)
                    request = TalentBatchUpdateRequest(
                        edit=[
                            TalentUpdateItem(
                                source=talent.source,
                                source_id=talent.source_id,
                                updates=updates
                            )
                        ],
                        operator=send
                    )

                    talent_service.update_talent_with_log(request)
        else:
            if vacancy:
                talent.vacancy = vacancy
                if status!="":
                    talent.current_status = status
                    print("innn")
                    print(status)
                talent.lock_status = "unlocked"
                response = talent_service.create_talent(talent,body)
                print(response.message)
                if not response.success :
                    print(response.error)
                    errors.append(response.error)
                    return errors, False

            else:
                errors.append("無填入職缺")
                logging.error("無填入職缺")
                return errors,False
        

        
        # 標記已讀
        if len(errors)==0:
            mail.Unread = False
    
        return   errors, False
        
    except Exception as e:
        error_msg = traceback.format_exc()
        error = f"處理 104 履歷時發生錯誤: {e}"
        logging.error(error+"\n\n"+error_msg, exc_info=True)
        errors.append(error)
        return   errors, False


def process_status_update_mail(mail, outlook) -> Tuple[Optional[LogEntry], List[str], bool]:
    """
    處理狀態更新回信
    
    Returns:
        (log_entry, errors, skip)
    """
    errors = []
    
    try:
        # 1️⃣ 解析主旨取得基本資訊
        source,source_id, name, vacancy = parse_subject(mail.Subject)
        
        if not source_id:
            errors.append("無法解析求職者代碼")
            return  errors, False
        
        # 2️⃣ 從資料庫取得人才資料
        talent = talent_service.get_one_talent(source,source_id).data
        talent_org = talent
        if not talent:
            errors.append(f"資料庫找不到求職者代碼: {source_id}")
            return  errors, False
        
        # 3️⃣ 解析指令
        instruction_str = extract_instruction(mail.Body)
        req_vacancy, req_status, action, note = parse_instruction(instruction_str)
        if status not in FLOW:
            status = ""
        if action not in ACTION:
            action = ""
        # 4️⃣ 取得收件人清單
        senders = get_sender_list(talent, outlook)
        
        # 5️⃣ 提取 HTML 內容 (用於會議邀請)
        html_content = extract_html_content_between_markers(mail.HTMLBody)
        
        # 6️⃣ 處理不同動作
        reply_warning = ""
        stage_info = ""
        meeting_id = None
        interview_time = None
        
        if action == "查詢":
            stage_info = f"當前狀態: {talent.current_status}"
            
        elif action == "刪除":
            talent_service.delete_talent(source,source_id)
            reply_warning = "<p>通知：人才已刪除</p>"
            stage_info = "人才已刪除"
            
        elif action == "復原":
            success, msg, prev_version = process_rollback(
                talent=talent,
                mail=mail,
                outlook=outlook,
                senders=senders,
                html_content=html_content
            )
            
            previous_version = prev_version
            
            if success:
                reply_warning = "<p>通知：狀態已復原</p>"
                stage_info = f"復原成功 - {talent.name} : {talent.current_status}"
            else:
                reply_warning = f"<p>通知：復原失敗 {msg}</p>"
                stage_info = f"復原失敗: {msg}"
                errors.append(msg)
        elif action =="取消":
            process_meeting_cancellation(talent,senders,outlook)
        elif action == "" or action == "更新":
            # 處理狀態更新
            result = process_status_update(
                talent=talent,
                req_status=req_status,
                note=note,
                mail=mail,
                outlook=outlook,
                senders=senders,
                html_content=html_content
            )

            talent.current_status = result.new_status
            talent.note = result.updated_note
            talent.vacancy = req_vacancy
            reply_warning = result.warning_message
            stage_info = result.stage_info
            talent.meeting = result.meeting_id
            interview_time = result.interview_time
            errors.extend(result.errors)
            request =TalentBatchUpdateRequest.create_batch_request(talent.to_dict(),senders[0])
            # 更新資料庫    
            talent_service.update_talent_with_log(
                request         
            )
        
        # 7️⃣ 發送狀態更新通知信
        send_status_update(
            to=mail.SenderEmailAddress,
            talent=talent,
            stage_info=stage_info,
            reply_warning=reply_warning,
            outlook=outlook
        )
        
        # 標記已讀
        if len(errors)==0:
            mail.Unread = False
        
        return  errors, False
        
    except Exception as e:
        error_msg = traceback.format_exc()
        error = f"狀態更新錯誤: {e}"
        logging.error(error+"\n\n"+error_msg, exc_info=True)
        errors.append(error)
        return  errors, False


# ==================== 輔助函式 ====================

def extract_instruction(body: str) -> str:
    """提取 ###...### 指令"""
    import re
    match = re.search(r"###(.*?)###", body, re.DOTALL)
    return match.group(1).strip() if match else ""


def parse_subject(subject: str) -> Tuple[str, str, str]:
    """
    解析主旨取得 source_id, name, vacancy
    
    Example:
        "RE: 系統回信-求職者代碼:12345678,求職者名稱:王小明,職缺:軟體工程師,狀態更新信"
        → ("12345678", "王小明", "軟體工程師")
    """
    try:
        parts = subject.split("-")[1].split(",")
        source = "104" ####未來要改掉 標題要加上來源
        source_id = parts[0].split(":")[1]
        name = parts[1].split(":")[1]
        vacancy = parts[2].split(":")[1]
        return source,source_id, name, vacancy
    except:
        return "","", "", ""


def get_sender_list(talent: Talent, outlook) -> List[str]:
    """取得應發送通知的收件人清單"""
    from ..utils.outlook_helper import to_smtp
    
    senders = []
    
    # 1. 從 JD 取得主管清單
    supervisors = get_senders(talent,outlook)
    senders.extend(supervisors)
    
    # 2. 加入推薦人
    if talent.recommender and talent.recommender not in senders:
        senders.append(talent.recommender)
    
    # 3. 轉換為 SMTP 格式
    clean_senders = []
    for s in senders:
        smtp = to_smtp(s, outlook)
        if smtp and smtp not in clean_senders:
            clean_senders.append(smtp)
    
    return clean_senders

def merge_talent_data(existing: Talent, new: Talent) -> Talent:
    """合併現有與新資料 (新資料優先，但不覆蓋空值)"""
    from dataclasses import fields
    
    for field in fields(Talent):
        new_value = getattr(new, field.name)
        
        # 跳過時間戳記
        if field.name in [ "received_time"]:
            continue
        
        # 新值非空才更新
        if new_value is not None and new_value != "":
            old_value = getattr(existing, field.name)
            if str(new_value).strip() != str(old_value).strip():
                setattr(existing, field.name, new_value)
    
    # 更新時間戳記
    existing.update_time = new.update_time
    
    return existing

# ==================== 主程式進入點 ====================

def main():
    """主程式"""
    logging.info("Starting Mail Service")
    outlook = win32com.client.Dispatch("Outlook.Application")
    while True:
        result = get_unread_messages(outlook)
        messages = result["messages"]
        for mail in messages:
            logging.info(f"處理信件: {mail.Subject}")
            
            # 判斷郵件類型
            if "RE: 系統回信-求職者代碼:" in mail.Subject:
                # 狀態更新回信
                errors, skip = process_status_update_mail(mail)
            else:
                # 104 履歷
                errors, skip = process_104_resume(mail)
            
            if skip:
                continue

        logging.info("所有郵件處理完成")
        time.sleep(10)


main()
