# frontend/streamlit_app.py
"""

"""
import os
import json
import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime, date,timedelta
import urllib.parse
from bs4 import BeautifulSoup
import time
from share import render_candidate_readonly
from streamlit_quill import st_quill
from threading import Thread
import queue
import traceback
import re
from config import API_URL
import numpy as np
import streamlit_authenticator as stauth
from api_client import TalentAPI, LogAPI, UserAPI,SettingsAPI,APIResponse,VacancyAPI,LabAPI
from talent_search_engine import (
    FilterConditions ,
    TalentSearchEngine,
    APIConfig)
from user import show_user_page
from auth import AuthConfigGenerator
from css import load_custom_css
from vacancy import show_vacancy_page
from hr_analytics_dashboard import dashboard
from create_candidate import create_new
from resume import msg_backup
import copy
from settings import show_settings_page
from uuid import uuid4

# from config import config


# ==========================================
# 0. Global Configurations
# ==========================================
st.set_page_config(
    layout="wide", 
    page_title="Talent Management System", 
    page_icon="📑"
)
talent_api = TalentAPI()
log_api = LogAPI()
STATIC_DIR = Path(__file__).parent / "static"
PLACEHOLDER_PATTERN = re.compile(r"\$\$([a-zA-Z0-9_]+)\$\$")
# ==========================================
# 1. Authentication Configurationst.rerun()
# ==========================================

config = AuthConfigGenerator.generate_config()

# print(config["credentials"])

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# ==========================================
# 2. Logout Handler
# ==========================================
if st.query_params.get("logout") == "true":
    st.query_params.clear()
    
    # 1. 先執行 logout (清除 cookie)
    authenticator.logout('Logout', 'main')
    st.cache_data.clear()
    # 2. 再清除 session_state
    st.session_state.clear()
    
    # 3. 顯示訊息
    st.success("✅ Logged out successfully!")
    
    # 4. 停止執行
    st.stop()

# ==========================================
# 3. Login Process
# ==========================================
login_result = authenticator.login(location='main', key='login_widget')
auth_status = st.session_state.get("authentication_status")

if auth_status is False:
    st.error('❌ Username/password combination is incorrect.')
    st.stop()
elif auth_status is None:
    st.info("🔒 Please input valid system credentials to access the talent roster.")
    st.stop()
else:
# ==========================================
# 4. User Session Variables
# ==========================================
    UserAPI.login(user_account=st.session_state["username"])
    current_user = st.session_state["username"]
    user_display_name = st.session_state["name"]
    user_role = config["credentials"]["usernames"][current_user]["role"]
    st.session_state["user_role"] = user_role
    


# ==========================================
# 5. Utility Functions
# ==========================================


def get_absolute_static_url(relative_file_path):
    """生成靜態檔案的絕對 URL"""
    if not relative_file_path:
        return ""
    
    clean_path = relative_file_path.replace("\\", "/")
    part = clean_path.split("/static")[-1]
    clean_path = "app/static" + part
    encoded_path = urllib.parse.quote(clean_path)
    
    try:
        port = st.config.get_option("server.port")
    except:
        port = 8501
    
    return f"http://localhost:{port}/{encoded_path}"

# ==========================================
# 7. Session State Initialization
# ==========================================
def initialize_session_state():
    """初始化所有需要的 session state"""
    
    

    if "editor_version" not in st.session_state:
        st.session_state["editor_version"] = 0
    
    if "talent_loader" not in st.session_state:
        api_config = APIConfig(base_url=API_URL)
        st.session_state["talent_loader"] = TalentSearchEngine(
            api_config=api_config
        )
    if "changed" not in st.session_state:
        st.session_state["changed"] = False

    if "current_talent_data" not in st.session_state:
        st.session_state["current_talent_data"] = pd.DataFrame()
    
    if "loader_state" not in st.session_state:
        st.session_state["loader_state"] = None
    
    if "current_filters" not in st.session_state:
        st.session_state["current_filters"] = {}
    
    if "last_selected_id" not in st.session_state:
        st.session_state["last_selected_id"] = None
    
    if "editor_changes" not in st.session_state:
        st.session_state["editor_changes"] = {}
        
    if "warning" not in st.session_state:
        st.session_state["warning"] = []

    if "edited_df" not in st.session_state:
        st.session_state["edited_df"] = pd.DataFrame()

    if "create_vac" not in st.session_state:
        st.session_state["create_vac"] = False

    if "create_talent" not in st.session_state:
        st.session_state["create_talent"] = False

    if "create_talent_save" not in st.session_state:
        st.session_state["create_talent_save"] = False

    if "modify_mode" not in st.session_state:
        st.session_state["modify_mode"] = False

def reset_session_state():
    """重置所有需要的 session state"""
    

    st.session_state["editor_version"] = 0


    api_config = APIConfig(base_url=API_URL)
    st.session_state["talent_loader"] = TalentSearchEngine(
        api_config=api_config
    )

    st.session_state["changed"] = False

    st.session_state["current_talent_data"] = pd.DataFrame()

    st.session_state["loader_state"] = None

    st.session_state["current_filters"] = {}

    st.session_state["last_selected_id"] = None

    st.session_state["editor_changes"] = {}

    st.session_state["warning"] = []

    st.session_state["edited_df"] = pd.DataFrame()

    st.session_state["create_vac"] = False

    st.session_state["create_talent"] = False

    st.session_state["create_talent_save"] = False


# ==========================================
# 8. 🔄 改造後的篩選器 (呼叫 API 取得選項)
# ==========================================
def render_main_filter_section():
    """✅ 改造後:透過 API 取得篩選選項"""
    
    st.markdown("## Search / Filter")
    
    # 🌟 呼叫後端 API 取得篩選選項
    cities_result = talent_api.get_distinct_values("city")
    statuses_result = talent_api.get_distinct_values("current_status")
    sources_result = talent_api.get_distinct_values("source")

    vacancies_result = talent_api.get_distinct_values("vacancy")


    degrees_result = talent_api.get_distinct_values("education_degree")
    
    cities = cities_result.data if cities_result.success else []
    statuses = statuses_result.data if statuses_result.success else []
    sources = sources_result.data if sources_result.success else []
    vacancies = vacancies_result.data if vacancies_result.success else []
    degrees = degrees_result.data if degrees_result.success else []
    filters = {}
    
    # 關鍵字搜尋
    filter_container = st.empty()
    with filter_container.container():
        search_keyword = st.text_input(
            "**Keywords**",
            placeholder="Name, Company, Vacancy...",
            key="filter_search"
        )
        
        if search_keyword:
            filters['search_keyword'] = search_keyword
        
        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
        
        # 主要篩選條件
        col1, col2, col3 = st.columns(3)
        
        with col1:
            selected_statuses = st.multiselect(
                "**Hiring Status**",
                options=statuses,
                default=None,
                key="filter_status"
            )
            if selected_statuses:
                filters['current_status'] = selected_statuses
        with col2:
            selected_cities = st.multiselect(
                "**City**",
                options=cities,
                default=None,
                key="filter_city"
            )
            if selected_cities:
                filters['city'] = selected_cities
        
        with col3:
            selected_sources = st.multiselect(
                "**Source**",
                options=sources,
                default=None,
                key="filter_source"
            )
            if selected_sources:
                filters['source'] = selected_sources
        
        # 職缺與學歷
        col4, col5 = st.columns(2)
        
        with col4:
            selected_vacancies = st.multiselect(
                "**Vacancy**",
                options=vacancies,
                default=None,
                key="filter_vacancy"
            )
            if selected_vacancies:
                filters['vacancy'] = selected_vacancies
        
        with col5:
            selected_degrees = st.multiselect(
                "**Degree**",
                options=degrees,
                default=None,
                key="filter_degree"
            )
            if selected_degrees:
                filters['education_degree'] = selected_degrees
        
        # 範圍篩選
        col6, col7, col8 = st.columns(3)
        
        with col6:
            score_range = st.slider(
                "**AI Score**",
                min_value=0.0,
                max_value=100.0,
                value=(0.0, 100.0),
                step=5.0,
                key="filter_score"
            )
            if score_range != (0.0, 100.0):
                filters['score_min'] = score_range[0]
                filters['score_max'] = score_range[1]
        
        with col7:
            age_range = st.slider(
                "**Age**",
                min_value=18,
                max_value=65,
                value=(18, 65),
                step=1,
                key="filter_age"
            )
            if age_range != (18, 65):
                filters['age_min'] = age_range[0]
                filters['age_max'] = age_range[1]
        
        with col8:
            exp_range = st.slider(
                "**Work Experience**",
                min_value=0.0,
                max_value=30.0,
                value=(0.0, 30.0),
                step=0.5,
                key="filter_exp"
            )
            if exp_range != (0.0, 30.0):
                filters['exp_years_min'] = exp_range[0]
                filters['exp_years_max'] = exp_range[1]
        
        # 操作按鈕
        col9, col10, col11, col12 = st.columns([2, 2, 2, 2])
        
        with col9:
            exclude_blocked = st.checkbox(
                "Exclude Blacklist",
                value=True,
                key="filter_exclude_blocked"
            )
            filters['exclude_blocked'] = exclude_blocked
        
        with col10:
            st.write("")
        
        with col11:
            apply_filters = st.button(
                "Apply",
                type="primary",
                use_container_width=True,
                key="btn_apply_filters"
            )
        
        with col12:
            clear_filters = st.button(
                "Clear",
                type="secondary",
                use_container_width=True,
                key="btn_clear_filters"
            )
        
        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.session_state["changed"] = detect_changes(st.session_state["edited_df"])

    return filters, apply_filters, clear_filters

# ==========================================
# 9. Data Loading Functions
# ==========================================
def load_initial_data(filters_dict):
    """初始載入資料"""
    
    loader = st.session_state["talent_loader"]
    
    # 2. 建立篩選條件
    filter_conditions = FilterConditions(
        current_status=filters_dict.get('current_status'),
        city=filters_dict.get('city'),
        source=filters_dict.get('source'),
        vacancy=filters_dict.get('vacancy'),
        education_degree=filters_dict.get('education_degree'),
        score_min=filters_dict.get('score_min'),
        score_max=filters_dict.get('score_max'),
        age_min=filters_dict.get('age_min'),
        age_max=filters_dict.get('age_max'),
        exp_years_min=filters_dict.get('exp_years_min'),
        exp_years_max=filters_dict.get('exp_years_max'),
        exclude_blocked=filters_dict.get('exclude_blocked', True),
        search_keyword=filters_dict.get('search_keyword'),
    )

    result = loader.search(
        username = st.session_state["username"],
        filters=filter_conditions,
        page=1,
        page_size= 30,
    )

    loaded_count = result.page*result.page_size
    state = { "total_count" :result.total ,"loaded_count":loaded_count if loaded_count<result.total else result.total , "current_page":result.page ,"has_more":result.total>result.page*result.page_size,"progress_percentage": 100*(loaded_count/result.total) if loaded_count<result.total else 100}
    st.session_state["current_talent_data"] = pd.DataFrame(result.items)
    st.session_state["loader_state"] = state
    st.session_state["current_filters"] = filter_conditions
    st.session_state["edited_df"] = st.session_state["current_talent_data"]
    
    return result

