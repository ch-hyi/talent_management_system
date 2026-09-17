
import os
import logging
import win32com.client
from typing import List, Tuple, Optional
from celery.signals import worker_process_init
from ..repositories.log_repository import LogRepository 
from celery import Celery
from ..models.log import LogEntry
from ..models.talent import Talent
from ..utils.outlook_helper import get_senders
from ..config import REDIS_URL
import traceback
# ==================== 郵件發送 ====================
sending_service = None
log_repo = None
outlook = None
backend_service = Celery('mail_scoring_system',
        broker_url=REDIS_URL,
        result_backend=REDIS_URL,  
             )

class SendingService():
    def __init__(self,outlook):
        """
        初始化評分服務
        
        Args:
            jd_file_path: 職缺描述檔案路徑
            discipline_file_path: 學門分類檔案路徑
            sub_discipline_file_path: 學類分類檔案路徑
            model_name: Ollama 模型名稱
            num_ctx: 上下文 token 數量
            temperature: 模型溫度參數
        """
        self.outlook = outlook

    def send_notification_mail(
        self,
        to: str,
        talent:Talent,
        result: str,
        color: str,
        error_html: str,
        warning_text: str = ""
    ):
        """
        發送 AI 評分結果通知信
        
        Args:
            to: 收件人 email
            talent: Talent 物件
            result: 評分結果文字 (如 "通過 AI 鑑定")
            color: 結果顏色 (CSS color)
            error_html: 錯誤訊息 HTML
            outlook: Outlook Application 物件
            warning_text: 警告文字 (可選)
        """
        try:
            send_mail = self.outlook.CreateItem(0)  # 0 = olMailItem
            send_mail.To = to
            send_mail.Attachments.Add(talent.msg_backup_path)
            send_mail.Subject = (
                f"系統回信-求職者代碼:{talent.source_id},"
                f"求職者名稱:{talent.name},"
                f"職缺:{talent.vacancy},"
                f"AI判斷結果信"
            )
            
            # 組合 HTML 內容
            send_mail.HTMLBody = f"""
            <div style="font-family:Segoe UI, Arial; font-size:14px; line-height:1.6;">
                <p>
                    <b>求職者：</b>{talent.name}<br>
                    <b>職缺：</b>{talent.vacancy}<br>
                    <b>地區：</b>{talent.city or ''} {talent.district or ''}<br>
                    <b>簡述：</b>{talent.description or ''}<br>
                </p>
                
                <div style="font-family:Segoe UI, Arial; font-size:22px;">
                    <b>{error_html}</b>
                </div>
                
                <div style="font-family:Segoe UI, Arial; font-size:14px; line-height:1.6; background:#f5f5f5; display:block; padding:10px;">
                    <p>&nbsp;</p>
                    {talent.note or ''}
                    <p>&nbsp;</p>
                </div>
                
                <p>
                    <b>結果：</b>
                    <span style="color:{color};"><b>{result} - 總分 {round(talent.score or 0, 2)}分</b></span><br>
                    距離分數：{round(talent.score_distance or 0, 2)} | 
                    經歷分數：{round(talent.score_experience or 0, 2)} | 
                    年齡分數：{round(talent.score_age or 0, 2)} | 
                    學歷分數：{round(talent.score_education or 0, 2)} 
                    
                </p>
                
                {warning_text}
            </div>
            """
            
            send_mail.Send()
            logging.info(f"已發送 AI 判斷結果信給 {to}")
            
        except Exception as e:
            logging.error(f"發送通知信失敗: {e}", exc_info=True)


    def send_status_update_mail(
        self,
        to: str,
        talent:Talent,
        stage_info: str,
        reply_warning: str,
        warning_text: str = ""
    ):
        """
        發送狀態更新通知信
        
        Args:
            to: 收件人 email
            talent: Talent 物件
            stage_info: 階段資訊文字
            reply_warning: 回覆警告訊息
            outlook: Outlook Application 物件
            warning_text: 警告文字 (可選)
        """
        try:
            send_mail = self.outlook.CreateItem(0)
            send_mail.To = to
            send_mail.Attachments.Add(talent.msg_backup_path)
            send_mail.Subject = (
                f"系統回信-求職者代碼:{talent.source_id},"
                f"求職者名稱:{talent.name},"
                f"職缺:{talent.vacancy},"
                f"狀態更新信"
            )
            send_mail.BodyFormat = 2  # HTML 格式
            
            send_mail.HTMLBody = f"""
            <div style="font-family:Segoe UI, Arial; font-size:14px;">
                <p>
                    <b>求職者：</b>{talent.name}<br>
                    <b>職缺：</b>{talent.vacancy}<br>
                    <b>當前狀態：</b>{talent.current_status}
                </p>
                
                <p><b>階段：</b>{stage_info}</p>
                
                <div style="font-family:Segoe UI, Arial; font-size:14px; line-height:1.6; background:#f5f5f5; display:block; padding:10px;">
                    <p>&nbsp;</p>
                    {talent.note or ''}
                    <p>&nbsp;</p>
                </div>
                
                <div style="font-family:Segoe UI, Arial; font-size:14px; line-height:1.6;">
                    {reply_warning}
                </div>
                
                {warning_text}
            </div>
            """
            
            send_mail.Send()
            logging.info(f"已發送狀態更新信給 {to}")
            
        except Exception as e:
            logging.error(f"發送狀態更新信失敗: {e}", exc_info=True)

    def send(self,to ,attachments,mail_subject,mail_content):
        try:
            send_mail = self.outlook.CreateItem(0)
            send_mail.To = to
            for attachment in attachments:
                send_mail.Attachments.Add(str(attachment))
            send_mail.Subject = (mail_subject)
            send_mail.BodyFormat = 2  
            
            send_mail.HTMLBody = mail_content
            send_mail.Save()          # 關鍵：先存成草稿，才會產生 EntryID
            mail_id = send_mail.EntryID
            send_mail.Send()
            logging.info("Send Mail Successfully")
            return "SUCCESS",mail_id
        except:
            logging.error("Send Mail Failed")
            logging.error(traceback.format_exc())
            return "FAILED",None
    # ==================== 會議邀請 ====================

    def create_meeting_from_mail(
        self,
        mail_item,
        talent:Talent,
        meeting_time: str,
        location: str,
        title: str,
        duration: int,
        recipients: List[str],
        html_content: str
    ) -> Tuple[bool, Optional[str]]:
        """
        從郵件建立會議邀請
        
        Args:
            mail_item: 原始郵件物件
            talent: Talent 物件
            meeting_time: 會議時間 (格式: "YYYY-MM-DD HH:MM")
            location: 會議地點
            title: 會議標題
            duration: 會議時長 (分鐘)
            recipients: 收件人清單
            html_content: 會議內容 HTML
            outlook: Outlook Application 物件
            
        Returns:
            tuple: (成功, meeting_id)
            
        Example:
            >>> create_meeting_from_mail(
            ...     mail, talent, "2024-01-15 14:00", "線上", "面試",
            ...     120, ["hr@company.com"], "<p>面試內容</p>", outlook
            ... )
            (True, "AAMkAGI3...")
        """
        try:
            # 1️⃣ 建立會議物件
            meeting_obj = self.outlook.CreateItem(1)  # 1 = olAppointmentItem
            
            # 2️⃣ 設定基本資訊
            meeting_obj.Subject = f"{title}"
            meeting_obj.Start = meeting_time
            meeting_obj.Duration = duration
            meeting_obj.Location = location
            meeting_obj.MeetingStatus = 1  # olMeeting
            
            # 3️⃣ 加入收件人
            for address in recipients:
                meeting_obj.Recipients.Add(address)
            meeting_obj.Recipients.ResolveAll()
            
            # 4️⃣ 處理附件 (從原始郵件複製)
            temp_files = []
            if mail_item!=None:
                for att in mail_item.Attachments:
                    # 跳過內嵌圖片
                    try:
                        if att.PropertyAccessor.GetProperty("http://schemas.microsoft.com/mapi/proptag/0x3712001F"):
                            continue
                    except:
                        pass
                    
                    # 儲存附件到暫存目錄
                    import uuid
                    temp_dir = "C:/Users/rchang4/talent_system/temp"
                    os.makedirs(temp_dir, exist_ok=True)
                    
                    file_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{att.FileName}")
                    att.SaveAsFile(file_path)
                    meeting_obj.Attachments.Add(file_path)
                    temp_files.append(file_path)
            
            # 5️⃣ 複製 HTML 內容到會議中
            temp_mail = self.outlook.CreateItem(0)
            temp_mail.HTMLBody = html_content
            temp_mail.Display()
            meeting_obj.Display()
            
            try:
                temp_mail.GetInspector.WordEditor.Range().Copy()
                meeting_obj.GetInspector.WordEditor.Range().Paste()
            except Exception as e:
                logging.error(f"複製 HTML 格式失敗: {e}")
            finally:
                temp_mail.Delete()
            
            # 6️⃣ 附加原始郵件備份
            meeting_obj.Attachments.Add(talent.msg_backup_path)
            
            # 7️⃣ 儲存並發送
            meeting_obj.Save()
            meeting_id = meeting_obj.EntryID
            meeting_obj.Send()
            
            # 8️⃣ 清理暫存檔案
            for file_path in temp_files:
                try:
                    os.remove(file_path)
                except:
                    pass
            
            logging.info(f"會議邀請已發送，ID: {meeting_id}")
            return True, meeting_id
            
        except Exception as e:
            logging.error(f"建立會議邀請失敗: {e}", exc_info=True)
            return False, None

    def update_meeting_from_mail(self,meeting)->bool:
        pass

    def cancel_meeting(self,meeting_id: str) -> bool:
        """
        取消會議
        
        Args:
            meeting_id: 會議的 EntryID
            outlook: Outlook Application 物件
            
        Returns:
            bool: 成功返回 True
        """
        try:
            namespace = self.outlook.GetNamespace("MAPI")
            meeting_obj = namespace.GetItemFromID(meeting_id)
            
            try:
                meeting_obj.CancelMeeting()
                meeting_obj.Send()
            except:
                meeting_obj.Delete()
            
            logging.info(f"已取消會議: {meeting_id}")
            return True
            
        except Exception as e:
            logging.error(f"取消會議失敗: {e}", exc_info=True)
            return False

