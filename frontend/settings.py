from __future__ import annotations

import json
import shutil
import uuid
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from css  import load_custom_css
import streamlit as st
from api_client import SettingsAPI
from streamlit_quill import st_quill


# =========================================================
# 路徑設定
# 正式專案可以改成從共用 config 匯入
# =========================================================

BASE_DIR = Path(__file__).resolve().parent



# =========================================================
# 資料模型
# 後續若要增加設定，只需要在此新增欄位
# =========================================================


@dataclass
class EmailTemplateSettings:
    subject:str
    attachments: list 
    content: str = ""
    

@dataclass
class ThemeConfig():
    primary: str = ""
    secondary: str = ""
    hover: str = ""
    text_dark: str = ""
    text_gray: str = ""
    logo_address:str=""
    footer:str=""

@dataclass
class SystemSettings:
    score_threshold: int 
    theme:ThemeConfig
    internal_email: EmailTemplateSettings = field(
        default_factory=EmailTemplateSettings
    )
    external_email: EmailTemplateSettings = field(
        default_factory=EmailTemplateSettings
    )



# =========================================================
# Repository
# 目前使用 JSON 儲存，未來可以替換成 API 或資料庫
# =========================================================


# =========================================================
# Session State
# =========================================================

def initialize_settings_state() -> None:
    if "settings_data" not in st.session_state:
        settings = SettingsAPI.get_all_settings().data
        st.session_state.settings_data = SystemSettings(
            score_threshold=settings["score_threshold"],
            theme=ThemeConfig(**settings["theme"]),
            internal_email=EmailTemplateSettings(**settings["temp"]["internal"]),
            external_email=EmailTemplateSettings(**settings["temp"]["external"]),
            )

    if "deleted_internal_attachments" not in st.session_state:
        st.session_state.deleted_internal_attachments = set()

    if "deleted_external_attachments" not in st.session_state:
        st.session_state.deleted_external_attachments = set()


def reset_settings_state() -> None:
    settings = SettingsAPI.get_all_settings().data
    st.session_state.settings_data = SystemSettings(
        score_threshold=settings["score_threshold"],
        theme=ThemeConfig(**settings["theme"]),
        internal_email=EmailTemplateSettings(**settings["temp"]["internal"]),
        external_email=EmailTemplateSettings(**settings["temp"]["external"]),
        )
    st.session_state.deleted_internal_attachments = set()
    st.session_state.deleted_external_attachments = set()


# =========================================================
# UI 輔助函式
# =========================================================

def format_file_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"

    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"

    return f"{size / (1024 * 1024):.1f} MB"


def render_existing_attachments(
    title: str,
    ex: bool,
    settings,
    folder: Path,
    key_prefix: str,
) -> None:
    active_attachments = [f for f in folder.iterdir() if f.is_file()]

    if not active_attachments:
        return

    st.markdown(f"**{title}**")

    for index, attachment in enumerate(active_attachments):
        # attachment 已經是完整路徑，不要再跟 folder 拼接
        file_path = attachment

        name_column, action_column = st.columns(
            [8, 1],
            vertical_alignment="center",
        )

        size = file_path.stat().st_size / 1024 / 1024

        with name_column:
            st.caption(f"📎 {attachment.name} ({size:.2f}MB)")

        with action_column:
            if st.button(
                "Delete",
                key=f"{key_prefix}_delete_{index}_{attachment.name}",
                type="tertiary",
                use_container_width=True,
            ):
                attachment.unlink()

                # 依照 ex 判斷要修改哪個清單，並用檔名字串比對
                if ex:
                    settings.external_email.attachments.remove(attachment.name)
                    SettingsAPI.update_ex_temp(
                        asdict(settings.external_email),
                        st.session_state["username"],
                    )
                else:
                    settings.internal_email.attachments.remove(attachment.name)
                    SettingsAPI.update_in_temp(
                        asdict(settings.internal_email),
                        st.session_state["username"],
                    )
                st.success("Successfully Deleted "+attachment.name)
                st.rerun()