def load_more_data():
    """載入更多資料"""
    loader = st.session_state["talent_loader"]
    page = st.session_state["loader_state"]["current_page"]
    result = loader.search(
        username = st.session_state["username"],
        filters = st.session_state["current_filters"],
        page = page+1,
        page_size = 30
    )
    
    if result.items:
        new_df = pd.DataFrame(result.items)

        st.session_state["current_talent_data"] = pd.concat([
            st.session_state["current_talent_data"],
            new_df
        ], ignore_index=True)
        st.session_state["edited_df"] = st.session_state["current_talent_data"]
        loaded_count = result.page*result.page_size
        state = { "total_count" :result.total ,"loaded_count":loaded_count if loaded_count<result.total else result.total , "current_page":result.page ,"has_more":result.total>result.page*result.page_size,"progress_percentage": 100*(loaded_count/result.total) if loaded_count<result.total else 100}
        st.session_state["loader_state"] = state
    
    return result

# ==========================================
# 10. 🔄 改造後的資料庫操作函數 (全部改為 API 呼叫)
# ==========================================
def DB_LOCK_ROW(source, source_id):
    """✅ 改造後:透過 API 鎖定"""
    result = talent_api.lock_talent(source, source_id)
    if not result.success:
        print(f"[API] ❌ 鎖定失敗: {result.error}")
    else:
        print(f"[API] ✅ {result.message}")

def DB_UNLOCK_ROW(source, source_id):
    """✅ 改造後:透過 API 解鎖"""
    result = talent_api.unlock_talent(source, source_id)
    if not result.success:
        print(f"[API] ❌ 解鎖失敗: {result.error}")
    else:
        print(f"[API] ✅ {result.message}")

def DB_UPDATE_SCORE(source, source_id, score):
    """✅ 改造後:透過 API 更新分數"""
    result = talent_api.update_talent(
        source=source,
        source_id=source_id,
        updates={"score":score},
        operator=current_user
    )
    if not result.success:
        print(f"[API] ❌ 更新分數失敗: {result.error}")
    else:
        print(f"[API] ✅ {result.message}")

def DB_CHECK_IF_LOCKED(source, source_id):
    """✅ 改造後:透過 API 檢查鎖定狀態"""
    result = talent_api.check_if_locked(source, source_id)
    if not result.success:
        return False
    return result.data["is_locked"]

def detect_changes(edited_df):
    """檢測是否有變更"""
    original = st.session_state["current_talent_data"]
    current = edited_df  # ← 這是使用者剛編輯的資料
    if original.empty or current.empty:
        return False
    
    # 比較 DataFrame
    try:
        return not original.equals(current)
    except:
        return True
            
@st.fragment
def render_talent_editor(df_to_display, data, dynamic_editor_key,filters_dict):
    """將 data_editor 完全隔離在 fragment 中"""
    # editor_df = df_to_display.drop(["description","note","review_status"],axis =1)

    edited_df = st.data_editor(
        # editor_df,
        df_to_display,
        use_container_width=True,
        column_order=[
            "Select", "name", "id", "source", "source_id", "score", "score_distance","score_experience","score_age","score_education",
            "current_status", "gender", "age", "education_school", 
            "education_degree", "education_discipline", "education_mode", 
            "education_status", "vacancy", "city", "district", "phone", 
            "email", "update_time"
        ],
        # disabled=["id", "source", "source_id", "mail_id", "update_time", "score"],
        disabled=["id", "source", "source_id", "mail_id", "update_time", "score","description","note","review_status", "score_distance","score_experience","score_age","score_education"],
        column_config={
            "Select": st.column_config.CheckboxColumn("Select", default=False, width="small", pinned=True),
            "name": st.column_config.TextColumn("Name", width="small", pinned=True),
            "score": st.column_config.NumberColumn("AI Score", min_value=0, max_value=100, format="%.2f",required=False, default=None ),
            "current_status": st.column_config.SelectboxColumn(
                "Status",
                options=data["status"],
                required=True
            ),
            "vacancy": st.column_config.SelectboxColumn(
                "Vacancy",
                options=data["vacancies"],
                required=True
            ), 
            "education_discipline": st.column_config.SelectboxColumn(
                "Discipline",
                options=data["discipline"],
                required=True
            ),
            "education_status": st.column_config.SelectboxColumn(
                "Education Status",
                options=data["education_status"],
                required=True
            ),
            "education_mode": st.column_config.SelectboxColumn(
                "Education Mode",
                options=data["education_mode"],
                required=True
            ),              
            "education_degree": st.column_config.SelectboxColumn(
                "Degree",
                options=data["education_degree"],
                required=True
            ),
            "gender": st.column_config.SelectboxColumn(
                "Gender",
                options=data["gender"],
                required=True
            ),
            "city": st.column_config.SelectboxColumn(
                "City",
                options=data["city"],
                required=True
            ),
            "district": st.column_config.SelectboxColumn(
                "District",
                options=data["district"],
                required=True
            )   ,
            "score_distance": st.column_config.NumberColumn("Distance Score", min_value=0, max_value=100, format="%.2f",required=False, default=None ),
            "score_experience": st.column_config.NumberColumn("Experience Score", min_value=0, max_value=100, format="%.2f",required=False, default=None ),
            "score_age": st.column_config.NumberColumn("Age Score", min_value=0, max_value=100, format="%.2f",required=False, default=None ),
            "score_education": st.column_config.NumberColumn("Education Score", min_value=0, max_value=100, format="%.2f",required=False, default=None )
        },
        key=dynamic_editor_key,
        height=600,  
    )
    # st.write(st.session_state["edited_df"].compare(st.session_state["current_talent_data"]))
    

    # st.write(st.session_state["edited_df"])
    # st.write(st.session_state["current_talent_data"])
    # st.write(st.session_state["edited_df"].compare(st.session_state["current_talent_data"]))
    st.session_state["edited_df"] = edited_df.drop(columns=["Select"])  
    st.session_state["edited_df"]["note"] = st.session_state["current_talent_data"]["note"].values
    st.session_state["edited_df"]["description"] = st.session_state["current_talent_data"]["description"].values
    st.session_state["edited_df"]["review_status"] = st.session_state["current_talent_data"]["review_status"].values
    st.session_state["edited_df"] = st.session_state["edited_df"][st.session_state["current_talent_data"].columns]
    # st.write(st.session_state["edited_df"].compare(st.session_state["current_talent_data"]))
    st.session_state["changed"] = detect_changes(st.session_state["edited_df"])
    handle_editor_change(df_to_display)




    render_save_btn(filters_dict)
    selected_people = df_to_display.iloc[edited_df[edited_df["Select"] == True].index]
    if st.session_state["loader_state"] and st.session_state["loader_state"]['has_more']:
        remaining = st.session_state['loader_state']['total_count'] - st.session_state['loader_state']['loaded_count']
        
        
        btn_load_more = st.button("Load More", key="btn_load_more", use_container_width=True)
        if btn_load_more:
            with st.spinner("載入中..."):
                result = load_more_data()
                # st.session_state["changed"] = detect_changes(st.session_state["edited_df"])
                st.success(f"✅ Loaded {len(result.items)} candidate(s)")
                st.rerun()

    render_candidate_panal(selected_people,data)

    return edited_df

@st.fragment
def render_save_btn(filters_dict):
    if st.session_state["changed"] :
        st.warning("⚠️ You have unsaved changes!  ( All changes will be cleared if you select another candidate. )")
        if len(st.session_state["warning"])>0:
            st.warning("下列人才已鎖定無法變更,其變更項目將直接跳過" + str(st.session_state["warning"]))
        btn_col1, btn_col2 = st.columns(2)
        
        with btn_col1:
            if st.button("💾 Save Changes to DB", type="primary", use_container_width=True):
                edit = []

                current_data = (
                    st.session_state["current_talent_data"]
                    .replace({np.nan: None})
                    .to_dict(orient="records")
                )

                for row_index, value in st.session_state["editor_changes"]["edited_rows"].items():

                    if row_index == "lock_status":
                        continue

                    if isinstance(value, dict) and "changes" in value:
                        changes = value["changes"]
                    else:
                        changes = value

                    if "Select" in changes:
                        del changes["Select"]

                    raw = current_data[int(row_index)]

                    edit.append(
                        {
                            "source": raw["source"],
                            "source_id": raw["source_id"],
                            "updates": changes,
                        }
                    )

                request_changes = {
                    "edit": edit,
                    "operator": st.session_state["username"],
                }

                talent_api.update_talent_with_log(request_changes)
                
                st.session_state["editor_changes"] = {}
                st.session_state["warning"] = []
                load_initial_data(filters_dict)
                st.session_state["editor_version"] += 1
                st.session_state["changed"] = False
                st.rerun()
                
        with btn_col2:
            if st.button("❌ Cancel & Reset Changes", type="secondary", use_container_width=True):
                st.session_state["editor_changes"] = {}
                st.session_state["editor_version"] += 1
                st.cache_data.clear()
                st.session_state["changed"] = False
                st.session_state["warning"] = []
                st.session_state["edited_df"] = st.session_state["current_talent_data"]
                st.rerun()


