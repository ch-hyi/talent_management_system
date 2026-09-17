from pathlib import Path
from typing import Optional

import json
import logging
import tempfile
import re

from pydantic import BaseModel, Field
from ollama import chat


from pypdf import PdfReader

import pymupdf

from docling.document_converter import DocumentConverter

# --------------------------------------------------
# Celery
# --------------------------------------------------



# --------------------------------------------------
# Docling
# --------------------------------------------------

converter = DocumentConverter()

# --------------------------------------------------
# Schema
# --------------------------------------------------

from typing import Optional 
from pydantic import BaseModel, Field


from typing import Optional
from pydantic import BaseModel, Field


import re

from typing import Optional

from pydantic import BaseModel, Field


# ==========================
# Raw Schema
# ==========================

class Education(BaseModel):

    school: Optional[str] = Field(
        default=None,
        description="學校名稱"
    )

    department: Optional[str] = Field(
        default=None,
        description="系所名稱"
    )

    degree: Optional[str] = Field(
        default=None,
        description="學位，例如學士、碩士、博士"
    )


class Experience(BaseModel):

    company: Optional[str] = Field(
        default=None,
        description="公司名稱"
    )

    title: Optional[str] = Field(
        default=None,
        description="職稱"
    )

    start_date: Optional[str] = Field(
        default=None,
        description="開始日期，例如 2025.07"
    )

    end_date: Optional[str] = Field(
        default=None,
        description="結束日期，例如 2025.08。仍在職可填 Present。"
    )


class ResumeRawSchema(BaseModel):

    name: Optional[str] = Field(
        default=None,
        description="求職者姓名"
    )

    gender: Optional[str] = Field(
        default=None,
        description="求職者性別",
        json_schema_extra={
            "enum": ["男", "女"]
        }
    )

    age: Optional[int] = Field(
        default=None,
        description="求職者年齡"
    )

    city: Optional[str] = Field(
        default=None,
        description="居住城市"
    )

    district: Optional[str] = Field(
        default=None,
        description="居住行政區"
    )

    educations: list[Education] = Field(
        default_factory=list,
        description="所有教育背景"
    )

    experiences: list[Experience] = Field(
        default_factory=list,
        description="所有工作經歷與實習經歷"
    )

    skills: list[str] = Field(
        default_factory=list,
        description="所有技能"
    )

    expected_salary: Optional[int] = Field(
        default=None,
        description="期望薪資"
    )


# ==========================
# Final Schema
# ==========================

class ResumeSchema(BaseModel):

    name: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None

    phone: Optional[str] = None
    email: Optional[str] = None

    city: Optional[str] = None
    district: Optional[str] = None

    education: Optional[str] = None

    current_company: Optional[str] = None
    current_job_title: Optional[str] = None

    total_exp_years: Optional[float] = None

    expected_salary: Optional[int] = None


# ==========================
# Regex Helpers
# ==========================

def extract_email(text: str) -> str|None :
    match= re.search(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        text
    )

    return match.group(0) if match else None


