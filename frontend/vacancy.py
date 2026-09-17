import time
from typing import Dict

import pandas as pd
import streamlit as st
import traceback
from api_client import VacancyAPI ,UserAPI,LabAPI

from css import load_custom_css
from auth import AuthConfigGenerator
LAB_COLUMNS = [
        "lab_id",
        "name",
        "address",
        "latitude",
        "longitude",
        "template",
        "contact",
        "created_time",
    ]

def show_vacancy_page():
    """職缺管理頁面"""

    # =========================================================
    # API 資料取得
    # =========================================================

    def fetch_vacancy_data(
        filters: Dict | None = None,
        limit: int = 100
    ) -> pd.DataFrame:
        """取得職缺資料"""

        try:
            response = VacancyAPI.query_vacancy(
                filters=filters,
                limit=limit
            )

            if response.success and response.data:
                # 避免 API 回傳 {"vacancies": [...]}
                if isinstance(response.data, dict):
                    vacancies = response.data.get(
                        "vacancies",
                        response.data.get("data", [])
                    )
                else:
                    vacancies = response.data

                if vacancies:
                    return pd.DataFrame(vacancies)

            return pd.DataFrame()

        except Exception as e:
            st.error(f"❌ Load Vacancy Failed: {e}")
            return pd.DataFrame()

        

    def fetch_statistics() -> Dict:
        """取得職缺統計資料"""

        try:
            response = VacancyAPI.get_statistics()

            if response.success and response.data:
                if (
                    isinstance(response.data, dict)
                    and "data" in response.data
                ):
                    return response.data["data"]

                return response.data

        except Exception as e:
            st.error(f"❌ Load Statistics Failed: {e}")

        return {
            "total_vacancies": 0,
            "active_vacancies": 0,
            "inactive_vacancies": 0,
            "total_labs": 0,
        }

    # =========================================================
    # Header
    # =========================================================

    def render_header():
        st.markdown(
            """
            <div class="main-container">
                <h1 class="page-title" style="color: white;">
                    Vacancy Management
                </h1>
            </div>
            """,
            unsafe_allow_html=True
        )

    # =========================================================
    # Statistics
    # =========================================================

    def render_statistics(stats: Dict):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(
                f"""
                <div class="stat-card">
                    <div class="stat-label">Total Vacancy</div>
                    <div class="stat-value">
                        {stats.get("total_vacancies", 0):,}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with col2:
            st.markdown(
                f"""
                <div class="stat-card">
                    <div class="stat-label">Active Vacancy</div>
                    <div class="stat-value">
                        {stats.get("active_vacancies", 0):,}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with col3:
            st.markdown(
                f"""
                <div class="stat-card">
                    <div class="stat-label">Inactive Vacancy</div>
                    <div class="stat-value">
                        {stats.get("inactive_vacancies", 0):,}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with col4:
            st.markdown(
                f"""
                <div class="stat-card">
                    <div class="stat-label">Lab Count</div>
                    <div class="stat-value">
                        {stats.get("total_labs", 0):,}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )


    def load_labs() -> pd.DataFrame:
        """從 API 載入所有 Lab。"""
        response = LabAPI.get_all_labs()
        data = response.data

        if not data:
            return pd.DataFrame(columns=LAB_COLUMNS)

        df = pd.DataFrame(data)

        # 確保所有需要的欄位都存在
        for column in LAB_COLUMNS:
            if column not in df.columns:
                df[column] = None

        # 固定欄位順序
        return df[LAB_COLUMNS]


    def initialize_lab_state():
        """初始化頁面狀態。"""
        default_values = {
            "lab_form_mode": "",
            "selected_lab_id": None,
            "lab_name": "",
            "lab_address": "",
            "lab_latitude": None,
            "lab_longitude": None,
            "lab_template": "",
            "lab_contact": "",
            "lab_created_time": "",
        }

        for key, value in default_values.items():
            if key not in st.session_state:
                st.session_state[key] = value


    def reset_lab_form():
        """清空表單並切換至新增模式。"""
        st.session_state.lab_form_mode = "create"
        st.session_state.selected_lab_id = None
        st.session_state.lab_name = ""
        st.session_state.lab_address = ""
        st.session_state.lab_latitude = None
        st.session_state.lab_longitude = None
        st.session_state.lab_template = ""
        st.session_state.lab_contact = ""
        st.session_state.lab_created_time = ""
        st.rerun(scope="app")

    def _safe_str(value) -> str:
        """把 None / NaN 安全轉成字串，避免 pandas NaN 混進 UI widget。"""
        if value is None:
            return ""
        try:
            if pd.isna(value):
                return ""
        except (TypeError, ValueError):
            # value 是不支援 isna 的型別（例如 list），視為有效值
            pass
        return str(value)

    def load_lab_into_form(lab: dict):
        """將選取的 Lab 資料放入表單。"""
        st.session_state.lab_form_mode = "edit"
        st.session_state.selected_lab_id = lab.get("lab_id")

        st.session_state.lab_name = lab.get("name") or ""
        st.session_state.lab_address = lab.get("address") or ""

        latitude = lab.get("latitude")
        longitude = lab.get("longitude")

        st.session_state.lab_latitude = (
            float(latitude)
            if latitude is not None and not pd.isna(latitude)
            else None
        )

        st.session_state.lab_longitude = (
            float(longitude)
            if longitude is not None and not pd.isna(longitude)
            else None
        )

        st.session_state.lab_template = _safe_str(lab.get("template"))
        st.session_state.lab_contact = _safe_str(lab.get("contact"))
        st.session_state.lab_created_time = str(
            lab.get("created_time") or ""
        )

    @st.fragment
    def render_lab():
        initialize_lab_state()
        # =========================================================
        # 頂部操作區
        # =========================================================

        # =========================================================
        # Lab DataFrame
        # =========================================================
        
        try:
            labs_df = load_labs()
        except Exception as error:
            st.error(f"Failed to load labs: {error}")
            return

        st.subheader("Lab List")

        if labs_df.empty:
            st.info("No lab data found. Please create a new lab.")
        else:
            # 顯示比較適合閱讀的欄位名稱
            display_df = labs_df.rename(
                columns={
                    "lab_id": "Lab ID",
                    "name": "Name",
                    "address": "Address",
                    "latitude": "Latitude",
                    "longitude": "Longitude",
                    "template": "Template",
                    "contact": "Contact",
                    "created_time": "Created Time",
                }
            )

            selection_event = st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="lab_dataframe",
                column_config={
                    "Lab ID": st.column_config.TextColumn(
                        "Lab ID",
                        width="medium",
                    ),
                    "Name": st.column_config.TextColumn(
                        "Name",
                        width="small",
                    ),
                    "Address": st.column_config.TextColumn(
                        "Address",
                        width="large",
                    ),
                    "Latitude": st.column_config.NumberColumn(
                        "Latitude",
                        format="%.6f",
                    ),
                    "Longitude": st.column_config.NumberColumn(
                        "Longitude",
                        format="%.6f",
                    ),
                    "Template": st.column_config.TextColumn(
                        "Template",
                        width="medium",
                    ),
                    "Contact": st.column_config.TextColumn(
                        "Contact",
                        width="medium",
                    ),
                    "Created Time": st.column_config.DatetimeColumn(
                        "Created Time",
                        format="YYYY-MM-DD HH:mm:ss",
                    ),
                },
            )

            selected_rows = selection_event.selection.rows

            if selected_rows:
                selected_row_index = selected_rows[0]
                selected_lab = labs_df.iloc[selected_row_index].to_dict()
                selected_lab_id = selected_lab.get("lab_id")

                # 只有選取不同 Lab 時才更新表單，避免使用者輸入到一半被覆蓋
                if selected_lab_id != st.session_state.selected_lab_id:
                    load_lab_into_form(selected_lab)
                    st.rerun()
        header_col1, header_col2 = st.columns([1, 1])

        with header_col1:
            if st.button(
                "➕ Create New Lab",
                use_container_width=True,
                type="primary",
            ):
                reset_lab_form()
                st.rerun()

        with header_col2:
            if st.button(
                "🔄 Refresh",
                use_container_width=True,
            ):
                st.rerun()

        st.divider()

        # =========================================================
        # 新增、更新表單
        # =========================================================

