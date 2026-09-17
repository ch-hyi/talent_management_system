"""
狀態流程管理模組
處理人才招募流程的狀態轉換、會議建立、復原等邏輯
"""

import logging
from typing import Tuple, List, Optional
from dataclasses import dataclass
from datetime import datetime
import json
from ..services.send_service import create_meeting , cancel_meeting
from .outlook_helper import (
    extract_html_content_between_markers
)
from ..api.talent_controller import get_talent_service
from ..api.log_controller import get_log_service

# ==================== 常數定義 ====================
talent_service = get_talent_service()
log_service = get_log_service()

FLOW = ["感興趣", "電邀", "電訪", "面邀", "面試", "報到"]

WARNING_TEXT = """
<div style="margin-top:12px; font-family:Segoe UI, Arial; font-size:14px; line-height:1.6;">
    <p>
        <b>此求職者下一階段為：</b>
        <span style="color:#007bff;"><b>{next_stage}</b></span>
    </p>
    
    <p>
        若流程順利接續需安排行程，請於備註處按照指定格式回覆信件<br>
        <b>###職缺,狀態,動作,備註###</b>
    </p>
    
    <p>
        此階段備註處請格式：<br>
        時間格式請使用 <b>24 小時制</b>，且注意日與時中間需空格：<br>
        <code>年(yyyy)/月(mm)/日(dd) 時(hh):分(mm)_地點_標題</code>
    </p>
    
    <p style="background:#f8f9fa; padding:10px; border-radius:6px;">
        <b>指令範例：</b><br>
        <span style="color:#d9534f;"><b>
        ###,,,2025/05/27 09:30_線上_邀請您參加此會議###
        </b></span>
    </p>
</div>
"""


# ==================== 資料結構 ====================

@dataclass
class StatusUpdateResult:
    """狀態更新結果"""
    new_status: str
    updated_note: str
    warning_message: str
    stage_info: str
    meeting_id: Optional[str] = None
    interview_time: Optional[str] = None
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


# ==================== 指令解析 ====================

def parse_instruction(text: str) -> Tuple[str, str, str, str]:
    """
    解析指令字串
    
    Args:
        text: 指令內容 (格式: "職缺,狀態,動作,備註")
        
    Returns:
        tuple: (職缺, 狀態, 動作, 備註)
        
    Example:
        >>> parse_instruction("軟體工程師,電邀,更新,2024/01/15 14:00_線上_面試")
        ("軟體工程師", "電邀", "更新", "2024/01/15 14:00_線上_面試")
        
        >>> parse_instruction(",,查詢,")
        ("", "", "查詢", "")
    """
    parts = text.split("$$")
    return tuple(parts[i] if i < len(parts) else "" for i in range(4))


def parse_meeting_note(note: str) -> Optional[Tuple[str, str, str]]:
    """
    解析會議備註
    
    Args:
        note: 備註內容 (格式: "時間_地點_標題")
        
    Returns:
        tuple: (時間, 地點, 標題) 或 None
        
    Example:
        >>> parse_meeting_note("2024/01/15 14:00_線上_面試")
        ("2024/01/15 14:00", "線上", "面試")
        
        >>> parse_meeting_note("無效格式")
        None
    """
    if "_" not in note:
        return None
    
    parts = note.split("_")
    if len(parts) != 3:
        return None
    
    time_str, location, title = parts
    
    # 驗證時間格式
    try:
        datetime.strptime(time_str.strip(), "%Y/%m/%d %H:%M")
        return time_str.strip(), location.strip(), title.strip()
    except ValueError:
        return None


# ==================== 狀態轉換邏輯 ====================