def extract_phone(text: str) -> str|None: 
    patterns = [
        r"\+886[- ]?9\d{8}",
        r"09\d{8}"
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            return match.group(0)

    return None


# ==========================
# Experience Calculation
# ==========================

from datetime import datetime


def parse_date(date_str: str | None) -> datetime | None:

    if not date_str:
        return None

    date_str = date_str.strip()

    if date_str.lower() in ["present", "current", "now"]:
        return datetime.today()

    formats = [
        "%Y.%m",
        "%Y-%m",
        "%Y/%m",
        "%Y.%m.%d",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass

    return None


def calc_total_exp_years(
    experiences: list[Experience]
) -> float | None:

    if not experiences:
        return None

    total_months = 0

    for exp in experiences:

        start = parse_date(exp.start_date)
        end = parse_date(exp.end_date)

        if not start or not end:
            continue

        months = (
            (end.year - start.year) * 12
            + (end.month - start.month)
        )

        if months < 0:
            continue

        total_months += months

    years = round(total_months / 12, 1)

    return years if years > 0 else None



# ==========================
# Normalize
# ==========================

def normalize_resume(
    raw: ResumeRawSchema,
    resume_text: str
) -> ResumeSchema:

    email = extract_email(resume_text)

    phone = extract_phone(resume_text)

    highest_education = None

    if raw.educations:
        highest_education = raw.educations[-1]

    latest_exp = None

    if raw.experiences:
        latest_exp = raw.experiences[0]

    education_string = None

    if highest_education:

        school = highest_education.school or ""

        department = highest_education.department or ""

        education_string = f"{school} {department}".strip()

    return ResumeSchema(

        name=raw.name,

        gender=raw.gender,

        age=raw.age,

        phone=phone,

        email=email,

        city=raw.city,

        district=raw.district,

        education=education_string,

        current_company=(
            latest_exp.company
            if latest_exp
            else None
        ),

        current_job_title=(
            latest_exp.title
            if latest_exp
            else None
        ),

        total_exp_years=calc_total_exp_years(
            raw.experiences
        ),

        expected_salary=raw.expected_salary
    )


# ==========================
# Main
# ==========================

def llm_parse_resume(
    resume_text: str,
    model: str = "qwen3.5_9b"
):

    response = chat(

        model=model,

        messages=[

            {
                "role": "system",

                "content": """
你是一位專業的履歷解析專家。

任務：
從履歷內容中擷取所有事實資訊。

規則：

1. 僅根據履歷內容擷取資訊。
2. 保留原始語言。
3. 不可翻譯。
4. 不可推測。
5. 找不到資訊時回傳 null 或空陣列。
6. 若履歷同時包含中英文版本，視為同一份履歷。
7. 應盡可能擷取所有學歷。
8. 應盡可能擷取所有工作經歷與實習經歷。
9. 應盡可能擷取所有技能。
10. 僅輸出合法 JSON。
11. 不可輸出 Markdown。
12. 不可輸出說明文字。
13. 不可輸出思考過程。
"""
            },

            {
                "role": "user",
                "content": resume_text
            }
        ],

        options={
            "temperature": 0.1
        },

        think=False,

        format=ResumeRawSchema.model_json_schema()
    )

    content = response["message"]["content"]

    raw = ResumeRawSchema.model_validate_json(
        content
    )

    return normalize_resume(
        raw,
        resume_text
    )




# --------------------------------------------------
# PDF -> Image
# --------------------------------------------------

def pdf_to_images(pdf_path: str):

    pdf = pymupdf.open(pdf_path)
    temp_dir = tempfile.mkdtemp()

    image_paths = []

    for page_num in range(len(pdf)):

        page = pdf[page_num]

        pix = page.get_pixmap(
            matrix=pymupdf.Matrix(2, 2)
        )

        image_path = (
            Path(temp_dir)
            / f"page_{page_num}.png"
        )

        pix.save(str(image_path))

        image_paths.append(str(image_path))

    return image_paths


# --------------------------------------------------
# Docling OCR
# --------------------------------------------------

def docling_ocr_image(image_path: str) -> str:

    result = converter.convert(image_path)

    return result.document.export_to_markdown()


def docling_ocr_pdf(pdf_path: str) -> str:

    image_paths = pdf_to_images(pdf_path)

    texts = []

    for image_path in image_paths:

        try:

            text = docling_ocr_image(image_path)

            if text.strip():
                texts.append(text)

        except Exception as e:

            logging.exception(
                f"OCR failed: {image_path}"
            )

    return "\n\n".join(texts)


# --------------------------------------------------
# Text Extraction
# --------------------------------------------------

def extract_resume_text(file_path: str) -> str:

    file_path = str(file_path)

    suffix = Path(file_path).suffix.lower()

    if suffix in [".png", ".jpg", ".jpeg"]:

        logging.info(
            "Image detected -> Docling OCR"
        )

        return docling_ocr_image(file_path)

    if suffix == ".pdf":

        try:

            reader = PdfReader(file_path)

            if reader.is_encrypted:

                logging.info(
                    "Encrypted PDF -> OCR"
                )

                return docling_ocr_pdf(file_path)

        except Exception as e:

            logging.exception(
                "PDF validation failed"
            )

            return docling_ocr_pdf(file_path)

        try:

            logging.info(
                "Trying Docling text extraction"
            )

            result = converter.convert(file_path)

            text = (
                result.document
                .export_to_markdown()
                .strip()
            )

            if len(text) > 100:

                logging.info(
                    "Docling text extraction success"
                )

                return text

            logging.info(
                "Too little text -> OCR"
            )

            return docling_ocr_pdf(file_path)

        except Exception as e:

            logging.exception(
                "Docling failed -> OCR"
            )

            return docling_ocr_pdf(file_path)

    raise ValueError(
        f"Unsupported file type: {suffix}"
    )


# --------------------------------------------------
# LLM Parse Resume
# --------------------------------------------------

# def llm_parse_resume(
#     resume_text: str,
#     model: str = "qwen3.5_9b"
# ):
#     print(resume_text)
#     import re

#     emails = re.findall(
#         r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
#         resume_text
#     )

#     phones = re.findall(
#         r"(?:\+886[- ]?)?09\d{8}",
#         resume_text
#     )
#     result.phone = phones[0] if phones else None
#     result.email = emails[0] if emails else None
    
#     response = chat(
#         model=model,
#         messages=[
#             {
#                 "role": "system",
#                 "content": """
# 你是一位專業的履歷解析專家。

# 任務：
# 從履歷內容中擷取求職者資訊，並依照提供的 JSON Schema 輸出結果。

# 規則：

# 1. 僅根據履歷內容擷取資訊。
# 2. 保留原始語言，不要翻譯。
# 3. 必須嚴格遵循 JSON Schema。
# 4. 所有欄位都必須存在。
# 5. 找不到資訊時請填入 null。
# 6. 不得推測、補全或編造資訊。
# 7. 若履歷同時包含中英文版本，視為同一份履歷，不可重複解析。
# 8. 僅輸出合法 JSON。
# 9. 不可輸出 Markdown。
# 10. 不可輸出解釋、註解、前言或結語。
# 11. 不可輸出思考過程、分析內容或推理步驟。
# """
#             },
#             {
#                 "role": "user",
#                 "content": resume_text
#             }
#             ],
#             options={
#                 'temperature': 0.1,
#             },think=False,
#         format=ResumeSchema.model_json_schema()
#     )

#     full_content = response['message'].get('content', '')
#     result = full_content.strip()

#     json = ResumeSchema.model_validate_json(
#         result
#     )
#     if json :
#         return json 
#     else:
#         return None


# --------------------------------------------------
# Main
# --------------------------------------------------




def parse_resume(
    file_path: str,
    model: str = "qwen3.5_9b"
):

    text = extract_resume_text(file_path)
    logging.info(text)
    logging.info(
        f"Extracted {len(text)} chars"
    )

    candidate = llm_parse_resume(
        text,
        model=model
    )

    return candidate.model_dump()


# --------------------------------------------------
# Test
# --------------------------------------------------

if __name__ == "__main__":

    result = parse_resume(
        "resume.pdf",
        model="qwen3.5_9b"
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=4
        )
    )