@worker_process_init.connect
def init_worker(**kwargs):
    """Worker 啟動時初始化"""
    global sending_service
    global outlook
    global log_repo
    from ..database.connection import db_manager
    outlook = win32com.client.Dispatch("Outlook.Application")
    db_manager.connect()
    log_repo = LogRepository()
    logging.basicConfig(level=logging.INFO)
    sending_service = SendingService(outlook)
    logging.info("✅ Sending Worker 準備就緒")


@backend_service.task(name='tasks.send_status_update', max_retries=3)
def send_status_update(to, talent:Talent, stage_info, reply_warning, warning_text=""):
    status = "SUCCESS"
    try:
        
        logging.info(f"📤 發送狀態更新郵件給 {to}")
        
        # ✅ 調用你的類方法
        sending_service.send_status_update_mail(
            to=to,
            talent=talent,
            stage_info=stage_info,
            reply_warning=reply_warning,
            warning_text=warning_text
        )
        
        logging.info("✅ 狀態更新郵件已發送")
        
        return {"to": to, "status": "sent"}
    
    except Exception as e:
        status ="FAILED"
        logging.error(f"❌ 發送狀態更新失敗: {e}")

    log_entry = LogEntry.create_new(talent.source,talent.source_id,talent.name,1,"SendingService","",status,"UPDATE",None,talent.vacancy,"","",f"Mail to {to} {status}","")
    log_repo.create_log(log_entry)