def get_next_status(current_status: str, req_status: str = "") -> Tuple[str, str, str]:
    """
    計算下一個狀態
    
    Args:
        current_status: 當前狀態
        req_status: 請求的狀態 (可為空)
        
    Returns:
        tuple: (當前階段, 下一狀態, 下下狀態)
        
    Example:
        >>> get_next_status("感興趣", "")
        ("感興趣", "電邀", "電訪")
        
        >>> get_next_status("電邀", "面邀")
        ("電邀", "面邀", "面試")
        
        >>> get_next_status("報到", "")
        ("報到", "報到", "")
    """
    current_stage = ""
    next_status = current_status
    nn_status = ""
    
    # 如果指定了目標狀態且在流程中
    if req_status in FLOW:
        idx = FLOW.index(req_status)
        current_stage = FLOW[max(0, idx - 1)]
        next_status = req_status
        if idx + 1 < len(FLOW):
            nn_status = FLOW[idx + 1]
    
    # 否則往下一階段
    elif current_status in FLOW:
        idx = FLOW.index(current_status)
        current_stage = current_status
        if idx + 1 < len(FLOW):
            next_status = FLOW[idx + 1]
            if idx + 2 < len(FLOW):
                nn_status = FLOW[idx + 2]
        else:
            next_status = current_status  # 已到最後階段
    else:
        # 狀態不在流程中
        current_stage = "要求之狀態不在流程內"
        next_status = current_status
        nn_status = "要求之狀態不在流程內"
    
    return current_stage, next_status, nn_status


# ==================== 會議建立 ====================

def create_meeting_invitation(
    talent,
    mail,
    outlook,
    senders: List[str],
    note: str,
    html_content: str,
    current_status: str
) -> Tuple[bool, Optional[str], Optional[str], str]:
    """
    建立會議邀請
    
    Args:
        talent: Talent 物件
        mail: 郵件物件
        outlook: Outlook Application 物件
        senders: 收件人清單
        note: 備註 (包含會議資訊)
        html_content: 會議內容 HTML
        current_status: 當前狀態
        
    Returns:
        tuple: (成功, meeting_id, interview_time, 錯誤訊息)
    """
    # 解析會議資訊
    meeting_info = parse_meeting_note(note)
    
    if not meeting_info:
        error = "備註格式不合法，正確格式: 年/月/日 時:分_地點_標題"
        logging.error(error)
        return False, None, None, error
    
    time_str, location, title = meeting_info
    
    # 轉換時間格式
    try:
        meeting_time = datetime.strptime(time_str, "%Y/%m/%d %H:%M").strftime("%Y-%m-%d %H:%M")
    except ValueError as e:
        error = f"時間格式錯誤: {e}"
        logging.error(error)
        return False, None, None, error
    
    # 設定會議時長
    duration = 60 if current_status == "電邀" else 120
    
    # 建立會議
    success, meeting_id = create_meeting(
        mail_item=mail,
        talent=talent,
        meeting_time=meeting_time,
        location=location,
        title=title,
        duration=duration,
        recipients=senders,
        html_content=html_content,
        outlook=outlook
    )
    
    if success:
        logging.info(f"會議邀請已發送: {meeting_id}")
        return True, meeting_id, meeting_time, ""
    else:
        error = "建立會議邀請失敗"
        logging.error(error)
        return False, None, None, error


# ==================== 狀態更新處理 ====================

