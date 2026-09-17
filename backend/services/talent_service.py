"""
人才業務邏輯層
"""
import json
import pandas as pd
from typing import Dict, Any, Optional
from ..repositories.talent_repository import TalentRepository
from ..repositories.log_repository import LogRepository
from ..repositories.user_repository import UserRepository
from pathlib import Path
from ..models.response import APIResponse
from ..models.talent import  TalentFilter ,TalentUpdateRequest,Talent,TalentBatchUpdateRequest ,TalentOCRRequest
from ..models.log import LogEntry
import traceback
from .ocr_service import run_ocr
from .local_llm import run_score 
from .send_service import create_meeting,cancel_meeting,update_meeting,send_mail
from .code_translator import district_to_code
from datetime import datetime
from .user_service import UserService


class TalentService:
    """人才管理業務邏輯"""
    
    def __init__(self, talent_repo: TalentRepository, log_repo: LogRepository , user_repo:UserRepository):
        self.talent_repo = talent_repo
        self.log_repo = log_repo
        self.user_repo = user_repo
    
    def query_talents(
        self,
        username,
        filters: Optional[Dict] = None,
        limit: int = 30,
        offset: int = 0
    ) -> APIResponse:
        """查詢人才資料"""
        try:
            # 轉換篩選條件
            user_service = UserService(self.user_repo,self.log_repo)
            user = user_service.get_user_by_account(username).data

            allowed = set(
                user["vacancy_incharge"]
            )

            is_admin =True if user["user_role"] =="admin" else False
            if not is_admin:
                if "vacancy"not in filters:
                    filters["vacancy"] = allowed
                else:
                    requested = set(filters["vacancy"])
                    final_vacancies = list(requested & allowed)
                    filters["vacancy"] = final_vacancies
                

            talent_filter = TalentFilter(**filters) if filters else None
            
            
            # 執行查詢
            data = self.talent_repo.query_talents(talent_filter, limit, offset)
            
            return APIResponse(
                success=True,
                data=data,
                message=f"成功查詢 {len(data)} 筆資料"
            )
        except Exception as e:
            print(traceback.format_exc())
            return APIResponse(
                success=False,
                error=str(e),
                message="查詢失敗"
            )
        
    def get_len(self,username,filters)->APIResponse:

            # 轉換篩選條件
        user_service = UserService(self.user_repo,self.log_repo)
        user = user_service.get_user_by_account(username).data
        allowed = set(
            user["vacancy_incharge"]
        )

        is_admin =True if user["user_role"] =="admin" else False
        if not is_admin:
            if "vacancy"not in filters:
                filters["vacancy"] = allowed
            else:
                requested = set(filters["vacancy"])
                final_vacancies = list(requested & allowed)
                filters["vacancy"] = final_vacancies
            

        talent_filter = TalentFilter(**filters) if filters else None
        len = self.talent_repo.get_len(talent_filter)
        if len is not None:
            return APIResponse(success=True,data=len,message="查詢成功")
            
        else:
            return APIResponse(success=False,error="len為None",message="查詢失敗")


    def share(self,source,source_id,username)->APIResponse:
        import socket
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        result = self.talent_repo.share(source,source_id,username)
        site = f"http://{ip}:8501/share?token={result}"
        if result:
            return APIResponse(success=True,data=site,message="Share Complete")
        else:
            return APIResponse(success=False,error="Share Failed",message="Share Failed")

    def msg(self,source,source_id,user_account)->APIResponse:
        bool = self.user_repo.check_user_exists(user_account)
        if bool :
            path = self.get_one_talent(source,source_id).data.msg_backup_path
            html = self.talent_repo.get_textfile(path)
            if html :
                return APIResponse(success=True,data=html,message="Share Complete")
            else:
                return APIResponse(success=False,error="Resume backup not found",message="Read resume backup Failed")
        else:
            return APIResponse(success=False,error="User not found",message="Read resume backup Failed")

    def get_talent_by_share_id(self,share_id)->APIResponse:
        talent = self.talent_repo.get_talent_by_share_id(share_id)
        if not talent:
            print("expired")
        return APIResponse(success=True,data=talent,message="Share Complete")
    
    def get_taiwan_location(self)->APIResponse:
        location = pd.read_excel("C:/Users/rchang4/talent_system/backend/data/1050429_行政區經緯度.ods")
        location["merged"] = location['縣市']+"|"+location["區"]
        location = location[["中心點經度","中心點緯度","merged"]]
        location = location.rename(columns={"中心點緯度": "lat","中心點經度":"lon"})
        result = {row["merged"]: {"lat": row["lat"],"lon": row["lon"]}for _, row in location.iterrows()}

        return APIResponse(success=True,data=result,message="取得台灣縣市經緯度成功")



        

    def get_one_talent(self, source: str, source_id: str) -> APIResponse:
        """取得單一人才資料"""
        try:
            data = self.talent_repo.get_one_talent(source, source_id)
            
            if not data:
                return APIResponse(
                    success=False,
                    message="找不到該人才資料"
                )
            
            return APIResponse(
                success=True,
                data=data
            )
        except Exception as e:
            print(traceback.format_exc())
            return APIResponse(
                success=False,
                error=str(e),
                message="查詢失敗"
            )
    
    def create_talent(self,talent:Talent,resume_text) ->APIResponse:
        try:
            talent.update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            log_entry = LogEntry.create_new(
                    source=talent.source,
                    source_id=talent.source_id,
                    name=talent.name,
                    version=1,
                    operator=talent.recommender,
                    snapshot_json="",
                    status=talent.current_status,
                    action="CREATE",
                    previous_version=None,
                    vacancy=talent.vacancy,
                    note=talent.note,
                    meeting=talent.meeting,
                    changed_info="",
                    raw_text=f"{talent.recommender} edited {talent.name} 's info"
                )
            
            print("update ",talent.update_time )
            self.talent_repo.create_talent(
                talent
            )
            self.log_repo.create_log(log_entry)
            lock_result = self.lock_talent(talent.source , talent.source_id)
            print(lock_result.success)
            task = run_score.apply_async(
                args=[talent.to_dict(), resume_text, "ScoringService", []],
                queue='scoring_queue'
            )
            print("task background running:",task.id)
            return APIResponse(
                success=True,
                data={"source_id": talent.source_id},
                message=f"成功創建ID { talent.source_id} 的資料"
            )
        except Exception as e:
            print(e,traceback.format_exc())
            return APIResponse(
                success=False,
                error=str(e),
                message="創建失敗"
            )
        
    def delete_talent(self,source:str,source_id:str,operator:str) -> APIResponse:
        try:
            talent = self.get_one_talent(source_id=source_id,source=source).data
            previous_ver = self.log_repo.get_latest_version(source_id=source_id,source=source)
            version = self.log_repo.get_max_version(source_id=source_id,source=source)
            success = self.talent_repo.delete_talent(source, source_id)
            log_entry = LogEntry.create_new(
                    source=talent.source,
                    source_id=talent.source_id,
                    name=talent.name,
                    version=version+1,
                    snapshot_json = json.dumps(talent.to_dict(), ensure_ascii=False),
                    operator=operator,
                    status=talent.current_status,
                    action="DELETE",
                    previous_version=previous_ver,
                    vacancy=talent.vacancy,
                    note=talent.note,
                    meeting=talent.meeting,
                    changed_info="",
                    raw_text=f"{operator} deleted {talent.name}. "
                )
            self.log_repo.create_log(log_entry)
            return APIResponse(
                success=True,
                data={"status": success},
                message=f"刪除成功 {source}-{source_id}"
            )
        except Exception as e:
            return APIResponse(success=False,error=str(e))

    def ocr(self, request: TalentOCRRequest)->APIResponse:
        task = run_ocr.apply_async(args=[ request.file_path,request.username],queue='ocr_queue')
        print(task.id)
        if task:
            return APIResponse(success=True ,data=task.id,message="OCR task has been successfully added to queue.")
        else:
            return APIResponse(success=False,error="OCR Failed")

    def get_ocr_result(self,request:TalentOCRRequest)->APIResponse:
        result = self.talent_repo.get_ocr_result(request.file_path)
        if result:
            return APIResponse(success=True,data=result,message="OCR completed")
        else:
            return APIResponse(success=False,error="OCR Result not found")

    def update_talent(self, request: TalentUpdateRequest) -> APIResponse:
        """更新人才資料"""
        try:
            # 驗證請求
            is_valid, error_msg = request.validate()
            if not is_valid:
                print("invalid")
                return APIResponse(
                    success=False,
                    message=error_msg
                )
            
            # 執行更新
            affected_rows = self.talent_repo.update_talent(
                request.source,
                request.source_id,
                request.updates
            )
            
            return APIResponse(
                success=True,
                data={"affected_rows": affected_rows},
                message=f"成功更新 {affected_rows} 筆資料"
            )
        except Exception as e:
            print(traceback.format_exc())
            return APIResponse(
                success=False,
                error=str(e),
                message="更新失敗"
            )
    
    def lock_talent(self, source: str, source_id: str) -> APIResponse:
        """鎖定人才資料"""
        try:
            affected_rows = self.talent_repo.update_lock_status(source, source_id, "locked")
            
            return APIResponse(
                success=True,
                data={"affected_rows": affected_rows},
                message=f"已鎖定 {source}-{source_id}"
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e)
            )
    
    def unlock_talent(self, source: str, source_id: str) -> APIResponse:
        """解鎖人才資料"""
        try:
            affected_rows = self.talent_repo.update_lock_status(source, source_id, "unlocked")
            
            return APIResponse(
                success=True,
                data={"affected_rows": affected_rows},
                message=f"已解鎖 {source}-{source_id}"
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e)
            )
    
    def check_if_locked(self, source: str, source_id: str) -> APIResponse:
        """檢查是否鎖定"""
        try:
            talent = self.talent_repo.get_one_talent(source, source_id)
            if not talent:
                return APIResponse(
                    success=False,
                    message="找不到該人才資料"
                )
            
            is_locked = talent.lock_status == "locked"
            
            return APIResponse(
                success=True,
                data={"is_locked": is_locked}
            )
        except Exception as e:
            print(traceback.format_exc())
            return APIResponse(
                success=False,
                error=str(e)
            )
    
    def get_distinct_values(self, column_name: str) -> APIResponse:
        """取得欄位的不重複值列表"""
        try:
            values = self.talent_repo.get_distinct_values(column_name)
            
            return APIResponse(
                success=True,
                data=values,
                message=f"成功取得 {len(values)} 個不重複值"
            )
        except ValueError as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="查詢失敗"
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="查詢失敗"
            )
    
    def get_options( self) -> APIResponse:
        try:
           values = self.talent_repo.get_options()
           return APIResponse(
                success=True,
                data=values,
                message=f"成功取得 {len(values)}  個選項"
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="查詢失敗"
            )

    def update_talent_with_log(
        self,
        request: TalentBatchUpdateRequest,
    ) -> APIResponse:
        """更新人才資料並記錄日誌"""

        scoring = []
        log_results = []

        try:
            for item in request.edit:

                trigger_scoring = False

                source = item.source
                source_id = item.source_id
                update_columns = item.updates.copy()

                update_columns["update_time"] = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

                # ==========================================
                # 檢查是否鎖定
                # ==========================================
                lock_check = self.check_if_locked(
                    source,
                    source_id
                )

                if not lock_check.success:
                    return APIResponse(
                        success=False,
                        message="資料已鎖定,無法編輯"
                    )

                if lock_check.data["is_locked"]:
                    print("innnn")
                    return APIResponse(
                        success=False,
                        error="資料已鎖定,無法編輯"
                    )

                # ==========================================
                # 從DB取得最新資料
                # ==========================================
                talent_result = self.get_one_talent(
                    source,
                    source_id
                )
                if not talent_result.success:
                    return talent_result

                if not talent_result.data:
                    return APIResponse(
                        success=False,
                        message=f"找不到候選人 {source}-{source_id}"
                    )

                raw = talent_result.data.to_dict()

                name = raw["name"]
                candidate_name = raw["name"]
                target_vacancy = raw["vacancy"]
                current_meeting = raw.get("meeting")

                current_status = (
                    update_columns.get(
                        "current_status",
                        raw["current_status"]
                    )
                )

                # ==========================================
                # 是否需要重評分
                # ==========================================
                if "vacancy" in update_columns:
                    trigger_scoring = True
                    print("Rescore: True")

                def parse_id_state(item_id: str):
                    """
                    解析 id 狀態，回傳 (state, resolved_id)

                    state:
                        "new"              → id 剛好等於 "ADD"，代表新增、尚未建立會議
                        "delete_new"       → id 是 "DELETE-ADD"，代表新增後又立刻刪除，從未真正建立過會議
                        "delete_existing"  → id 是 "DELETE-<真實meeting_id>"，需要呼叫 cancel_meeting
                        "existing"         → 其他情況，視為既有的真實 meeting_id，維持原樣
                    resolved_id: 對於 delete_existing，回傳解包後的真實 meeting_id；其他狀態為 None
                    """
                    ADD_MARKER = "ADD"
                    DELETE_PREFIX = "DELETE-"

                    if item_id == ADD_MARKER:
                        return "new", None

                    if item_id.startswith(DELETE_PREFIX):
                        inner_id = item_id[len(DELETE_PREFIX):]
                        if inner_id == ADD_MARKER:
                            return "delete_new", None
                        return "delete_existing", inner_id

                    return "existing", item_id


                if "review_status" in update_columns:
                    review_status = []

                    if update_columns["review_status"]:
                        review_status = json.loads(update_columns["review_status"])

                    added_result = []
                    removed_meeting_ids = []
                    kept_review_status = []  # 最終要寫回資料庫的清單（刪除標記已被濾除）

                    for review_item in review_status:
                        state, resolved_id = parse_id_state(review_item.get("id", ""))

                        if state == "delete_new":
                            # 新增後立刻刪除，後端從未真正處理過這筆，直接丟棄，不寫回資料庫
                            continue

                        if state == "delete_existing":
                            # 曾經是真實 meeting_id，需要真的呼叫 cancel_meeting 取消
                            removed_meeting_ids.append(resolved_id)
                            # 這筆也不寫回資料庫（已被刪除）
                            continue

                        if state == "new":
                            added_result.append(review_item)

                        kept_review_status.append(review_item)  # existing 或 new 都保留寫回資料庫

                    # --- 處理新增 ---
                    for send_item in added_result:
                        print("innnnn")
                        if datetime.strptime(send_item["date"], "%Y-%m-%d %H:%M:%S") > datetime.now():
                            task = create_meeting.apply_async(
                                args=[
                                    None,
                                    raw,
                                    send_item["date"],
                                    send_item["location"],
                                    send_item["name"],
                                    60,
                                    [i["email"] for i in send_item["reviewers"]],
                                    send_item["note"]
                                ],
                                queue="mail_queue"
                            )
                            result = task.get()
                            if result:
                                send_item["id"] = result["meeting_id"]  # 因為是同一物件參照，會同步反映到 kept_review_status 裡

                            absolute_attachments = [
                                str(Path(__file__).resolve().parents[2] / "frontend" / "static" / "settings" / "external_attachments" / i)
                                for i in send_item["ex_attachments"]
                            ]

                            task = send_mail.apply_async(
                                args=[
                                    raw,
                                    raw["email"],
                                    absolute_attachments,
                                    "【Bureau Veritas CPS】面試邀請函 - Mr./Ms. " + raw["name"],
                                    send_item["candidate_mail"]
                                ],
                                queue="mail_queue"
                            )

                    # --- 處理移除 ---
                    for meeting_id in removed_meeting_ids:
                        task = cancel_meeting.apply_async(
                            args=[raw, meeting_id],
                            queue="mail_queue"
                        )

                    # --- 寫回資料庫，刪除標記已被濾除，新增已換成真實 meeting_id ---
                    update_columns["review_status"] = json.dumps(kept_review_status, ensure_ascii=False)


                # ==========================================
                # 版本資訊
                # ==========================================
                previous_version = self.log_repo.get_latest_version(
                    source,
                    source_id
                )

                new_version = (
                    self.log_repo.get_max_version(
                        source,
                        source_id
                    )
                    + 1
                )

                # ==========================================
                # 建立 Log
                # ==========================================
                detailed_note = (
                    f"{request.operator}對以下欄位進行修改:"
                    f"{list(update_columns.keys())}"
                )

                log_entry = LogEntry.create_new(
                    source=source,
                    source_id=source_id,
                    name=name,
                    version=new_version,
                    operator=request.operator,
                    snapshot_json=json.dumps(
                        raw,
                        ensure_ascii=False
                    ),
                    status="SUCCESS" if not item.error_message else "FAILED",
                    action="UPDATE",
                    previous_version=previous_version,
                    vacancy=target_vacancy,
                    note=detailed_note,
                    meeting=current_meeting,
                    changed_info=json.dumps(
                        update_columns,
                        ensure_ascii=False
                    ),
                    raw_text=(
                        f"{request.operator} edited "
                        f"{candidate_name}'s info"
                    ),
                    error_message=item.error_message
                )

                self.log_repo.create_log(log_entry)
                log_results.append(log_entry)

                # ==========================================
                # 更新資料
                # ==========================================
                if trigger_scoring:
                    
                    talent = Talent(**raw)
                    talent.vacancy = update_columns["vacancy"]
                    rescore_note = talent.note or ""

                    rescore_note += (
                        f"\n<p>使用者：System 於 "
                        f"{update_columns['update_time']} 留言："
                        f"{request.operator} 將其職缺從 {raw["vacancy"]}"
                        f"(score:{raw["score"]} | distance:{raw["score_distance"]},experience:{raw["score_experience"]},age:{raw["score_age"]},education:{raw["score_education"]}) 改為 "
                        f"\n"
                        f"改為 {update_columns['vacancy']}</p>"
                    )

                    update_columns["note"] = rescore_note

                    update_request = TalentUpdateRequest(
                        source=source,
                        source_id=source_id,
                        updates=update_columns,
                        operator=request.operator
                    )

                    update_result = self.update_talent(
                        update_request
                    )

                    if not update_result.success:
                        log_entry.error_message = (
                            update_result.message
                        )
                        return update_result
                    lock_result = self.lock_talent(talent.source , talent.source_id)
                    print(lock_result.success)
                    task = run_score.apply_async(
                        args=[
                            talent.to_dict(),
                            None,
                            request.operator,
                            []
                        ],
                        queue="scoring_queue"
                    )
                    print("task background running:",task.id)
                    scoring.append({
                        "task_id": task.id,
                        "source": source,
                        "source_id": source_id
                    })

                else:

                    update_request = TalentUpdateRequest(
                        source=source,
                        source_id=source_id,
                        updates=update_columns,
                        operator=request.operator
                    )
                    update_result = self.update_talent(
                        update_request
                    )

                    if not update_result.success:
                        log_entry.error_message = (
                            update_result.message
                        )
                        return update_result

            return APIResponse(
                success=True,
                data={
                    "updated_rows": len(request.edit),
                    "log_entries": len(log_results),
                    "scoring": scoring
                },
                message=(
                    f"成功更新 {len(request.edit)} 筆資料 "
                    f"並記錄 {len(log_results)} 筆日誌 "
                    f"並評分 {len(scoring)} 人"
                )
            )

        except Exception as e:
            print(traceback.format_exc())

            return APIResponse(
                success=False,
                error=str(e) + "\n\n" + traceback.format_exc(),
                message="更新失敗"
            )