@backend_service.task(name='tasks.send_mail', max_retries=3)
def send_mail( talent,to,attachments,mail_subject,mail_content):
    print("sendmail")
    status ,id = sending_service.send(to,attachments,mail_subject,mail_content)
    log_entry = LogEntry.create_new(talent["source"],talent["source_id"],talent["name"],1,"SendingService","",status,"UPDATE",None,talent["vacancy"],"","",f"Send mail to {talent["name"]} {status} {id if id else ""}","")
    log_repo.create_log(log_entry)

@backend_service.task(name='tasks.create_meeting', max_retries=3)
def create_meeting( mail_item, talent, meeting_time, location, 
                   title, duration, recipients, html_content):
    status = "SUCCESS"
    meeting_id = ""
    try:
        
        logging.info(f"📅 建立會議邀請: {title}")
        
        # 注意: mail_item 無法序列化,需要特殊處理
        # 這裡簡化處理,實際使用時需要傳遞 mail_id 然後重新獲取
        
        # ✅ 調用你的類方法
        if not isinstance(talent, Talent):  
            talent = Talent(**talent)
        success, meeting_id = sending_service.create_meeting_from_mail(
            mail_item=mail_item,  # 需要特殊處理
            talent=talent,
            meeting_time=meeting_time,
            location=location,
            title=title,
            duration=duration,
            recipients=recipients,
            html_content=html_content
        )
        
        if success:
            logging.info(f"✅ 會議邀請已建立: {meeting_id}")
            return {"meeting_id": meeting_id, "status": "created"}
        else:
            status ="FAILED"
    
    except Exception as e:
        status ="FAILED"
        logging.error(f"❌ 建立會議失敗: {e}")

    log_entry = LogEntry.create_new(talent.source,talent.source_id,talent.name,1,"SendingService","",status,"UPDATE",None,talent.vacancy,"","",f"Create meeting with {recipients} {status} {meeting_id if meeting_id else ""}","","")
    log_repo.create_log(log_entry)