def process_status_update(
    talent,
    req_status: str,
    note: str,
    mail,
    outlook,
    senders: List[str],
    html_content: str
) -> StatusUpdateResult:
    """
    處理狀態更新邏輯
    
    Args:
        talent: Talent 物件
        req_status: 請求的狀態
        note: 備註
        mail: 郵件物件
        outlook: Outlook Application 物件
        senders: 收件人清單
        html_content: HTML 內容
        
    Returns:
        StatusUpdateResult: 更新結果
    """
    errors = []
    current_status = talent.current_status
    db_note = talent.note or ""
    
    # 特殊狀態: rollback
    if req_status == "rollback":
        current_stage, next_status, nn_status = get_next_status(current_status, "")
        warning = WARNING_TEXT.format(next_stage=nn_status)
        return StatusUpdateResult(
            new_status=next_status,
            updated_note=db_note,
            warning_message=warning,
            stage_info="rollback",
            errors=errors
        )
    
    # 特殊狀態: new
    if req_status == "new":
        return StatusUpdateResult(
            new_status=current_status,
            updated_note=db_note,
            warning_message="",
            stage_info="rollback",
            errors=errors
        )
    
    # 計算狀態轉換
    current_stage, next_status, nn_status = get_next_status(current_status, req_status)
    
    meeting_id = None
    interview_time = None
    meeting_success = None
    
    # 處理備註
    if note and "_" not in note and note != "取消":
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_note += f"<p>使用者：{senders[0]} 於 {timestamp} 留言：{note}</p>"
    
    # 判斷是否需要建立會議
    need_meeting = (
        (req_status == "" or req_status == "y" or req_status == "skip") and
        nn_status in ["電邀", "面邀"]
    )
    
    if need_meeting:
        if req_status == "skip":
            # 跳過會議建立
            pass
        else:
            # 嘗試建立會議
            success, meeting_id, interview_time, error = create_meeting_invitation(
                talent=talent,
                mail=mail,
                outlook=outlook,
                senders=senders,
                note=note,
                html_content=html_content,
                current_status=current_status
            )
            
            meeting_success = success
            
            if not success:
                errors.append(error)
                # 會議建立失敗，退回上一階段
                current_stage, next_status, nn_status = get_next_status(
                    FLOW[FLOW.index(current_status) - 1] if current_status in FLOW else current_status,
                    ""
                )
    
    # 更新狀態
    if req_status == "" or req_status == "y" or req_status == "skip":
        # 自動往下一階段
        pass
    
    elif req_status == "n":
        # 拒絕
        next_status = f"{current_status}_拒絕"
    
    elif req_status == "不合格":
        # 不合格
        next_status = f"{current_stage}_不合格"
        nn_status = "無"
    
    elif req_status in FLOW:
        # 指定狀態
        pass
    
    # 生成警告訊息
    warning_message = ""
    if next_status in ["電邀", "面邀"]:
        warning_message = WARNING_TEXT.format(next_stage=nn_status)
    
    # 生成階段資訊
    if meeting_success is True or meeting_success is None:
        stage_info = f"{current_stage} -> 處理狀態更新成功 - {talent.name}：{next_status} -> {nn_status}"
        logging.info(stage_info)
    else:
        stage_info = f"{current_stage} -> 處理狀態更新失敗 - {talent.name}：{next_status} -> {nn_status}"
        warning_message = (
            "<span style='color:#7e0c08; font-size: 25px'>"
            "<b>**備註格式錯誤，狀態更新失敗**</b></span>" + warning_message
        )
        logging.error("**備註格式錯誤** " + stage_info)
    
    return StatusUpdateResult(
        new_status=next_status,
        updated_note=db_note,
        warning_message=warning_message,
        stage_info=stage_info,
        meeting_id=meeting_id,
        interview_time=interview_time,
        errors=errors
    )


# ==================== 復原處理 ====================

def process_rollback(
    talent,
    mail,
    outlook,
    senders: List[str],
) -> Tuple[bool, str, Optional[int]]:
    """
    處理狀態復原
    
    Args:
        talent: Talent 物件
        mail: 郵件物件
        outlook: Outlook Application 物件
        senders: 收件人清單
        html_content: HTML 內容
        
    Returns:
        tuple: (成功, 訊息, 復原到的版本號)
    """
    # 1️⃣ 取消現有會議 (如果存在)
    if talent.meeting:
        try:
            cancel_meeting(talent.meeting, outlook)
            logging.info(f"已取消會議: {talent.meeting}")
        except Exception as e:
            logging.error(f"取消會議失敗: {e}")
    
    # 2️⃣ 從資料庫取得上一個成功的快照
    talent_org = talent_service.get_one_talent(talent.source, talent.source_id).data
    snapshot = log_service.get_previous_log(talent.source, talent.source_id).data
    
    if not snapshot:
        return False, "沒有可復原的版本", None
    
    # 3️⃣ 解析快照
    try:
        snapshot_data = json.loads(snapshot["snapshot_json"])
        version = snapshot["version"]
    except Exception as e:
        logging.error(f"解析快照失敗: {e}")
        return False, "快照資料損壞", None
    
    # 4️⃣ 復原資料
    try:
        # 移除不應復原的欄位
        talent_service.update_talent_with_log(snapshot_data, senders[0], [talent_org])
        
        logging.info(f"已復原到版本 {version}")
        return True, "復原成功", version
        
    except Exception as e:
        logging.error(f"復原失敗: {e}")
        return False, f"復原失敗: {e}", None


# ==================== 狀態檢查 ====================

