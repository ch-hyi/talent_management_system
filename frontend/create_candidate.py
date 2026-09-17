# frontend/streamlit_app.py
"""

"""
import json
import streamlit as st
import uuid
from datetime import datetime
import time
from pathlib import Path
from api_client import TalentAPI

import uuid

# from config import config

@st.fragment
def create_new(talent_api:TalentAPI,status_options):
    st.write(st.session_state["create_talent"])
    if st.session_state["create_talent"]:
        st.write("innnn")
        with st.form("talent_form"):

            st.subheader("Candidate Info ( * Required)")

            col1, col2 = st.columns(2)

            with col1:
                source = st.text_input("Source",disabled=True,value="Internal")
                source_id = st.text_input("Source ID",disabled=True,value=str(uuid.uuid4()))
                source_link = st.text_input("Source Link")
                recommender = st.text_input("Recommender" ,disabled=True,value = st.session_state["username"])
                age_value=18
                tptal_exp_years_value = 0
                expected_salary_value = 0
                name_value = ""
                gender_list = [ "男", "女"]
                gender_value = 0
                phone_value = "" 
                email_value = ""
                city_value = ""
                district_value = ""
                current_company_value = ""
                current_job_title_value = ""
                if "ocr_result" in st.session_state:
                    if st.session_state["ocr_result"]["age"] :
                        try:
                            age_value = int(st.session_state["ocr_result"]["age"])  
                        except:
                            pass
                    if st.session_state["ocr_result"]["total_exp_years"]:
                        try:
                            tptal_exp_years_value = int(st.session_state["ocr_result"]["total_exp_years"])
                        except:
                            pass
                    if st.session_state["ocr_result"]["expected_salary"]:
                        try:
                            expected_salary_value = int(st.session_state["ocr_result"]["expected_salary"])
                        except:
                            pass
                    if st.session_state["ocr_result"]["name"]:
                        name_value = st.session_state["ocr_result"]["name"]
                    if st.session_state["ocr_result"]["gender"]:
                        if st.session_state["ocr_result"]["gender"] in gender_list:
                            gender_value = gender_list.index(st.session_state["ocr_result"]["gender"])
                    if st.session_state["ocr_result"]["phone"]:
                        phone_value = st.session_state["ocr_result"]["phone"]
                    if st.session_state["ocr_result"]["email"]:
                        email_value = st.session_state["ocr_result"]["email"]
                    if st.session_state["ocr_result"]["city"]:    
                        city_value = st.session_state["ocr_result"]["city"]
                    if st.session_state["ocr_result"]["district"]:
                        district_value = st.session_state["ocr_result"]["district"]
                    if st.session_state["ocr_result"]["current_company"]:
                        current_company_value = st.session_state["ocr_result"]["current_company"]
                    if st.session_state["ocr_result"]["current_job_title"]:
                        current_job_title_value = st.session_state["ocr_result"]["current_job_title"]
                name = st.text_input("Name *" ,value=name_value)
                


                gender = st.selectbox(
                    "Sex *",
                    gender_list,
                    index= gender_value
                )
                
                age = st.number_input(
                    "Age *",
                    min_value=0,
                    step=1,
                    value=age_value
                )

                phone = st.text_input("Phone *",value=phone_value)
                email = st.text_input("Email *",value=email_value)

                city = st.text_input("City *",value=city_value)
                district = st.text_input("District *",value = district_value)

            with col2:

                vacancy = st.text_input("Vacancy *")

                current_status = st.selectbox("Hiring Status *",options=status_options)

                current_company = st.text_input("Current Company",value=current_company_value)
                current_job_title = st.text_input("Current Job Title",value = current_job_title_value)

                total_exp_years = st.number_input(
                    "Experience Years",
                    min_value=0,
                    step=1,
                    value=tptal_exp_years_value
                )

                expected_salary = st.number_input(
                    "Expected Salary",
                    min_value=0,
                    step=1000,
                    value=expected_salary_value
                )

                received_time = st.date_input(
                    "Create Time",
                    value=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )

                interview_time = st.date_input(
                    "Interview Time",
                    value=None
                )

                onboarding_date = st.date_input(
                    "Onboarding Date",
                    value=None
                )

            st.divider()

            st.subheader("教育背景")

            edu1, edu2, edu3 = st.columns(3)

            with edu1:
                education_school = st.text_input("School *")
                education_department = st.text_input("Department *")

            with edu2:
                education_degree = st.text_input("Degree *")
                education_discipline = st.text_input("Discipline *")

            with edu3:
                education_mode = st.text_input("Mode *")
                education_status = st.text_input("Status *")

            st.divider()

            st.subheader("系統欄位")

            sys1, sys2 = st.columns(2)

            with sys1:
                block = st.checkbox("Block", value=False)


            with sys2:
                block_reason = st.text_input(
                    "Block Reason"
                )

                # msg_backup_path = st.text_input(
                #     "Resume Path"
                # )


            note = st.text_area(
                "Note",
                height=150
            )

            meeting = st.text_area(
                "Meeting ID",
                height=120
            )

            btn1, btn2, btn3 = st.columns(3)
            empty = []
            with btn1:
                if st.form_submit_button(
                    "💾 Save",
                    use_container_width=True
                ):
                    
                    
                    if not name:
                        empty.append("Name")

                    if not recommender:
                        empty.append("Recommender")

                    if not gender:
                        empty.append("Gender")

                    if not age:
                        empty.append("Age")

                    if not phone:
                        empty.append("Phone")

                    if not email:
                        empty.append("Email")

                    if not city:
                        empty.append("City")

                    if not district:
                        empty.append("District")

                    if not vacancy:
                        empty.append("Vacancy")

                    if not current_status:
                        empty.append("Vacancy")

                    if not education_school:
                        empty.append("Vacancy")

                    if not education_department:
                        empty.append("Vacancy")

                    if not education_degree:
                        empty.append("Vacancy")

                    if not education_discipline:
                        empty.append("Vacancy")

                    if not education_mode:
                        empty.append("Vacancy")

                    if not education_status:
                        empty.append("Vacancy")

                    
                    if len(empty)==0:
                        st.session_state["create_talent"] = False
                        talent = {
                            "source": source,
                            "source_id": source_id,
                            "source_link": source_link,
                            "mail_id": "",

                            "received_time": str(received_time) if received_time else None,
                            "interview_time": str(interview_time) if interview_time else None,
                            "onboarding_date": str(onboarding_date) if onboarding_date else None,

                            "recommender": recommender,
                            "name": name,
                            "gender": gender,
                            "age": age,

                            "score": 0,
                            "score_distance": 0,
                            "score_experience": 0,
                            "score_education": 0,
                            "score_age": 0,

                            "review_status": "待審核",
                            "review_reason": "無",
                            "reviewer": None,

                            "education_department": education_department,
                            "education_school": education_school,
                            "education_degree": education_degree,
                            "education_discipline": education_discipline,
                            "education_mode": education_mode,
                            "education_status": education_status,

                            "vacancy": vacancy,
                            "city": city,
                            "district": district,

                            "phone": phone,
                            "email": email,

                            "current_company": current_company,
                            "current_job_title": current_job_title,
                            "total_exp_years": total_exp_years,

                            "expected_salary": expected_salary,
                            "current_status": current_status,

                            "note": note,
                            "meeting": meeting,
                            "description": "",

                            "msg_backup_path": "",

                            "block": int(block),
                            "lock_status": 0,
                            "block_reason": block_reason,
                        }
                        body = "TODO"
                        response = TalentAPI.create_talent(talent,body)
                        if response.success:
                            st.session_state["create_talent"] = False
                            st.session_state["create_talent_save"] = True
                            st.rerun(scope="app")
                        else:
                            st.error(response.error)
            with btn2:
                if st.form_submit_button(
                    "📄 OCR",
                    use_container_width=True,
                    key="create_form"
                ):
                    st.session_state["ocr_btn"] = True
                

            with btn3:
                if st.form_submit_button(
                    "取消",
                    use_container_width=True
                ):
                    st.session_state["create_talent"] = False
                    st.rerun()


            if len(empty)>0:
                st.error('"'+" , ".join(empty)+'"' +" can't be empty.")
        if "ocr_btn" in st.session_state :
            uploaded_file = st.file_uploader(label="OCR File Upload",label_visibility="collapsed",accept_multiple_files=False,type=["pdf", "docx", "xlsx","jpg", "jpeg", "png","ppt"],key="ocr_uploader")
            if uploaded_file:
                if st.button("Upload", key="btn_upload_ocr_file", use_container_width=True):
                    file_name = source+"_"+uploaded_file.name
                    save_path = (
                        Path(__file__).parent
                        / "static"
                        / "temp"
                        / file_name
                    )
                    if save_path.exists():
                        with st.spinner("Loading..."):
                            result = talent_api.get_ocr_result(str(save_path),st.session_state["username"])
                            if result.success:
                                st.session_state["ocr_result"] = json.loads(result.data["result_json"])
                                st.session_state["create_talent"] = True
                                st.rerun(scope="fragment")
                            else:
                                st.warning(f"{file_name} already exists but has no OCR result.")

                    else:
                        with open(save_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                            st.success(f"Succeed")
                        with st.spinner("OCR in progress..."):
                            
                            queue_result = talent_api.ocr(
                                str(save_path),
                                st.session_state["username"]
                            )

                            if queue_result.success:
                                st.success(queue_result.message)
                                result = None

                                for _ in range(20):

                                    task_result = talent_api.get_ocr_result(str(save_path),st.session_state["username"])

                                    if task_result.success:

                                        result = task_result.data
                                        break

                                    time.sleep(5)

                                if result:

                                    st.success("OCR Completed")
                                    st.session_state["ocr_result"] = json.loads(result["result_json"])
                                    st.session_state["create_talent"] = True
                                    st.rerun()
                                else:
                                    st.warning(
                                        "OCR is still processing in background. Please refresh later and then upload the same file."
                                    )
                            else:
                                st.error(queue_result.error)

                    del st.session_state["ocr_uploader"]
                    del st.session_state["ocr_btn"]
                    # st.rerun()
                