def logo_file(
    title: str,

    folder: Path,

) -> None:
    active_attachments = [f for f in folder.iterdir() if f.is_file()]

    if not active_attachments:
        return

    st.markdown(f"**{title}**")

    for index, attachment in enumerate(active_attachments):
        # attachment 已經是完整路徑，不要再跟 folder 拼接
        file_path = attachment

        name_column, action_column = st.columns(
            [8, 1],
            vertical_alignment="center",
        )

        size = file_path.stat().st_size / 1024 / 1024

        with name_column:
            st.caption(f"📎 {attachment.name} ({size:.2f}MB)")
        with action_column:
            if st.button(
                "Delete",
                key=f"delete_{index}_{attachment.name}",
                type="tertiary",
                use_container_width=True,
            ):
                attachment.unlink()
                st.rerun()

def get_remaining_attachments(
    attachments: list,
    deleted_attachment_names: set[str],
) -> list:
    return [
        attachment
        for attachment in attachments
        if attachment not in deleted_attachment_names 
    ]


# =========================================================
# Settings Page
# =========================================================
def show_settings_page() -> None:
    initialize_settings_state()
    footer = load_custom_css()
    settings: SystemSettings = st.session_state.settings_data

    st.title("Settings")

    selected_section = st.segmented_control(
        "Settings Section",
        options=[
            "Template",
            "Score Threshold",
            "Theme",
            "Information",
            "Restart System"
            
        ],
        default="Template",
        label_visibility="collapsed",
        key="settings_section",
    )

    # 預設值，避免未顯示某個區塊時變數不存在
    internal_content = settings.internal_email.content
    external_content = settings.external_email.content
    internal_uploaded_files = []
    external_uploaded_files = []
    logo_uploaded_files = []
    score_threshold = float(settings.score_threshold)

    # -----------------------------------------------------
    # Template
    # -----------------------------------------------------
    if selected_section == "Template":
        internal_tab, external_tab = st.tabs(
            [
                "Internal Letter",
                "External Letter",
            ]
        )

        with internal_tab:
            st.subheader("Internal Letter Template")

            with st.popover("Help"):
                st.markdown("""To insert candidate or vacancy information into the template, please use the syntax below.
Formatting (such as **bold**, color, font size, etc.) applied to the placeholder will be preserved after replacement.

## Syntax""")
                st.code("""
$$candidate_name$$
""")
                st.markdown("""

---

## Available Variables

### Candidate

| Placeholder | Description |
|---|---|
| `$$candidate_name$$` | Candidate Name |
| `$$candidate_ai_score$$` | AI Score |
| `$$candidate_city$$` | City |
| `$$candidate_district$$` | District |
| `$$candidate_education$$` | Education |
| `$$candidate_description$$` | Description |
| `$$candidate_current_company$$` | Current Company |
| `$$candidate_total_exp_years$$` | Total Years of Experience |
| `$$candidate_expected_salary$$` | Expected Salary |

### Vacancy

| Placeholder | Description |
|---|---|
| `$$vacancy_position$$` | Position |
| `$$vacancy_introduction$$` | Introduction |
| `$$vacancy_compensation$$` | Compensation |
| `$$vacancy_location$$` | Location |
| `$$vacancy_template$$` | Template |

### Interview

| Placeholder | Description |
|---|---|
| `$$interview_name$$` | Interview Name |
| `$$interview_date$$` | Interview Date |
| `$$interview_time_start$$` | Interview Time |
| `$$interview_time_end$$` | Interview Time |
| `$$interview_location$$` | Interview Location |
| `$$interviewer1_name$$` | Interviewer 1 Name |
| `$$interviewer1_comment$$` | Interviewer 1 Comment |
| `$$interviewer1_email$$` | Interviewer 1 Email |

> **Note:** `interviewer1`, `interviewer2`, `interviewer3`, `interviewer4` correspond to interviewers
> in the order they were filled in (i.e., the 1st, 2nd, 3rd, and 4th manager/interviewer entered).""")

            internal_content = st_quill(
                value=settings.internal_email.content,

                html=True,
                toolbar=[
                    ["bold", "italic", "underline", "strike"],
                    [{"header": [1, 2, 3, False]}],
                    [{"list": "ordered"}, {"list": "bullet"}],
                    [{"color": []}, {"background": []}],
                    ["link"],
                    ["clean"],
                ],
                key="internal_email_content",
            )

            st.markdown("##### Default Attachment")

            internal_uploaded_files = st.file_uploader(
                "Upload Internal Letter Attachment",
                accept_multiple_files=True,
                key="internal_email_attachments",
                help="""### Attachment Naming Rules

- If no lab is specified, use `general_` as the filename prefix.  
  Example: `general_人事資料表.pdf`

- If a lab is specified, use the lab name as the filename prefix.  
  Example: `文德_Map.pdf`

- When the lab name is changed, the corresponding attachment filenames will be updated automatically.""",
            )
            settings.internal_email.content = internal_content
            render_existing_attachments(
                title="Current Attachment",
                ex = False,
                settings = settings,
                folder= BASE_DIR / "static" / "settings" / "internal_attachments",
                key_prefix="internal",
            )

        with external_tab:
            st.subheader("External Letter Template")

            with st.popover("Help"):
                st.markdown("""To insert candidate or vacancy information into the template, please use the syntax below.
Formatting (such as **bold**, color, font size, etc.) applied to the placeholder will be preserved after replacement.

## Syntax""")
                st.code("""
$$candidate_name$$
""")
                st.markdown("""

---

## Available Variables

### Candidate

| Placeholder | Description |
|---|---|
| `$$candidate_name$$` | Candidate Name |
| `$$candidate_ai_score$$` | AI Score |
| `$$candidate_city$$` | City |
| `$$candidate_district$$` | District |
| `$$candidate_education$$` | Education |
| `$$candidate_description$$` | Description |
| `$$candidate_current_company$$` | Current Company |
| `$$candidate_total_exp_years$$` | Total Years of Experience |
| `$$candidate_expected_salary$$` | Expected Salary |

### Vacancy

| Placeholder | Description |
|---|---|
| `$$vacancy_position$$` | Position |
| `$$vacancy_introduction$$` | Introduction |
| `$$vacancy_compensation$$` | Compensation |
| `$$vacancy_location$$` | Location |
| `$$vacancy_template$$` | Template |

### Interview

| Placeholder | Description |
|---|---|
| `$$interview_name$$` | Interview Name |
| `$$interview_date$$` | Interview Date |
| `$$interview_time_start$$` | Interview Time |
| `$$interview_time_end$$` | Interview Time |
| `$$interview_location$$` | Interview Location |
| `$$interviewer1_name$$` | Interviewer 1 Name |
| `$$interviewer1_comment$$` | Interviewer 1 Comment |
| `$$interviewer1_email$$` | Interviewer 1 Email |

> **Note:** `interviewer1`, `interviewer2`, `interviewer3`, `interviewer4` correspond to interviewers
> in the order they were filled in (i.e., the 1st, 2nd, 3rd, and 4th manager/interviewer entered).""")

            external_content = st_quill(
                value=settings.external_email.content,
                html=True,
                toolbar=[
                    ["bold", "italic", "underline", "strike"],
                    [{"header": [1, 2, 3, False]}],
                    [{"list": "ordered"}, {"list": "bullet"}],
                    [{"color": []}, {"background": []}],
                    ["link"],
                    ["clean"],
                ],
                key="external_email_content",
            )

            st.markdown("##### Default Attachment")

            external_uploaded_files = st.file_uploader(
                "Upload External Letter Attachment",
                accept_multiple_files=True,
                key="external_email_attachments",
                help="""### Attachment Naming Rules

- If no lab is specified, use `general_` as the filename prefix.  
  Example: `general_人事資料表.pdf`

- If a lab is specified, use the lab name as the filename prefix.  
  Example: `文德_Map.pdf`

- When the lab name is changed, the corresponding attachment filenames will be updated automatically."""
            )
            settings.external_email.content = external_content
            render_existing_attachments(
                title="Current Attachment",
                ex= True,
                settings=settings,
                folder= BASE_DIR / "static" / "settings" / "external_attachments",
                key_prefix="external",
            )

    # -----------------------------------------------------
    # Score Threshold
    # -----------------------------------------------------
    elif selected_section == "Score Threshold":
        st.subheader("Score Threshold")

        score_threshold = st.number_input(
            "Minimum value",
            min_value=0.0,
            max_value=100.0,
            value=float(settings.score_threshold),
            step=1.0,
            format="%.1f",
            help=(
                "If the candidate's score meets or exceeds the "
                "threshold, the result will be marked as 'PASS'."
            ),
        )
        settings.score_threshold = score_threshold

    elif selected_section =="Theme":
        if len([f for f in Path(BASE_DIR / "static" / "settings").iterdir() if f.is_file()])<1:
            logo_uploaded_files.append(st.file_uploader(
                "Logo Upload Restrictions: PNG / JPG / SVG",
                accept_multiple_files=False,
                type=["jpg", "jpeg", "png","svg"],
                key="logo_attachments",
            ))
        logo_file("Logo",BASE_DIR / "static" / "settings")
        col1, col2, col3 ,col4,col5= st.columns(5)
        with col1:
            primary_color = st.color_picker(
                "Primary Color",
                value=settings.theme.primary
            )
        with col2:
            secondary_color = st.color_picker(
                "Secondary Color",
                value=settings.theme.secondary
            )
        with col3:
            hover_color = st.color_picker(
                "Hover Color",
                value=settings.theme.hover
            )
        with col4:
            text_dark_color = st.color_picker(
                "Text Dark Color",
                value=settings.theme.text_dark
            )
        with col5:
            text_light_color = st.color_picker(
                "Text Light Color",
                value=settings.theme.text_gray
            )

        settings.theme.primary=primary_color
        settings.theme.secondary=secondary_color
        settings.theme.hover=hover_color
        settings.theme.text_dark=text_dark_color
        settings.theme.text_gray=text_light_color
    
        footer = st.text_input("Footer",settings.theme.footer)
        settings.theme.footer = footer

    elif selected_section =="Information":
        info = json.loads(SettingsAPI.get_currnet_info(st.session_state["username"]).data)
        st.markdown("### Version")
        st.write(info["version"])
        st.markdown("### Name")
        st.write(info["name"])
        st.markdown("### Date")
        st.write(info["date"])
        st.markdown("### Summary")
        st.write(info["summary"])

        check = False
        if "update_info" in st.session_state:
            if "version" in st.session_state["update_info"] :
                st.markdown("### Update Version")
                st.write(update_info["version"])
                st.markdown("### Update Name")
                st.write(update_info["name"])
                st.markdown("### Update Date")
                st.write(update_info["date"])
                st.markdown("### Update Summary")
                st.write(update_info["summary"])
        else:
            check = st.button("Check for updates")
        if check:
            update_info = SettingsAPI.get_update_info(st.session_state["username"]).data
            st.write(update_info)
            st.session_state["update_info"] = update_info
    
    
    # -----------------------------------------------------
    # Restart System
    # -----------------------------------------------------
    elif selected_section == "Restart System":
        st.subheader("Restart System")

        st.warning(
            "Please ensure that no background processes, such as "
            "scoring, OCR, or file uploads, are currently in progress."
        )


        restart_confirmed = st.checkbox(
            "I understand that active processes may be interrupted.",
            key="restart_system_confirmation",
        )

        st.divider()

        restart_column, empty_column = st.columns([1, 6])

        with restart_column:
            restart_clicked = st.button(
                "Restart",
                type="primary",
                use_container_width=True,
                disabled=not restart_confirmed,
            )

        if restart_clicked:
            try:
                # with st.spinner("Restarting the system..."):
                    # 請替換成你實際呼叫 Restart API 的方法
                    # SystemAPI.restart_system()
                SettingsAPI.restart(st.session_state["username"])
                st.success("The restart request was submitted successfully.")

            except Exception as error:
                st.error(f"Failed to restart the system: {error}")

        # Restart 頁面不執行後面的 Save / Reload
        return

    # -----------------------------------------------------
    # Save / Reload Buttons
    # -----------------------------------------------------
    st.divider()

    save_column, reload_column, empty_column = st.columns(
        [1, 1, 5]
    )
    if selected_section:
        with save_column:
            save_clicked = st.button(
                "Save",
                type="primary",
                use_container_width=True,
            )

        with reload_column:
            reload_clicked = st.button(
                "Reload",
                use_container_width=True,
            )

        if reload_clicked:
            reset_settings_state()
            st.rerun()

        # -----------------------------------------------------
        # Save Settings
        # -----------------------------------------------------
        if save_clicked:
            try:
                if selected_section =="Template":
                    remaining_internal_attachments = get_remaining_attachments(
                        attachments=settings.internal_email.attachments,
                        deleted_attachment_names=st.session_state.deleted_internal_attachments,
                    )

                    remaining_external_attachments = get_remaining_attachments(
                        attachments=settings.external_email.attachments,
                        deleted_attachment_names=st.session_state.deleted_external_attachments,
                    )

                    error = False

                    # ---------- 處理外部信件附件上傳 ----------
                    new_external_filenames = []
                    for file in external_uploaded_files:
                        save_path = BASE_DIR / "static" / "settings" / "external_attachments" / file.name
                        if file.name not in remaining_external_attachments:
                            with open(save_path, "wb") as f:
                                f.write(file.getbuffer())
                            new_external_filenames.append(file.name)
                        else:
                            error = True
                            st.warning(file.name + " exist")
                            break

                    if not error and external_uploaded_files:
                        st.success(f"成功上傳 {len(new_external_filenames)} 個檔案")

                    # ---------- 處理內部信件附件上傳 ----------
                    new_internal_filenames = []
                    for file in internal_uploaded_files:
                        save_path = BASE_DIR / "static" / "settings" / "internal_attachments" / file.name
                        if file.name not in remaining_internal_attachments:
                            with open(save_path, "wb") as f:
                                f.write(file.getbuffer())
                            new_internal_filenames.append(file.name)
                        else:
                            error = True
                            st.warning(file.name + " exist")
                            break

                    if not error and internal_uploaded_files:
                        st.success(f"成功上傳 {len(new_internal_filenames)} 個檔案")

                    # ---------- 組合最終 attachments 並寫入 DB ----------
                    if not error:
                        settings.internal_email.attachments = (
                            remaining_internal_attachments + new_internal_filenames
                        )
                        settings.external_email.attachments = (
                            remaining_external_attachments + new_external_filenames
                        )

                        SettingsAPI.update_ex_temp(
                            asdict(settings.external_email), st.session_state["username"]
                        )
                        SettingsAPI.update_in_temp(
                            asdict(settings.internal_email), st.session_state["username"]
                        )

                elif selected_section=="Theme":
                    SettingsAPI.update_theme(asdict(settings.theme),st.session_state["username"])
                    for file in logo_uploaded_files:
                        save_path = BASE_DIR /"static" /"settings" / file.name
                        if save_path.exists():
                            st.warning(f"{file.name} already exists.")
                            continue
                        with open(save_path, "wb") as f:
                            f.write(file.getbuffer())
                            st.success(f"成功上傳 {len(logo_uploaded_files)} 個檔案")
                elif selected_section=="Score Threshold":
                    SettingsAPI.update_score_threshold(asdict(settings.score_threshold),st.session_state["username"])
                st.session_state.settings_data = settings
                st.session_state.deleted_internal_attachments = set()
                st.session_state.deleted_external_attachments = set()

                st.success("Settings saved successfully.")
                st.rerun()
            except Exception as error:
                st.error(f"Failed to save settings: {error}")
    else:
        st.warning("Please Select a Section")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.markdown(f"""
        <div style="text-align: center; color: #666; padding: 2rem 0;">
            <p>{footer}</p>
        </div>
        """, unsafe_allow_html=True)