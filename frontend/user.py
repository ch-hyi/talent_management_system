import json
import pandas as pd
import streamlit as st
import uuid
from datetime import datetime, date
import urllib.parse
from bs4 import BeautifulSoup
import time
from threading import Thread
import queue
import traceback
import re
import numpy as np
import streamlit_authenticator as stauth
from api_client import UserAPI,LogAPI,VacancyAPI, APIResponse
from talent_search_engine import (
    FilterConditions ,
    APIConfig)



import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import time
from auth import AuthConfigGenerator
from css import load_custom_css 

# 假設這些是你的 API 類別
# from your_api_module import UserAPI, APIResponse
# config = AuthConfigGenerator.generate_config()

def show_user_page():
    """使用者資訊管理頁面主函數"""
    
    # ==================== 內部函數定義 ====================
    
    
    def fetch_user_data(filters: Dict = None, limit: int = 100) -> pd.DataFrame:
        """取得使用者資料"""
        try:
            response = UserAPI.query_user(filters=filters, limit=limit)
            response.data
            if response.success and response.data:
                users = response.data
                if users:
                    return pd.DataFrame(users)
            return pd.DataFrame()
        except Exception as e:
            st.error(f"❌ Load Data Failed: {str(e)}")
            return pd.DataFrame()
    
    
    def fetch_statistics() -> Dict:
        """取得統計資料"""
        try:
            response = UserAPI.get_statistics()
            if response.success and response.data:
                return response.data
            return {
                'total_users': 0,
                'active_users': 0,
                'admin_users': 0,
                'today_new': 0
            }
        except Exception as e:
            st.error(f"❌ Load Statistics Failed: {str(e)}")
            return {
                'total_users': 0,
                'active_users': 0,
                'admin_users': 0,
                'today_new': 0
            }
    
    
    def render_header():
        """渲染頁面標題"""
        st.markdown("""
            <div class="main-container">
                <h1 class="page-title" style="color: white;">User Management</h1>
            </div>
        """, unsafe_allow_html=True)
    
    
    def render_statistics(stats: Dict):
        """渲染統計卡片"""
        col1, col2, col3, col4 = st.columns(4)
    
        with col1:
            st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-label">Total User</div>
                    <div class="stat-value">{stats.get('total_users', 0):,}</div>
                </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-label">Active User</div>
                    <div class="stat-value">{stats.get('active_users', 0):,}</div>
                </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-label">Admin</div>
                    <div class="stat-value">{stats.get('by_role').get('admin',0):,}</div>
                </div>
            """, unsafe_allow_html=True)
        
        with col4:
            today = datetime.now().strftime("%Y-%m-%d")
            logs = LogAPI.query_logs({"timestamp_start": today,"timestamp_end":today}).data
            st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-label">Daily Usage Count </div>
                    <div class="stat-value">{stats.get('today_new', len(logs)):,}</div>
                </div>
            """, unsafe_allow_html=True)
    
    
    def render_search_filters(is_admin: bool) -> Dict:
        """渲染搜尋與篩選區塊"""
        filters = {}
        
        if is_admin:
            st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
            st.markdown("## Serch / Filter")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                search_name = st.text_input(
                    "User Name",
                    placeholder="e.g. Apple Chang",
                    key="search_name"
                )
                if search_name:
                    filters['name'] = search_name
            
            with col2:
                search_email = st.text_input(
                    "Email",
                    placeholder="e.g. abc@gmail.com",
                    key="search_email"
                )
                if search_email:
                    filters['email'] = search_email
            
            with col3:
                search_id = st.text_input(
                    "ID",
                    placeholder="e.g. apch4",
                    key="search_id"
                )
                if search_id:
                    filters['user_id'] = search_id
            
            col4, col5, col6 = st.columns(3)
            
            with col4:
                role_filter = st.selectbox(
                    "Role",
                    options=["ALL", "admin", "user", "guest"],
                    index=0,
                    key="role_filter"
                )
                if role_filter != "ALL":
                    filters['user_role'] = role_filter
            
            with col5:
                status_filter = st.selectbox(
                    "Status",
                    options=["ALL", "ACTIVE", "INACTIVE"],
                    index=0,
                    key="status_filter"
                )
                if status_filter != "ALL":
                    filters['status'] = "ACTIVE" if status_filter == "ACTIVE" else "INACTIVE"
            
            with col6:
                department_filter = st.text_input(
                    "Vacancy",
                    placeholder="e.g. RF test engineer",
                    key="vacancy_filter"
                )
                if department_filter:
                    filters['department'] = department_filter
            
            # 日期篩選
            st.markdown("##### Register Time")
            col7, col8 = st.columns(2)
            
            with col7:
                date_from = st.date_input(
                    "Start",
                    value=None,
                    key="date_from"
                )
                if date_from:
                    filters['created_from'] = date_from.isoformat()
            
            with col8:
                date_to = st.date_input(
                    "End",
                    value=None,
                    key="date_to"
                )
                if date_to:
                    filters['created_to'] = date_to.isoformat()
            
            # 清除篩選按鈕
            col_clear1, col_clear2, col_clear3 = st.columns([1, 1, 3])
            with col_clear1:
                if st.button("Apply", use_container_width=True, key="reload_btn"):
                    st.rerun()
            
            with col_clear2:
                if st.button("Clear", use_container_width=True, key="clear_filter_btn"):
                    # 清除所有篩選相關的 session state
                    for key in list(st.session_state.keys()):
                        if key.startswith(('search_', 'filter_', 'date_')):
                            del st.session_state[key]
                    st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        return filters
    
    
    @st.fragment
    def render_user_editor(
        user_data: pd.DataFrame,
        is_admin: bool,
        current_user_id: str
    ):
        """
        渲染使用者編輯器。

        功能：
        1. Admin 可選擇任一使用者
        2. Admin 可建立使用者
        3. Admin 可更新使用者
        4. Admin 可刪除使用者
        5. 一般使用者只能查看及更新自己的基本資料
        """

        # =========================================================
        # Session State 初始化
        # =========================================================
        if "create_user" not in st.session_state:
            st.session_state["create_user"] = False

        if "selected_user_id" not in st.session_state:
            st.session_state["selected_user_id"] = None

        if user_data is None:
            user_data = pd.DataFrame()

        current_user_id = str(current_user_id)

        operator = str(
            st.session_state.get(
                "username",
                current_user_id
            )
        )

        is_create = bool(
            st.session_state.get(
                "create_user",
                False
            )
        )

        # =========================================================
        # 安全處理 API Response
        # =========================================================
        def response_success(response) -> bool:
            if response is None:
                return False

            if isinstance(response, dict):
                return bool(
                    response.get("success", False)
                )

            return bool(
                getattr(response, "success", False)
            )

        def response_message(
            response,
            default: str = "Unknown response"
        ) -> str:
            if response is None:
                return default

            if isinstance(response, dict):
                return str(
                    response.get("message", default)
                )

            return str(
                getattr(response, "message", default)
            )

        # =========================================================
        # User List
        # =========================================================
        st.markdown(
            '<div class="edit-title">User List</div>',
            unsafe_allow_html=True
        )

        selected_users = pd.DataFrame()

        if user_data.empty:
            st.markdown(
                """
                <div class="warning-message">
                    ⚠️ No User Available
                </div>
                """,
                unsafe_allow_html=True
            )

        else:
            selection_df = user_data.copy()
            selection_df = selection_df.set_index("user_id")


            # 避免資料本身已經存在 selected 欄位

            # display_columns = [
            #     "user_id",
            #     "user_account",
            #     "user_name",
            #     "user_email",
            #     "user_role",
            #     "status"
            # ]

            # selection_df = selection_df[
            #     display_columns
            # ]

            event = st.dataframe(
                selection_df,
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    "user_id":
                        st.column_config.TextColumn(
                            "User ID",
                            disabled=True,
                            width="large"
                        ),

                    "user_account":
                        st.column_config.TextColumn(
                            "Account",
                            disabled=True,
                            width="medium"
                        ),

                    "user_name":
                        st.column_config.TextColumn(
                            "Name",
                            disabled=True,
                            width="medium"
                        ),

                    "user_email":
                        st.column_config.TextColumn(
                            "Email",
                            disabled=True,
                            width="large"
                        ),

                    "user_role":
                        st.column_config.TextColumn(
                            "Role",
                            disabled=True,
                            width="small"
                        ),

                    "status":
                        st.column_config.TextColumn(
                            "Status",
                            disabled=True,
                            width="small"
                        )
                },
                use_container_width=True,
                key="user_selection_editor"
            )
        selected_rows = event.get("selection", {}).get("rows", [])
        selected_user_id = ""
        if selected_rows:
            # 拿到被選中的那一列的資料索引 (log_id)
            selected_idx = selected_rows[0]
            selected_user_id = selection_df.index[selected_idx]
            # 從 full_df 中抽取出被點選的那一筆完整資料
            selected_users = user_data[user_data['user_id'] == selected_user_id].iloc[0]

        # =========================================================
        # Admin Create New User
        # =========================================================
        create_button = None
        if is_admin:
            if selected_users.empty:
                create_button = st.button(
                    "Create New",
                    key="create_new_user_button"
                )
                if create_button:
                    st.session_state["create_user"] = True
                    st.session_state["selected_user_id"] = None
                    st.rerun()
                
                if not st.session_state["create_user"]:
                    st.warning("Please select a user to view or edit.")
                    return
        if not selected_users.empty:
            st.session_state["create_user"] = False
        # Create 按鈕觸發 rerun 後，重新讀取狀態
        is_create = bool(
            st.session_state.get(
                "create_user",
                False
            )
        )

        # =========================================================
        # 決定 Create / Edit 目標
        # =========================================================

        if is_create:
            if not is_admin:
                st.session_state["create_user"] = False
                st.error(
                    "You do not have permission "
                    "to create users."
                )
                return

            target_user = pd.Series(
                {
                    "user_id": "",
                    "user_account": "",
                    "user_name": "",
                    "user_email": "",
                    "user_role": "user",
                    "status": "ACTIVE",
                    "vacancy_in_charge": ""
                }
            )

            selected_user_id = ""

        else:
            # -----------------------------------------------------
            # Admin 選擇使用者
            # -----------------------------------------------------
            if len(selected_user_id)==0:
                return
            if is_admin:
                if user_data.empty:
                    st.info(
                        "Click Create New User "
                        "to create a user."
                    )
                    return
                # if selected_user_id:
                target_user = UserAPI.get_user_by_id(selected_user_id).data
            # -----------------------------------------------------
            # 一般使用者只能取得自己的資料
            # -----------------------------------------------------
            else:
                if user_data.empty:
                    st.warning(
                        "Your user information "
                        "cannot be found."
                    )
                    return

                if "user_id" not in user_data.columns:
                    st.error(
                        "user_id column cannot be found."
                    )
                    return

                # selected_user_id = current_user_id

                target_user = UserAPI.get_user_by_id(selected_user_id).data
                
            st.session_state[
                "selected_user_id"
            ] = selected_user_id

        # =========================================================
        # 安全讀取資料
        # =========================================================
        def safe_text(
            column: str,
            default: str = ""
        ) -> str:
            value = target_user.get(
                column,
                default
            )
            if column=="vacancy_incharge":
                if value =="":
                    return []
                else:
                    return value

            

            try:
                if pd.isna(value):
                    return default
            except (TypeError, ValueError):
                pass

            return str(value)

        # =========================================================
        # 目前欄位值
        # =========================================================
        current_name = safe_text(
            "user_name"
        )

        current_account = safe_text(
            "user_account"
        )

        current_email = safe_text(
            "user_email"
        )

        
        # 相容舊資料可能使用 role
        current_role = (
            safe_text("user_role")
            or "user"
        ).lower()

        current_vacancy_incharge = safe_text(
            "vacancy_incharge"
        )

        current_status = (
            safe_text("status")
            or "ACTIVE"
        )

        # current_vacancy_incharge = safe_text(
        #     "vacancy_in_charge"
        # )
        current_password = safe_text("password_hash")

        role_options = [
            "admin",
            "user",
            "guest"
        ]

        if current_role not in role_options:
            role_options.insert(
                0,
                current_role
            )

        status_options = [
            "ACTIVE",
            "INACTIVE"
        ]

        if current_status not in status_options:
            status_options.insert(
                0,
                current_status
            )

        role_index = role_options.index(
            current_role
        )

        status_index = status_options.index(
            current_status
        )

        # =========================================================
        # Title
        # =========================================================
        if is_create:
            title_name = "New User"
        else:
            title_name = (
                current_name
                or current_account
                or selected_user_id
                or "N/A"
            )

        st.markdown(
            f"""
            <div class="edit-title">
                User Info：{title_name}
            </div>
            """,
            unsafe_allow_html=True
        )

        # Create / Edit 使用不同 key，避免 Streamlit 保留舊值
        form_mode = (
            "create"
            if is_create
            else f"edit_{selected_user_id}"
        )

        # =========================================================
        # User Form
        # =========================================================
        with st.form(
            key=f"user_edit_form_{form_mode}",
            clear_on_submit=False
        ):
            col1, col2 = st.columns(2)

            with col1:
                # Create 時才能設定 account
                # Edit 時 account 不允許修改
                new_account = st.text_input(
                    "Account",
                    value=current_account,
                    disabled=not is_create
                )

                new_name = st.text_input(
                    "Name",
                    value=current_name
                )

                new_email = st.text_input(
                    "Email",
                    value=current_email
                )

            with col2:
                if is_admin:
                    new_role = st.selectbox(
                        "Role",
                        options=role_options,
                        index=role_index
                    )

                    new_status = st.selectbox(
                        "Status",
                        options=status_options,
                        index=status_index
                    )
                    new_password =  st.text_input(
                        "Password",
                        placeholder="Please enter the plain password",
                        value = current_password,
                    )

                else:
                    new_role = current_role
                    new_status = current_status
                    new_password = current_password

                    st.text_input(
                        "Role",
                        value=current_role,
                        disabled=True
                    )

                    st.text_input(
                        "Status",
                        value=current_status,
                        disabled=True
                    )
                    new_password = st.text_input(
                        "Password",
                        value = current_password,

                    )

            new_vacancy_incharge = st.multiselect(
                "Vacancies In Charged",
                options=VacancyAPI.get_distinct_values("position_title").data ,
                default = current_vacancy_incharge ,
                disabled = False if  st.session_state["user_role"]=="admin" and new_role!="admin" else True
            )

            if is_create:
                st.caption(
                    "User ID will be generated "
                    "by the backend."
                )
            else:
                st.caption(
                    f"User ID: {selected_user_id}"
                )

            st.markdown("---")

            # =====================================================
            # Buttons
            # =====================================================
            cancel_button = None
            submit_button = None
            col_btn1, col_btn2= (
                st.columns([1, 1])
            )

            with col_btn1:
                submit_button = (
                    st.form_submit_button(
                        "💾 Create" if is_create else "💾 Update",
                        use_container_width=True,
                        type="primary"
                    )
                )

            with col_btn2:
                cancel_button = (
                    st.form_submit_button(
                        "❌ Cancel" if is_create else "🗑️Delete",
                        use_container_width=True
                    )
                )

            # =====================================================
            # Cancel
            # =====================================================
            if cancel_button and is_create:
                st.session_state["create_user"] = False
                st.session_state[
                    "selected_user_id"
                ] = None

                st.rerun()

            # =====================================================
            # Delete
            # =====================================================
            if cancel_button and not is_create:
                st.session_state["create_user"] = False
                st.session_state[
                    "selected_user_id"
                ] = None
                if not is_admin:
                    st.error(
                        "You do not have permission "
                        "to delete users."
                    )

                elif str(selected_user_id) == current_user_id:
                    st.error(
                        "You cannot delete your own "
                        "currently logged-in account."
                    )

                else:
                    try:
                        with st.spinner(
                            "Deleting user..."
                        ):
                            response = UserAPI.delete_user(
                                user_id=str(
                                    selected_user_id
                                ),
                                operator=operator
                            )
                
                        if response_success(response):
                            st.session_state[
                                "create_user"
                            ] = False

                            st.session_state[
                                "selected_user_id"
                            ] = None

                            st.success(
                                "User deleted successfully."
                            )

                            time.sleep(1)
                            st.rerun()

                        else:
                            st.error(
                                "Delete failed: "
                                f"{response_message(response)}"
                            )

                    except Exception as e:
                        st.error(
                            f"Delete user error: {e}"
                            "\n\n"
                            f"{traceback.format_exc()}"
                        )

            # =====================================================
            # Create / Update
            # =====================================================
            if submit_button:
                new_name = new_name.strip()
                new_email = new_email.strip()
                new_account = new_account.strip()
                new_password = new_password.strip()

                # -------------------------------------------------
                # Validation
                # -------------------------------------------------
                validation_error = None

                if is_create and not new_account:
                    validation_error = (
                        "Account cannot be empty."
                    )

                elif not new_name:
                    validation_error = (
                        "Name cannot be empty."
                    )

                elif not new_email:
                    validation_error = (
                        "Email cannot be empty."
                    )

                elif (
                    "@" not in new_email
                    or new_email.startswith("@")
                    or new_email.endswith("@")
                ):
                    validation_error = (
                        "Please enter a valid email."
                    )

                if validation_error:
                    st.error(validation_error)

                else:
                    try:
                        # =========================================
                        # Create User
                        # =========================================
                        if is_create:
                            create_data = {
                                "user_account":
                                    new_account,

                                "user_name":
                                    new_name,

                                "user_email":
                                    new_email,

                                "user_role":
                                    new_role,
                                "password_hash":
                                    new_password,
                                "status":
                                    new_status,

                                # "vacancy_in_charge":
                                #    new_vacancy_incharge
                            }

                            with st.spinner(
                                "Creating user..."
                            ):
                                create_data["created_by"] = operator
                                response = (
                                    UserAPI.create_user(
                                    create_data
                                    )
                                )

                            success_message = (
                                "User created successfully."
                            )

                        # =========================================
                        # Update User
                        # =========================================
                        else:
                            updates = {
                                "user_name":
                                    new_name,

                                "user_email":
                                    new_email,
                            }
                            if new_password !=current_password :
                                updates["password_hash"] = new_password

                            # 只有 Admin 能修改 role/status
                            if is_admin:
                                updates[
                                    "user_role"
                                ] = new_role

                                updates[
                                    "status"
                                ] = new_status
                                updates["vacancy_incharge"] =new_vacancy_incharge


                            with st.spinner(
                                "Updating user..."
                            ):
                                response = (
                                    UserAPI.update_user(
                                        user_id=str(
                                            selected_user_id
                                        ),
                                        updates=updates,
                                        operator=operator
                                    )
                                )

                            success_message = (
                                "User updated successfully."
                            )

                        if response_success(response):
                            st.session_state[
                                "create_user"
                            ] = False

                            st.session_state[
                                "selected_user_id"
                            ] = None

                            st.success(
                                success_message
                            )

                            time.sleep(1)
                            st.rerun()

                        else:
                            st.error(
                                "Save failed: "
                                f"{response_message(response.error)}"
                            )
                        st.session_state["create_user"] ==False
                    except Exception as e:
                        st.error(
                            f"Save user error: {e}"
                            "\n\n"
                            f"{traceback.format_exc()}"
                        )
    
    
    
    

    
    # 載入自訂樣式
    footer = load_custom_css()
    render_header()
    
    # 渲染頁面標題
    current_user = st.session_state["username"]
    user_display_name = st.session_state["name"]
    config = AuthConfigGenerator.generate_config()
    user_role = config["credentials"]["usernames"][current_user]["role"]
    is_admin = True if user_role== "admin" else False
    
    # 取得統計資料（僅 admin 可見）
    if is_admin:
        with st.spinner("Statistics "):
            stats = fetch_statistics()["data"]
        render_statistics(stats)
    
    # 渲染搜尋與篩選
    filters = render_search_filters(is_admin)
    
    # 顯示當前篩選條件（如果有）
    if filters and is_admin:
        with st.expander("Current Filter", expanded=False):
            st.json(filters)
    
    # 取得使用者資料
    with st.spinner("Loading..."):
        if is_admin:
            user_data = fetch_user_data(filters=filters if filters else None)
        else:
            # 一般使用者只能看到自己的資料
            user_data = fetch_user_data(
                filters={'user_account': current_user}
            )
            print(user_data["user_id"].iloc[0])
    

    current_user_id = user_data[user_data["user_account"]==current_user]["user_id"].iloc[0]
    # 渲染編輯器（使用 fragment）
    render_user_editor(user_data, is_admin, current_user_id)

    
    # 頁尾資訊
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.markdown(f"""
        <div style="text-align: center; color: #666; padding: 2rem 0;">
            <p>{footer}</p>
        </div>
        """, unsafe_allow_html=True)