def check_status_locked(current_status: str) -> Tuple[bool, str, str]:
    """
    檢查狀態是否被鎖定 (拒絕/不合格)
    
    Args:
        current_status: 當前狀態
        
    Returns:
        tuple: (是否鎖定, 鎖定原因, 階段資訊)
        
    Example:
        >>> check_status_locked("電訪_拒絕")
        (True, "人才已拒絕", "電訪 狀態：拒絕")
        
        >>> check_status_locked("面試_不合格")
        (True, "人才不合格", "面試 狀態：不合格")
        
        >>> check_status_locked("電邀")
        (False, "", "")
    """
    parts = current_status.split("_")
    
    if len(parts) == 2:
        stage, status = parts
        
        if status == "不合格":
            return (
                True,
                "*人才不合格，狀態將不進行更動，若要解除鎖定請於動作中輸入解鎖*",
                f"{stage} 狀態：不合格"
            )
        
        elif status == "拒絕":
            return (
                True,
                "*人才已拒絕，狀態將不進行更動，若要解除鎖定請於動作中輸入解鎖*",
                f"{stage} 狀態：拒絕"
            )
    
    return False, "", ""


# ==================== 會議取消處理 ====================

def process_meeting_cancellation(
    talent,
    senders,
    outlook
) -> Tuple[bool, str]:
    """
    處理會議取消
    
    Args:
        talent: Talent 物件
        outlook: Outlook Application 物件
        
    Returns:
        tuple: (成功, 訊息)
    """
    talent_org = talent
    if not talent.meeting:
        return False, "無會議可取消"
    
    try:
        success = cancel_meeting(talent.meeting, outlook)
        
        if success:
            # 退回上兩步狀態
            if talent.current_status in FLOW:
                idx = FLOW.index(talent.current_status)
                new_status = FLOW[max(0, idx - 2)]
                talent.current_status = new_status
                talent.meeting = ""
                talent.interview_time = ""
                # 更新資料庫
                talent_service.update_talent_with_log(
                    talent,
                    senders[0],
                    talent_org,
                )
                
                return True, f"已取消會議，狀態退回至 {new_status}"
            else:
                return True, "已取消會議"
        else:
            return False, "取消會議失敗"
            
    except Exception as e:
        error = f"取消會議失敗: {e}"
        logging.error(error)
        return False, error


# ==================== 狀態驗證 ====================

def validate_status_transition(current_status: str, target_status: str) -> Tuple[bool, str]:
    """
    驗證狀態轉換是否合法
    
    Args:
        current_status: 當前狀態
        target_status: 目標狀態
        
    Returns:
        tuple: (是否合法, 錯誤訊息)
        
    Example:
        >>> validate_status_transition("感興趣", "電邀")
        (True, "")
        
        >>> validate_status_transition("電邀", "報到")
        (False, "不可跳過中間階段")
    """
    if not target_status or target_status not in FLOW:
        return True, ""  # 空白或非流程狀態，允許
    
    if current_status not in FLOW:
        return True, ""  # 當前狀態異常，允許修正
    
    current_idx = FLOW.index(current_status)
    target_idx = FLOW.index(target_status)
    
    # 允許往前或往後一步，或指定特定狀態
    if abs(target_idx - current_idx) <= 2:
        return True, ""
    
    return False, f"不可從 {current_status} 直接跳至 {target_status}"


# ==================== 輔助函式 ====================

def format_status_change_note(
    operator: str,
    old_status: str,
    new_status: str,
    note: str = ""
) -> str:
    """
    格式化狀態變更備註
    
    Args:
        operator: 操作者
        old_status: 舊狀態
        new_status: 新狀態
        note: 額外備註
        
    Returns:
        str: 格式化的 HTML 備註
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    color = "#007bff" if new_status in FLOW else "#6c757d"
    
    html = f"""
    <p style="color:{color}; margin:0;">
        使用者：{operator} 於 {timestamp} 
        將狀態從 <b>{old_status}</b> 更新為 <b>{new_status}</b>
    </p>
    """
    
    if note:
        html += f"<p style='margin:0; padding-left:20px;'>備註：{note}</p>"
    
    return html


def get_stage_color(status: str) -> str:
    """
    取得狀態對應的顏色
    
    Args:
        status: 狀態
        
    Returns:
        str: CSS 顏色代碼
    """
    if "拒絕" in status or "不合格" in status:
        return "#dc3545"  # 紅色
    elif "完成" in status or status == "報到":
        return "#28a745"  # 綠色
    elif status in FLOW:
        return "#007bff"  # 藍色
    else:
        return "#6c757d"  # 灰色