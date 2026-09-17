
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple,Callable
import inspect
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from css import load_custom_css
from api_client import UserAPI,TalentAPI,LogAPI,VacancyAPI


# =============================================================================
# Page configuration
# =============================================================================

st.set_page_config(
    page_title="Talent Intelligence Center",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
footer = load_custom_css()

# =============================================================================
# User-editable configuration
# =============================================================================


# TODO: Arrange these in the exact business-process order used by your company.
# Keep aliases in STATUS_ALIASES rather than duplicating stages here.
LOCATION_COORDINATES = None
STAGE_ORDER = [
    "AI REVIEW",
    "感興趣",
    "電邀",
    "電訪",
    "面邀",
    "面試",
    "OFFER",
    "報到",
]

WATCHED_STAGE = [
    "AI REVIEW",
    "感興趣",
    "電邀",
    "電訪",
    "面邀",
    "面試",
    "OFFER",
]

NOT_PASS = [
"AI REVIEW-NOT PASS",
"電邀-NOT PASS",
"電訪-NOT PASS",
"面邀-NOT PASS",
"面試-NOT PASS",
"OFFER-NOT PASS"
]

STAGE_CONFIG = {
    "AI REVIEW": {
        "fail_type": "unqualified"
    },
    "感興趣": {
        "fail_type": "unqualified"
    },
    "電邀": {
        "fail_type": "reject"
    },
    "電訪": {
        "fail_type": "unqualified"
    },
    "面邀": {
        "fail_type": "reject"
    },
    "面試": {
        "fail_type": "unqualified"
    },
    "OFFER": {
        "fail_type": "reject"
    }
}
# TODO: Map all historical spellings/status codes to one canonical stage.
STATUS_ALIASES = {
    # "INTERESTED": "感興趣",
    # "PHONE_SCREEN": "電邀",
    # "CV_REVIEW": "履歷審核",
    # "MANAGER_REVIEW": "主管審核",
    # "INTERVIEW": "面試",
    # "OFFER": "Offer",
    # "ONBOARDED": "報到",
}

# Statuses that indicate the candidate has left the funnel.
# TODO: Replace with your actual values.
TERMINAL_REJECT_STATUSES = {
    "不適任",
    "婉拒",
    "撤回",
    "拒絕Offer",
    "未報到",
    "REJECTED",
    "WITHDRAWN",
}

# Aging warning thresholds, in calendar days.
# TODO: Tune by stage according to HR SLA.
STAGE_SLA_DAYS = {
    "感興趣": 3,
    "電邀": 3,
    "履歷審核": 5,
    "主管審核": 5,
    "面試": 7,
    "核薪": 5,
    "Offer": 7,
    "報到": 30,
}
DEFAULT_SLA_DAYS = 7

# TODO: Add your city/district coordinates.
# Keys should preferably be "city|district". A city-only fallback is supported.


# Which log source values represent talent records.
TALENT_LOG_SOURCES = {"104", "user_management", "vacancy_management"}

# Color design system.
COLORS = {
    "navy": "#132238",
    "blue": "#3A78F2",
    "cyan": "#23B5D3",
    "green": "#2EAD77",
    "amber": "#F5A623",
    "red": "#E45757",
    "purple": "#7656D6",
    "muted": "#718096",
    "paper": "#FFFFFF",
    "background": "#F4F7FB",
}


# =============================================================================
# Styling
# =============================================================================
st.markdown(
    f"""
    <style>
        .stApp {{ background: {COLORS['background']}; }}
        .block-container {{ padding-top: 1.4rem; padding-bottom: 3rem; }}
        h1, h2, h3 {{ color: {COLORS['navy']}; letter-spacing: -0.02em; }}
        [data-testid="stMetric"] {{
            background: white;
            border: 1px solid #E7ECF3;
            padding: 16px 18px;
            border-radius: 18px;
            box-shadow: 0 8px 24px rgba(19, 34, 56, 0.06);
        }}
        [data-testid="stMetricLabel"] {{ color: #667085; }}
        [data-testid="stMetricValue"] {{ color: {COLORS['navy']}; }}
        div[data-testid="stPlotlyChart"] {{
            background: white;
            border: 1px solid #E7ECF3;
            border-radius: 18px;
            padding: 8px;
            box-shadow: 0 8px 24px rgba(19, 34, 56, 0.05);
        }}
        .section-note {{
            color: #667085;
            margin-top: -10px;
            margin-bottom: 14px;
        }}
        .health-card {{
            background: linear-gradient(135deg, #132238 0%, #24456F 100%);
            color: white;
            padding: 22px;
            border-radius: 20px;
            box-shadow: 0 12px 30px rgba(19,34,56,.18);
        }}
        .health-card h3 {{ color: white; margin: 0 0 6px 0; }}
        .health-card p {{ color: #D8E4F2; margin: 0; }}
        div[data-baseweb="select"] > div {{ border-radius: 12px; }}
        .stButton > button, .stDownloadButton > button {{ border-radius: 12px; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# API layer: replace api_call() only if your project already has a wrapper
# =============================================================================


def _extract_records(data: Any) -> List:
    """
    將不同 APIResponse.data 格式轉成 List[Dict]。

    支援：
    1. data = [...]
    2. data = {"items": [...]}
    3. data = {"records": [...]}
    4. data = {"rows": [...]}
    5. data = {"data": [...]}
    """

    if data is None:
        return []

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in (
            "items",
            "records",
            "rows",
            "results",
            "data"
        ):
            records = data.get(key)

            if isinstance(records, list):
                return records

    return []


def _extract_total(data: Any) -> Optional[int]:
    """
    從 APIResponse.data 取得總筆數。

    如果 API 沒有回傳 total，則回傳 None。
    """

    if not isinstance(data, dict):
        return None

    for key in (
        "total",
        "total_count",
        "count"
    ):
        value = data.get(key)

        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass

    return None

@st.cache_data(
    ttl=120,
    show_spinner=False
)
def fetch_report_data(
    start_date: str,
    end_date: str
) -> Dict[str, pd.DataFrame]:
    """
    使用現有 Client API 取得 Dashboard 原始資料。

    Args:
        start_date:
            開始日期，格式為 YYYY-MM-DD。

        end_date:
            結束日期，格式為 YYYY-MM-DD。

    Returns:
        包含 talents、logs、vacancies、users
        以及 _errors 的 DataFrame Dictionary。
    """

    frames: Dict[str, pd.DataFrame] = {
        "talents": pd.DataFrame(),
        "logs_104": pd.DataFrame(),
        "logs_status" : pd.DataFrame(),
        "logs_vacancy_management": pd.DataFrame(),
        "logs_user_management": pd.DataFrame(),
        "vacancies": pd.DataFrame(),
        "users": pd.DataFrame(),
        "_errors": pd.DataFrame()
    }

    errors: List[str] = []

    # =========================================================
    # Talent Filter
    # =========================================================
    talent_filter ={
        "received_time_start":start_date,
        "received_time_end":end_date,
        "exclude_blocked":False,
        "only_scored":False,
        "sort_by":"received_time",
        "sort_order":"ASC"
    }

    # =========================================================
    # Log Filter
    # =========================================================
    log_filter_104 = {
        "timestamp_start":start_date,
        "timestamp_end":end_date,
        "source":["104"],
        "sort_by":"timestamp",
        "sort_order":"ASC"
    }

    log_filter_user_management = {
        "timestamp_start":start_date,
        "timestamp_end":end_date,
        "source":["user_management"],
        "sort_by":"timestamp",
        "sort_order":"ASC"
    }

    log_filter_vacancy_management = {
        "timestamp_start":start_date,
        "timestamp_end":end_date,
        "source":["vacancy_management"],
        "sort_by":"timestamp",
        "sort_order":"ASC"
    }

    # 如果 log.source 代表資料類型，
    # 而人才 Log 的 source 固定是 talent，
    # 可以改成：
    #
    # log_filter = LogFilter(
    #     source=["talent"],
    #     timestamp_start=start_date,
    #     timestamp_end=end_date,
    #     sort_by="timestamp",
    #     sort_order="ASC"
    # )

    # =========================================================
    # Vacancy Filter
    # 保留 ACTIVE、INACTIVE 等歷史職缺，只排除 DELETED
    # =========================================================
    vacancy_filter = {}

    # =========================================================
    # User Filter
    # 不限制角色及狀態
    # =========================================================
    user_filter = {}

    # =========================================================
    # Talents
    # =========================================================
    try:
        talent_records = fetch_all_pages(
            username=st.session_state["username"],
            query_function=TalentAPI.query_talents,
            filters=talent_filter,
            page_size=10000000000
        )
        frames["talents"] = pd.DataFrame(
            talent_records
        )

    except Exception as error:
        errors.append(
            f"Talent API: {error}"
        )

    # =========================================================
    # Logs
    # =========================================================
    try:
        log_records_104 = fetch_all_pages(
            query_function=LogAPI.query_logs,
            filters=log_filter_104,
            page_size=100000000000
        )

        frames["logs_104"] = pd.DataFrame(
            log_records_104
        )

    except Exception as error:
        errors.append(
            f"Log API: {error}"
        )

    try:
        log_records_status = fetch_all_pages(
            query_function=LogAPI.get_status_logs,
            filters=log_filter_104,
            page_size=100000000000
        )

        frames["logs_status"] = pd.DataFrame(
            log_records_status
        )

    except Exception as error:
        errors.append(
            f"Log API: {error}"
        )

    try:
        log_records_user_management = fetch_all_pages(
            query_function=LogAPI.query_logs,
            filters=log_filter_user_management,
            page_size=100000000000
        )

        frames["logs_user_management"] = pd.DataFrame(
            log_records_user_management
        )

    except Exception as error:
        errors.append(
            f"Log API: {error}"
        )

    try:
        log_records_vacancy_management = fetch_all_pages(
            query_function=LogAPI.query_logs,
            filters=log_filter_vacancy_management,
            page_size=10000000000
        )

        frames["logs_vacancy_management"] = pd.DataFrame(
            log_records_vacancy_management
        )

    except Exception as error:
        errors.append(
            f"Log API: {error}"
        )

    # =========================================================
    # Vacancies
    # =========================================================
    try:
        vacancy_records = fetch_all_pages(
            query_function=VacancyAPI.query_vacancy,
            filters=vacancy_filter,
            page_size=10000000000
        )

        frames["vacancies"] = pd.DataFrame(
            vacancy_records
        )

    except Exception as error:
        errors.append(
            f"Vacancy API: {error}"
        )

    # =========================================================
    # Users
    # =========================================================
    try:
        user_records = fetch_all_pages(
            query_function=UserAPI.query_user,
            filters=user_filter,
            page_size=100000000000
        )

        frames["users"] = pd.DataFrame(
            user_records
        )

    except Exception as error:
        errors.append(
            f"User API: {error}"
        )

    # =========================================================
    # API Errors
    # =========================================================
    frames["_errors"] = pd.DataFrame(
        {
            "error": errors
        }
    )

    return frames

def fetch_all_pages(
    query_function: Callable,
    *,
    username:str = None,
    filters: Optional[Dict] = None,
    page_size: int = 500,
    max_records: int = 100_000000000
) -> List:
    """
    持續呼叫 query_function，直到抓完所有資料。

    query_function 必須支援：
        filters
        limit
        offset
    """

    all_records: List[Dict] = []
    offset = 0

    while offset < max_records:
        kwargs = {
            "filters": filters or {},
            "limit": page_size,
            "offset": offset
        }

        if "username" in inspect.signature(
            query_function
        ).parameters:
            kwargs["username"] = username

        response = query_function(**kwargs)
        if response is None:
            raise RuntimeError(
                "API returned None."
            )

        if not response.success:
            raise RuntimeError(
                response.message
                or "API request failed."
            )

        records = _extract_records(
            response.data
        )

        total = _extract_total(
            response.data
        )

        if not records:
            break

        all_records.extend(records)

        # API 有回傳總數時，以總數判斷
        if total is not None:
            if len(all_records) >= total:
                break

        # 回傳數量小於 page_size，
        # 表示這是最後一頁
        if len(records) < page_size:
            break

        offset += len(records)

    if len(all_records) >= max_records:
        st.warning(
            f"資料已達安全上限 "
            f"{max_records:,} 筆，"
            "報表可能不是完整資料。"
        )

    return all_records

# =============================================================================
# Data normalization
# =============================================================================
def ensure_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = pd.NA
    return out


def to_datetime_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


# def normalize_status(value: Any) -> str:
#     text = clean_text(value)
#     return STATUS_ALIASES.get(text, text)


def normalize_frames(frames: Dict[str, pd.DataFrame]) -> Tuple[pd.DataFrame, ...]:
    talents = ensure_columns(frames.get("talents", pd.DataFrame()), [
        "source_id", "name", "vacancy", "source", "received_time", "update_time",
        "current_status", "score", "score_distance", "score_experience",
        "score_education", "score_age", "city", "district", "age", "gender",
        "education_degree", "education_school", "total_exp_years", "expected_salary",
        "interview_time", "onboarding_date", "block", "lock_status", "block_reason",
        "recommender",
    ])
    logs_104 = ensure_columns(frames.get("logs_104", pd.DataFrame()), [
        "log_id", "source", "source_id", "name", "version", "operator", "timestamp",
        "snapshot_json", "status", "action", "previous_version", "vacancy", "note",
        "meeting", "operate_status", "changed_info", "raw_text", "error_message",
    ])

    logs_status = ensure_columns(frames.get("logs_status", pd.DataFrame()), [
        "log_id", "source", "source_id", "name", "version", "operator", "timestamp",
        "snapshot_json", "status", "action", "previous_version", "vacancy", "note",
        "meeting", "operate_status", "changed_info", "raw_text", "error_message",
    ])

    logs_user_management = ensure_columns(frames.get("logs_user_management", pd.DataFrame()), [
        "log_id", "source", "source_id", "name", "version", "operator", "timestamp",
        "snapshot_json", "status", "action", "previous_version", "vacancy", "note",
        "meeting", "operate_status", "changed_info", "raw_text", "error_message",
    ])

    logs_vacancy_management = ensure_columns(frames.get("logs_vacancy_management", pd.DataFrame()), [
        "log_id", "source", "source_id", "name", "version", "operator", "timestamp",
        "snapshot_json", "status", "action", "previous_version", "vacancy", "note",
        "meeting", "operate_status", "changed_info", "raw_text", "error_message",
    ])
    vacancies = ensure_columns(frames.get("vacancies", pd.DataFrame()), [
        "vacancy_id", "position_title", "work_location", "senior", "lab", "status",
        "created_at", "updated_at",
    ])
    users = ensure_columns(frames.get("users", pd.DataFrame()), [
        "user_id", "user_account", "user_name", "user_email", "user_role", "status",
        "create_time", "update_time", "deleted_time", "last_login",
    ])

    for col in ("received_time", "update_time", "interview_time", "onboarding_date"):
        talents[col] = to_datetime_series(talents[col])
    logs_104["timestamp"] = to_datetime_series(logs_104["timestamp"])
    logs_status["timestamp"] = to_datetime_series(logs_status["timestamp"])
    logs_user_management["timestamp"] = to_datetime_series(logs_user_management["timestamp"])
    logs_vacancy_management["timestamp"] = to_datetime_series(logs_vacancy_management["timestamp"])
    for col in ("created_at", "updated_at"):
        vacancies[col] = to_datetime_series(vacancies[col])
    for col in ("create_time", "update_time", "deleted_time", "last_login"):
        users[col] = to_datetime_series(users[col])

    talents["current_status"] = talents["current_status"]
    logs_104["status"] = logs_104["status"]
    logs_status["status"] = logs_status["status"]
    logs_user_management["status"] = logs_user_management["status"]
    logs_vacancy_management["status"] = logs_vacancy_management["status"]

    numeric_cols = [
        "score", "score_distance", "score_experience", "score_education", "score_age",
        "age", "total_exp_years", "expected_salary", "block",
    ]
    for col in numeric_cols:
        talents[col] = pd.to_numeric(talents[col], errors="coerce")

    return talents, logs_104,logs_status,logs_user_management,logs_vacancy_management, vacancies, users


# =============================================================================
# Stage-event extraction from logs
# =============================================================================
def safe_json_load(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    text = clean_text(value)
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}



def build_stage_events(
    logs: pd.DataFrame,
    talents: pd.DataFrame,
) -> pd.DataFrame:
    result_columns = [
        "source",
        "source_id",
        "stage",
        "entered_at",
        "vacancy",
        "operator",
    ]

    if logs.empty:
        return pd.DataFrame(columns=result_columns)

    work = logs.copy()
    talents = talents.copy()

    # ==========================================
    # 檢查必要欄位
    # ==========================================
    required_log_columns = {
        "source",
        "source_id",
        "timestamp",
        "status",
    }

    missing_log_columns = (
        required_log_columns - set(work.columns)
    )

    if missing_log_columns:
        raise ValueError(
            f"logs 缺少必要欄位：{sorted(missing_log_columns)}"
        )

    required_talent_columns = {
        "source",
        "source_id",
        "vacancy",
    }

    missing_talent_columns = (
        required_talent_columns - set(talents.columns)
    )

    if not talents.empty and missing_talent_columns:
        raise ValueError(
            f"talents 缺少必要欄位："
            f"{sorted(missing_talent_columns)}"
        )

    # ==========================================
    # 清理唯一識別欄位
    # ==========================================
    work = work[
        work["timestamp"].notna()
        & work["source"].notna()
        & work["source_id"].notna()
    ].copy()

    if work.empty:
        return pd.DataFrame(columns=result_columns)

    work["source"] = (
        work["source"]
        .astype("string")
        .str.strip()
        .str.lower()
    )

    work["source_id"] = (
        work["source_id"]
        .astype("string")
        .str.strip()
    )

    work["timestamp"] = pd.to_datetime(
        work["timestamp"],
        errors="coerce",
    )

    work = work.dropna(
        subset=[
            "source",
            "source_id",
            "timestamp",
        ]
    )

    # ==========================================
    # 只保留 Talent 相關來源
    # ==========================================
    allowed_sources = {
        str(item).strip().lower()
        for item in TALENT_LOG_SOURCES
    }

    candidate_mask = work["source"].isin(allowed_sources)

    # 保留你原本的行為：
    # 確實存在符合的來源時才執行過濾
    if candidate_mask.any():
        work = work.loc[candidate_mask].copy()

    # ==========================================
    # 取得階段
    # ==========================================
    work["stage"] = work["status"]

    known_statuses = set(WATCHED_STAGE)

    work = work[
        work["stage"].isin(known_statuses)
    ].copy()

    if work.empty:
        return pd.DataFrame(columns=result_columns)

    # 欄位可能不存在時補空值
    if "version" not in work.columns:
        work["version"] = pd.NA

    if "vacancy" not in work.columns:
        work["vacancy"] = pd.NA

    if "operator" not in work.columns:
        work["operator"] = pd.NA

    # ==========================================
    # 排序事件
    # ==========================================
    work = work.sort_values(
        [
            "source",
            "source_id",
            "timestamp",
            "version",
        ],
        na_position="last",
    ).reset_index(drop=True)

    # ==========================================
    # 只移除「連續重複的同階段 Log」
    #
    # 例如：
    # 感興趣 → 感興趣 → 面邀
    # 第一、二筆可能是同一次更新產生的重複 log
    #
    # 但：
    # 感興趣 → 面邀 → 感興趣
    # 最後一筆必須保留，因為是重新進入該階段
    # ==========================================
    previous_stage = work.groupby(
        ["source", "source_id"],
        dropna=False,
    )["stage"].shift()

    events = work.loc[
        work["stage"] != previous_stage
    ].copy()

    events = (
        events
        .rename(columns={"timestamp": "entered_at"})
        [
            [
                "source",
                "source_id",
                "stage",
                "entered_at",
                "vacancy",
                "operator",
            ]
        ]
    )

    # ==========================================
    # 建立 Talent vacancy lookup
    # ==========================================
    if talents.empty:
        events["vacancy"] = events["vacancy"]
        return events.reset_index(drop=True)

    talents["source"] = (
        talents["source"]
        .astype("string")
        .str.strip()
        .str.lower()
    )

    talents["source_id"] = (
        talents["source_id"]
        .astype("string")
        .str.strip()
    )

    # 如果同一位 Talent 有多筆，保留 update_time 最新的
    if "update_time" in talents.columns:
        talents["update_time"] = pd.to_datetime(
            talents["update_time"],
            errors="coerce",
        )

        talents = talents.sort_values(
            "update_time",
            na_position="first",
        )

    talent_lookup = (
        talents[
            [
                "source",
                "source_id",
                "vacancy",
            ]
        ]
        .drop_duplicates(
            subset=["source", "source_id"],
            keep="last",
        )
    )

    # ==========================================
    # 必須使用 source + source_id merge
    # ==========================================
    events = events.merge(
        talent_lookup,
        on=["source", "source_id"],
        how="left",
        suffixes=("_log", "_talent"),
        validate="many_to_one",
    )

    events["vacancy"] = (
        events["vacancy_log"]
        .fillna(events["vacancy_talent"])
    )

    return (
        events
        .drop(
            columns=[
                "vacancy_log",
                "vacancy_talent",
            ]
        )
        .sort_values(
            [
                "source",
                "source_id",
                "entered_at",
            ]
        )
        .reset_index(drop=True)
    )

def build_stage_durations(
    events: pd.DataFrame,
    talents: pd.DataFrame,
    now: Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    """
    每位候選人的每個階段一列，
    並計算該階段停留的日曆天數。

    候選人唯一識別鍵：
    source + source_id
    """

    now = now if now is not None else pd.Timestamp.now()

    result_columns = [
        "source",
        "source_id",
        "vacancy",
        "stage",
        "entered_at",
        "left_at",
        "duration_days",
        "is_current",
        "operator",
    ]

    if events.empty:
        return pd.DataFrame(columns=result_columns)

    events = events.copy()
    talents = talents.copy()

    # ==========================================
    # 檢查必要欄位
    # ==========================================
    required_event_columns = {
        "source",
        "source_id",
        "stage",
        "entered_at",
    }

    missing_event_columns = (
        required_event_columns - set(events.columns)
    )

    if missing_event_columns:
        raise ValueError(
            "events 缺少必要欄位："
            f"{sorted(missing_event_columns)}"
        )

    required_talent_columns = {
        "source",
        "source_id",
        "current_status",
    }

    missing_talent_columns = (
        required_talent_columns - set(talents.columns)
    )

    if not talents.empty and missing_talent_columns:
        raise ValueError(
            "talents 缺少必要欄位："
            f"{sorted(missing_talent_columns)}"
        )

    # ==========================================
    # 統一唯一鍵型別
    # ==========================================
    events["source"] = (
        events["source"]
        .astype("string")
        .str.strip()
    )

    events["source_id"] = (
        events["source_id"]
        .astype("string")
        .str.strip()
    )

    events["entered_at"] = pd.to_datetime(
        events["entered_at"],
        errors="coerce",
    )

    if not talents.empty:
        talents["source"] = (
            talents["source"]
            .astype("string")
            .str.strip()
        )

        talents["source_id"] = (
            talents["source_id"]
            .astype("string")
            .str.strip()
        )

    # 移除無法識別候選人或時間無效的事件
    events = events.dropna(
        subset=[
            "source",
            "source_id",
            "stage",
            "entered_at",
        ]
    )

    if events.empty:
        return pd.DataFrame(columns=result_columns)

    # ==========================================
    # 建立目前狀態 lookup
    # key: (source, source_id)
    # value: current_status
    # ==========================================
    if not talents.empty:
        if "update_time" in talents.columns:
            talents["update_time"] = pd.to_datetime(
                talents["update_time"],
                errors="coerce",
            )

            talents = talents.sort_values(
                "update_time",
                na_position="first",
            )

        latest_talents = talents.drop_duplicates(
            subset=["source", "source_id"],
            keep="last",
        )

        current_lookup = {
            (str(row["source"]), str(row["source_id"])): row[
                "current_status"
            ]
            for _, row in latest_talents.iterrows()
        }

    else:
        current_lookup = {}

    rows: List[Dict[str, Any]] = []

    # ==========================================
    # 每位候選人分開建立 stage timeline
    # ==========================================
    grouped_events = events.groupby(
        ["source", "source_id"],
        dropna=False,
        sort=False,
    )

    for (source, source_id), group in grouped_events:
        group = (
            group
            .sort_values("entered_at")
            .reset_index(drop=True)
        )

        lookup_key = (
            str(source),
            str(source_id),
        )

        current_stage = current_lookup.get(lookup_key)

        for idx, row in group.iterrows():
            if idx + 1 < len(group):
                next_time = group.iloc[idx + 1]["entered_at"]
            else:
                next_time = pd.NaT

            # 必須同時符合：
            # 1. 此事件是最後一筆
            # 2. 此事件階段等於人才目前狀態
            is_open_stage = (
                pd.isna(next_time)
                and row["stage"] == current_stage
            )

            end_time = now if is_open_stage else next_time

            if (
                pd.notna(end_time)
                and pd.notna(row["entered_at"])
            ):
                duration_days = (
                    end_time - row["entered_at"]
                ).total_seconds() / 86400

                duration_days = max(
                    float(duration_days),
                    0.0,
                )
            else:
                duration_days = pd.NA

            rows.append(
                {
                    "source": source,
                    "source_id": source_id,
                    "vacancy": row.get("vacancy"),
                    "stage": row["stage"],
                    "entered_at": row["entered_at"],
                    "left_at": end_time,
                    "duration_days": duration_days,
                    "is_current": bool(is_open_stage),
                    "operator": row.get("operator"),
                }
            )

    return (
        pd.DataFrame(
            rows,
            columns=result_columns,
        )
        .reset_index(drop=True)
    )

# =============================================================================
# Analytics helpers
# =============================================================================
def filter_data(
    talents: pd.DataFrame,
    logs: pd.DataFrame,
    vacancies: pd.DataFrame,
    users: pd.DataFrame,
    date_range: Tuple[Any, Any],
    selected_vacancies: List[str],
    selected_sources: List[str],
    selected_labs: List[str],
    selected_recommender : List[str]
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    start = pd.Timestamp(date_range[0])
    end = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1)

    t = talents.copy()
    if t["received_time"].notna().any():
        t = t[t["received_time"].between(start, end, inclusive="left")]
    if selected_vacancies:
        t = t[t["vacancy"].astype(str).isin(selected_vacancies)]
    if selected_sources:
        t = t[t["source"].astype(str).isin(selected_sources)]

    v = vacancies.copy()
    if selected_labs:
        v = v[v["lab"].astype(str).isin(selected_labs)]
        valid_positions = set(v["position_title"].dropna().astype(str))
        valid_ids = set(v["vacancy_id"].dropna().astype(str))
        t = t[t["vacancy"].astype(str).isin(valid_positions | valid_ids)]

    if selected_recommender : 
        t = t[t["recommender"].astype(str).isin(selected_recommender)]

    candidate_ids = set(t["source_id"].dropna().astype(str))
    lg = logs[logs["source_id"].astype(str).isin(candidate_ids)].copy()
    return t, lg, v, users.copy()


def calculate_funnel( talents: pd.DataFrame) -> pd.DataFrame:

    normalized_status = talents["current_status"]

    stage_order_map = {
        stage: idx
        for idx, stage in enumerate(STAGE_ORDER)
    }

    stage_level = normalized_status.map(stage_order_map)

    rows = []

    for idx, stage in enumerate(STAGE_ORDER):
        if idx==0:
            count = len(talents)
        else:
            count = stage_level.ge(idx).sum()

        previous_count = rows[-1]["count"] if rows else count

        stage_pass_rate = (
            count / previous_count * 100
            if previous_count
            else 0
        )

        overall_conversion = (
            count / rows[0]["count"] * 100
            if rows and rows[0]["count"]
            else 100
        )

        rows.append({
            "stage": stage,
            "count": int(count),
            "stage_pass_rate": round(
                stage_pass_rate if idx > 0 else 100,
                1,
            ),
            "overall_conversion": round(
                overall_conversion,
                1,
            ),
        })

    return pd.DataFrame(rows)


def stage_time_summary(durations: pd.DataFrame) -> pd.DataFrame:
    if durations.empty:
        return pd.DataFrame(columns=["stage", "avg_days", "median_days", "p75_days", "current_count"])
    valid = durations[durations["duration_days"].notna()].copy()
    summary = (
        valid.groupby("stage", as_index=False)
        .agg(
            avg_days=("duration_days", "mean"),
            median_days=("duration_days", "median"),
            p75_days=("duration_days", lambda s: s.quantile(0.75)),
            candidates=("source_id", "nunique"),
        )
    )
    current_counts = (
        durations[durations["is_current"]]
        .groupby("stage")["source_id"].nunique()
        .rename("current_count")
    )
    summary = summary.merge(current_counts, on="stage", how="left").fillna({"current_count": 0})
    summary["stage"] = pd.Categorical(summary["stage"], STAGE_ORDER, ordered=True)
    return summary.sort_values("stage")


def build_aging_table(durations: pd.DataFrame, talents: pd.DataFrame) -> pd.DataFrame:
    current = durations[durations["is_current"]].copy() if not durations.empty else pd.DataFrame()
    if current.empty:
        return pd.DataFrame()

    detail_cols = ["source","source_id", "name", "vacancy", "current_status", "update_time", "block", "block_reason"]
    detail = talents[detail_cols].drop_duplicates(
        subset=["source", "source_id"],
        keep="last",
    )

    out = current.merge(
        detail,
        on=["source", "source_id"],
        how="left",
        suffixes=("", "_talent"),
        validate="many_to_one",
    )
    out["vacancy"] = out["vacancy"].fillna(out["vacancy_talent"])
    out["sla_days"] = out["stage"].map(STAGE_SLA_DAYS).fillna(DEFAULT_SLA_DAYS)
    out["overdue_days"] = (out["duration_days"] - out["sla_days"]).clip(lower=0)
    out["risk"] = pd.cut(
        out["duration_days"] / out["sla_days"].replace(0, 1),
        bins=[-float("inf"), 0.7, 1.0, float("inf")],
        labels=["正常", "接近 SLA", "逾期"],
    )
    # st.text(out)
    return out.sort_values(["overdue_days", "duration_days"], ascending=False)


def add_coordinates(talents: pd.DataFrame) -> pd.DataFrame:
    geo = talents.copy()

    def lookup(row: pd.Series) -> Tuple[Optional[float], Optional[float]]:
        city = clean_text(row.get("city"))
        district = clean_text(row.get("district"))
        item = LOCATION_COORDINATES.get(f"{city}|{district}") or LOCATION_COORDINATES.get(city)
        if not item:
            return None, None
        return item.get("lat"), item.get("lon")

    coords = geo.apply(lookup, axis=1, result_type="expand")
    if coords.shape[1] == 2:
        geo[["lat", "lon"]] = coords
    else:
        geo["lat"], geo["lon"] = None, None
    return geo


def style_figure(fig: go.Figure, height: int = 390) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=18, r=18, t=55, b=18),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Arial, Microsoft JhengHei, sans-serif", color=COLORS["navy"]),
        title_font=dict(size=18),
        legend_title_text="",
        hoverlabel=dict(bgcolor="white"),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#EDF1F6")
    return fig


def fmt_days(value: Any) -> str:
    return "—" if pd.isna(value) else f"{float(value):.1f} 天"


# =============================================================================
# UI sections
# =============================================================================
def render_header() -> None:
    left, right = st.columns([4, 1])
    with left:
        st.title("Recruitment Dashboard")

    with right:
        st.markdown(
            f"<div style='text-align:right;color:{COLORS['muted']};padding-top:18px'>Updated<br><b>{datetime.now():%Y-%m-%d %H:%M}</b></div>",
            unsafe_allow_html=True,
        )


def render_executive_overview(
    talents: pd.DataFrame,
    vacancies: pd.DataFrame,
    funnel: pd.DataFrame,
    durations: pd.DataFrame,
    aging: pd.DataFrame,
) -> None:
    st.subheader("Executive pulse")
    active_vacancies = int((vacancies["status"].astype(str).str.upper() == "ACTIVE").sum())
    hired = int((talents["current_status"] == "報到").sum())
    total = talents["source_id"].nunique()
    conversion = hired / total * 100 if total else 0
    avg_cycle = pd.NA

    first_stage = durations[durations["stage"] == STAGE_ORDER[0]][["source_id", "entered_at"]]
    hired_stage = durations[durations["stage"] == STAGE_ORDER[-1]][["source_id", "entered_at"]]
    if not first_stage.empty and not hired_stage.empty:
        cycle = first_stage.merge(hired_stage, on="source_id", suffixes=("_start", "_hire"))
        avg_cycle = (cycle["entered_at_hire"] - cycle["entered_at_start"]).dt.total_seconds().div(86400).mean()

    overdue = int((aging.get("risk", pd.Series(dtype=str)).astype(str) == "逾期").sum()) if not aging.empty else 0
    blocked = int((pd.to_numeric(talents["block"], errors="coerce").fillna(0) == 1).sum())

    cols = st.columns(6)
    metrics = [
        ("Talents", f"{total:,}", None),
        ("Active Vacancy", f"{active_vacancies:,}", None),
        ("Onboard", f"{hired:,}", None),
        ("Onboard Rate", f"{conversion:.1f}%", None),
        ("Average Hiring Days", fmt_days(avg_cycle), None),
        ("Overdue/Blocked", f"{overdue} / {blocked}", None),
    ]
    for col, (label, value, delta) in zip(cols, metrics):
        col.metric(label, value, delta)

    if overdue > 0:
        st.warning(f"目前有 {overdue} 位候選人超過階段 SLA；建議優先查看「流程效率」頁的卡關清單。")

def calculate_stage_rates(talents: pd.DataFrame) -> pd.DataFrame:

    STAGES = [
        "AI REVIEW",
        "感興趣",
        "電邀",
        "電訪",
        "面邀",
        "面試",
        "OFFER",
    ]

    status_counts = (
        talents["current_status"]
        .fillna("")
        .value_counts()
        .to_dict()
    )

    rows = []

    for idx, stage in enumerate(STAGES):

        fail_status = f"{stage}-NOT PASS"

        # 進入該階段的人數
        entered = status_counts.get(fail_status, 0)

        for future_stage in STAGES[idx:]:
            entered += status_counts.get(future_stage, 0)

        # 通過該階段的人數
        passed = 0

        if idx < len(STAGES) - 1:

            for future_stage in STAGES[idx + 1:]:
                passed += status_counts.get(future_stage, 0)

        else:
            passed = status_counts.get("報到", 0)

        fail_count = status_counts.get(fail_status, 0)

        reject_count = 0
        unqualified_count = 0

        if stage=="面邀" or stage=="電邀" or stage=="OFFER":
            reject_count = fail_count
        else:
            unqualified_count = fail_count

        rows.append({
            "stage": stage,
            "entered": entered,
            "passed": passed,
            "reject": reject_count,
            "unqualified": unqualified_count,
            "pass_rate": round(
                passed / entered * 100,
                1
            ) if entered else 0,
            "reject_rate": round(
                reject_count / entered * 100,
                1
            ) if entered else 0,
            "unqualified_rate": round(
                unqualified_count / entered * 100,
                1
            ) if entered else 0,
        })

    return pd.DataFrame(rows)

def render_funnel_tab(
    talents: pd.DataFrame,
    durations: pd.DataFrame,
    aging: pd.DataFrame,
) -> None:
    funnel = calculate_funnel(talents)
    time_summary = stage_time_summary(durations)

    st.subheader("Recruitment funnel")


    c1, c2 ,c3 = st.columns([1, 1,1])
    with c1:
        fig = go.Figure(go.Funnel(
            y=funnel["stage"],
            x=funnel["count"],
            textinfo="value+percent initial",
            marker={"color": px.colors.sequential.Blues[::-1][:len(funnel)]},
            connector={"line": {"color": "#CFD8E6"}},
            hovertemplate="%{y}<br>人數：%{x}<extra></extra>",
        ))
        fig.update_layout(title="各階段到達人數")
        st.plotly_chart(style_figure(fig, 460), use_container_width=True)

    with c2:
        rate = funnel.iloc[1:].copy()
        fig = px.bar(
            rate,
            x="stage_pass_rate",
            y="stage",
            orientation="h",
            text=rate["stage_pass_rate"].map(lambda x: f"{x:.1f}%"),
            color="stage_pass_rate",
            color_continuous_scale="Blues",
            title="Stage Pass Rate",
        )
        fig.update_traces(textposition="outside", hovertemplate="%{y}<br>Pass Rate：%{x:.1f}%<extra></extra>")
        fig.update_layout(coloraxis_showscale=False, xaxis_title="Pass Rate (%)", yaxis_title="")
        st.plotly_chart(style_figure(fig, 460), use_container_width=True)
    with c3:
        stage_df = calculate_stage_rates(talents)
        show_df = stage_df.melt(
            id_vars="stage",
            value_vars=[
                "pass_rate",
                "reject_rate",
                "unqualified_rate"
            ],
            var_name="result",
            value_name="rate"
        )
        show_df["result"] = show_df["result"].replace({
            "pass_rate": "Passed",
            "reject_rate": "Rejected",
            "unqualified_rate": "Unqualified",
        })
        fig = px.bar(
            show_df,
            x="stage",
            y="rate",
            color="result",
            barmode="stack",
            color_discrete_map={
                "Passed": "#0204a0",
                "Rejected": "#9e0000",
                "Unqualified": "#caa409",
            }
        )
        fig.update_layout(title="Distribution Chart")
        st.plotly_chart(style_figure(fig, 460), use_container_width=True)
    st.subheader("Stage time profile")
    if time_summary.empty:
        st.info("Log 尚無法解析出階段異動。請配置 STAGE_ORDER、STATUS_ALIASES 與 extract_log_stage()。")
    else:
        fig = go.Figure()
        fig.add_bar(
            x=time_summary["stage"].astype(str),
            y=time_summary["avg_days"],
            name="Average Days",
            marker_color=COLORS["blue"],
            text=time_summary["avg_days"].map(lambda x: f"{x:.1f}"),
            textposition="outside",
        )
        fig.add_scatter(
            x=time_summary["stage"].astype(str),
            y=time_summary["p75_days"],
            name="P75 Days",
            mode="lines+markers",
            line=dict(color=COLORS["amber"], width=3),
        )
        fig.update_layout(title="平均停留時間與 P75", yaxis_title="日曆天", xaxis_title="")
        st.plotly_chart(style_figure(fig), use_container_width=True)

        display = time_summary.copy()
        display["stage"] = display["stage"].astype(str)
        display = display.rename(columns={
            "stage": "階段", "avg_days": "平均天數", "median_days": "中位數",
            "p75_days": "P75 天數", "candidates": "樣本數", "current_count": "目前人數",
        })
        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "平均天數": st.column_config.NumberColumn(format="%.1f"),
                "中位數": st.column_config.NumberColumn(format="%.1f"),
                "P75 天數": st.column_config.NumberColumn(format="%.1f"),
            },
        )

    st.subheader("Aging & bottleneck watchlist")
    if aging.empty:
        st.info("目前沒有可計算的在途階段資料。")
    else:
        risk_counts = aging["risk"].astype(str).value_counts().reindex(["逾期", "接近 SLA", "正常"], fill_value=0)
        cols = st.columns(3)
        for col, label, color in zip(cols, risk_counts.index, [COLORS["red"], COLORS["amber"], COLORS["green"]]):
            col.markdown(
                f"<div style='background:white;border-left:6px solid {color};padding:16px;border-radius:14px'><b>{label}</b><br><span style='font-size:28px'>{risk_counts[label]:,}</span></div>",
                unsafe_allow_html=True,
            )

        show = aging[[
            "name","source","source_id", "vacancy", "stage", "entered_at", "duration_days", "sla_days",
            "overdue_days", "risk", "block_reason",
        ]].copy()
        render_funnel_list(show)

@st.fragment
def render_funnel_list(show: pd.DataFrame):
    if show.empty:
        st.info("目前沒有可編輯資料。")
        return

    if "aging_editor_version" not in st.session_state:
        st.session_state["aging_editor_version"] = 0

    editor_key = (
        f"aging_editor_"
        f"{st.session_state['aging_editor_version']}"
    )

    # 每次都使用外部最新傳進來的 show
    original = show.copy()

    # 統一唯一鍵格式
    original["source"] = (
        original["source"]
        .astype("string")
        .str.strip()
    )

    original["source_id"] = (
        original["source_id"]
        .astype("string")
        .str.strip()
    )

    # 檢查是否有重複的人
    duplicate_mask = original.duplicated(
        subset=["source", "source_id"],
        keep=False,
    )

    if duplicate_mask.any():
        st.error(
            "Aging 資料中存在重複的 source + source_id，"
            "同一個人有多筆 current stage，請先檢查 "
            "build_stage_durations() 的 is_current。"
        )

        st.dataframe(
            original.loc[
                duplicate_mask,
                [
                    "name",
                    "source",
                    "source_id",
                    "stage",
                    "entered_at",
                ],
            ].sort_values(
                ["source", "source_id", "entered_at"]
            ),
            use_container_width=True,
            hide_index=True,
        )

        return

    # 使用複合鍵作為 DataFrame index
    # 即使表格排序，stage 仍然會和同一個人綁定
    original["_candidate_key"] = (
        original["source"]
        + "::"
        + original["source_id"]
    )

    original = original.set_index(
        "_candidate_key",
        drop=True,
    )

    max_duration = pd.to_numeric(
        original["duration_days"],
        errors="coerce",
    ).max()

    if pd.isna(max_duration):
        max_duration = 30

    with st.form(
        f"edit_form_{st.session_state['aging_editor_version']}"
    ):
        edited = st.data_editor(
            original,
            use_container_width=True,
            hide_index=True,
            disabled=[
                "name",
                "source",
                "source_id",
                "vacancy",
                "entered_at",
                "duration_days",
                "sla_days",
                "overdue_days",
                "risk",
                "block_reason",
            ],
            column_config={
                "duration_days": st.column_config.ProgressColumn(
                    min_value=0,
                    max_value=max(
                        30,
                        int(max_duration),
                    ),
                    format="%.1f days",
                ),
                "overdue_days": (
                    st.column_config.NumberColumn(
                        format="%.1f"
                    )
                ),
                "stage": st.column_config.SelectboxColumn(
                    options=STAGE_ORDER + NOT_PASS,
                    required=True,
                ),
                "entered_at": (
                    st.column_config.DatetimeColumn(
                        format="YYYY-MM-DD HH:mm"
                    )
                ),
            },
            key=editor_key,
        )

        col1, col2 = st.columns([1, 1])

        with col1:
            save = st.form_submit_button(
                "Save",
                type="primary",
                use_container_width=True,
            )

        with col2:
            cancel = st.form_submit_button(
                "Cancel",
                use_container_width=True,
            )

    if save:
        try:
            # 用 candidate key 對齊，不使用 row position
            edited = edited.reindex(original.index)

            original_stage = (
                original["stage"]
                .fillna("")
                .astype(str)
            )

            edited_stage = (
                edited["stage"]
                .fillna("")
                .astype(str)
            )

            changed_mask = (
                original_stage != edited_stage
            )

            changed_rows = edited.loc[changed_mask]

            if changed_rows.empty:
                st.warning("No changes detected.")
                return

            edit = []

            for candidate_key, row in changed_rows.iterrows():
                # source/source_id/stage 全部來自同一列
                edit.append(
                    {
                        "source": str(row["source"]),
                        "source_id": str(row["source_id"]),
                        "updates": {
                            "current_status": row["stage"],
                        },
                    }
                )

                # 額外顯示 key，方便確認人與狀態
                st.write(
                    {
                        "candidate_key": candidate_key,
                        "name": row["name"],
                        "source": row["source"],
                        "source_id": row["source_id"],
                        "old_stage": original.loc[
                            candidate_key,
                            "stage",
                        ],
                        "new_stage": row["stage"],
                    }
                )

            request_changes = {
                "edit": edit,
                "operator": st.session_state["username"],
            }

            st.write(
                "Request payload:",
                request_changes,
            )

            result = TalentAPI.update_talent_with_log(
                request_changes
            )

            if isinstance(result, dict):
                success = result.get("success", False)
                message = result.get(
                    "message",
                    "Update failed.",
                )
                error = result.get("error")

            else:
                success = result.success
                message = (
                    result.message
                    or "Update failed."
                )
                error = getattr(
                    result,
                    "error",
                    None,
                )

            if not success:
                st.error(message)

                if error:
                    st.code(error)

                return

            # 建立新的 editor widget
            st.session_state[
                "aging_editor_version"
            ] += 1

            st.success(message)
            fetch_report_data.clear()
            # 完整重新執行，重新抓 API 並計算 aging
            st.rerun(scope="app")

        except Exception as e:
            st.error(f"Update failed: {e}")
            st.exception(e)

    if cancel:
        # 不需要檢查 edited_rows
        # Cancel 就直接丟棄目前 widget
        st.session_state[
            "aging_editor_version"
        ] += 1

        st.info("Changes cancelled.")
        st.rerun(scope="fragment")

def render_vacancy_tab(talents: pd.DataFrame, vacancies: pd.DataFrame, durations: pd.DataFrame) -> None:
    st.subheader("Vacancy portfolio")
    stats = talents.groupby("vacancy", dropna=False).agg(
        candidates=("source_id", "nunique"),
        avg_score=("score", "mean"),
        onboarded=("current_status", lambda s: (s == "報到").sum()),
        interviewed = ("current_status", lambda s: ((s == "報到")| (s == "面試")).sum()) 
    ).reset_index()
    stats["hire_rate"] = stats["onboarded"] / stats["candidates"].replace(0, pd.NA) * 100
    stats["interview_rate"] = stats["interviewed"] / stats["candidates"].replace(0, pd.NA) * 100

    if not durations.empty:
        first = durations[durations["stage"] == STAGE_ORDER[0]][["source_id", "vacancy", "entered_at"]]
        last = durations[durations["stage"] == STAGE_ORDER[-1]][["source_id", "entered_at"]]
        cycles = first.merge(last, on="source_id", suffixes=("_start", "_end"))
        cycles["cycle_days"] = (cycles["entered_at_end"] - cycles["entered_at_start"]).dt.total_seconds() / 86400
        cycle_stats = cycles.groupby("vacancy")["cycle_days"].mean().rename("avg_cycle_days")
        stats = stats.merge(cycle_stats, on="vacancy", how="left")
    else:
        stats["avg_cycle_days"] = pd.NA

    active = vacancies[vacancies["status"].astype(str).str.upper() == "ACTIVE"].copy()
    # vacancy in talent may store title or id; support both.
    meta_by_title = active.rename(columns={"position_title": "vacancy"})
    meta_by_id = active.rename(columns={"vacancy_id": "vacancy"})
    meta_cols = ["vacancy", "position_title", "lab", "senior", "work_location", "created_at"]
    for frame in (meta_by_title, meta_by_id):
        for col in meta_cols:
            if col not in frame.columns:
                frame[col] = pd.NA
    metadata = pd.concat([meta_by_title[meta_cols], meta_by_id[meta_cols]], ignore_index=True).drop_duplicates("vacancy")
    stats = stats.merge(metadata, on="vacancy", how="left")

    c1, c2 = st.columns(2)
    with c1:
        top = stats.nlargest(12, "candidates").sort_values("candidates")
        fig = px.bar(top, x="candidates", y="vacancy", orientation="h", color="avg_score", color_continuous_scale="Blues", title="職缺人才量與平均分數")
        fig.update_layout(xaxis_title="候選人數", yaxis_title="", coloraxis_colorbar_title="平均分")
        st.plotly_chart(style_figure(fig), use_container_width=True)
    with c2:
        plot = stats.dropna(subset=["candidates", "hire_rate"]).copy()
        plot["bubble"] = plot["candidates"].clip(lower=1)
        fig = px.scatter(
            plot, x="candidates", y="hire_rate", size="bubble", color="avg_cycle_days",
            hover_name="vacancy", color_continuous_scale="RdYlGn_r",
            title="職缺健康矩陣：人才量 × 報到率",
        )
        fig.update_layout(xaxis_title="候選人數", yaxis_title="報到率 (%)", coloraxis_colorbar_title="週期天數")
        st.plotly_chart(style_figure(fig), use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        plot = stats.dropna(subset=["candidates", "interview_rate"]).copy()
        plot["bubble"] = plot["candidates"].clip(lower=1)
        fig = px.scatter(
            plot, x="candidates", y="interview_rate", size="bubble", color="avg_cycle_days",
            hover_name="vacancy", color_continuous_scale="RdYlGn_r",
            title="人才量 × 面試率",
        )
        fig.update_layout(xaxis_title="候選人數", yaxis_title="面試率 (%)", coloraxis_colorbar_title="週期天數")
        st.plotly_chart(style_figure(fig), use_container_width=True)
    with c4:
        st.text("PASS")

    st.markdown("#### Active vacancy aging")
    active["open_days"] = (pd.Timestamp.now() - active["created_at"]).dt.total_seconds() / 86400
    active_show = active[["position_title", "lab", "senior", "work_location", "open_days", "updated_at"]].copy()
    active_show.columns = ["職缺", "Lab", "Senior", "工作地點", "開缺天數", "最後更新"]
    st.dataframe(active_show.sort_values("開缺天數", ascending=False), use_container_width=True, hide_index=True)


def render_source_tab(talents: pd.DataFrame) -> None:
    st.subheader("Source quality")
    source = talents.groupby("source", dropna=False).agg(
        candidates=("source_id", "nunique"),
        avg_score=("score", "mean"),
        interviews=("interview_time", lambda s: s.notna().sum()),
        onboarded=("current_status", lambda s: (s == "報到").sum()),
    ).reset_index()
    source["interview_rate"] = source["interviews"] / source["candidates"].replace(0, pd.NA) * 100
    source["hire_rate"] = source["onboarded"] / source["candidates"].replace(0, pd.NA) * 100

    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(source.sort_values("candidates", ascending=False), x="source", y="candidates", color="avg_score", text="candidates", color_continuous_scale="Blues", title="來源量與人才品質")
        fig.update_layout(xaxis_title="來源", yaxis_title="人才數", coloraxis_colorbar_title="平均分")
        st.plotly_chart(style_figure(fig), use_container_width=True)
    with c2:
        fig = px.scatter(source, x="interview_rate", y="hire_rate", size="candidates", color="avg_score", hover_name="source", color_continuous_scale="Viridis", title="來源效率矩陣")
        fig.update_layout(xaxis_title="面試率 (%)", yaxis_title="報到率 (%)", coloraxis_colorbar_title="平均分")
        st.plotly_chart(style_figure(fig), use_container_width=True)

    st.dataframe(source.sort_values("hire_rate", ascending=False), use_container_width=True, hide_index=True)


def render_geo_tab(talents: pd.DataFrame) -> None:
    st.subheader("Candidate geography")
    geo = add_coordinates(talents)
    located = geo.dropna(subset=["lat", "lon"]).copy()
    missing = geo[geo["lat"].isna() | geo["lon"].isna()]

    if located.empty:
        st.info("請先在 LOCATION_COORDINATES 補上縣市／鄉鎮座標，地圖就會自動啟用。")
    else:
        points = located.groupby(["city", "district", "lat", "lon"], as_index=False).agg(
            candidates=("source_id", "nunique"),
            avg_score=("score", "mean"),
        )
        fig = px.density_mapbox(
            points,
            lat="lat", lon="lon", z="candidates", radius=32,
            center={"lat": 23.7, "lon": 121.0}, zoom=6.5,
            mapbox_style="carto-positron",
            hover_name="district",
            hover_data={"city": True, "candidates": True, "avg_score": ":.1f", "lat": False, "lon": False},
            title="求職者居住地熱度",
        )
        fig.update_layout(height=620, margin=dict(l=0, r=0, t=50, b=0))
        st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        city = talents.groupby("city", dropna=False)["source_id"].nunique().reset_index(name="candidates").nlargest(15, "candidates")
        fig = px.bar(city.sort_values("candidates"), x="candidates", y="city", orientation="h", title="候選人主要縣市", color_discrete_sequence=[COLORS["blue"]])
        fig.update_layout(xaxis_title="候選人數", yaxis_title="")
        st.plotly_chart(style_figure(fig), use_container_width=True)
    with c2:
        district = talents.groupby(["city", "district"], dropna=False)["source_id"].nunique().reset_index(name="candidates").nlargest(15, "candidates")
        district["location"] = district["city"].fillna("").astype(str) + " " + district["district"].fillna("").astype(str)
        fig = px.bar(district.sort_values("candidates"), x="candidates", y="location", orientation="h", title="主要鄉鎮市區", color_discrete_sequence=[COLORS["cyan"]])
        fig.update_layout(xaxis_title="候選人數", yaxis_title="")
        st.plotly_chart(style_figure(fig), use_container_width=True)

    if not missing.empty:
        with st.expander(f"尚未匹配座標：{missing['source_id'].nunique()} 人"):
            missing_location = missing.groupby(["city", "district"], dropna=False)["source_id"].nunique().reset_index(name="人數")
            st.dataframe(missing_location.sort_values("人數", ascending=False), use_container_width=True, hide_index=True)


def render_user_tab(users: pd.DataFrame, logs: pd.DataFrame) -> None:
    st.subheader("User adoption & operational activity")
    active_users = int((users["status"].astype(str).str.upper() == "ACTIVE").sum())
    logged_30 = int((users["last_login"] >= pd.Timestamp.now() - pd.Timedelta(days=30)).sum())
    never_logged = int(users["last_login"].isna().sum())
    distinct_operators = logs["operator"].dropna().nunique()

    cols = st.columns(4)
    for col, item in zip(cols, [
        ("Active users", active_users), ("30 日登入", logged_30),
        ("從未登入", never_logged), ("期間操作人數", distinct_operators),
    ]):
        col.metric(item[0], f"{item[1]:,}")

    c1, c2 = st.columns(2)
    with c1:
        role = users.groupby("user_role", dropna=False)["user_id"].nunique().reset_index(name="users")
        fig = px.pie(role, names="user_role", values="users", hole=.58, title="使用者角色分布", color_discrete_sequence=px.colors.qualitative.Set2)
        st.plotly_chart(style_figure(fig), use_container_width=True)
    with c2:
        activity = logs.dropna(subset=["timestamp"]).copy()
        activity["date"] = activity["timestamp"].dt.date
        daily = activity.groupby("date").agg(operations=("log_id", "count"), operators=("operator", "nunique")).reset_index()
        fig = go.Figure()
        fig.add_bar(x=daily["date"], y=daily["operations"], name="操作數", marker_color=COLORS["blue"])
        fig.add_scatter(x=daily["date"], y=daily["operators"], name="操作者數", yaxis="y2", mode="lines", line=dict(color=COLORS["amber"], width=3))
        fig.update_layout(title="每日系統活動", yaxis_title="操作數", yaxis2=dict(title="操作者數", overlaying="y", side="right"))
        st.plotly_chart(style_figure(fig), use_container_width=True)

    operator = logs.groupby("operator", dropna=False).agg(
        operations=("log_id", "count"),
        candidates_touched=("source_id", "nunique"),
        last_activity=("timestamp", "max"),
        errors=("error_message", lambda s: s.fillna("").astype(str).str.strip().ne("").sum()),
    ).reset_index().sort_values("operations", ascending=False)
    st.markdown("#### Operator activity")
    st.caption("這是系統採用與工作量觀察，不建議直接作為個人績效排名。")
    st.dataframe(operator, use_container_width=True, hide_index=True)


def render_data_quality_tab(talents: pd.DataFrame, logs: pd.DataFrame, vacancies: pd.DataFrame, users: pd.DataFrame) -> None:
    st.subheader("Data quality & system health")
    checks = []

    def add_check(domain: str, issue: str, affected: int, total: int) -> None:
        checks.append({
            "domain": domain,
            "issue": issue,
            "affected": affected,
            "total": total,
            "rate": affected / total * 100 if total else 0,
        })

    total_t = len(talents)
    add_check("Talent", "缺少 current_status", int(talents["current_status"].eq("").sum() + talents["current_status"].isna().sum()), total_t)
    add_check("Talent", "缺少 vacancy", int(talents["vacancy"].fillna("").astype(str).str.strip().eq("").sum()), total_t)
    add_check("Talent", "缺少 received_time", int(talents["received_time"].isna().sum()), total_t)
    add_check("Talent", "缺少 city/district", int((talents["city"].isna() | talents["district"].isna()).sum()), total_t)
    add_check("Talent", "疑似重複 email", int(talents["email"].dropna().duplicated(keep=False).sum()) if "email" in talents else 0, total_t)
    add_check("Log", "缺少 timestamp", int(logs["timestamp"].isna().sum()), len(logs))
    add_check("Log", "有 error_message", int(logs["error_message"].fillna("").astype(str).str.strip().ne("").sum()), len(logs))
    add_check("Vacancy", "缺少 Lab", int(vacancies["lab"].fillna("").astype(str).str.strip().eq("").sum()), len(vacancies))
    add_check("User", "從未登入", int(users["last_login"].isna().sum()), len(users))

    quality = pd.DataFrame(checks).sort_values("rate", ascending=False)
    fig = px.bar(quality, x="rate", y="issue", color="domain", orientation="h", text=quality["rate"].map(lambda x: f"{x:.1f}%"), title="資料缺漏／異常率")
    fig.update_layout(xaxis_title="受影響比例 (%)", yaxis_title="")
    st.plotly_chart(style_figure(fig, 480), use_container_width=True)
    st.dataframe(quality, use_container_width=True, hide_index=True)

    unknown = talents.loc[~talents["current_status"].isin(set(STAGE_ORDER) | TERMINAL_REJECT_STATUSES), "current_status"].value_counts().reset_index()
    unknown.columns = ["尚未設定的狀態", "筆數"]
    if not unknown.empty:
        st.warning("以下 current_status 尚未納入漏斗，請補進 STAGE_ORDER、STATUS_ALIASES 或 TERMINAL_REJECT_STATUSES。")
        st.dataframe(unknown, use_container_width=True, hide_index=True)


# =============================================================================
# Main
# =============================================================================
def dashboard() -> None:
    render_header()
    footer = load_custom_css()
    global LOCATION_COORDINATES
    LOCATION_COORDINATES = TalentAPI.get_taiwan_location().data
    today = datetime.now().date()
    default_start = today - timedelta(days=90)

    # =========================================================
    # 第一層篩選：日期
    # 日期會影響 API 查詢，因此需要先取得日期，再呼叫 API
    # =========================================================
    st.markdown("### 🔎 Dashboard Filters")

    filter_container = st.container(
        border=True
    )

    with filter_container:
        date_col, refresh_col = st.columns(
            [4, 1]
        )

        with date_col:
            date_range = st.date_input(
                "Received Time",
                value=(
                    default_start,
                    today
                ),
                max_value=today,
                key="report_date_range"
            )

        with refresh_col:
            # 用空白讓按鈕和 date_input 大致對齊
            st.markdown(
                "<div style='height: 28px;'></div>",
                unsafe_allow_html=True
            )

            refresh_button = st.button(
                "Reload",
                use_container_width=True,
                key="refresh_report_data"
            )

    # date_input 在只選到一個日期時，
    # 可能只回傳長度為 1 的 tuple
    if (
        not isinstance(
            date_range,
            (tuple, list)
        )
        or len(date_range) != 2
    ):
        st.info(
            "請完整選擇開始日期與結束日期。"
        )
        st.stop()

    if refresh_button:
        fetch_report_data.clear()
        st.rerun()

    # =========================================================
    # 呼叫 API
    # =========================================================
    with st.spinner(
        "Loading recruiting intelligence..."
    ):
        frames = fetch_report_data(
            str(date_range[0]),
            str(date_range[1])
        )

        talents, logs_104,logs_status,logs_user_management,logs_vacancy_management, vacancies, users = (
            normalize_frames(frames)
        )
    if not frames["_errors"].empty:
        st.error(
            "部分 API 載入失敗：\n"
            + "\n".join(
                frames["_errors"]["error"].tolist()
            )
        )
    # =========================================================
    # 建立篩選選項
    # =========================================================
    vacancy_options = sorted(
        talents["vacancy"]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda value: value.ne("")]
        .unique()
        .tolist()
    )

    source_options = sorted(
        talents["source"]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda value: value.ne("")]
        .unique()
        .tolist()
    )

    lab_options = sorted(
        vacancies["lab"]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda value: value.ne("")]
        .unique()
        .tolist()
    )

    recommender_options = sorted(
        talents["recommender"]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda value: value.ne("")]
        .unique()
        .tolist()
    )

    status_options = [
        status
        for status in STAGE_ORDER
        if status
    ]

    # =========================================================
    # 第二層篩選：職缺、來源、Lab、目前階段
    # =========================================================
    with filter_container:
        vacancy_col, source_col = st.columns(
            2
        )

        with vacancy_col:
            selected_vacancies = (
                st.multiselect(
                    "Vacancy",
                    options=vacancy_options,
                    placeholder="All",
                    key="report_vacancies"
                )
            )

        with source_col:
            selected_sources = (
                st.multiselect(
                    "Source",
                    options=source_options,
                    placeholder="All",
                    key="report_sources"
                )
            )
        
        lab_col, status_col,recommender_col = st.columns(
            3
        )

        with lab_col:
            selected_labs = st.multiselect(
                "Lab",
                options=lab_options,
                placeholder="All",
                key="report_labs"
            )

        with status_col:
            selected_statuses = (
                st.multiselect(
                    "Status",
                    options=status_options,
                    placeholder="All",
                    key="report_statuses"
                )
            )

        filter_info_col, clear_col = (
            st.columns([4, 1])
        )

        with recommender_col:
            selected_recommender = st.multiselect("Recommender",options = recommender_options,placeholder = "All Recommender",key = "report_recommender")

        with filter_info_col:
            active_filter_count = sum([
                bool(selected_vacancies),
                bool(selected_sources),
                bool(selected_labs),
                bool(selected_statuses),
                bool(selected_recommender)
            ])

            if active_filter_count:
                st.caption(
                    f"目前已使用 "
                    f"{active_filter_count} 組篩選條件"
                )
            else:
                st.caption(
                    "Showing all data within the selected date range."
                )

        with clear_col:
            clear_filters = st.button(
                "Clear",
                use_container_width=True,
                key="clear_report_filters"
            )

    # =========================================================
    # 清除篩選
    # =========================================================
    if clear_filters:
        filter_keys = [
            "report_vacancies",
            "report_sources",
            "report_labs",
            "report_statuses",
            "report_recommender"
        ]

        for key in filter_keys:
            st.session_state.pop(
                key,
                None
            )

        st.rerun()

    # =========================================================
    # 套用原本的 Filter
    # =========================================================
    talents, logs_104, vacancies, users = (
        filter_data(
            talents=talents,
            logs=logs_104,
            vacancies=vacancies,
            users=users,
            date_range=date_range,
            selected_vacancies=(
                selected_vacancies
            ),
            selected_sources=(
                selected_sources
            ),
            selected_labs=selected_labs,
            selected_recommender = selected_recommender
        )
    )
    
    _, logs_status, _, _ = (
        filter_data(
            talents=talents,
            logs=logs_status,
            vacancies=vacancies,
            users=users,
            date_range=date_range,
            selected_vacancies=(
                selected_vacancies
            ),
            selected_sources=(
                selected_sources
            ),
            selected_labs=selected_labs,
            selected_recommender = selected_recommender
        )
    )
    # filter_data 原本沒有 current_status，
    # 所以在這裡額外篩選
    if selected_statuses:
        talents = talents[
            talents["current_status"]
            .astype(str)
            .isin(selected_statuses)
        ].copy()

        # Status 篩選後，Log 也要同步限制候選人
        filtered_source_ids = set(
            talents["source_id"]
            .dropna()
            .astype(str)
        )

        logs_104 = logs_104[
            logs_104["source_id"]
            .astype(str)
            .isin(filtered_source_ids)
        ].copy()
        logs_status = logs_status[
            logs_status["source_id"]
            .astype(str)
            .isin(filtered_source_ids)
        ].copy()

    # =========================================================
    # 建立報表分析資料
    # =========================================================

    analyze_talents = talents[talents["score"]>=60]
    events = build_stage_events(
        logs_status,
        analyze_talents
    )

    durations = build_stage_durations(
        events,
        analyze_talents
    )

    aging = build_aging_table(
        durations,
        analyze_talents
    )

    funnel = calculate_funnel(
        analyze_talents
    )

    # =========================================================
    # Executive Overview
    # =========================================================
    render_executive_overview(
        talents,
        vacancies,
        funnel,
        durations,
        aging
    )

    # =========================================================
    # Dashboard Tabs
    # =========================================================
    tabs = st.tabs([
        "流程效率",
        "職缺分析",
        "來源品質",
        "地理熱圖",
        "使用情形",
        "資料品質",
    ])

    with tabs[0]:
        render_funnel_tab(
                talents,
                durations,
                aging
            )

    with tabs[1]:
        render_vacancy_tab(
            talents,
            vacancies,
            durations
        )

    with tabs[2]:
        render_source_tab(
            talents
        )

    with tabs[3]:
        render_geo_tab(
            talents
        )

    with tabs[4]:
        logs = pd.concat([logs_104, logs_user_management,logs_vacancy_management]).reset_index()
        render_user_tab(
            users,
            logs
        )

    with tabs[5]:
        render_data_quality_tab(
            talents,
            logs_104,
            vacancies,
            users
        )

    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.markdown(f"""
        <div style="text-align: center; color: #666; padding: 2rem 0;">
            <p>{footer}</p>
        </div>
        """, unsafe_allow_html=True)