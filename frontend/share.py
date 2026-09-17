# frontend/streamlit_app.py
"""

"""
import json

import streamlit as st
from pathlib import Path
from bs4 import BeautifulSoup
import urllib.parse
import re
from css import  load_custom_css
import streamlit.components.v1 as components
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


def render_candidate_readonly(person):
    footer = load_custom_css()
    c1, c2 = st.columns(2)
    if person:
        with c1:
            st.markdown(
                        f"### :blue[[{person['name']}]({person.get('source_link', '#')})] "
                        f"<span style='color: gray; font-size: 15px; font-weight: normal; margin-left: 10px;'>"
                        f"update {person.get('update_time', 'N/A')}</span>",
                        unsafe_allow_html=True
                    )

            st.write(f"**Gender:** {person.get('gender','')}")
            st.write(f"**Age:** {person.get('age','')}")
            st.write(
                f"**Education:** "
                f"{person.get('education_school','')} "
                f"{person.get('education_department','')} "
                f"{person.get('education_degree','')}"
            )

            st.write(
                f"**Vacancy:** {person.get('vacancy','')}"
            )

            st.write(
                f"**Location:** "
                f"{person.get('city','')} "
                f"{person.get('district','')}"
            )

            st.write(
                f"**Experience:** "
                f"{person.get('total_exp_years','')} years"
            )

            st.write(
                f"**Company:** "
                f"{person.get('current_company','')}"
            )

            st.write(
                f"**Title:** "
                f"{person.get('current_job_title','')}"
            )

        with c2:

            st.write(
                f"**Phone:** {person.get('phone','')}"
            )

            st.write(
                f"**Email:** {person.get('email','')}"
            )

            st.write(
                f"**Status:** {person.get('current_status','')}"
            )

            st.write(
                f"**Expected Salary:** "
                f"{person.get('expected_salary','')}"
            )
            st.write(
                f"**Score:** "
                f"{person.get('score','')}"
            )
            st.write(
                f"**Ditance Score:** "
                f"{person.get('score_distance','')}"
            )
            st.write(
                f"**Experience Score:** "
                f"{person.get('score_experience','')}"
            )
            st.write(
                f"**Education Score:** "
                f"{person.get('score_education','')}"
            )
            st.write(
                f"**Age Score:** "
                f"{person.get('score_age','')}"
            )


        st.divider()

        st.subheader("Description")

        st.markdown(
            person.get("description","")
        )

        st.divider()

        st.subheader("Invitation")

        st.code(
            person.get("invitation","")
        )

        st.divider()

        if person.get("msg_backup_path"):

            resume_url = (
                f"/resume?"
                f"source={person["source"]}"
                f"&source_id={person["source_id"]}"
            )

            st.markdown(f"**📁 [Open Resume]({resume_url})**")

        user_dir = (
            Path(__file__).parent
            / "static"
            / "attachment"
            / f"{person['source']}_{person['source_id']}"
        )

        if user_dir.exists():

            for file in user_dir.iterdir():

                if file.is_file():

                    with open(file, "rb") as f:

                        st.download_button(
                            label=file.name,
                            data=f.read(),
                            file_name=file.name,
                            use_container_width=True,
                        )

        st.divider()

        review_status = person.get(
            "review_status"
        )

        if review_status:

            try:

                interviews = json.loads(
                    review_status
                )

                st.subheader(
                    "Interview Records"
                )

                for interview in interviews:

                    with st.expander(
                        interview.get(
                            "name",
                            "Interview"
                        ),
                        expanded=True
                    ):

                        st.write(
                            "**Date:**",
                            interview.get(
                                "date",
                                ""
                            )
                        )

                        st.write(
                            "**Location:**",
                            interview.get(
                                "location",
                                ""
                            )
                        )

                        note = interview.get(
                            "note",
                            ""
                        )   
                        candidate_mail = interview.get("candidate_mail")
                        ex_attachments = interview.get("ex_attachments")
                        if note:
                            st.write("**Note:**")
                            components.html(
                                note,
                                height=500,
                                scrolling=True
                            )
                        if candidate_mail:
                            st.write("**Candidate Mail:**")
                            components.html(
                                    candidate_mail,
                                    height=500,
                                    scrolling=True
                                )
                        if ex_attachments:
                            st.write("**External Attachments:**")
                            st.write(ex_attachments)
                        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
                        for reviewer in interview.get(
                            "reviewers",
                            []
                        ):

                            st.write(
                                "**Interviewer:**",reviewer.get('interviewer','')
                            )

                            st.write("**Email:**",reviewer.get("email","")
                            )

                            st.write("**Comments:**",reviewer.get("comment","")
                            )
                            st.divider()

            except Exception:
                pass

        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
        st.markdown(f"""
            <div style="text-align: center; color: #666; padding: 2rem 0;">
                <p>{footer}</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.error("This link has expired.")

    # st.subheader("Notes")

    # if person.get("note"):
    #     person_key = f"comments_{person['source_id']}"
    #     st.session_state[person_key] = []
    #     soup = BeautifulSoup(str(person["note"]), "html.parser")
    #     p_tags = soup.find_all("p")
        
    #     for idx, p in enumerate(p_tags):
    #         full_text = p.get_text()
            
    #         # 檢查是否已被刪除
    #         is_deleted = "已刪除" in full_text or "[已刪除]" in full_text
            
    #         try:
    #             # 匹配正常留言格式
    #             match = re.match(
    #                 r"使用者：(.*?)\s*於\s*(.*?)\s*留言：\s*(.*)",
    #                 full_text,
    #                 flags=re.DOTALL
    #             )
    #             if match:
    #                 st.session_state[person_key].append({
    #                     "id": idx,
    #                     "author": match.group(1),
    #                     "text": match.group(3),
    #                     "time": match.group(2),
    #                     "is_deleted": is_deleted
    #                 })
    #             # 匹配已刪除留言格式
    #             elif "已刪除" in full_text:
    #                 deleted_match = re.match(r"使用者：(.*?) 於 (.*?) 的留言已刪除", full_text)
    #                 if deleted_match:
    #                     st.session_state[person_key].append({
    #                         "id": idx,
    #                         "author": deleted_match.group(1),
    #                         "text": "",
    #                         "time": deleted_match.group(2),
    #                         "is_deleted": True
    #                     })
    #         except Exception as e:
    #                 st.session_state[person_key].append({
    #                     "id": idx,
    #                     "author": "系統紀錄",
    #                     "text": full_text,
    #                     "time": "",
    #                     "is_deleted": is_deleted
    #                 })
    #     comment_container = st.container(height=500)
    #     with comment_container:
    #         current_user = st.session_state.get("email", "User")
            
    #         for idx, c in enumerate(st.session_state[person_key]):
    #             author_name = str(c.get("author", "User")).strip()
    #             is_deleted = c.get("is_deleted", False)
                
    #             # 創建刪除確認的 session_state key
    #             confirm_key = f"confirm_delete_{person['source_id']}_{idx}"
    #             if confirm_key not in st.session_state:
    #                 st.session_state[confirm_key] = False
                
    #             # 創建兩欄布局:留言內容 + 刪除按鈕
    #             col_msg, col_del = st.columns([0.6, 0.065])
                
    #             with col_msg:
    #                 with st.chat_message("user"):
    #                     if is_deleted:
    #                         # 已刪除的留言樣式
    #                         st.markdown(
    #                             f"**{author_name}** <span style='color:gray; font-size:12px;'>{c.get('time', '')}</span>",
    #                             unsafe_allow_html=True
    #                         )
    #                         st.markdown(
    #                             "<span style='color:#999; font-style:italic;'>🚫 The note had been deleted.</span>",
    #                             unsafe_allow_html=True
    #                         )
    #                     else:
    #                         # 正常留言
    #                         st.markdown(
    #                             f"**{author_name}** <span style='color:gray; font-size:12px;'>{c.get('time', '')}</span>",
    #                             unsafe_allow_html=True
    #                         )
    #                         st.write(c.get("text", ""))