@backend_service.task(name='tasks.update_meeting', max_retries=3)
def update_meeting( mail_item, talent, meeting_time, location, 
                   title, duration, recipients, html_content):
    status = "SUCCESS"
    meeting_id = ""
    try:
        
        logging.info(f"📅 建立會議邀請: {title}")
        
        # 注意: mail_item 無法序列化,需要特殊處理
        # 這裡簡化處理,實際使用時需要傳遞 mail_id 然後重新獲取
        
        # ✅ 調用你的類方法
        if not isinstance(talent, Talent):  
            talent = Talent(**talent)
        success, meeting_id = sending_service.update_meeting_from_mail(
            mail_item=mail_item,  # 需要特殊處理
            talent=talent,
            meeting_time=meeting_time,
            location=location,
            title=title,
            duration=duration,
            recipients=recipients,
            html_content=html_content
        )
        
        if success:
            logging.info(f"✅ 會議邀請已建立: {meeting_id}")
            return {"meeting_id": meeting_id, "status": "created"}
        else:
            status ="FAILED"
    
    except Exception as e:
        status ="FAILED"
        logging.error(f"❌ 建立會議失敗: {e}")

    log_entry = LogEntry.create_new(talent.source,talent.source_id,talent.name,1,"SendingService","",status,"UPDATE",None,talent.vacancy,f"Create meeting with {recipients} {status} {meeting_id if meeting_id else ""}")
    log_repo.create_log(log_entry)



@backend_service.task(name='tasks.cancel_meeting', max_retries=3)
def cancel_meeting( talent , meeting_id):
    status = "SUCCESS"
    try:
        logging.info(f"🗑️ 取消會議: {meeting_id}")
        
        # ✅ 調用你的類方法
        if not isinstance(talent, Talent):  
            talent = Talent(**talent)
        success = sending_service.cancel_meeting(meeting_id)
        
        if success:
            logging.info("✅ 會議已取消")
            return {"meeting_id": meeting_id, "status": "cancelled"}
        else:
            status ="FAILED"
    
    except Exception as e:
        status ="FAILED"
        logging.error(f"❌ 取消會議失敗: {e}")

    log_entry = LogEntry.create_new(talent.source,talent.source_id,talent.name,1,"SendingService","",status,"UPDATE",None,talent.vacancy,"","",f"Cancel {meeting_id} {status}","","")
    log_repo.create_log(log_entry)

    
@backend_service.task(name='tasks.send_ai_result_notification')
def send_ai_result_notification(talent: Talent, errors: List[str]):
    """發送 AI 評分結果通知信"""
    # 判斷是否通過
    talent_obj = Talent.from_dict(talent)
    senders = get_senders(talent_obj,outlook)
    if talent_obj.score and talent_obj.score >= 60:
        result = "通過 AI 鑑定"
        color = "#28a745"
    else:
        result = "未通過 AI 鑑定"
        color = "#7e0c08"
    
    error_html = "<br>".join(errors) if errors else ""
    
    for address in senders:
        sending_service.send_notification_mail(
            to=address,
            talent=talent_obj,
            result=result,
            color=color,
            error_html=error_html,
        )