@st.fragment
def render_candidate_panal(selected_people,data ):
    if not selected_people.empty:
        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
        st.subheader("🔍 Deep Dive Inspection Panel")
        person = selected_people.iloc[0]





        # ==========================================
        # 初始化評論系統
        # ==========================================
        person_key = f"comments_{person['source_id']}"
        if person_key not in st.session_state:
            st.session_state[person_key] = []
            
            # 從資料庫載入現有評論
            if person.get("note") and str(person["note"]).strip() and str(person["note"]) != 'nan':
                soup = BeautifulSoup(str(person["note"]), "html.parser")
                p_tags = soup.find_all("p")
                
                for idx, p in enumerate(p_tags):
                    full_text = p.get_text()
                    
                    # 檢查是否已被刪除
                    is_deleted = "已刪除" in full_text or "[已刪除]" in full_text
                    
                    try:
                        # 匹配正常留言格式
                        match = re.match(
                            r"使用者：(.*?)\s*於\s*(.*?)\s*留言：\s*(.*)",
                            full_text,
                            flags=re.DOTALL
                        )
                        if match:
                            st.session_state[person_key].append({
                                "id": idx,
                                "author": match.group(1),
                                "text": match.group(3),
                                "time": match.group(2),
                                "is_deleted": is_deleted
                            })
                        # 匹配已刪除留言格式
                        elif "已刪除" in full_text:
                            deleted_match = re.match(r"使用者：(.*?) 於 (.*?) 的留言已刪除", full_text)
                            if deleted_match:
                                st.session_state[person_key].append({
                                    "id": idx,
                                    "author": deleted_match.group(1),
                                    "text": "",
                                    "time": deleted_match.group(2),
                                    "is_deleted": True
                                })
                    except Exception as e:
                        st.session_state[person_key].append({
                            "id": idx,
                            "author": "系統紀錄",
                            "text": full_text,
                            "time": "",
                            "is_deleted": is_deleted
                        })
        
        # ==========================================
        # 顯示候選人詳細資訊
        # ==========================================
        candidate_key= person["source"]+"_"+person["source_id"] 
        c1, c2 = st.columns(2)
        b1, b2,_ = st.columns([0.6,0.5,8])

        def enter_modify_mode():
            st.session_state[f"modify_btn_{candidate_key}"] = True
            if f"site_{candidate_key}" in st.session_state:
                del st.session_state[f"site_{candidate_key}"]

        def enter_share():
            site = talent_api.share(person["source"],person["source_id"],st.session_state["username"]).data
            st.session_state[f"site_{candidate_key}"] = site


        if not st.session_state["modify_mode"] and st.session_state["user_role"] =="admin":
            with b1:
                st.button("Modify",on_click=enter_modify_mode,key= f"m_btn_{candidate_key}]")

        if not st.session_state["modify_mode"] and st.session_state["user_role"] =="admin":
            with b2:
                st.button("Share",on_click=enter_share)

        if f"site_{candidate_key}" in st.session_state:
            st.code(st.session_state[f"site_{candidate_key}"])

        if f"modify_btn_{candidate_key}" in st.session_state:
            if  st.session_state[f"modify_btn_{candidate_key}"]  or st.session_state["modify_mode"]:
                uploaded_files = None
                st.session_state["modify_mode"] =True
                if f"m_btn_{candidate_key}]" in st.session_state:
                    st.rerun(scope="fragment")
                with c1:
                    edited_person = {}
                    edited_person["name"] = st.text_input(
                        "Name",
                        value=str(person.get("name", "")),
                        key=f"name_{candidate_key}"
                    )
                    
                    edited_person["source_link"] = st.text_input(
                        "Link",
                        value=str(person.get("source_link", "")),
                        key=f"source_link_{candidate_key}"
                    )
                    

                    edited_person["gender"] = st.selectbox(
                        "Gender",
                        index=data["gender"].index(str(person.get("gender", ""))),
                        options=data["gender"],
                        key=f"gender_{candidate_key}"
                    )

                    edited_person["age"] = st.number_input(
                        "Age",
                        value=int(person.get("age", "")),
                        step=1,
                        key=f"age_{candidate_key}"
                    )

                    edited_person["education_school"] = st.text_input(
                        "Education School",
                        value=str(person.get("education_school", "")),
                        key=f"education_school_{candidate_key}"
                    )

                    edited_person["education_department"] = st.text_input(
                        "Education Department",
                        value=str(person.get("education_department", "")),
                        key=f"education_department_{candidate_key}"
                    )

                    edited_person["education_degree"] = st.selectbox(
                        "Education Degree",
                        index=data["education_degree"].index(str(person.get("education_degree", ""))) if person["education_degree"] else None,
                        options=data["education_degree"],
                        key=f"education_degree_{candidate_key}"
                    )

                    edited_person["vacancy"] = st.selectbox(
                        "Target Vacancy",
                        index=data["vacancies"].index(str(person.get("vacancy", ""))) ,
                        options=data["vacancies"],
                        key=f"vacancy_{candidate_key}"
                    )

                    edited_person["city"] = st.selectbox(
                        "City",
                        index=data["city"].index(str(person.get("city", ""))) if  person["city"] else None,
                        options=data["city"],
                        key=f"city_{candidate_key}"
                    )

                    edited_person["district"] = st.selectbox(
                        "District",
                        index=data["district"].index(str(person.get("district", ""))) if person["district"] else None,
                        options=data["district"],
                        key=f"district_{candidate_key}"
                    )

                    exp_years = person.get("total_exp_years", 0)
                    if pd.isna(exp_years):
                        exp_years = 0

                    edited_person["total_exp_years"] = st.number_input(
                        "Total Work Experience (Years)",
                        value=int(exp_years),
                        step=1,
                        key=f"total_exp_years_{candidate_key}"
                    )

                    edited_person["current_company"] = st.text_input(
                        "Current Company",
                        value=str(person.get("current_company", "")),
                        key=f"current_company_{candidate_key}"
                    )

                    edited_person["current_job_title"] = st.text_input(
                        "Current Job Title",
                        value=str(person.get("current_job_title", "")),
                        key=f"current_job_title_{candidate_key}"
                    )

                with c2:

                    edited_person["source"] = st.text_input(
                        "Source",
                        value=str(person.get("source", "")),
                        key=f"source_{candidate_key}"
                    )

                    edited_person["source_id"] = st.text_input(
                        "Source ID",
                        value=str(person.get("source_id", "")),
                        key=f"source_id_{candidate_key}"
                    )

                    edited_person["phone"] = st.text_input(
                        "Phone",
                        value=str(person.get("phone", "")),
                        key=f"phone_{candidate_key}"
                    )

                    edited_person["email"] = st.text_input(
                        "Email",
                        value=str(person.get("email", "")),
                        key=f"email_{candidate_key}"
                    )


                    edited_person["onboarding_date"] = st.date_input(
                        "Onboarding Date",
                        value=person.get("onboarding_date"),
                        key=f"onboarding_date_{candidate_key}"
                    )
                    edited_person["current_status"] = st.selectbox(
                        "Hiring Status",
                        index=data["status"].index(str(person.get("current_status", ""))),
                        options=data["status"],
                        key=f"current_status_{candidate_key}"
                    )

                    edited_person["expected_salary"] = st.number_input(
                        "Expected Salary",
                        value=person.get("expected_salary"),
                        step=1000,
                        key=f"expected_salary_{candidate_key}"
                    )
                    edited_person["block"] = st.checkbox(
                        "Block",
                        value=person.get("block"),
                        key=f"block_{candidate_key}"
                    )
                    edited_person["block"] = 1 if edited_person["block"] else 0
                    if  st.session_state[f"block_{candidate_key}"]:
                        edited_person["block_reason"] = st.text_input(
                            "Block Reason",
                            value=person.get("block_reason"),
                            key=f"block_reason_{candidate_key}",
                            disabled= not st.session_state[f"block_{candidate_key}"]
                        )

                    st.session_state["edited_person"] = edited_person
                    d1,d2 ,_= st.columns([2,2,8])
                    with d1:
                        if st.button("Save", key=f"save_{candidate_key}"):
                            mask = (
                                (st.session_state["current_talent_data"]["source"] == person["source"])
                                &
                                (st.session_state["current_talent_data"]["source_id"] == person["source_id"])
                            )
                            edited_person = {
                                k: v
                                for k, v in edited_person.items()
                                if person.get(k) != v
                            }
                            for col, value in edited_person.items():

                                st.session_state["current_talent_data"].loc[mask, col] = value


                            request_changes = {
                            "edit": [
                                {
                                    "source": person["source"],
                                    "source_id": person["source_id"],
                                    "updates": edited_person
                                }
                            ],
                            "operator": st.session_state["username"],
                            }
                            st.session_state["modify_mode"] = False
                            del st.session_state["edited_person"]
                            del st.session_state[f"modify_btn_{candidate_key}"] 
                            if f"site_{candidate_key}" in st.session_state:
                                del st.session_state[f"site_{candidate_key}"] 
                            talent_api.update_talent_with_log(request_changes)
                            st.success("Saved")
                            st.rerun()
                    with d2:
                        if st.button("Cancel", key=f"cancel_{candidate_key}"):
                            del st.session_state["edited_person"]
                            del st.session_state[f"modify_btn_{candidate_key}"]
                            st.session_state["modify_mode"] = False
                            if f"site_{candidate_key}" in st.session_state:
                                del st.session_state[f"site_{candidate_key}"] 
                            st.rerun()
        else:
            with c1:
                st.markdown(
                    f"### :blue[[{person['name']}]({person.get('source_link', '#')})] "
                    f"<span style='color: gray; font-size: 15px; font-weight: normal; margin-left: 10px;'>"
                    f"update {person.get('update_time', 'N/A')}</span>",
                    unsafe_allow_html=True
                )
                
                st.write(f"**Gender:** {person.get('gender', 'N/A')}")
                st.write(f"**Age:** {person.get('age', 'N/A')}")
                st.write(f"**Education:** {person.get('education_mode','')}{person.get('education_degree', '')}{person.get('education_status','')} {person.get('education_school', '')} {person.get('education_department', '')}")
                st.write(f"**Target Vacancy:** {person.get('vacancy', 'N/A')}")
                st.write(f"**Location:** {person.get('city', 'N/A')}, {person.get('district', 'N/A')}")
                
                exp_years = person.get('total_exp_years', 0)
                if pd.notna(exp_years):
                    st.write(f"**Total Work Experience:** {int(float(exp_years))} year")
                
                st.write(f"**Current Company-title:** {person.get('current_company', 'N/A')} - {person.get('current_job_title', 'N/A')}")
            
            with c2:
                st.markdown("### Contact & Evaluation")
                st.write(f"**Source:** {person.get('source', 'N/A')}")
                st.write(f"**Source ID:** {person.get('source_id', 'N/A')}")
                st.write(f"**Phone:** {person.get('phone', 'N/A')}")
                st.write(f"**Email:** {person.get('email', 'N/A')}")
                st.write(f"**Archive:** {person.get('received_time', 'N/A')}")
                
                status = person.get('current_status', '未處理')
                status_color = "green" if len(status.split("-")) ==1 else "red"
                st.write(f"**Hiring Status:** :{status_color}[**{status}**]")
                
                score = float(person.get('score', 0) or 0)
                score_color = "green" if score >= 60 else "red"
                st.write(f"**AI Recommendation Score:** :{score_color}[**{score:.2f}**]")
                st.write(f"**Distance** {person["score_distance"]} ,**Experience** {person["score_experience"]} ,**Age** {person["score_age"]} ,**Education** {person["score_education"]}")
        
        # ==========================================
        # AI 生成的候選人摘要
        # ==========================================
        description = person.get('description', 'No description available')
        invitation = person.get('invitation', 'No invitation available')
        with st.form("description_form"):
            user_input = st.text_area(
                "AI generated description",
                value=description,
                height=300
            )
            user_input_invitation = st.text_area(
                "AI generated invitation",
                value=invitation,
                height=350
            )
            
            # 在 form 內，Ctrl+Enter 不會觸發頁面重新執行
            # 只有點擊 submit 按鈕才會提交
            submitted = st.form_submit_button("submit")
            
            if submitted:
                updata_talent = person.copy()
                updata_talent.pop("Select")
                updata_talent = (
                    updata_talent
                    .replace({np.nan: None})
                    .to_dict()
                )
                request_changes = {
                    "edit": [
                        {
                            "source": updata_talent["source"],
                            "source_id": updata_talent["source_id"],
                            "updates": {
                                "description": user_input,
                                "invitation":user_input_invitation
                            }
                        }
                    ],
                    "operator": st.session_state["username"],
                }
                response = talent_api.update_talent_with_log(request_changes)
                st.session_state["current_talent_data"].loc[st.session_state["current_talent_data"]["source_id"] == person['source_id'], "description"] = user_input
                st.session_state["edited_df"] = st.session_state["current_talent_data"]
                st.session_state["changed"] = False
                st.session_state["editor_changes"] = {}
                if response.success:
                    st.success("Upload Successfully")
                else:
                    st.warning("Upload Failed")

        # ==========================================
        # 履歷連結
        # ==========================================
        if person.get('msg_backup_path'):
            resume_url = (
                f"/resume?"
                f"source={person["source"]}"
                f"&source_id={person["source_id"]}"
            )

            st.markdown(f"**📁 [Open Resume]({resume_url})**")
        
        st.markdown("#### Attachment:")

        user_dir = (
            Path(__file__).parent
            / "static"
            / "attachment"
            / f"{person['source']}_{person['source_id']}"
        )

        # 資料夾不存在
        if not user_dir.exists():
            st.info("No attachment.")
        else:

            files = [
                f
                for f in user_dir.iterdir()
                if f.is_file()
            ]

            # 資料夾存在但沒有檔案
            if not files:
                st.info("No attachment.")

            else:

                for file in files:

                    confirm_key = f"confirm_delete_{file.name}"

                    if confirm_key not in st.session_state:
                        st.session_state[confirm_key] = False

                    col1, col2 = st.columns([8, 1])

                    # -----------------------------
                    # Download Button
                    # -----------------------------
                    with col1:

                        with open(file, "rb") as f:

                            st.download_button(
                                label=f" {file.name}",
                                data=f.read(),
                                file_name=file.name,
                                key=f"download_{file.name}",
                                use_container_width=True
                            )

                    # -----------------------------
                    # Delete Button
                    # -----------------------------
                    with col2:

                        # 第一次按垃圾桶
                        if not st.session_state[confirm_key]: 
                            if st.button(
                                "🗑️",
                                key=f"delete_{file.name}",
                                use_container_width=True
                            ):
                                st.session_state[confirm_key] = True
                                st.rerun()

                        # 顯示確認刪除
                        else:

                            st.warning("Delete?")

                            c1, c2 = st.columns(2)

                            with c1:

                                if st.button(
                                    "✓",
                                    key=f"yes_{file.name}",
                                    use_container_width=True
                                ):

                                    file.unlink()

                                    st.session_state[confirm_key] = False

                                    st.success(
                                        f"{file.name} deleted"
                                    )

                                    st.rerun()

                            with c2:

                                if st.button(
                                    "✗",
                                    key=f"no_{file.name}",
                                    use_container_width=True
                                ):

                                    st.session_state[confirm_key] = False

                                    st.rerun()
                                
        uploaded_files = st.file_uploader("upload",label_visibility="collapsed",accept_multiple_files=True,type=["pdf", "docx", "xlsx","jpg", "jpeg", "png","ppt"],key="meeting_attachment_uploader")
        if uploaded_files:
            
            if st.button("Upload"):
                user_dir = (
                    Path(__file__).parent
                    / "static"
                    / "attachment"
                    / (person["source"]+"_"+person["source_id"])
                )

                user_dir.mkdir(
                    parents=True,
                    exist_ok=True
                )
                for file in uploaded_files:
                    save_path = user_dir / file.name
                    if save_path.exists():
                        st.warning(f"{file.name} already exists.")
                        continue
                    with open(save_path, "wb") as f:
                        f.write(file.getbuffer())
                        st.success(f"成功上傳 {len(uploaded_files)} 個檔案")
                del st.session_state["meeting_attachment_uploader"]
                st.rerun()


        review_panal(person)
        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
        
        # ==========================================
        # 💬 留言板區塊
        # ==========================================
        st.markdown("### 💬 NOTE")
        
        # 顯示評論區
        comment_container = st.container(height=500)
        with comment_container:
            current_user = st.session_state.get("email", "User")
            
            for idx, c in enumerate(st.session_state[person_key]):
                author_name = str(c.get("author", "User")).strip()
                is_deleted = c.get("is_deleted", False)
                
                # 創建刪除確認的 session_state key
                confirm_key = f"confirm_delete_{person['source_id']}_{idx}"
                if confirm_key not in st.session_state:
                    st.session_state[confirm_key] = False
                
                # 創建兩欄布局:留言內容 + 刪除按鈕
                col_msg, col_del = st.columns([0.6, 0.065])
                
                with col_msg:
                    with st.chat_message("user"):
                        if is_deleted:
                            # 已刪除的留言樣式
                            st.markdown(
                                f"**{author_name}** <span style='color:gray; font-size:12px;'>{c.get('time', '')}</span>",
                                unsafe_allow_html=True
                            )
                            st.markdown(
                                "<span style='color:#999; font-style:italic;'>🚫 The note had been deleted.</span>",
                                unsafe_allow_html=True
                            )
                        else:
                            # 正常留言
                            st.markdown(
                                f"**{author_name}** <span style='color:gray; font-size:12px;'>{c.get('time', '')}</span>",
                                unsafe_allow_html=True
                            )
                            st.write(c.get("text", ""))
                
                with col_del:
                    # 只有作者本人且留言未刪除才顯示刪除按鈕
                    if author_name == current_user and not is_deleted:
                        # 如果尚未點擊確認,顯示刪除按鈕
                        if not st.session_state[confirm_key]:
                            if st.button("🗑️", key=f"delete_{person['source_id']}_{idx}",use_container_width=True):
                                st.session_state[confirm_key] = True
                                st.rerun(scope="fragment")
                                
                        
                        # 如果已點擊刪除,顯示確認對話框
                        if  st.session_state[confirm_key]:
                            st.warning("Delete?")
                            col_yes, col_no = st.columns(2)
                            
                            with col_yes:
                                if st.button("✓ ", key=f"confirm_yes_{person['source_id']}_{idx}",use_container_width=True):
                                    # 執行刪除
                                    st.session_state[person_key][idx]["is_deleted"] = True
                                    st.session_state[person_key][idx]["text"] = ""
                                    st.session_state[person_key][idx]["deleted_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    
                                    # 重建 HTML note
                                    html_parts = []
                                    for comment in st.session_state[person_key]:
                                        if comment.get("is_deleted", False):
                                            html_parts.append(
                                                f"<p>使用者：{comment['author']} 於 {comment['time']} 的留言已刪除</p>"
                                            )
                                        else:
                                            html_parts.append(
                                                f"<p>使用者：{comment['author']} 於 {comment['time']} 留言： {comment['text']}</p>"
                                            )
                                    
                                    updated_note = "\n".join(html_parts)
                                    
                                    # 更新資料庫
                                    request_changes = {
                                        "edit": [
                                            {
                                                "source": person["source"],
                                                "source_id": person["source_id"],
                                                "updates": {
                                                    "note": updated_note
                                                }
                                            }
                                        ],
                                        "operator": current_user
                                    }

                                    talent_api.update_talent_with_log(
                                        request_changes
                                    )
                                    st.session_state["current_talent_data"].loc[st.session_state["current_talent_data"]["source_id"] == person['source_id'], "note"] = updated_note
                                    st.session_state["edited_df"] = st.session_state["current_talent_data"]
                                    st.session_state["changed"] = False
                                    st.session_state["editor_changes"] = {}
                                    
                                    # 重置確認狀態
                                    st.session_state[confirm_key] = False
                                    st.rerun()
                            
                            with col_no:
                                if st.button("✗ ", key=f"confirm_no_{person['source_id']}_{idx}",use_container_width=True):
                                    # 取消刪除
                                    st.session_state[confirm_key] = False
                                    st.rerun(scope="fragment")
        
        # ==========================================
        # 新增留言表單
        # ==========================================
        with st.form(key=f"form_{person['source_id']}", clear_on_submit=True):
            cc1, cc2 = st.columns([1, 3])
            with cc1:
                hr_name = st.session_state.get("email", "User")
                st.markdown("**Author**")
                st.markdown(f"`{hr_name}`")
            with cc2:
                comment = st.text_input("**Comment**", key=f"txt_{person['source_id']}")
            
            submit_comment = st.form_submit_button("Upload Note")
            
            if submit_comment:
                if hr_name.strip() == "" or comment.strip() == "":
                    st.error("請填評語內容！")
                else:
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    new_item = {"author": hr_name, "text": comment, "time": now_str}
                    st.session_state[person_key].append(new_item)
                    
                    new_html_note = f"<p>使用者：{hr_name} 於 {now_str} 留言： {comment}</p>"
                

                    current_db_note = person.get("note", "")

                    if current_db_note is None or str(current_db_note) == "nan":
                        current_db_note = ""

                    db_note = str(current_db_note) + new_html_note

                    request_changes = {
                        "edit": [
                            {
                                "source": person["source"],
                                "source_id": person["source_id"],
                                "updates": {
                                    "note": db_note
                                }
                            }
                        ],
                        "operator": current_user,
                    }

                    response = talent_api.update_talent_with_log(
                        request_changes
                    )

                    if response.success:

                        mask = (
                            (st.session_state["current_talent_data"]["source"] == person["source"])
                            &
                            (st.session_state["current_talent_data"]["source_id"] == person["source_id"])
                        )

                        st.session_state["current_talent_data"].loc[
                            mask,
                            "note"
                        ] = db_note

                        comment = ""
                        st.session_state["changed"] = False
                        st.session_state["editor_changes"] = {}
                        st.session_state["edited_df"] = st.session_state["current_talent_data"]
                        st.rerun()
                    else:
                        st.error("發生問題"+str(response.error))
        if st.button("Delete User",type="primary"):
            response_delete = talent_api.delete_talent(person.get("source"),person.get("source_id"),st.session_state["username"])
            if response_delete.success:
                st.success("Successfully delete "+person.get("name"))
                st.cache_data.clear()
                load_initial_data(st.session_state["current_filters"].to_dict())
                reset_session_state()
                st.session_state["changed"] = detect_changes(st.session_state["edited_df"])
                st.rerun(scope="app")
            else:
                st.error(response_delete.error)

            
    else:
        st.info("💡 **Please check the 'Select' box** on the left of any candidate to expand their full AI summary and contact details here.")   


@st.fragment
def review_panal(person):

    # ==================================================
    # 內部工具函數
    # ==================================================

    def create_reviewer():
        return {
            "id": str(uuid4()),
            "interviewer": "",
            "email": "",
            "comment": "",
        }

    def create_interview(number: int):
        return {
            "id": "ADD",           # 只有使用者按下「New Interview」才會產生這個標記
            "uid": str(uuid4()),   # 前端專用，只用來當 widget key / 定位，不會上傳給後端
            "name": "",
            "date": datetime.now().isoformat(timespec="seconds"),
            "location": "",
            "note": "",
            "candidate_mail": "",
            "ex_attachments": "",
            "in_attachments": "",
            "reviewers": [create_reviewer()],
        }

    def is_blank_new_interview(item: dict) -> bool:
        """
        判斷這筆是否為「使用者按了 New Interview 但完全沒填寫」的空白項目。
        id 仍為 ADD，且除了 id/date/reviewers/uid 以外欄位全空 → 上傳前直接濾除，
        避免建立一場空白的 Outlook 會議。
        """
        if item.get("id") != "ADD":
            return False
        ignored_keys = {"id", "date", "reviewers", "uid"}
        return all(
            (value == "" or value is None or value == [])
            for key, value in item.items()
            if key not in ignored_keys
        )

    def build_placeholder_map(
        candidate: dict = None,
        vacancy: dict = None,
        lab: dict = None,
        interview: dict = None,
        interviewers: list = None,
    ) -> dict:
        """
        根據 candidate / vacancy / interview 資料，
        建立 placeholder key -> 實際值 的對照表。

        interviewers: List[dict]，依「填寫順序」排列，
        每個 dict 需包含 name / comment / email
        """
        candidate = candidate or {}
        vacancy = vacancy or {}
        interview = interview or {}
        interviewers = interviewers or []
        try:
            time_start_dt = datetime.strptime(
                interview["date"],
                "%Y-%m-%d %H:%M:%S"
            )

        except (ValueError, TypeError, AttributeError):
            st.error("Please enter a valid date and time. ")
            return {
                "date": "",
                "time_start": "",
                "time_end": "",
            }

        time_end_dt = time_start_dt + timedelta(hours=1.5)

        time = {
            "date": time_start_dt.strftime("%Y-%m-%d"),
            "time_start": time_start_dt.strftime("%H:%M"),
            "time_end": time_end_dt.strftime("%H:%M"),
        }

        mapping = {
            "candidate_name": candidate.get("name", ""),
            "candidate_ai_score": candidate.get("ai_score", ""),
            "candidate_city": candidate.get("city", ""),
            "candidate_district": candidate.get("district", ""),
            "candidate_education": candidate.get("education", ""),
            "candidate_description": candidate.get("description", ""),
            "candidate_current_company": candidate.get("current_company", ""),
            "candidate_total_exp_years": candidate.get("total_exp_years", ""),
            "candidate_expected_salary": candidate.get("expected_salary", ""),

            "vacancy_position": vacancy.get("position_title", ""),
            "vacancy_introduction": vacancy.get("introduction", ""),
            "vacancy_compensation": vacancy.get("compensation", ""),
            "vacancy_location": vacancy.get("work_location", ""),
            "vacancy_template": lab.get("template", ""),

            "interview_name": interview.get("name", ""),
            "interview_date": time.get("date", ""),
            "interview_time_start": time.get("time_start", ""),
            "interview_time_end": time.get("time_end", ""),
            "interview_location": interview.get("location", ""),
        }

        for idx, person in enumerate(interviewers[:4], start=1):
            mapping[f"interviewer{idx}_name"] = person.get("name", "")
            mapping[f"interviewer{idx}_comment"] = person.get("comment", "")
            mapping[f"interviewer{idx}_email"] = person.get("email", "")

        for idx in range(len(interviewers) + 1, 5):
            mapping[f"interviewer{idx}_name"] = ""
            mapping[f"interviewer{idx}_comment"] = ""
            mapping[f"interviewer{idx}_email"] = ""

        return mapping

    def replace_placeholders(text: str, mapping: dict) -> str:
        """
        純字串取代（適用於 markdown / HTML / plain text）。
        找不到對應值時保留原樣的 $$xxx$$，方便除錯找出漏帶的變數。
        """
        def _replace(match: re.Match) -> str:
            key = match.group(1)
            value = mapping.get(key)
            return str(value) if value is not None else match.group(0)
        return PLACEHOLDER_PATTERN.sub(_replace, text)

    def template(ex, talent, vacancy, interview, interviewers):
        vac = VacancyAPI.query_vacancy({"position_title": vacancy}, 1, 0).data[0]
        lab = LabAPI.get_lab_by_name(vac["lab"]).data
        if ex:
            settings = SettingsAPI.get_ex_temp().data
            temp = settings["content"]
            atta = settings["attachments"]
            mapping = build_placeholder_map(talent, vac, lab, interview, interviewers)
            text = replace_placeholders(temp, mapping)
            return text, atta
        else:
            settings = SettingsAPI.get_in_temp().data
            temp = settings["content"]
            atta = settings["attachments"]
            mapping = build_placeholder_map(talent, vac, lab, interview, interviewers)
            text = replace_placeholders(temp, mapping)
            return text, atta

    def normalize_interviews(data):
        """
        確保舊 DB JSON 也有：
        - interview id / uid
        - 必要欄位
        """

        if not isinstance(data, list):
            return []

        normalized = []

        for interview_index, interview in enumerate(data):
            if not isinstance(interview, dict):
                continue

            interview = copy.deepcopy(interview)

            # 向下相容舊資料 —— 舊版用空字串代表「尚未建立會議」，
            # 統一轉換成新版的 "ADD" 標記語意
            if not interview.get("id"):
                interview["id"] = "ADD"

            interview.setdefault("candidate_mail", "")
            interview.setdefault("name", f"Interview {interview_index + 1}")
            interview.setdefault("date", datetime.now().isoformat(timespec="seconds"))
            interview.setdefault("location", "")
            interview.setdefault("uid", str(uuid4()))

            reviewers = interview.get("reviewers")
            if not isinstance(reviewers, list):
                reviewers = []

            normalized_reviewers = []
            for reviewer in reviewers:
                if not isinstance(reviewer, dict):
                    continue

                reviewer = copy.deepcopy(reviewer)

                if not reviewer.get("id"):
                    reviewer["id"] = str(uuid4())

                reviewer.setdefault("manager", "")
                reviewer.setdefault("comment", "")

                normalized_reviewers.append(reviewer)

            if len(normalized_reviewers) == 0:
                normalized_reviewers.append(create_reviewer())

            interview["reviewers"] = normalized_reviewers

            normalized.append(interview)

        return normalized

    def parse_review_status(review_status):
        """
        把 review_status JSON 轉成 interviews list。
        沒資料或 JSON 解析失敗時，回傳空 list（不再自動建立預設 Interview，
        改成由使用者主動按 New Interview 才會產生）。
        """

        parsed_interviews = []

        if isinstance(review_status, list):
            parsed_interviews = normalize_interviews(review_status)

        elif isinstance(review_status, str) and review_status.strip():
            try:
                loaded_data = json.loads(review_status)
                parsed_interviews = normalize_interviews(loaded_data)
            except (json.JSONDecodeError, TypeError, ValueError):
                parsed_interviews = []

        return parsed_interviews

    def parse_datetime(value):
        if isinstance(value, datetime):
            return value

        if isinstance(value, str) and value.strip():
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass

        return datetime.now()

    def remove_widget_keys(prefix):
        """
        清除指定 Candidate 的 Review Panel widget。
        """
        keys_to_delete = [
            key for key in list(st.session_state.keys())
            if (isinstance(key, str) and key.startswith(prefix))
        ]
        for key in keys_to_delete:
            st.session_state.pop(key, None)

    def strip_frontend_only_fields(interviews: list) -> list:
        """上傳前移除前端專用欄位，維持原有 id 語意不受影響"""
        cleaned = copy.deepcopy(interviews)
        for interview in cleaned:
            interview.pop("uid", None)
        return cleaned

    # ==================================================
    # PERSON 格式處理
    # ==================================================

    if person is None:
        st.info("Please select a candidate.")
        return

    if isinstance(person, pd.DataFrame):
        if person.empty:
            st.info("Please select a candidate.")
            return

        if len(person) > 1:
            st.warning("Please select only one candidate.")
            return

        person = person.iloc[0]

    if isinstance(person, dict):
        person = pd.Series(person)

    if not isinstance(person, pd.Series):
        st.error("person 必須是 pd.Series、dict，或只有一筆資料的 DataFrame。")
        return

    required_columns = {"source", "source_id"}
    missing_columns = required_columns - set(person.index)

    if missing_columns:
        st.error(f"person 缺少必要欄位：{sorted(missing_columns)}")
        return

    source = person["source"]
    source_id = person["source_id"]

    candidate_key = (str(source), str(source_id))
    widget_prefix = f"review_panel_{candidate_key[0]}_{candidate_key[1]}_"

    previous_candidate_key = st.session_state.get("current_review_candidate")
    candidate_changed = previous_candidate_key != candidate_key

    # ==================================================
    # 換 CANDIDATE 時重新載入 review_status
    # ==================================================

    if candidate_changed:
        review_status = person.get("review_status", None)
        new_interviews = parse_review_status(review_status)

        st.session_state["interviews"] = copy.deepcopy(new_interviews)
        st.session_state["current_review_candidate"] = candidate_key

    elif "interviews" not in st.session_state:
        review_status = person.get("review_status", None)
        st.session_state["interviews"] = copy.deepcopy(parse_review_status(review_status))

    # 確保舊 JSON 一定補上 ID（不會強制補一筆空白 interview）
    st.session_state["interviews"] = normalize_interviews(st.session_state["interviews"])


    # ==================================================
    # INTERVIEW UI
    # ==================================================
    st.markdown("---")
    st.session_state["attachments_ex"] = SettingsAPI.get_ex_temp().data["attachments"]

    with st.expander("Interview Panal", expanded=True):

        # 沒有任何面試時提示使用者，不再自動生成空白表單
        if len(st.session_state["interviews"]) == 0:
            st.info("No interviews yet. Click '➕ New Interview' below to add one.")

        for interview_index, interview in enumerate(st.session_state["interviews"]):

            # 已標記刪除的面試不再顯示於畫面上，但仍保留在陣列中等待上傳處理
            if str(interview.get("id", "")).startswith("DELETE-"):
                continue

            interview_id = interview["uid"]

            title_column, delete_column = st.columns([10, 1])

            with title_column:
                interview_title = interview.get("name") or f"Interview {interview_index + 1}"
                st.markdown(
                    f"### {interview_title} "
                    f"<span style='color: gray; font-size: 15px; font-weight: normal; margin-left: 10px;'>"
                    f"ID {interview.get('id', 'N/A')}</span>",
                    unsafe_allow_html=True
                )

            # ==================================================
            # DELETE INTERVIEW
            # ==================================================
            with delete_column:
                delete_interview = st.button(
                    "🗑️",
                    key=f"{widget_prefix}delete_interview_{interview_id}",
                    help="Delete this interview",
                )

                if delete_interview:
                    current_id = interview.get("id", "")

                    if current_id == "ADD":
                        # 從未上傳過、後端不知道這筆存在 → 直接從陣列移除即可，
                        # 不需要包 DELETE- 標記，也不會觸發任何 cancel_meeting
                        st.session_state["interviews"] = [
                            iv for iv in st.session_state["interviews"]
                            if iv["uid"] != interview_id
                        ]
                    elif not str(current_id).startswith("DELETE-"):
                        # 曾經是真實 meeting_id → 包上 DELETE- 標記，
                        # 讓後端有機會呼叫 cancel_meeting 取消該場會議
                        interview["id"] = f"DELETE-{current_id}"

                    remove_widget_keys(widget_prefix)
                    st.rerun()

            column_1, column_2, column_3 = st.columns(3)

            # ==================================================
            # INTERVIEW NAME
            # ==================================================
            with column_1:
                interview["name"] = st.text_input(
                    "Interview Name",
                    value=interview.get("name", ""),
                    key=f"{widget_prefix}interview_name_{interview_id}",
                )

            # ==================================================
            # INTERVIEW DATE
            # ==================================================
            with column_2:
                date_value = parse_datetime(interview.get("date"))
                selected_datetime = st.datetime_input(
                    "Interview Date",
                    value=date_value,
                    key=f"{widget_prefix}interview_date_{interview_id}",
                )
                interview["date"] = str(selected_datetime)

            # ==================================================
            # LOCATION
            # ==================================================
            with column_3:
                interview["location"] = st.text_input(
                    "Location",
                    value=interview.get("location", ""),
                    key=f"{widget_prefix}interview_location_{interview_id}",
                )

            # ==================================================
            # MAIL FOR MANAGER
            # ==================================================
            st.write("Mail for Manager ")
            if f"gen_in_{interview_id}" not in st.session_state:
                st.session_state[f"gen_in_{interview_id}"] = 0

            interview["note"] = st_quill(
                value=(
                    st.session_state[f"in_template_{person.name}_{interview_id}"]
                    if f"in_template_{person.name}_{interview_id}" in st.session_state
                    else interview.get("note", "")
                ),
                html=True,
                key=(
                    f"{widget_prefix}interview_note_{interview_id}"
                    f"{str(st.session_state[f'gen_in_{interview_id}'])}"
                )
            )

            if f"attachments_in_{interview_id}" in st.session_state:
                in_atta = st.multiselect(
                    label="Attachments",
                    options=st.session_state[f"attachments_in_{interview_id}"],
                    default=st.session_state[f"attachments_in_{interview_id}"],
                    key=f"in_atta_{str(st.session_state[f'gen_in_{interview_id}'])}_{interview_id}"
                )
                interview["in_attachments"] = in_atta

            in_button = st.button("Generate Template", key=f"in_gen_{person.name}_{interview_id}")
            if in_button:
                st.session_state[f"gen_in_{interview_id}"] += 1
                st.session_state[f"in_template_{person.name}_{interview_id}"], \
                    st.session_state[f"attachments_in_{interview_id}"] = template(
                        False, person.to_dict(), person["vacancy"], interview, interview["reviewers"]
                    )
                st.rerun()

            # ==================================================
            # MAIL FOR CANDIDATE
            # ==================================================
            st.write("Mail for Candidate")
            if f"gen_ex_{interview_id}" not in st.session_state:
                st.session_state[f"gen_ex_{interview_id}"] = 0

            interview["candidate_mail"] = st_quill(
                value=(
                    st.session_state[f"ex_template_{person.name}_{interview_id}"]
                    if f"ex_template_{person.name}_{interview_id}" in st.session_state
                    else interview.get("candidate_mail", "")
                ),
                html=True,
                key=(
                    f"{widget_prefix}interview_candidate_mail_{interview_id}"
                    f"{str(st.session_state[f'gen_ex_{interview_id}'])}"
                )
            )

            st.warning(
                "Ensure the candidate has a valid email address before enabling 'Mail for Candidate'. "
                "Leave it empty to skip sending an email to candidate."
            )

            ex_atta = st.multiselect(
                label="Attachments",
                options=st.session_state["attachments_ex"],
                default=interview["ex_attachments"] if len(interview["ex_attachments"]) != 0 else [],
                key=f"ex_atta_{str(st.session_state[f'gen_ex_{interview_id}'])}_{interview_id}"
            )
            interview["ex_attachments"] = ex_atta

            ex_button = st.button("Generate Template", key=f"ex_gen_{person.name}_{interview_id}")
            if ex_button:
                st.session_state[f"gen_ex_{interview_id}"] += 1
                st.session_state[f"ex_template_{person.name}_{interview_id}"], \
                    st.session_state[f"attachments_ex_{interview_id}"] = template(
                        True, person.to_dict(), person["vacancy"], interview, interview["reviewers"]
                    )
                st.rerun()

            st.markdown("##### Reviewers")

            # ==================================================
            # REVIEWERS
            # ==================================================
            for reviewer_index, reviewer in enumerate(interview["reviewers"]):

                reviewer_id = reviewer["id"]

                reviewer_column_1, reviewer_column_2, reviewer_column_3, review_column_4 = \
                    st.columns([1, 2, 4, 1])

                with reviewer_column_1:
                    reviewer["interviewer"] = st.text_input(
                        "Interviewer",
                        value=reviewer.get("interviewer", ""),
                        key=f"{widget_prefix}interviewer_{interview_id}_{reviewer_id}",
                    )

                with reviewer_column_2:
                    reviewer["email"] = st.text_input(
                        "Email",
                        value=reviewer.get("email", ""),
                        key=f"{widget_prefix}email_{interview_id}_{reviewer_id}",
                    )

                with reviewer_column_3:
                    reviewer["comment"] = st.text_input(
                        "Comment",
                        value=reviewer.get("comment", ""),
                        key=f"{widget_prefix}comment_{interview_id}_{reviewer_id}",
                    )

                with review_column_4:
                    if len(interview["reviewers"]) > 1:
                        delete_reviewer = st.button(
                            "🗑️",
                            key=f"{widget_prefix}delete_reviewer_{interview_id}_{reviewer_id}",
                            help="Delete this reviewer",
                        )

                        if delete_reviewer:
                            interview["reviewers"] = [
                                current_reviewer
                                for current_reviewer in interview["reviewers"]
                                if current_reviewer.get("id") != reviewer_id
                            ]
                            remove_widget_keys(widget_prefix)
                            st.rerun()

            # ==================================================
            # ADD REVIEWER
            # ==================================================
            add_reviewer = st.button(
                "➕ Reviewer",
                key=f"{widget_prefix}add_reviewer_{interview_id}",
            )

            if add_reviewer:
                interview["reviewers"].append(create_reviewer())
                st.rerun()

        st.markdown("---")

        add_column, save_column = st.columns(2)

        # ==================================================
        # NEW INTERVIEW
        # ==================================================
        with add_column:
            add_interview = st.button(
                "➕ New Interview",
                key=f"{widget_prefix}add_interview",
                use_container_width=True,
            )

            if add_interview:
                interview_number = len(st.session_state["interviews"]) + 1
                st.session_state["interviews"].append(create_interview(interview_number))
                st.rerun()

        # ==================================================
        # SAVE
        # ==================================================
        with save_column:
            upload = st.button(
                "Upload",
                key=f"{widget_prefix}upload",
                type="primary",
                use_container_width=True,
            )

            if upload:
                with st.spinner("Processing..."):

                    interviews = strip_frontend_only_fields(st.session_state["interviews"])

                    # 上傳前濾除「按了 New Interview 但完全沒填寫」的空白項目，
                    # 避免後端誤建立一場空白會議
                    interviews = [iv for iv in interviews if not is_blank_new_interview(iv)]

                    if len(interviews) == 0:
                        review_status_json = None
                        updates = {"review_status": None}
                    else:
                        review_status_json = json.dumps(interviews, ensure_ascii=False, default=str)
                        updates = {"review_status": review_status_json}

                    request = {
                        "edit": [
                            {
                                "source": source,
                                "source_id": source_id,
                                "updates": updates,
                            }
                        ],
                        "operator": st.session_state["username"],
                    }

                    try:
                        response = talent_api.update_talent_with_log(request)
                    except Exception as error:
                        st.error(f"Review save failed: {error}")
                        return

                    if not response.success:
                        st.error(response.error)
                        return

                    # ==================================================
                    # 更新本地 current_talent_data
                    # ==================================================
                    current_df = st.session_state.get("current_talent_data")

                    if current_df is None:
                        st.warning("Review 已儲存至 DB，但 current_talent_data 不存在。")
                        return

                    mask = (
                        current_df["source"].astype(str).eq(str(source))
                        & current_df["source_id"].astype(str).eq(str(source_id))
                    )

                    matched_count = int(mask.sum())

                    if matched_count == 0:
                        st.warning("Review 已儲存至 DB，但 current_talent_data 找不到這位 Candidate。")
                        return

                    st.session_state["current_talent_data"].loc[mask, "review_status"] = review_status_json

                    # 清除本地已標記刪除的項目，避免下次存檔時
                    # 對同一筆會議重複呼叫 cancel_meeting，也避免資料一直殘留在畫面外
                    st.session_state["interviews"] = [
                        iv for iv in st.session_state["interviews"]
                        if not str(iv.get("id", "")).startswith("DELETE-")
                    ]

                    # 不再強制補一筆空白 interview，維持「無資料則畫面空白，
                    # 等使用者主動按 New Interview」的行為一致性

                    for iv in st.session_state["interviews"]:
                        gen_ex_key = f"gen_ex_{iv['uid']}"
                        if gen_ex_key in st.session_state:
                            del st.session_state[gen_ex_key]

                    st.warning(
                        "已儲存。若剛新增的面試會議仍在背景建立中，"
                        "建議重新整理頁面以取得最新的會議 ID，避免重複建立會議。"
                    )
                    st.success("Review Saved")
                          
def handle_editor_change(df_to_display):
    """
    ✅ 完整版編輯處理器
    - 檢查鎖定狀態
    - 更新資料庫
    - 觸發重新評分 (當 Vacancy 變更時)
    """
    current_key = f"talent_editor_v{st.session_state['editor_version']}"
    editor_state = st.session_state.get(current_key, {})
    edited_rows = editor_state.get("edited_rows", {})
    
    if not edited_rows :
        return
    
    # 清空編輯摘要
    st.session_state.edit_summary = {"success": [], "locked": [], "scored": []}
    
    
    for row_idx, changes in edited_rows.items():
        if row_idx not in df_to_display.index:
            continue
        
        source = df_to_display.loc[row_idx, "source"]
        source_id = df_to_display.loc[row_idx, "source_id"]
        st.session_state.setdefault("editor_changes", {}).setdefault("edited_rows", {})
        
        # 累積更新
        row_idx_str = str(row_idx)
        if row_idx_str in st.session_state["editor_changes"]["edited_rows"]:
            st.session_state["editor_changes"]["edited_rows"][row_idx_str]["changes"].update(changes)
        else:
            st.session_state["editor_changes"]["edited_rows"][row_idx_str] = {
                "changes": changes.copy()
            }

        # 處理 Select 欄位變更
        if "Select" in changes:
            is_checked = changes["Select"]
            if is_checked:
                st.session_state["last_selected_id"] = source_id
                st.session_state["edited_df"] = st.session_state["current_talent_data"]
                st.rerun()
            else:
                if st.session_state["last_selected_id"] == source_id:
                    st.session_state["last_selected_id"] = None
            st.session_state["changed"] = False
        else:
            st.session_state["changed"] = True


        # 過濾出實際的資料變更
        actual_modifications = {
            k: v for k, v in changes.items() 
            if k not in ["Select", "id", "source", "source_id", "mail_id", "update_time", "score", "lock_status"]
        }
        
        if not actual_modifications:
            continue
        
        # 🔧 檢查是否已鎖定（在更新前檢查）
        is_locked = DB_CHECK_IF_LOCKED(source, source_id)
        
        if is_locked:
            # ❌ 已鎖定：拒絕所有編輯
            st.session_state.edit_summary["locked"].append({
                "id": f"{source}-{source_id}",
                "attempted_changes": ", ".join([f"{k}→{v}" for k, v in actual_modifications.items()])
            })
            st.session_state["warning"].append(df_to_display.loc[row_idx, "name"])
            continue  # ← 跳過這筆資料
        


# ==========================================
# 11. Background Scorer (保持不變,但使用 API)

# ==========================================
# 12. 主頁面函數
# ==========================================
def show_talent_page():
    """顯示人才管理頁面"""
    
    try:
        # 初始化評分引擎
        # keep_dataframe_scroll_position()
        # keep_scroll_position()
        if "edit_summary" not in st.session_state:
            st.session_state.edit_summary = {
                "success": [],
                "locked": [],
                "scored": []
            }
        footer = load_custom_css()
        initialize_session_state()
        if st.session_state["create_talent_save"] == True:
            load_initial_data(st.session_state["current_filters"].to_dict())
            reset_session_state()
            st.session_state["changed"] = detect_changes(st.session_state["edited_df"])
            st.session_state["create_talent_save"] = False
            st.rerun()
        data = talent_api.get_options().data
        # 頁面標題
        st.markdown("""
            <div class="main-container">
                <h1 class="page-title" style="color: white;">Talent Data Management</h1>
            </div>
        """, unsafe_allow_html=True)
        st.caption("💡 **Tip**: Check the **'Select'** box on the far left to view full details below.")
        # 顯示編輯摘要
        if any(st.session_state.edit_summary.values()):
            st.divider()
            
            if st.session_state.edit_summary["success"]:
                with st.success("✅ Successfully Updated"):
                    for item in st.session_state.edit_summary["success"]:
                        st.write(f"- ID {item['id']}: {item['changes']}")
            
            if st.session_state.edit_summary["locked"]:
                with st.error("🔒 Locked - Edit Rejected"):
                    for item in st.session_state.edit_summary["locked"]:
                        st.write(f"- ID {item['id']}: {item['attempted_changes']}")
            
            if st.session_state.edit_summary["scored"]:
                with st.info("🚀 Submitted for Scoring"):
                    for item in st.session_state.edit_summary["scored"]:
                        st.write(f"- ID {item['id']}: Background scoring in progress")
            
            if st.button("✖️ Close Summary"):
                st.session_state.edit_summary = {"success": [], "locked": [], "scored": []}
                st.rerun()
            
            st.divider()
        
        # 渲染篩選器

        filters_dict, apply_filters, clear_filters = render_main_filter_section()

        # 處理篩選器動作
        if clear_filters:
            st.cache_data.clear()
            
            keys_to_delete = [
                            "filter_city",
                            "filter_status",
                            "filter_source",
                            "filter_vacancy",
                            "filter_degree",
                            "filter_score",
                            "filter_age",
                            "filter_exp",
                            "filter_search",
                            "filter_exclude_blocked"
                            ]   
            for key in keys_to_delete:
                del st.session_state[key] 
            reset_session_state()
            result = load_initial_data({})
            st.session_state["changed"] = detect_changes(st.session_state["edited_df"])

            st.success(f"✅ Found {st.session_state["loader_state"]['total_count']} Candidate(s)")
            st.rerun()
        
        if apply_filters or st.session_state["current_talent_data"].empty:
            with st.spinner("🔍 Searching..."):
                result = load_initial_data(filters_dict)
                st.session_state["changed"] = detect_changes(st.session_state["edited_df"])

                st.success(f"✅ Found {st.session_state["loader_state"]['total_count']} Candidate(s)")
        
        # 顯示載入狀態
        if st.session_state["loader_state"]:
            state = st.session_state["loader_state"]
            progress = state.get('progress_percentage', 0.0)
            
            metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
            
            with metric_col1:
                st.metric(label="Total", value=f"{state.get('total_count', 0)}")
            
            with metric_col2:
                st.metric(label="Loaded", value=f"{state.get('loaded_count', 0)}")
            
            with metric_col3:
                st.metric(label="Progress", value=f"{progress:.1f}%")
            
            with metric_col4:
                total = state.get('total_count', 0)
                loaded = state.get('loaded_count', 0)
                remaining = total - loaded
                st.metric(label="Remains", value=f"{remaining}")
            
            st.progress(progress / 100, text=f"Loading Progress：{loaded}/{total}") 
        
        # 處理編輯變更

        
        if st.button("🔄 Reload Database", key="btn_reload_database", use_container_width=True):
            st.cache_data.clear()
            reset_session_state()
            load_initial_data(filters_dict)
            st.session_state["changed"] = detect_changes(st.session_state["edited_df"])
            st.toast("Database cache cleared!", icon="🔄")
            st.rerun()

        if st.button("Create New", key="btn_create", use_container_width=True):
            st.session_state["create_talent"] = True
            create_new(talent_api,data["status"])


        
        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
        



        # 顯示資料表格
        df_to_display = st.session_state["current_talent_data"].copy()
        
        if df_to_display.empty:
            st.info("There are currently no candidates who meet the criteria.")
            return
        
        if st.session_state["last_selected_id"] is not None:
            df_to_display.insert(0, "Select", df_to_display["source_id"] == st.session_state["last_selected_id"])
        else:
            df_to_display.insert(0, "Select", False)
        

        locked_count = (df_to_display["lock_status"] == "locked").sum()
        if locked_count > 0:
            locked_ids = df_to_display[df_to_display["lock_status"] == "locked"]["name"].tolist()
            st.warning(f"{locked_count} candidates are currently locked (NAME: {locked_ids}).")
        
        # 編輯器回調函數



        

        
        # 渲染資料編輯器
        st.subheader("Candidate Roster")
        if st.button("Download Table", key="btn_download", use_container_width=True):
            result = talent_api.query_talents(st.session_state["username"],filters_dict,1000000000000000,0).data
            df = pd.DataFrame(result)
            df["source_id"] = '="' + df["source_id"].astype(str) + '"'
            csv = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="Download Table",
                data=csv,
                file_name=f"talents_{datetime.now().strftime("%Y-%m-%d")}.csv",
                mime="text/csv"
            )
        dynamic_editor_key = f"talent_editor_v{st.session_state['editor_version']}"
        

        
        
        
        edited_df = render_talent_editor(df_to_display,data,dynamic_editor_key,filters_dict)
        # st.text(edited_df)

        # 載入更多按鈕

        
        
        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div style="text-align: center; color: #666; padding: 2rem 0;">
            <p>{footer}</p>
        </div>
        """, unsafe_allow_html=True)
        
    
    except Exception as e:
        error_msg = traceback.format_exc()
        st.error(f"❌ 程式碼執行失敗：{e}")
        with st.expander("🔍 查看詳細錯誤"):
            st.code(error_msg, language="python")
    
    except Exception as e:
        error_msg = traceback.format_exc()
        st.error(f"❌ 程式碼執行失敗：{e}")
        with st.expander("🔍 查看詳細錯誤"):
            st.code(error_msg, language="python")

# ==========================================
# 13. 🔄 改造後的日誌頁面 (呼叫 API)
# ==========================================
def show_log_page():
    """✅ 改造後:透過 API 查詢日誌 (完整版)"""
    footer = load_custom_css()
    st.markdown("""
            <div class="main-container">
                <h1 class="page-title" style="color: white;">Operation Logs</h1>
            </div>
        """, unsafe_allow_html=True)
    
    # ==========================================
    # 1. 初始化分頁計數器
    # ==========================================
    if "log_limit" not in st.session_state:
        st.session_state["log_limit"] = 30
    
    def reset_limit():
        st.session_state["log_limit"] = 30
    
    try:
        # ==========================================
        # 2. 🌟 呼叫 API 取得日誌元資料
        # ==========================================
        options_column = [
            'operator', 'action', 'status', 'timestamp',
            'vacancy', 'operate_status', 'source_id',
            'source'
        ]
        filter_options = {}
        
        for i in options_column :
            options = log_api.get_distinct_values(i).data
            if i =="timestamp":
                filter_options["min_timestamp"] = options["min_timestamp"]
                filter_options["max_timestamp"] = options["max_timestamp"]
            else:
                filter_options[i] = options

        statistics = log_api.get_statistics().data
        # ==========================================
        # 3. 頂部統計指標 (Metrics)
        # ==========================================
        c1, c2, c3 = st.columns(3)
        total_count = statistics["total_count"]
        c1.metric("📊 Total Log Entries",total_count )
        success = statistics["operate_status_distribution"]["SUCCESS"]
        err_count = total_count - success
        c2.metric(
            "⚠️ Intercepted Failures", 
            err_count, 
            delta=f"{err_count} issues" if err_count > 0 else "Normal", 
            delta_color="inverse"
        )
        
        c3.metric("👥 Unique Target Entities", statistics["distinct_id_count"])
        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
        
        # ==========================================
        # 4. 進階篩選器 (Advanced Filters)
        # ==========================================
        st.markdown("## Search / Filter")
        
        f1, f2, f3, f4, f5 = st.columns(5)
        
        with f1:
            operator_filter = st.multiselect(
                "Filter Operator:", 
                options=filter_options.get("operator", []), 
                on_change=reset_limit
            )
        
        with f2:
            action_filter = st.multiselect(
                "Filter Action:", 
                options=filter_options.get("action", []), 
                on_change=reset_limit
            )
        
        with f3:
            status_filter = st.multiselect(
                "Filter Status:", 
                options=filter_options.get("status", []), 
                on_change=reset_limit
            )
        
        with f4:
            min_date = filter_options.get("min_timestamp",[])
            max_date = filter_options.get("max_timestamp",[])
            min_date = pd.to_datetime(
                filter_options["min_timestamp"]
            ).date()

            max_date = pd.to_datetime(
                filter_options["max_timestamp"]
            ).date()
            date_range = st.date_input(
                "Filter Date Range:", 
                value=(min_date, max_date), 
                min_value=min_date, 
                max_value=max_date, 
                on_change=reset_limit
            )
        
        with f5:
            source_filter = st.multiselect(
                "Filter Source:", 
                options=filter_options.get("source", []), 
                on_change=reset_limit
            )
        
        # 第二排篩選器
        f11, f12, f13 = st.columns(3)
        
        with f11:
            source_id_filter = st.multiselect(
                "Filter ID:", 
                options=filter_options.get("source_id", []),
                on_change=reset_limit
            )
        
        with f12:
            op_status_filter = st.multiselect(
                "Filter Operate Status:", 
                options=filter_options.get("operate_status", []),
                on_change=reset_limit
            )
        
        with f13:
            vacancy_filter = st.multiselect(
                "Filter Vacancy:", 
                options=filter_options.get("vacancy", []), 
                on_change=reset_limit
            )
        
        # Reload 按鈕
        if st.button("🔄 Reload Database", key="btn_reload_log_database", use_container_width=True):
            st.cache_data.clear()
            st.toast("Database cache cleared! Fetching fresh logs...", icon="🔄")
            st.rerun()
        
        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
        
        # ==========================================
        # 5. 條件過濾
        # ==========================================

        filter_dict = {}
        if operator_filter:
            filter_dict["operator"] = operator_filter

        if action_filter:
            filter_dict["action"] = action_filter

        if status_filter:
            filter_dict["status"] = status_filter

        if source_filter:
            filter_dict["source"] = source_filter

        if source_id_filter:
            filter_dict["source_id"] = source_id_filter

        if op_status_filter:
            filter_dict["operate_status"] = op_status_filter

        if vacancy_filter:
            filter_dict["vacancy"] = vacancy_filter

        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range

            filter_dict["timestamp_start"] = (
                datetime.combine(
                    start_date,
                    datetime.min.time()
                ).strftime("%Y-%m-%d")
            )

            filter_dict["timestamp_end"] = (
                datetime.combine(
                    end_date,
                    datetime.max.time()
                ).strftime("%Y-%m-%d")
            )
        current_limit = st.session_state["log_limit"]

        logs_result = log_api.query_logs(
            filter_dict,
            current_limit,
            0
        )

        if not logs_result.success:
            st.error(f"❌ 查詢失敗: {logs_result.error}")
            return
        
        full_df = pd.DataFrame(logs_result.data)
        
        if full_df.empty:
            st.info("📭 No logs match the selected filters.")
            return
        
        # ==========================================
        # 7. 顯示時間軸表格 (啟用點擊選取行功能)
        # ==========================================
        st.subheader("📅 Operations Timeline")
        st.caption("💡 點擊表格內任意日誌（最左側勾選或整行），下方會自動展開該日誌的詳細內容。")
        if st.button("Download Table", key="btn_download", use_container_width=True):
            result = log_api.query_logs(filter_dict,1000000000000000,0).data
            df = pd.DataFrame(result)
            df["source_id"] = '="' + df["source_id"].astype(str) + '"'
            csv = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="Download Table",
                data=csv,
                file_name=f"talents_{datetime.now().strftime("%Y-%m-%d")}.csv",
                mime="text/csv"
            )
        # 整理要呈現給使用者看的欄位
        display_df = full_df[[
            "operator","log_id", "timestamp",  "version", "action", 
            "previous_version", "source", "source_id", "vacancy", 
            "operate_status", "status"
        ]].set_index("log_id")
        
        # 利用 selection_mode="single-row" 限制一次只能點選一列
        event = st.dataframe(
            display_df,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "operator": st.column_config.TextColumn("Operator", width="small",pinned=True),
                "timestamp": st.column_config.DatetimeColumn("Timestamp", format="YYYY-MM-DD HH:mm:ss"),
                "operate_status": st.column_config.TextColumn("Status", width="small"),
                "version": st.column_config.NumberColumn("Ver", width="small"),
                "previous_version": st.column_config.NumberColumn("Prev Ver", width="small")
            }
        )
        
        # ==========================================
        # 8. 載入更多按鈕
        # ==========================================
        btn_col1, btn_col2, btn_col3 = st.columns([1, 2, 1])
        
        with btn_col2:
            if current_limit < total_count:
                if st.button(
                    f"📥 Load More Logs ({total_count - current_limit} remaining)", 
                    use_container_width=True,
                    key="btn_load_more_logs"
                ):
                    st.session_state["log_limit"] += 50
                    st.rerun()
            else:
                st.info(f"✅ All {total_count} matching logs have been successfully loaded.")
        
        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
        
        # ==========================================
        # 9. 🌟 動態顯示詳細資訊 (Master-Detail 展開)
        # ==========================================
        st.subheader("📄 Log Details Inspector")
        
        # 檢查使用者是否有在表格中點選資料
        selected_rows = event.get("selection", {}).get("rows", [])
        
        if selected_rows:
            # 拿到被選中的那一列的資料索引 (log_id)
            selected_idx = selected_rows[0]
            selected_log_id = display_df.index[selected_idx]
            
            # 從 full_df 中抽取出被點選的那一筆完整資料
            row = full_df[full_df['log_id'] == selected_log_id].iloc[0]
            
            # 決定狀態標籤
            is_error = "error" in str(row['operate_status']).lower() or "fail" in str(row['operate_status']).lower()
            badge = "🔴 FAILED" if is_error else "🟢 SUCCESS"
            
            # 直接在畫面上漂亮呈現
            st.markdown(f"#### {badge} | `{row['timestamp']}`")
            
            t1, t2 = st.columns(2)
            try :
                pre_ver = int(row['previous_version'])
            except:
                pre_ver = None
            with t1:
                st.info(f"**Operator:** {row['operator']} ➔ **Action:** {row['action']}")
                st.write(f"**Log ID:** `{row['log_id']}`")
                st.write(f"**Target ID (Source):** `{row['source']}-{row['source_id']}`")
                st.write(f"**Vacancy Title:** {row['vacancy']}")
                st.write(f"**Version:** {row['version']} (Previous: {pre_ver})")
                if row['note']:
                    st.write(f"**Operational Note:**")
                    st.markdown(row['note'])
            
            with t2:
                if is_error or row['error_message']:
                    st.error(f"**Stack Trace / Error Message:**")
                    st.code(row['error_message'], language="text")
                else:
                    st.success("✅ Python worker script executed successfully. No exceptions raised.")
                
                with st.expander("🔍 View Changed Information", expanded=True):
                    try:
                        changed_info = json.loads(row['changed_info'])
                        st.json(changed_info)
                    except:
                        st.text(row['changed_info'] if row['changed_info'] else "No changed information.")
            
            st.markdown("##### 📦 Payload Details")
            sub1, sub2 = st.columns(2)
            
            with sub1:
                with st.expander("📸 Snapshot State Data (JSON)", expanded=False):
                    try:
                        snapshot = json.loads(row['snapshot_json'])
                        st.json(snapshot)
                    except:
                        st.text(row['snapshot_json'] if row['snapshot_json'] else "No snapshot logged.")
            
            with sub2:
                with st.expander("📝 View Raw Text", expanded=False):
                    st.text(row['raw_text'] if row['raw_text'] else "No raw input body saved.")
        
        else:
            # 使用者尚未點選時的提示畫面
            st.info("💡 Please select a row from the **Operations Timeline** table above to view its technical payloads and stack traces.")
        
        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div style="text-align: center; color: #666; padding: 2rem 0;">
            <p>{footer}</p>
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        error_msg = traceback.format_exc()
        st.error(f"❌ Unable to read log table schema. Error: {e}")
        with st.expander("🔍 查看詳細錯誤"):
            st.code(error_msg, language="python")

# ==========================================
# 14. Navigation
# ==========================================
if st.session_state.get("authentication_status"):
    st.html("""
    <style>
        section[data-testid="stSidebar"] > div {
            padding-top: 2rem !important;
        }

        section[data-testid="stSidebar"] [alt="Logo"] {
            height: 7rem !important;
            width: auto !important;
            object-fit: contain;
            margin-bottom: 2rem !important;
        }

    </style>
    """)

    current_dir = os.path.dirname(os.path.abspath(__file__)) + "/static"  +"/settings"
    contents = os.listdir(current_dir)
    for i in contents:
        content = i.split(".")[-1]
        if content == "png" or content =="jpg" or content =="JPEG" or content =="JPG" or content =="PNG":
            st.logo(current_dir+"/"+i,size="large")

    st.sidebar.markdown(f"🔹 Active User: \n\n  **{user_display_name}**")
    st.sidebar.markdown(
        f"🔹 Role Permission: \n\n`     {user_role.upper()}     `",
    )
    st.sidebar.markdown("---")
    authenticator.logout('**Logout**', 'sidebar')
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    share_id = st.query_params.get("token",None)
    source = st.query_params.get("source")
    source_id = st.query_params.get("source_id")
    if share_id:
        talent = talent_api.get_talent_by_share_id(share_id).data
        render_candidate_readonly(talent)
    elif source and source_id:
        path = talent_api.get_talent_detail(source,source_id).data["msg_backup_path"]
        html = talent_api.msg(source,source_id,st.session_state["username"]).data
        msg_backup(html)
    else:
        if user_role == "admin":
            pages = {
                "Recruitment Management": [st.Page(show_talent_page, title="Candidates")],
                "Vacancy Management":[st.Page(show_vacancy_page, title="Vacancies")],
                "User Management":[st.Page(show_user_page, title=user_display_name)],
                "Data Analytics" :[st.Page(dashboard,title="Analytics")],
                "Operation Log": [st.Page(show_log_page, title="Logs")],
                "System Setting" :[st.Page(show_settings_page, title="Settings")]
                
            }
            pg = st.navigation(pages )
            try:
                if st.session_state["last_pages"]!=pg.title:
                    reset_session_state()
            except:
                pass
            st.session_state["last_pages"] = pg.title
            # reset_session_state()
            pg.run()
        elif user_role =="user":
            pages = {
                "Recruitment Management": [st.Page(show_talent_page, title="Candidates")],
                "Vacancies Management":[st.Page(show_vacancy_page, title="Vacancies")],
                "User Management":[st.Page(show_user_page, title=user_display_name)]
            }
            pg = st.navigation(pages )
            try:
                if st.session_state["last_pages"]!=pg.title:
                    reset_session_state()
            except:
                pass
            st.session_state["last_pages"] = pg.title
            # reset_session_state()
            pg.run()
        elif user_role =="guest":
            st.write("Permission Denied")