# =========================================================
# 新增、更新表單
# =========================================================

        form_mode = st.session_state.lab_form_mode

        # 沒有選取資料，也沒有按 Create 時，不顯示下面的詳細面板
        if form_mode in ("create", "edit") :

            is_create = form_mode == "create"

            if is_create:
                st.subheader("Create Lab")
                st.caption(
                    "Fill in the information below to create a new lab."
                )
            else:
                st.subheader("Edit Lab")
                st.caption(
                    f"Selected Lab ID: {st.session_state.selected_lab_id}"
                )

            form_key = (
                "lab_create_form"
                if is_create
                else f"lab_edit_form_{st.session_state.selected_lab_id}"
            )

            with st.form(
                key=form_key,
                clear_on_submit=False,
            ):
                # 編輯時顯示 lab_id，但不允許修改
                if not is_create:
                    st.text_input(
                        "Lab ID",
                        value=st.session_state.selected_lab_id or "",
                        disabled=True,
                    )

                name = st.text_input(
                    "Name *",
                    key="lab_name",
                    placeholder="Example: 華亞",
                )

                address = st.text_input(
                    "Address *",
                    key="lab_address",
                    placeholder="Example: 桃園市龜山區華亞二路19號",
                )

                coordinate_col1, coordinate_col2 = st.columns(2)

                with coordinate_col1:
                    latitude = st.number_input(
                        "Latitude",
                        key="lab_latitude",
                        min_value=-90.0,
                        max_value=90.0,
                        step=0.000001,
                        format="%.6f",
                        value=None,
                        placeholder="Leave blank to automatically retrieve the coordinates."
                    )

                with coordinate_col2:
                    longitude = st.number_input(
                        "Longitude",
                        key="lab_longitude",
                        min_value=-180.0,
                        max_value=180.0,
                        step=0.000001,
                        format="%.6f",
                        value=None,
                        placeholder="Leave blank to automatically retrieve the coordinates."
                    )

                template = st.text_area(
                    "Template",
                    key="lab_template",
                    placeholder=(
                        "Enter the lab template or related configuration."
                    ),
                    height=120,
                )

                contact = st.text_input(
                    "Contact",
                    key="lab_contact",
                    placeholder="Contact person, phone number, or email",
                )

                if not is_create:
                    st.text_input(
                        "Created Time",
                        key="lab_created_time",
                        disabled=True,
                    )

                st.caption("* Required field")

                submit_button = st.form_submit_button(
                    "💾 Create" if is_create else "💾 Update",
                    type="primary",
                    use_container_width=True,
                )
                if not is_create and st.session_state.selected_lab_id:
                    st.warning(
                        "Deleting this lab is permanent and cannot be undone."
                    )
    
                    if st.form_submit_button(
                        "🗑️ Delete Lab",
                        type="secondary",
                        use_container_width=True,
                    ):
                        lab_id = st.session_state.selected_lab_id
    
                        try:
                            LabAPI.delete_lab(lab_id=lab_id)
    
                            # reset_lab_form()
    
                            # 刪除成功後，讓詳細面板收起來
                            st.session_state.lab_form_mode = ""
    
                            st.success("Lab deleted successfully.")
                            st.rerun()
    
                        except Exception as error:
                            st.error(
                                f"Failed to delete lab: {error}"
                            )

            # =========================================================
            # 處理新增或更新
            # =========================================================

            if submit_button:
                cleaned_name = name.strip()
                cleaned_address = address.strip()
                cleaned_template = template.strip() or None
                cleaned_contact = contact.strip() or None

                validation_errors = []

                if not cleaned_name:
                    validation_errors.append("Name is required.")

                if not cleaned_address:
                    validation_errors.append("Address is required.")

                if validation_errors:
                    for validation_error in validation_errors:
                        st.error(validation_error)

                else:
                    lab_payload = {
                        "name": cleaned_name,
                        "address": cleaned_address,
                        "latitude": latitude,
                        "longitude": longitude,
                        "template": cleaned_template,
                        "contact": cleaned_contact,
                    }

                    try:
                        if is_create:
                            LabAPI.create_lab(lab_payload)

                            # 建立成功後，讓詳細面板收起來
                            reset_lab_form()
                            st.session_state.lab_form_mode = ""

                            st.success("Lab created successfully.")
                            st.rerun()

                        else:
                            lab_id = st.session_state.selected_lab_id

                            if not lab_id:
                                st.error("No lab selected.")

                            else:
                                LabAPI.update_lab(
                                    lab_id=lab_id,
                                    updates=lab_payload
                                )

                                st.success("Lab updated successfully.")
                                st.rerun()

                    except Exception as error:
                        operation = "create" if is_create else "update"
                        st.error(
                            f"Failed to {operation} lab: {error}"
                        )

            # =========================================================
            # 刪除區域
            # =========================================================

            

    # =========================================================
    # Search / Filter
    # =========================================================

    def render_search_filters() -> Dict:
        filters = {}

        st.markdown(
            '<div class="custom-divider"></div>',
            unsafe_allow_html=True
        )

        st.markdown("## Search / Filter")

        col1, col2, col3 = st.columns(3)

        with col1:
            position_title = st.text_input(
                "Position",
                placeholder="e.g. RF Test Engineer",
                key="vacancy_search_position"
            )

            if position_title:
                filters["position_title"] = position_title

        with col2:
            lab = st.text_input(
                "Lab",
                placeholder="e.g. Wireless Lab",
                key="vacancy_search_lab"
            )

            if lab:
                filters["lab"] = lab

        with col3:
            work_location = st.text_input(
                "Work Location",
                placeholder="e.g. Taipei",
                key="vacancy_search_location"
            )

            if work_location:
                filters["work_location"] = work_location

        col4, col5, col6 = st.columns(3)

        with col4:
            senior = st.selectbox(
                "Senior",
                options=[
                    "All",
                    "S",
                    "M",
                    "L"
                ],
                key="vacancy_filter_senior"
            )

            if senior != "All":
                filters["senior"] = senior

        with col5:
            status = st.selectbox(
                "Status",
                options=[
                    "ALL",
                    "INACTIVE",
                    "ACTIVE",
                    "DELETED"
                ],
                key="vacancy_filter_status"
            )
        if status !="ALL":
            filters["status"] = status

        with col6:
            vacancy_id = st.text_input(
                "Vacancy ID",
                placeholder="Vacancy UUID",
                key="vacancy_search_id"
            )

            if vacancy_id:
                filters["vacancy_id"] = vacancy_id

        col_button1, col_button2, _ = st.columns([1, 1, 4])

        with col_button1:
            if st.button(
                "Apply",
                use_container_width=True,
                key="vacancy_apply_filter"
            ):
                st.rerun()

        with col_button2:
            if st.button(
                "Clear",
                use_container_width=True,
                key="vacancy_clear_filter"
            ):
                filter_prefixes = (
                    "vacancy_search_",
                    "vacancy_filter_"
                )

                for key in list(st.session_state.keys()):
                    if key.startswith(filter_prefixes):
                        del st.session_state[key]

                st.rerun()

        return filters

    # =========================================================
    # Vacancy Editor
    # =========================================================

    @st.fragment
    def render_vacancy_editor(
        vacancy_data: pd.DataFrame,
        is_admin: bool,
        current_user_account: str
    ):
        # =========================================================
        # Session State 初始化
        # =========================================================
        if "create_vac" not in st.session_state:
            st.session_state["create_vac"] = False

        if "selected_vacancy_id" not in st.session_state:
            st.session_state["selected_vacancy_id"] = None

        is_create = st.session_state["create_vac"]

        # API 使用的操作者
        operator = st.session_state.get(
            "username",
            current_user_account
        )

        # =========================================================
        # Vacancy List
        # 即使 vacancy_data 是空的，仍然允許管理員 Create New
        # =========================================================
        st.markdown(
            '<div class="edit-title">Vacancy List</div>',
            unsafe_allow_html=True
        )

        selected_rows = []

        if vacancy_data is None:
            vacancy_data = pd.DataFrame()

        if vacancy_data.empty:
            st.warning("⚠️ No Vacancy Available")

        else:
            selection_df = vacancy_data.copy().set_index("vacancy_id")

            event = st.dataframe(
                selection_df,
                on_select="rerun",
                selection_mode="single-row",
                column_config={

                    "vacancy_id": st.column_config.TextColumn(
                        "Vacancy ID",
                        disabled=True,
                        width="large"
                    ),
                    "position_title": st.column_config.TextColumn(
                        "Position",
                        disabled=True,
                        width="large"
                    ),
                    "lab": st.column_config.TextColumn(
                        "Lab",
                        disabled=True,
                        width="medium"
                    ),
                    "senior": st.column_config.TextColumn(
                        "Senior",
                        disabled=True,
                        width="small"
                    ),
                    "work_location": st.column_config.TextColumn(
                        "Location",
                        disabled=True,
                        width="medium"
                    ),
                    "weight": st.column_config.TextColumn(
                        "Weight",
                        disabled=True,
                        width="small"
                    ),
                    "manager": st.column_config.TextColumn(
                        "Manager",
                        disabled=True,
                        width="small"
                    ),
                    "status": st.column_config.TextColumn(
                        "Status",
                        disabled=True,
                        width="small"
                    )
                },
                use_container_width=True,
                key="vacancy_selection_editor"
            )
            selected_rows = event.get("selection", {}).get("rows", [])
            selected_vacancy_id = None

            if selected_rows and not selection_df.empty:
                selected_idx = selected_rows[0]

                # 如果刪掉最後一筆，原本的位置超出範圍，就改選新的最後一筆
                selected_idx = min(selected_idx, len(selection_df) - 1)

                selected_vacancy_id = selection_df.index[selected_idx]

            
                # 從 full_df 中抽取出被點選的那一筆完整資料
                selected_rows = vacancy_data[vacancy_data['vacancy_id'] == selected_vacancy_id].iloc[0]



        # =========================================================
        # Create New
        # =========================================================
        create_button = None
        if  len(selected_rows)==0 :
            create_button = st.button(
                "Create New",
                disabled=not is_admin,
                key="create_new_vacancy_button"
            )
            if create_button:
                st.session_state["create_vac"] = True
                st.session_state["selected_vacancy_id"] = None
                st.rerun()
            if not st.session_state["create_vac"]:
                st.warning("Please select a vacancy to view or edit.")
                return
        else:
            st.session_state["create_vac"] = False



        # Create New 觸發 rerun 後，重新取得最新 state
        is_create = st.session_state["create_vac"]

        # =========================================================
        # 決定 Create Mode / Edit Mode
        # =========================================================
        if is_create:
            # Create Mode 不需要 selected_rows
            target_df = pd.DataFrame(
                [
                    {
                        "vacancy_id": "",
                        "position_title": "",
                        "introduction": "",
                        "compensation": "",
                        "requirements": "",
                        "work_location": "",
                        "manager":"",
                        "senior": "",
                        "lab": "華亞",
                        "weight": "",
                        "education_score_error": "",
                        "education_score_5": "",
                        "education_score_4": "",
                        "education_score_3": "",
                        "education_score_2": "",
                        "education_score_1": "",
                        "education_score_0": "",
                        "status": "ACTIVE",
                        "created_at": "",
                        "updated_at": ""
                    }
                ]
            )

            selected_vacancy_id = ""

        else:
            # Edit Mode 才檢查 selected_rows
            if vacancy_data.empty:
                st.info(
                    "Click Create New to create a vacancy."
                    if is_admin
                    else "No vacancy is available."
                )
                return


            st.session_state[
                "selected_vacancy_id"
            ] = selected_vacancy_id

            target_df = vacancy_data[
                vacancy_data["vacancy_id"].astype(str)
                == selected_vacancy_id
            ].copy()

            if target_df.empty:
                st.error(
                    "Selected vacancy cannot be found."
                )
                return

        target_vacancy = target_df.iloc[0]

        # =========================================================
        # Safe value functions
        # =========================================================
        def safe_text(column: str) -> str:
            value = target_vacancy.get(column)

            if value is None:
                return ""

            try:
                if pd.isna(value):
                    return ""
            except (TypeError, ValueError):
                pass

            return str(value)

        # =========================================================
        # Editor title
        # =========================================================
        if is_create:
            position_name = "New Vacancy"
        else:
            position_name = (
                safe_text("position_title")
                or "N/A"
            )

        st.markdown(
            f"""
            <div class="edit-title">
                Vacancy Info：{position_name}
            </div>
            """,
            unsafe_allow_html=True
        )

        # 非管理員只能查看
        # disabled = not is_admin
        disabled = False

        # =========================================================
        # Lab options
        # =========================================================
        try:
            lab_response = (
                VacancyAPI.get_lab_options()
            )

            lab_options =  [item["name"] for item in LabAPI.get_all_labs().data]

        except Exception as e:
            lab_options = []
            st.warning(
                f"Failed to load Lab options: {e}"
            )

        if lab_options is None:
            lab_options = []

        # 避免 API 回傳非 list
        lab_options = list(lab_options)

        # 移除 None、空字串及重複值
        lab_options = list(
            dict.fromkeys(
                str(option).strip()
                for option in lab_options
                if option is not None
                and str(option).strip()
            )
        )

        current_lab = safe_text("lab").strip()

        # 確保 selectbox 一定有選項
        if not lab_options:
            lab_options = [
                current_lab or "華亞"
            ]

        # DB 現有值不在 API options 時，保留現有值
        if (
            current_lab
            and current_lab not in lab_options
        ):
            lab_options.insert(
                0,
                current_lab
            )

        if not current_lab:
            if "華亞" in lab_options:
                current_lab = "華亞"
            else:
                current_lab = lab_options[0]

        current_lab_index = lab_options.index(
            current_lab
        )

        # =========================================================
        # Status options
        # =========================================================
        status_options = [
            "ACTIVE",
            "INACTIVE",
            "DELETED"
        ]

        current_status = (
            safe_text("status").strip().upper()
            or "ACTIVE"
        )

        if current_status not in status_options:
            status_options.insert(
                0,
                current_status
            )

        current_status_index = (
            status_options.index(current_status)
        )

        # =========================================================
        # Form
        # Create 和 Edit 使用不同 key，避免 widget state 混在一起
        # =========================================================
        form_mode = (
            "create"
            if is_create
            else f"edit_{selected_vacancy_id}"
        )
        with st.form(
            key=f"vacancy_edit_form_{form_mode}",
            clear_on_submit=False
        ):
            col1, col2 = st.columns(2)
            
            with col1:
                new_position_title = st.text_input(
                    "Position",
                    value=safe_text(
                        "position_title"
                    ),
                    disabled=disabled
                )

                new_compensation = st.text_input(
                    "Compensation",
                    value=safe_text(
                        "compensation"
                    ),
                    disabled=disabled
                )

                new_work_location = st.text_input(
                    "Work Location",
                    value=safe_text(
                        "work_location"
                    ),
                    disabled=disabled
                )
                senior_list = ["S","M","L"]
                new_senior = st.selectbox(
                    "Senior",
                    options=senior_list,
                    index=senior_list.index(safe_text("senior")) if safe_text("senior") in senior_list else 0,
                    disabled=disabled
                )

                new_lab = st.selectbox(
                    "Lab",
                    options=lab_options,
                    index=current_lab_index,
                    disabled=disabled
                )

                new_weight = st.text_area(
                    "Weight",
                    value=safe_text("weight"),
                    disabled=disabled
                )
                new_manager = st.text_area(
                    "Manager",
                    value=safe_text("manager"),
                    disabled=disabled
                )

            with col2:
                new_status = st.selectbox(
                    "Status",
                    options=[
            "ACTIVE",
            "INACTIVE"],
                    index=current_status_index,
                    disabled=disabled
                )

                new_education_score_error = (
                    st.text_area(
                        "Education Score - Error",
                        value=safe_text(
                            "education_score_error"
                        ),
                        disabled=disabled
                    )
                )

                new_education_score_5 = (
                    st.text_area(
                        "Education Score - 5",
                        value=safe_text(
                            "education_score_5"
                        ),
                        disabled=disabled
                    )
                )

                new_education_score_4 = (
                    st.text_area(
                        "Education Score - 4",
                        value=safe_text(
                            "education_score_4"
                        ),
                        disabled=disabled
                    )
                )

                new_education_score_3 = (
                    st.text_area(
                        "Education Score - 3",
                        value=safe_text(
                            "education_score_3"
                        ),
                        disabled=disabled
                    )
                )

                new_education_score_2 = (
                    st.text_area(
                        "Education Score - 2",
                        value=safe_text(
                            "education_score_2"
                        ),
                        disabled=disabled
                    )
                )

                new_education_score_1 = (
                    st.text_area(
                        "Education Score - 1",
                        value=safe_text(
                            "education_score_1"
                        ),
                        disabled=disabled
                    )
                )

                new_education_score_0 = (
                    st.text_area(
                        "Education Score - 0",
                        value=safe_text(
                            "education_score_0"
                        ),
                        disabled=disabled
                    )
                )

            new_introduction = st.text_area(
                "Introduction",
                value=safe_text("introduction"),
                height=300,
                disabled=disabled
            )

            new_requirements = st.text_area(
                "Requirements",
                value=safe_text("requirements"),
                height=200,
                disabled=disabled
            )

            if is_create:
                st.caption(
                    "Vacancy ID will be generated "
                    "after creation."
                )
            else:
                st.caption(
                    f"Vacancy ID: "
                    f"{selected_vacancy_id}"
                )

            # if not is_admin:
            #     st.info(
            #         "You have read-only access "
            #         "to this vacancy."
            #     )

            st.markdown("---")

            col_button1, col_button2,col_button3, _ = (
                st.columns([1, 1,1, 4])
            )

            with col_button1:
                submit_button = (
                    st.form_submit_button(
                        (
                            "💾 Create"
                            if is_create
                            else "💾 Update"
                        ),
                        type="primary",
                        use_container_width=True,
                        disabled=disabled
                    )
                )
            cancel_button = None
            if safe_text("status")!="DELETED":
                with col_button2:
                    cancel_button = (
                        st.form_submit_button(
                            "❌ Cancel" if is_create else "🗑️Delete",
                            use_container_width=True
                        )
                    )
            with col_button3:
                copy_button = st.form_submit_button(
                    label = "Copy",
                    disabled = True if is_create else False
                )
            if copy_button:
                updates = {
                        "position_title":
                            "*COPY "+ new_position_title.strip(),
    
                        "introduction":
                            new_introduction.strip(),
    
                        "compensation":
                            new_compensation.strip(),
    
                        "requirements":
                            new_requirements.strip(),
    
                        "work_location":
                            new_work_location.strip(),
    
                        "manager":
                            new_manager.strip(),
    
                        "senior":
                            new_senior.strip(),
    
                        "lab":
                            new_lab.strip(),
    
                        "weight":
                            new_weight,
    
                        "education_score_error":
                            new_education_score_error,
    
                        "education_score_5":
                            new_education_score_5,
    
                        "education_score_4":
                            new_education_score_4,
    
                        "education_score_3":
                            new_education_score_3,
    
                        "education_score_2":
                            new_education_score_2,
    
                        "education_score_1":
                            new_education_score_1,
    
                        "education_score_0":
                            new_education_score_0,
    
                        "status":
                            new_status
                    }
                with st.spinner("Copying"):
                    response = (
                        VacancyAPI.create_vacancy(
                            vacancy=updates,
                            operator=operator
                        )
                    )
                    if response.success:
                        st.success("Copy Success")
                        st.rerun(scope="app")
                    else:
                        st.warning("Copy Failed")
                
            # =====================================================
            # Cancel
            # =====================================================
            if cancel_button:
                if is_create:
                    st.session_state[
                        "create_vac"
                    ] = False

                    st.session_state[
                        "selected_vacancy_id"
                    ] = None

                    st.rerun()
                else:
                    VacancyAPI.delete_vacancy(vacancy_ids=selected_vacancy_id,operator=st.session_state["username"])
                    st.success(f"{safe_text("position_title")} has been Deleted")
                    st.session_state[
                        "create_vac"
                    ] = False

                    st.session_state[
                        "selected_vacancy_id"
                    ] = None
                    st.rerun()

            # =====================================================
            # Create / Update
            # =====================================================
            if submit_button:
                updates = {
                    "position_title":
                        new_position_title.strip(),

                    "introduction":
                        new_introduction.strip(),

                    "compensation":
                        new_compensation.strip(),

                    "requirements":
                        new_requirements.strip(),

                    "work_location":
                        new_work_location.strip(),

                    "manager":
                        new_manager.strip(),

                    "senior":
                        new_senior.strip(),

                    "lab":
                        new_lab.strip(),

                    "weight":
                        new_weight,

                    "education_score_error":
                        new_education_score_error,

                    "education_score_5":
                        new_education_score_5,

                    "education_score_4":
                        new_education_score_4,

                    "education_score_3":
                        new_education_score_3,

                    "education_score_2":
                        new_education_score_2,

                    "education_score_1":
                        new_education_score_1,

                    "education_score_0":
                        new_education_score_0,

                    "status":
                        new_status
                }

                if not updates["position_title"]:
                    st.error(
                        "Position cannot be empty."
                    )

                else:
                    try:
                        action_text = (
                            "Creating vacancy..."
                            if is_create
                            else "Updating vacancy..."
                        )

                        with st.spinner(action_text):
                            if is_create:
                                response = (
                                    VacancyAPI.create_vacancy(
                                        vacancy=updates,
                                        operator=operator
                                    )
                                )

                            else:

                                original_vacancy_name = str(
                                    selected_rows[
                                        "position_title"
                                    ]
                                )

                                response = (
                                    VacancyAPI.update_vacancy(
                                        vacancy_name=(
                                            original_vacancy_name
                                        ),
                                        vacancy_id=str(
                                            selected_vacancy_id
                                        ),
                                        updates=updates,
                                        operator=operator
                                    )
                                )

                        if response.success:
                            # API 成功後才退出 Create Mode
                            st.session_state[
                                "create_vac"
                            ] = False

                            st.session_state[
                                "selected_vacancy_id"
                            ] = None

                            success_message = (
                                "Vacancy created successfully."
                                if is_create
                                else
                                "Vacancy updated successfully."
                            )

                            st.success(success_message)

                            time.sleep(1)
                            st.rerun( scope= "app")

                        else:
                            st.error(
                                "Save failed: "
                                f"{response.error}"
                            )

                    except Exception as e:
                        st.error(
                            "Save vacancy error: "
                            f"{e}\n\n"
                            f"{traceback.format_exc()}"
                        )

    # =========================================================
    # Main Page
    # =========================================================

    footer = load_custom_css()
    render_header()

    current_user = st.session_state["username"]
    user_display_name = st.session_state["name"]
    config = AuthConfigGenerator.generate_config()
    user_role = config["credentials"]["usernames"][current_user]["role"]
    is_admin = True if user_role== "admin" else False

    # Admin 顯示全部統計
    if is_admin:
        with st.spinner("Loading statistics..."):
            stats = fetch_statistics()

        render_statistics(stats)
    render_lab()
    filters = render_search_filters()

    # 非管理員只查自己負責的職缺
    if not is_admin:

        user = UserAPI.get_user_by_account(current_user).data

        filters["position_title_authority"] = user["vacancy_incharge"]

    if filters:
        with st.expander(
            "Current Filter",
            expanded=False
        ):
            st.json(filters)

    with st.spinner("Loading vacancies..."):
        vacancy_data = fetch_vacancy_data(
            filters=filters or None,
            limit=100
        )

    render_vacancy_editor(
        vacancy_data=vacancy_data,
        is_admin=is_admin,
        current_user_account=current_user
    )

    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.markdown(f"""
        <div style="text-align: center; color: #666; padding: 2rem 0;">
            <p>{footer}</p>
        </div>
        """, unsafe_allow_html=True)