def display_user_info(user_data: Dict):
    """
    漂亮地顯示使用者資訊
    
    Args:
        user_data: 使用者資料字典（從 API 解析後的資料）
    """
    
    # 處理可能的資料結構
    if isinstance(user_data, dict):
        # 如果是 API response，提取實際資料
        if "user" in user_data:
            user_data = user_data["user"]
        elif "users" in user_data and isinstance(user_data["users"], list):
            user_data = user_data["users"][0] if user_data["users"] else {}
    
    # 安全取值函數
    def get_value(key, default="N/A"):
        value = user_data.get(key, default)
        return value if value not in [None, "", "None"] else default
    
    # 格式化日期
    def format_date(date_str):
        if not date_str or date_str == "N/A":
            return "N/A"
        try:
            if isinstance(date_str, str):
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%d %H:%M')
        except:
            pass
        return str(date_str)
    
    # 格式化狀態
    def format_status(status):
        status_map = {
            "ACTIVE": "✅ ACTIVE",
            "INACTIVE": "❌ INACTIVE",
            "PENDING": "⏳ 待審核",
        }
        return status_map.get(status, status)
    
    # 格式化角色
    def format_role(role):
        role_map = {
            "admin": "Admin",
            "user": "User",
            "guest": "Guest",
        }
        return role_map.get(role, role)
    
    # ==================== 顯示區塊 ====================
    
    st.markdown("""
        <style>
        .user-info-container {
            background: white;
            border-radius: 15px;
            padding: 2rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin: 1.5rem 0;
        }
        .user-header {
            display: flex;
            align-items: center;
            padding-bottom: 1.5rem;
            margin-bottom: 1.5rem;
            border-bottom: 2px solid #667eea;
        }
        .user-avatar {
            width: 70px;
            height: 70px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2rem;
            margin-right: 1.5rem;
            flex-shrink: 0;
        }
        .user-name-section h2 {
            margin: 0;
            color: #333;
            font-size: 1.8rem;
        }
        .user-name-section p {
            margin: 0.5rem 0 0 0;
            color: #666;
            font-size: 1rem;
        }
        .user-info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1rem;
        }
        .info-item {
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 8px;
            border-left: 3px solid #667eea;
        }
        .info-label {
            color: #666;
            font-size: 0.85rem;
            margin-bottom: 0.5rem;
            font-weight: 500;
        }
        .info-value {
            color: #333;
            font-size: 1.1rem;
            font-weight: 600;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # 取得資料
    name = get_value("name")
    email = get_value("email")
    user_id = get_value("user_id")
    role = get_value("role", "user")
    status = get_value("status", "ACTIVE")
    created_at = format_date(get_value("created_at"))
    last_login = format_date(get_value("last_login"))

    
    # 角色圖示
    role_icon = "🔑" if role == "admin" else "👤"
    
    # 頭部
    st.markdown(f"""
        <div class="user-info-container">
            <div class="user-header">
                <div class="user-avatar">{role_icon}</div>
                <div class="user-name-section">
                    <h2>{name}</h2>
                    <p>{email}</p>
                </div>
            </div>
    """, unsafe_allow_html=True)
    
    # 資訊網格
    st.markdown('<div class="user-info-grid">', unsafe_allow_html=True)
    
    # 定義要顯示的欄位
    info_items = [
        ("User ID", user_id),
        ("Role", format_role(role)),
        ("Status", format_status(status)),
        ("Rigester Time", created_at),
        ("Last Login Time", last_login),
    ]
    
    for label, value in info_items:
        if value != "N/A":  # 只顯示有值的欄位
            st.markdown(f"""
                <div class="info-item">
                    <div class="info-label">{label}</div>
                    <div class="info-value">{value}</div>
                </div>
            """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 備註（如果有）
    # if vacancy_incharge != "N/A":
    #     st.markdown(f"""
    #         <div style="margin-top: 1.5rem; padding-top: 1.5rem; border-top: 1px solid #e0e0e0;">
    #             <div class="info-label">Vacancies In Charged</div>
    #             <div style="color: #555; margin-top: 0.5rem; line-height: 1.6;">{vacancy_incharge}</div>
    #         </div>
    #     """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    

# ==================== 如果直接執行此檔案 ====================
if __name__ == "__main__":
    # 設定頁面配置
    st.set_page_config(
        page_title="User Manegement",
        page_icon="",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 呼叫主函數
    show_user_page()