"""
評分服務模組
提供履歷評分、學歷驗證、英文能力評估等功能
"""

import ollama
from . import code_translator
import math
from difflib import get_close_matches
import pandas as pd
import re
import random
from typing import Optional, Tuple, Dict
from pathlib import Path
import requests
from ..models.talent import Talent,TalentBatchUpdateRequest
import time
from .vacancy_service import VacancyService
from ..repositories.log_repository import LogRepository
from ..repositories.vacancy_repository import VacancyRepository
from ..models.log import LogEntry
from celery.signals import worker_process_init
from celery import Celery
from dataclasses import dataclass
from . import config
import logging
from ..config import REDIS_URL
import traceback

backend_service = Celery('mail_scoring_system',
        broker_url=REDIS_URL, 
        result_backend=REDIS_URL,  
             )


# 全局評分服務
scoring_service = None
talent_service = None



@dataclass
class ScoringWeights:
    """評分權重配置"""
    distance: int
    experience: int
    age: int
    education: int


@dataclass
class EducationResult:
    """學歷評估結果"""
    score: float
    discipline: str  # 學門
    status: str  # 就學狀態
    degree: str  # 學位
    department: str  # 科系
    school: str  # 學校
    mode: str  # 就讀模式


@dataclass
class ScoringResult:
    """完整評分結果"""
    total_score: float
    distance_score: float
    experience_score: float
    education_score: float
    age_score: float
    
    # 權重
    weight_distance: int
    weight_experience: int
    weight_education: int
    weight_age: int
    
    # 學歷詳情
    education_discipline: str
    education_status: str
    education_degree: str
    education_department: str
    education_school: str
    education_mode: str
    
    # 地理資訊
    city: str
    district: str
    
    # 工作經驗
    invitation:str
    total_exp_years: str
    current_company: str
    current_job_title: str


class ScoringService:
    """履歷評分服務"""
    
    # 常數定義
    ENGLISH_LEVEL_MAP = {
        "母語": 5,
        "流利": 4,
        "尚可": 3,
        "待加強": 2,
        "難以溝通": 1,
        "完全不會": 0
    }
    
    DEGREE_SCORE_MAP = {
        "博士": 1.0,
        "碩士": 1.0,
        "學士": 0.95,
        "二技": 0.95,
        "五專": 0.9,
        "高職": 0.8,
        "高中": 0.75,
        "國中以下": 0.6,
    }
    
    SCHOOL_SCORE_MAP = {
        "CODE_A": 1.0,
        "CODE_B": 1.0,
        "CODE_C": 0.9,
        "CODE_D": 0.85,
        "CODE_E": 0.8,
        "CODE_F": 0.7,
        "CODE_G": 0.65
    }
    
    MODE_SCORE_MAP = {
        "日間部": 1.0,
        "進修部": 0.9,
        "夜間部": 0.9,
        "在職專班": 0.8,
        "假日班":0.7,
        "學分班": 0.7
    }

    def __init__(
        self,
        discipline_file_path: str = "C:/Users/rchang4/talent_system/backend/data/學門.xlsx",
        sub_discipline_file_path: str = "C:/Users/rchang4/talent_system/backend/data/學類.xlsx",
        model_name: str = 'qwen3.5_9b',
        num_ctx: int = 6144,
        temperature: float = 0.2
    ):
        """
        初始化評分服務
        
        Args:
            jd_file_path: 職缺描述檔案路徑
            discipline_file_path: 學門分類檔案路徑
            sub_discipline_file_path: 學類分類檔案路徑
            model_name: Ollama 模型名稱
            num_ctx: 上下文 token 數量
            temperature: 模型溫度參數
        """
        self.log_repo = LogRepository()
        self.vacancy_repo = VacancyRepository()
        self.vacancy_service = VacancyService(self.vacancy_repo,self.log_repo)
        self.discipline_file_path = Path(discipline_file_path)
        self.sub_discipline_file_path = Path(sub_discipline_file_path)
        self.model_name = model_name
        self.num_ctx = num_ctx
        self.temperature = temperature
        
        # 載入資料
        self._load_data()
    
    def _load_data(self):
        """載入所需的 Excel 資料"""
        try:
            
            self.df_discipline = pd.read_excel(
                self.discipline_file_path,
                dtype={"代碼": str}
            )
            self.df_sub_discipline = pd.read_excel(
                self.sub_discipline_file_path,
                dtype={"代碼": str}
            )
        except FileNotFoundError as e:
            raise FileNotFoundError(f"無法載入資料檔案: {e}")
        
    def wait_for_ollama(
            self,
        check_interval: int = 3
    ):
        """Ollama啟動程序"""
        
        print(f" 等待 Ollama 服務啟動 (模型: {self.model_name})...")
        
        attempt = 0
        
        while True:
            attempt += 1
            
            try:
                response = requests.get(
                    'http://127.0.0.1:11434/api/tags',
                    timeout=5
                )
                if int(response.status_code) != 200:
                    print(f" [{attempt}] 服務未響應 (狀態: {response.status_code})")
                    time.sleep(check_interval)
                    continue

                test_response = ollama.chat(
                    model=self.model_name,
                    messages=[{'role': 'user', 'content': 'test'}],
                    options={'num_ctx': 1}
                )

                print(f"✅ Ollama 服務就緒(請求 {attempt} 次)")
                return True
                
            except requests.exceptions.ConnectionError:
                print(f" [{attempt}] 連線失敗...")
                time.sleep(check_interval)
                
            except requests.exceptions.Timeout:
                print(f" [{attempt}] 請求超時...")
                time.sleep(check_interval)
                
            except ollama.ResponseError as e:
                if "No user query found" in str(e):
                    print(f" [{attempt}] Chat template 未就緒...")
                else:
                    print(f" [{attempt}] 未知 ResponseError: {e}")
                time.sleep(check_interval)
                    
            except Exception as e:
                print(f" [{attempt}] 檢查失敗: {type(e).__name__}: {e}")
                time.sleep(check_interval)

    def verify_resume(
        self,
        name:str,
        vacancy: str,
        education: str,
        location: str,
        age: int,
        resume_body: str
    ) -> Tuple[Optional[str], ScoringResult]:
        """
        驗證履歷並評分
        
        Args:
            vacancy: 職缺名稱
            education: 學歷資訊
            location: 地點
            age: 年齡
            resume_body: 履歷內容
        
        Returns:
            (錯誤訊息, 評分結果)
        """
        # 查找職缺
        print(vacancy)

        vac = self.vacancy_service.query_vacancies({"position_title":vacancy},1,0).data[0]
        print(vac)
        if len(vac) == 0:
            error_msg = "<p>**評分失敗，輸入之職缺不在公司職缺EXCEL中**</p>"
            return error_msg, None
        
        # 提取職缺資訊
        jd = vac["introduction"]
        jd_condition = vac["requirements"]
        is_senior = vac["senior"] 
        education_requirements = {
            k: vac[k]
            for k in [
                "education_score_5",
                "education_score_4",
                "education_score_3",
                "education_score_2",
                "education_score_1",
                "education_score_0"
            ]
        }
        
        # 解析權重
        weights = self._parse_weights(vac["weight"])
        
        # 生成隨機種子
        random_seed = random.randint(1, 1000000)
        
        # 計算各項分數
        invitation = self._invitation(name,vacancy,resume_body,random_seed)

        experience_score = self._calculate_experience_score(
            vacancy, jd,jd_condition, resume_body, random_seed
        )
        
        english_score = self._calculate_english_score(
            vacancy, jd, resume_body, random_seed
        )
        
        # 如果需要英文,調整經驗分數
        if self._is_mostly_english(jd):
            experience_score *= english_score
        
        # 提取工作經驗資訊
        work_info = self._extract_work_info(resume_body, random_seed)
        
        # 計算距離分數
        city = location.split(",")[0]
        district = location.split(",")[1]
        
        code = code_translator.district_to_code(city,district)
        distance_score = code_translator.distance_search(
            vac["lab"], vacancy, code
        )
        
        
        # 計算學歷分數
        education_result = self._evaluate_education(
            education, education_requirements, random_seed
        )
        
        # 計算年齡分數
        age_score = self._calculate_age_score(age, is_senior)

        # 應用權重
        weighted_distance = distance_score * weights.distance
        weighted_experience = experience_score * weights.experience
        weighted_education = education_result.score * weights.education
        weighted_age = age_score * weights.age
        
        # 計算總分
        total_score = (
            weighted_distance +
            weighted_experience +
            weighted_education +
            weighted_age
        )
        
        # 組裝結果
        result = ScoringResult(
            total_score=round(total_score, 2),
            distance_score=round(weighted_distance, 2),
            experience_score=round(weighted_experience, 2),
            education_score=round(weighted_education, 2),
            age_score=round(weighted_age, 2),
            weight_distance=weights.distance,
            weight_experience=weights.experience,
            weight_education=weights.education,
            weight_age=weights.age,
            education_discipline=education_result.discipline,
            education_status=education_result.status,
            education_degree=education_result.degree,
            education_department=education_result.department,
            education_school=education_result.school,
            education_mode=education_result.mode,
            city=city,
            district=district,
            invitation = invitation,
            total_exp_years=work_info['years'],
            current_company=work_info['company'],
            current_job_title=work_info['title']
        )
        
        return None, result
    
    def _parse_weights(self, weight_string: str) -> ScoringWeights:
        """解析權重字串"""
        weights = [int(w) * 10 for w in weight_string.split(",")]
        return ScoringWeights(
            distance=weights[0],
            experience=weights[1],
            age=weights[2],
            education=weights[3]
        )
    
    def _is_mostly_english(self, text: str) -> bool:
        """
        判斷文本是否以英文為主
        
        Args:
            text: 待判斷文本
        
        Returns:
            是否以英文為主
        """
        english_words = re.findall(r'\b[a-zA-Z]+\b', text)
        english_count = len(english_words)
        
        chinese_chars = re.findall(r'[\u4e00-\u9fa5]', text)
        chinese_count = len(chinese_chars)
        
        if english_count == 0 and chinese_count == 0:
            return False
        
        return english_count > chinese_count

    def _invitation(
        self,  
        name:str     , 
        vacancy: str,
        resume_content:str,
        random_seed: int):
        invitation_instruction="""
你是專業招募顧問。請依以下履歷與職缺內容根據規範，撰寫一封高度客製化的面試邀請函。
請先判斷求職者最可能重視的 1 至 2 項職涯需求，例如：職涯成長、職責提升、薪資潛力、通勤便利、專業發揮、學習資源、工作氛圍或生活品質，再選擇最相關的重點深入撰寫，不要羅列所有福利。
可使用的公司優勢包括：具競爭力的薪酬與績效獎金、完善的夥伴制度、免費課程資源、社團補助、免費咖啡與零食、免費供餐、汽機車免費停車位、佳節福利及推薦獎金。不得虛構其他條件。
撰寫要求：
1. 清楚說明注意到求職者的原因，以及其經歷與職缺的連結。
2. 委婉呈現此機會如何協助其拓展下一階段的職涯發展。
3. 不得直接批評其現況，或使用「卡住、瓶頸、薪資太低、討厭制度」等說法。
4. 不得推測個性、經濟壓力、家庭狀況或其他履歷未明確提供的資訊。
5. 避免提及年齡、家庭背景等敏感細節，也不要過度引用履歷中的私人資訊。
6. 不得虛構薪資數字、職稱、福利、升遷或工作制度。
7. 使用繁體中文，語氣專業、真誠、自然，避免誇張及制式 AI 用語。
8. 全文約 200 至 300 個中文字，包含邀請面談及自然結尾。
9. 不要輸出標題、分析、Markdown 或任何額外說明，直接輸出完整信件。
10. 禁止使用「貴公司」、「貴團隊」或其他將招募方誤寫為第三方公司的稱呼。
11. 不得輸出任何收件人稱呼或招呼語，例如「您好」、「王先生您好」、「陳小姐您好」、「Hi」、「Dear」等，請直接進入邀請函內文。"""
        response = ollama.chat(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        invitation_instruction
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"職缺名稱：{vacancy}\n\n"
                        f"候選人履歷：\n\n{resume_content}\n\n"

                        "請用最真誠的口吻生成令人嚮往的200字以內面試邀請函"
                    )
                }
            ],
            options={
                'num_ctx': self.num_ctx,
                'temperature': 0.5,
                'seed': random_seed
            },
            think=False
        )
        full_content = response['message'].get('content', '')
        result = full_content.strip()

        invitation = f"""Mr./Ms. {name} 您好，我們是Bureau Veritas的招募團隊，我們正在尋找 {vacancy} 人才，非常高興在104人力銀行上看到了您的履歷！

        {result}

若您對我們公司的發展方向感興趣，不曉得是否方便安排10-15分鐘與您通話？
再請讓我知道您方便接聽電話的時間，期待您的回應，謝謝！
 
關於Bureau Veritas，歡迎點擊連結：https://ee.bureauveritas.com.tw
 
Best Regards,
Bureau Veritas的招募團隊
        """

        return invitation
        
    def _calculate_experience_score(
        self,
        vacancy: str,
        jd: str,
        jd_condiition:str,
        resume_body: str,
        random_seed: int
    ) -> float:
        """
        計算經驗匹配分數
        
        Returns:
            0-1 之間的分數
        """
        MAP =  {
                "完全符合": 1.0,        # 深度掌握
                "幾乎符合": 0.8,        # 日常運用
                "大致符合": 0.6,        # 基本認知
                "稍微符合": 0.4,        # 知道概念
                "幾乎不符合": 0.2,        # 幾乎不懂
                "完全不符合": 0.0    
                }
        try:
            resume_content = resume_body.split("個人資料")[1].split("附件")[0].strip()
        except IndexError:
            resume_content = resume_body
        
        response_special = ollama.chat(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": ("""
你是嚴格且客觀的履歷經歷分析系統。

任務：
僅根據候選人的「工作經驗」與「技術技能」，提取16個可供職缺適配度評估的經歷亮點。

亮點不是單純形容候選人優秀，而是履歷中可被驗證、可與不同職缺要求進行比較的經歷事實。

優先提取以下類型的資訊：

1. 產業與領域經驗
例如：在半導體產業工作5年、具3年RF檢測經驗、長期從事餐飲門市管理。

2. 職務與核心工作經驗
例如：擔任設備工程師3年、負責自動化測試系統開發、負責門市營運與人員管理。

3. 技術、工具與設備的實際使用經驗
例如：使用Python開發測試工具、操作網路分析儀、維護蝕刻設備。
只有列出技能名稱但沒有使用情境時，不得自行補充熟練度或實務成果。

4. 問題解決與異常處理經驗
例如：處理設備異常、分析測試失敗原因、改善產品良率。
不得僅因職稱而推測候選人具備問題解決能力。

5. 溝通、合作與協調經驗
例如：跨部門協調、客戶技術溝通、供應商協作、團隊合作。
不得將「個性開朗」等自我描述當成工作溝通經驗。

6. 成果與影響
例如：提升效率20%、降低錯誤率、縮短測試時間、完成特定專案。
必須保留履歷中的數字或明確成果，不得自行估算。

7. 經歷深度與穩定性
例如：在同一產業累積10年經驗、單一公司任職5年、連續三份工作皆超過2年。
必須根據履歷中明確記載的任職期間計算，不得猜測缺失日期。

8. 管理、帶領與責任範圍
例如：帶領5人團隊、負責教育訓練、獨立負責專案、管理實驗室運作。

9. 工作情境與特殊條件經驗
例如：具輪班經驗、實驗室工作經驗、現場設備維護經驗、出差支援經驗。

10. 工作中實際使用外語的經驗
例如：以英文與海外客戶溝通、閱讀英文技術文件、參與跨國專案。
只有語言能力或檢定分數，不算工作經驗亮點。

提取規則：

1. 只能使用履歷中明確存在的內容。
2. 不得根據職稱、公司名稱或產業常識補充履歷未提及的能力。
3. 每個亮點必須是完整、獨立且可理解的經歷事實。
4. 優先保留年資、頻率、規模、成果數字、對象、設備、工具及工作情境。
5. 不得使用「經驗豐富」、「能力良好」、「熟悉相關工作」等無法驗證的空泛描述。
6. 不得把同一項經歷拆成多個意思高度重複的亮點。
7. 不同亮點可以來自同一份工作，但必須代表不同的能力或經歷證據。
8. 不得使用學歷、年齡、性別或單純的語言檢定成績。
9. 如果履歷沒有足夠資訊，不得為了湊滿16個而虛構或重複。
10. 每個亮點保持精簡，原則上不超過50個中文字。
11. 只輸出亮點，不得輸出解釋、標題、編號或Markdown語法。
12. 使用井字號分隔每個亮點，開頭必須有井字號。

輸出格式：
#亮點1#亮點2#亮點3

正確示例：
#具5年RF檢測產業經驗#於同一公司連續任職4年#操作網路分析儀進行產品測試#負責測試異常分析與原因排查#與研發及製造部門協調異常改善

錯誤示例：
#能力優秀#具良好溝通能力#熟悉各種技術#可能具備異常處理能力
                        """
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"職缺名稱：{vacancy}\n\n"
                        f"候選人履歷：\n\n{resume_content}\n\n"

                        "請提取 16 個技術亮點（只能從工作經驗和技能提取，禁止學歷）"
                    )
                }
            ],
            options={
                'num_ctx': self.num_ctx,
                'temperature': 0.3,
                'seed': random_seed
            },
            think=False
        )
        
        full_content_special = response_special['message'].get('content', '')
        result_special = full_content_special.strip()

        logging.info(result_special)
        answer = []
        score_answer = []
        response_topk =  ollama.chat(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                    """你是嚴格且客觀的技術人資排序系統。

任務：
根據職缺描述，將候選人的全部經歷亮點按照「對該職缺的適配證據強度」由高至低排序。

排序時依序考慮：

1. 是否直接符合職缺的必要條件
例如：指定職務經驗、產業經驗、技術、設備、證照、輪班或工作情境要求。

2. 經驗的直接程度
排序優先級原則：
相同職務且相同產業
高於
相近職務或相近產業
高於
可以轉移的通用能力
高於
僅有關鍵字相似但工作內容不同。

3. 經驗的深度
在其他條件相近時：
多年且持續的實務經驗
高於
短期實務經驗
高於
僅接觸、協助或沒有期間資訊的經驗。

4. 經驗的實際程度
實際負責、獨立執行、處理異常或完成成果
高於
參與或協助
高於
只列出技能名稱而無使用情境。

5. 職缺明確重視的能力
包括問題解決、異常處理、溝通協調、團隊合作、管理、客戶應對、外語使用或其他職缺明確要求。

6. 工作穩定性與領域累積
只有當職缺描述明確重視年資、穩定性、產業累積或即戰力時，才提高相關亮點的排序。

7. 工作條件
輪班、出差、現場作業、實驗室環境等亮點，只有在職缺明確要求時才提高排序。

排序限制：

1. 必須輸出所有原始亮點，不得刪除。
2. 每個亮點只能出現一次。
3. 排序後的亮點文字必須與原始文字完全一致。
4. 只能改變亮點順序，禁止改寫、縮寫、合併或新增內容。
5. 不得因為亮點含有與JD相同的單一關鍵字，就判定為高度相關。
6. 必須判斷該亮點所代表的實際工作內容是否符合職缺。
7. 不得輸出解釋、分數、標題、編號或Markdown語法。
8. 使用井字號分隔亮點，開頭必須有井字號。

輸出格式：
#排序後亮點1#排序後亮點2#排序後亮點3
         """
                )
                },
                {
                    "role": "user",
                    "content": (
                        f"""請根據職缺與職缺描述後只從下列亮點中重新排序：

                        {result_special}

                        *
                        禁止新增亮點。
                        禁止刪除亮點。
                        禁止修改亮點文字。
                        禁止生成職缺亮點。
                        完全根據候選人亮點進行排序。
                        *

                        
                        職缺：{vacancy}\n
                        職缺描述：\n{jd}\n\n
                        請按相關度排序亮點（最相關放最前面)，請直接輸出候選人亮點""")
                    
                }
            ],
            options={
                'num_ctx': self.num_ctx,
                'temperature': 0,
                'seed': random_seed,
                
            },
            think=False
        )
        full_content_topk = response_topk['message'].get('content', '')
        result_topk = full_content_topk.strip()
        logging.info(result_topk)
        specialties = re.findall(r'#([^#]+)', result_topk)
        for spec in specialties[:8]:
            response_answer = ollama.chat(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
"""  你是嚴格且客觀的技術人資評估系統。

任務：
根據候選人的一項經歷亮點與完整職缺描述，判斷此亮點對該職缺的符合程度。

你只能使用候選人亮點中明確提供的資訊，不得根據職稱、公司、產業常識或職缺內容，推測候選人具有亮點未提及的能力。

請依照以下標準判斷：

完全符合：
亮點直接對應職缺的核心工作、必要技能、指定產業、指定職務或必要工作條件，且亮點提供明確的實務經驗證據；若職缺有年資要求，亮點也明確達到或超過要求。

幾乎符合：
亮點直接對應職缺的重要要求，且有明確實務經驗，但存在一項非核心差異，例如產業相近但不完全相同、年資略低、工具不同但用途高度相近，或工作責任範圍稍有不足。

大致符合：
亮點與職缺要求具有明確可轉移性，候選人具備相近的工作內容、技術基礎、產業背景或能力，但不是直接從事相同職務，仍需要一定程度的訓練或適應。

稍微符合：
亮點僅對應職缺中的次要要求或通用能力，例如一般溝通、合作、問題處理或工作穩定性；或者只有部分關鍵字相關，但缺乏足夠的實際工作內容證據。

幾乎不符合：
亮點與職缺只有非常間接的關係，工作內容、產業、技術或情境差異明顯，只有少量能力可能轉移，無法作為候選人能勝任該職缺的有效證據。

完全不符合：
亮點與職缺的工作內容、能力要求及工作條件沒有實質關聯，或亮點明確顯示的經驗方向與職缺要求不同。

額外判定規則：

1. 相同關鍵字不代表符合，必須判斷實際工作內容。
2. 不同工具但用途、原理和工作情境高度相近，可以判斷為幾乎符合或大致符合，不得一律判為不符合。
3. 通用能力只有在職缺明確重視該能力時才具有較高相關性。
4. 若職缺要求特定年資，而亮點未記載年資，不得自行假設已達到。
5. 若亮點只列出技術名稱，沒有實際使用情境，最高只能判定為大致符合。
6. 若亮點僅表示「協助」或「參與」，不得視為獨立負責。
7. 若職缺將某條件列為必要條件，直接符合該條件的亮點應獲得較高判定。
8. 若職缺僅將某條件列為加分條件，不得因符合該條件就忽略核心工作不相符。
9. 只評估目前提供的單一亮點，不得使用其他亮點補足其證據。
10. 不得懲罰亮點中沒有被要求表達的資訊；但不得自行補充缺失資訊。

輸出結果必須嚴格限制為下列六種之一：

完全符合
幾乎符合
大致符合
稍微符合
幾乎不符合
完全不符合

只能輸出其中一項，不得輸出原因、標題、符號、分數、Markdown語法或任何其他內容。"""
                    )
                },
                {
                    "role": "user",
                    "content": (
                        
                        f"【求職者的特色/專長： {spec}】\n\n\n"
                        f"職缺-{vacancy}\n"
                        f"工作描述\n{jd}\n"
                        f"條件\n{jd_condiition}\n"
                    )
                }
            ],
            options={
                'num_ctx': self.num_ctx,
                'temperature': 0,
                'seed': random_seed
            },think=False
            )

            full_content_answer = response_answer['message'].get('content', '')
            response_answer = full_content_answer.strip()

            logging.info(response_answer)
            response_answer = re.findall(r'[\u4e00-\u9fff]+', response_answer)[0]
            logging.info(spec)
            
            try:
                score_question = MAP[response_answer]
            except:
                print(f"警告: 無法解析經驗分數 '{response_answer}', 使用預設值 0")
                score_question = 0
            answer.append(response_answer)
            score_answer.append(score_question)

        score = 0
        for index, i in enumerate(score_answer) :
            score+=i*(1-index*0.07)
        score/=6.04
        
        return score
    
    def _calculate_english_score(
        self,
        vacancy: str,
        jd_description: str,
        resume_body: str,
        random_seed: int
    ) -> float:
        """
        計算英文能力分數
        
        Returns:
            0-1 之間的分數
        """
        if not self._is_mostly_english(jd_description):
            return 1.0  # 不需要英文,返回滿分
        
        prefill_text = (
            "<think>\n"
            "我正在執行履歷比對任務。我的審閱標準如下：\n"
            "- 母語：英文能力如母語者。\n"
            "- 流利：任何商務、技術英文對談都能應對自如但不如母語者能運用各種流行、俚語或特殊用法。\n"
            "- 尚可：足以應對日常對話，並且練習後可以進行專業英文報告。\n"
            "- 待加強：僅能透過單字進行對話，無法組織整段語句，能聽懂與閱讀日常文章。\n"
            "- 難以溝通：僅能透過比手畫腳進行溝通，並且只能聽懂、閱讀簡單短文。\n"
            "- 完全不會：完全無法溝通且也無法閱讀、聽懂幾乎所有英文單字。\n\n"
            "我要嚴謹分類該候選人的英文程度，並且只分類使用者所提供的類別(如 '流利')，"
            "內容絕不包含任何描述或解釋的字語。\n"
            "</think>"
        )
        
        response = ollama.chat(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一個嚴格且精準的技術人資系統。"
                        "你的唯一任務是嚴謹的檢驗履歷中暗藏或是明示的任何英文能力資訊，"
                        "並根據下列指引進行 母語、流利、尚可、待加強、難以溝通、完全不會 的分類。"
                    )
                },
                {
                    "role": "user",
                    "content": f"職缺-{vacancy}\n\n【應徵者履歷】\n\n{resume_body.strip()}"
                },
                {
                    "role": "assistant",
                    "content": prefill_text
                }
            ],
            options={
                'num_ctx': self.num_ctx,
                'temperature': self.temperature,
                'seed': random_seed
            }
        )
        
        full_content = response['message'].get('content', '')
        result = full_content.replace(prefill_text, "").strip()
        print(result)
        score = self.ENGLISH_LEVEL_MAP.get(result, 0) / 5.0
        return score
    
    def _extract_work_info(
        self,
        resume_body: str,
        random_seed: int
    ) -> Dict[str, str]:
        """
        提取工作經驗資訊
        
        Returns:
            包含 years, company, title 的字典
        """
        prefill_text = (
            "<think>\n"
            "我已完全讀懂使用者對我的命令與輸出條件限制，"
            "我身為專業的人資，我會仔細閱讀履歷並嚴禁任何廢話直接輸出使用者要求的格式與資訊，"
            "接下來為乾淨準確的輸出：\n"
            "</think>"
        )
        logging.info(resume_body)
        response = ollama.chat(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一位非常資深專業的人資，"
                        "請根據以下履歷幫我找出他的總年資(若是區間 3~4年則挑小的寫並不用包含單位，"
                        "故結果為 3 不是3年也不是3~4年，若小於一年(包含n個月)則寫 1)、"
                        "最近期的公司名稱(若不公開、無經驗則如實填寫)、還有他的頭銜，"
                        "嚴格限制禁止任何除了要求以外的markdown語法/解釋/描述，"
                        "嚴格規範輸出格式為：總年資 xx\n公司名稱 xxxxx\n頭銜 xxxx"
                    )
                },
                {
                    "role": "user",
                    "content": f"此為其履歷：\n{resume_body.strip()}"
                },
                {
                    "role": "assistant",
                    "content": prefill_text
                }
            ],
            options={
                'num_ctx': self.num_ctx,
                'temperature': self.temperature,
                'seed': random_seed
            }
        )
        
        full_content = response['message'].get('content', '')
        result = full_content.replace(prefill_text, "").strip()
        # 解析結果
        try:
            lines = result.split("\n")
            years_line = lines[0].split(" ")[1]
            years = re.search(r'\d+', years_line).group()
            company = lines[1].split(" ", 1)[1]
            title = lines[2].split(" ", 1)[1]
        except (IndexError, AttributeError):
            years = "0"
            company = "未知"
            title = "未知"
        
        return {
            'years': years,
            'company': company,
            'title': title
        }
    
    def _calculate_age_score(self, age: int, is_senior: bool) -> float:
        """
        計算年齡分數
        
        Args:
            age: 年齡
            is_senior: 是否為資深職位
        
        Returns:
            0-1 之間的分數
        """
        if is_senior=="S":
            # 非資深職位: 中心 22歲, 標準差 8
            return 0 if age < 18 else math.exp(-((age - 22) ** 2) / (2 * 8 ** 2))
        elif is_senior=="M":
            # 資深職位: 中心 30 歲
            center = 30
            sigma = 5 if age < center else 20
            return math.exp(-((age - center) ** 2) / (2 * sigma ** 2))
        elif is_senior=="L":
            # 資深職位: 中心 35 歲
            center = 35
            sigma = 5 if age < center else 20
            return math.exp(-((age - center) ** 2) / (2 * sigma ** 2))
    
    def _evaluate_education(
        self,
        education_text: str,
        requirements: pd.Series,
        random_seed: int
    ) -> EducationResult:
        """
        評估學歷
        
        Args:
            education_text: 學歷文本
            requirements: 學歷要求 (DataFrame Series)
            random_seed: 隨機種子
        
        Returns:
            學歷評估結果
        """
        # 評估學門
        try:
            print("沒東西沒東西沒東西",education_text)
            parts = education_text.split(" ")

            studied_status = parts[0] if len(parts) >= 1 else "未知"
            school_name = parts[1] if len(parts) > 1 else "未知"
            if len(parts)>=3:
                department = " ".join(parts[2:])
            else:
                department = parts[2] if len(parts) > 2 else "未知"

        except IndexError:
            print("index_error",education_text)
            school_name = "未知"
            department = "未知"
        discipline = self._classify_discipline(education_text, random_seed)
        
        # 評估學類
        sub_discipline = self._classify_sub_discipline(
            education_text, discipline, random_seed
        )
        
        # 計算科系匹配分數
        dept_score = self._calculate_department_score(
            sub_discipline, requirements
        )
        
        # 評估學位
        degree = self._classify_degree(studied_status)
        degree_score = self.DEGREE_SCORE_MAP.get(degree, 0.6)
        
        # 評估學校
        school_code = self._classify_school(school_name, random_seed)
        school_score = self.SCHOOL_SCORE_MAP.get(school_code, 0.7)
        
        # 評估就讀模式
        mode = self._classify_mode(studied_status)
        mode_score = self.MODE_SCORE_MAP.get(mode, 0.7)
        
        # 評估就學狀態
        status, status_score = self._classify_status(studied_status)
        print(status)
        
        # 提取學校名稱和科系

        

        # 計算總分
        total_score = (
            dept_score *
            degree_score *
            school_score *
            mode_score *
            status_score
        )
        
        return EducationResult(
            score=total_score,
            discipline=discipline,
            status=status,
            degree=degree,
            department=department,
            school=school_name,
            mode=mode
        )
    
    def _classify_discipline(self, education_text: str, random_seed: int) -> str:
        """分類學門"""
        prefill_text = (
            "<think>\n"
            "我正在執行學歷判斷任務，我需要根據上面的指引進行最嚴謹專業的學歷科系判斷\n"
            "接下來我將直接進行上述指令提示的輸出，並且嚴格遵守指令要求的格式。\n"
            "</think>"
        )
        
        discipline_nocode = self.df_discipline.drop("代碼", axis=1)
        
        prompt = (
            f"你是一位專業的台灣科系選擇專家，下列給你科系，"
            f"請根據學門指引進行判斷該科系為何種學門，"
            f"嚴謹限制只能輸出學門名稱，不可輸出任何解釋或是MarkDown語法或是任何敘述。\n"
            f"學歷：{education_text}\n\n"
            f"學門指引：\n{discipline_nocode.to_string(index=False)}"
        )
        
        response = ollama.chat(
            model=self.model_name,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": prefill_text}
            ],
            options={
                'num_ctx': 4096,
                'temperature': 0.1,
                'seed': random_seed
            }
        )
        
        full_content = response['message'].get('content', '')
        result = full_content.replace(prefill_text, "").strip()
        return result
    
    def _classify_sub_discipline(
        self,
        education_text: str,
        discipline: str,
        random_seed: int
    ) -> str:
        """分類學類"""
        prefill_text = (
            "<think>\n"
            "我正在執行學歷判斷任務，我需要根據上面的指引進行最嚴謹專業的學歷科系判斷\n"
            "接下來我將直接進行上述指令提示的輸出，並且嚴格遵守指令要求的格式。\n"
            "</think>"
        )
        
        # 找到學門代碼
        discipline_row = self.df_discipline[
            self.df_discipline["名稱"] == discipline
        ]
        
        if len(discipline_row) == 0:
            return "未知"
        
        code = discipline_row["代碼"].iloc[0].strip()
        
        # 篩選對應的學類
        sub_discipline_filtered = self.df_sub_discipline[
            self.df_sub_discipline["代碼"].astype(str).str.startswith(code)
        ].drop("代碼", axis=1)
        
        prompt = (
            f"你是一位專業的台灣科系選擇專家，下列給你科系，"
            f"請根據學類指引進行判斷該科系為何種學類，"
            f"嚴謹限制只能輸出學類名稱，不可輸出任何解釋或是MarkDown語法或是任何敘述。\n"
            f"學歷：{education_text}\n\n"
            f"學類指引：\n{sub_discipline_filtered.to_string(index=False)}"
        )
        
        response = ollama.chat(
            model=self.model_name,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": prefill_text}
            ],
            options={
                'num_ctx': 4096,
                'temperature': 0.1,
                'seed': random_seed
            }
        )
        
        full_content = response['message'].get('content', '')
        result = full_content.replace(prefill_text, "").strip()
        return result
    
    def _calculate_department_score(
        self,
        sub_discipline: str,
        requirements: dict
    ) -> float:
        """計算科系匹配分數"""
        # 找到學類代碼
        sub_disc_row = self.df_sub_discipline[
            self.df_sub_discipline["名稱"] == sub_discipline
        ]
        
        if len(sub_disc_row) == 0:
            return 0.0
        
        target_code = sub_disc_row["代碼"].iloc[0]
        
        for score in range(5, -1, -1):

            value = requirements.get(f"education_score_{score}")

            if not value:
                continue

            codes = [c.strip() for c in str(value).split(",")]

            if target_code in codes:
                return score / 5.0

        return 0.0
    
    def _classify_degree(self, education_text: str) -> str:
        # """分類學位"""
        # prefill_text = (
        #     "<think>\n"
        #     "我正在執行學歷判斷任務，我需要根據上面的指引進行最嚴謹專業的學歷科系判斷\n"
        #     "接下來我將直接進行上述指令提示的輸出，並且嚴格遵守指令要求的格式。\n"
        #     "</think>"
        # )
        
        # prompt = (
        #     f"你現在是台灣科技業的資深 HR，請嚴格根據以下三個步驟，"
        #     f"對候選人的學歷進行學位評估，協助我判斷是下列何種學位。"
        #     f"嚴格限制只能輸出下列標籤文字(如輸出 '博士')，嚴禁任何其他描述或推理字眼！"
        #     f"以下為學歷標籤，請仔細選擇：\n"
        #     f"博士\n碩士\n學士\n五專\n高中\n高職\n二技\n國中以下\n\n"
        #     f"【當前候選人資料】\n學歷：{education_text}"
        # )
        
        # response = ollama.chat(
        #     model=self.model_name,
        #     messages=[
        #         {"role": "user", "content": prompt},
        #         {"role": "assistant", "content": prefill_text}
        #     ],
        #     options={
        #         'num_ctx': 4096,
        #         'temperature': 0.1,
        #         'seed': random_seed
        #     }
        # )
        
        # full_content = response['message'].get('content', '')
        # result = full_content.replace(prefill_text, "").strip()

        result = ""
        for degree, score in self.DEGREE_SCORE_MAP.items():
            if degree in education_text:
                result = degree

        if  len(result)==0:
            from difflib import SequenceMatcher
            result = max(
                self.DEGREE_SCORE_MAP.keys(),
                key=lambda d: SequenceMatcher(None, education_text, d).ratio()
            )

        print(result)
        return result
    
    def _classify_school(self, education_text: str, random_seed: int) -> str:
        """分類學校等級"""
        prefill_text = (
            "<think>\n"
            "我正在執行學歷判斷任務，我需要根據上面的指引進行最嚴謹專業的學歷科系判斷\n"
            "接下來我將直接進行上述指令提示的輸出，並且嚴格遵守指令要求的格式。\n"
            "</think>"
        )
        
        prompt = f"""
        【系統強制指令：你現在是精密台灣大專院校分類器。你只能從指定代碼中挑選一個輸出。】
        
        請仔細閱讀以下候選人的畢業學校：{education_text}
        
        請嚴格根據以下【校排名單】進行比對，並原封不動輸出對應的【唯一代碼】（例如：CODE_A）。
        絕對不允許輸出任何其他中文字、空格或標點符號：

        ▶ CODE_A ➔ 【台清交成政央】：台灣大學、清華大學、政治大學、陽明交通大學、成功大學、中央大學、國外菁英大學(QS200名以內)。
        ▶ CODE_B ➔ 【頂尖國立與科大】：台灣科技大學、台北科技大學、中山大學、中興大學、台灣師範大學、國外優質大學(QS200~500名)。
        ▶ CODE_C ➔ 【中堅國立大】：中正大學、台北大學、台灣海洋大學、高雄大學。
        ▶ CODE_D ➔ 【地方國立與頂尖私大】：高雄師範大學、彰化師範大學、高雄科技大學、東華大學、暨南大學、嘉義大學、長庚大學、元智大學、國外普通大學(QS500名以後)。
        ▶ CODE_E ➔ 【一般國立與老牌私大】：台東大學、聯合大學、雲林科技大學、虎尾科技大學、勤益科技大學、屏東科技大學、澎湖科技大學、輔仁大學、逢甲大學、淡江大學、中原大學、東吳大學。
        ▶ CODE_F ➔ 【其餘私立普通大學】：文化大學、世新大學、中華大學、銘傳大學、實踐大學、大同大學，以及上述未提及之其餘私立普通大學。
        ▶ CODE_G ➔ 【其餘私立科技大學/專科/技職】：朝陽科大、南台科大、龍華科大、明志科大，以及所有私立科技大學、技術學院、五專高職學校。
        """
        
        response = ollama.chat(
            model=self.model_name,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": prefill_text}
            ],
            options={
                'num_ctx': 4096,
                'temperature': 0.1,
                'seed': random_seed
            }
        )
        
        full_content = response['message'].get('content', '')
        result = full_content.replace(prefill_text, "").strip()
        return result
    
    def _classify_mode(self, education_text: str) -> str:
        """分類就讀模式"""
        # prefill_text = (
        #     "<think>\n"
        #     "我正在執行學歷判斷任務，我需要根據上面的指引進行最嚴謹專業的學歷科系判斷\n"
        #     "接下來我將直接進行上述指令提示的輸出，並且嚴格遵守指令要求的格式。\n"
        #     "</think>"
        # )
        
        # prompt = f"""
        # 你是一位專業的台灣科系選擇專家，給你其學歷，請仔細判斷該學歷屬於哪種學位性質，
        # 其中下列為學位性質與其解釋：
        # 1.日間部：學校在週一至週五的白天進行常態授課的正式學制，有正式學籍，頒發正式學位證書。
        # 2.進修部：利用週一至週五晚上或週末假日進行授課。早期社會通稱為「夜校 / 夜間部」，有正式學籍，
        #   與日間部享有同等法律效力，畢業頒發正式學士或副學士學位（目前台灣多數大學的畢業證書已不再加註「進修部」字樣）。
        # 3.在職專班：專為累積一定工作年資的在職人士所開設的正式碩士、博士或二專班別。
        #   通常在週末五六日或平日晚上上課，且錄取極度看重工作經歷，有正式學籍，
        #   畢業時需修滿學分並完成學位論文（碩博士），頒發正式碩博士學位證書（通常證書上會加註「在職專班」字樣）。
        # 4.學分班：大學推廣教育部開設的「非學制教育」（推廣教育）。開放給社會大眾免試修讀單科課程，
        #   修完後僅發給「學分證明書」，不授予任何學位，無正式學籍，無畢業證書，僅有「學分證明」。
        #   若未來通過考試考上上述 1~3 類的正式學制，此學分通常可申請抵免。
        
        # 嚴謹限制只能輸出學位性質(日間部、進修部、在職專班、學分班)，
        # 不可輸出任何解釋或是MarkDown語法或是任何敘述，若是國外學歷亦如此判斷。

        # 以下為該候選人學歷
        # 學歷：{education_text}
        # """
        
        # response = ollama.chat(
        #     model=self.model_name,
        #     messages=[
        #         {"role": "user", "content": prompt},
        #         {"role": "assistant", "content": prefill_text}
        #     ],
        #     options={
        #         'num_ctx': 4096,
        #         'temperature': 0.1,
        #         'seed': random_seed
        #     }
        # )
        
        # full_content = response['message'].get('content', '')
        # result = full_content.replace(prefill_text, "").strip()

        result = ""

                
        from difflib import SequenceMatcher

        best_match = max(
            self.MODE_SCORE_MAP.keys(),
            key=lambda d: SequenceMatcher(None, education_text, d).ratio()
        )

        score = SequenceMatcher(None, education_text, best_match).ratio()

        if score >= 0.5:
            result = best_match
        else:
            result = ""

        if len(result)==0:
            for degree, score in self.MODE_SCORE_MAP.items():
                if degree in education_text:
                    result = degree
        if len(result)==0:
            result="日間部"

        print(result)
        return result
    
    def _classify_status(self, education_text: str) -> Tuple[str, float]:
        """
        分類就學狀態
        
        Returns:
            (狀態名稱, 狀態分數)
        """
        if re.search(r"就學|就讀|在學|修讀", education_text):
            return "就學中", 0.95
        elif re.search(r"肄業|修業|休學", education_text):
            return "肄業", 0.8
        elif re.search(r"畢業", education_text):
            return "畢業", 1.0
        else:
            return "未知", 0.9
    
    def summarize_resume(self, resume_text: str) -> str:
        """
        生成履歷總結
        
        Args:
            resume_text: 履歷內容
        
        Returns:
            總結文本
        """

            
        prefill_text = (
            "<think>\n"
            "不需要過度思考，直接針對履歷進行總結。\n"
            "</think>\n"
        )
        
        prompt = (
            "請根據該篇履歷內容進行300~500字的專業總結"
            "(包含經歷與工作發展等職涯發展)，"
            "嚴禁憑空捏造，完完全全根據履歷適時進行分析與陳述！"
            "並且使用繁體中文回復，並且嚴謹限制過度思考，"
            "禁止過多內心戲導致Token用完而無法輸出答案，"
            "並且嚴格限制內容只包含履歷總結，"
            "不可輸出任何給自己或是給使用者的內容提示，完全只需要總結內容即可。\n\n"
            f"以下為履歷內容：\n\n{resume_text}"
        )
        response = ollama.chat(
            model=self.model_name,
            messages=[
                {"role": "system", "content": f"我是專業的人資助理，我擅長於總結履歷資訊，確保所有重要資訊都有被提取與保留，也絕對不會自行推測或遐想其具備的能力或資質，完全根據履歷內容進行總結。"},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": prefill_text}
            ],
            options={
                'num_ctx': self.num_ctx,
                'temperature': 0.6
            }
        )
        
        full_content = response['message'].get('content', '')
        result = full_content.replace(prefill_text, "").strip()

        return result


@worker_process_init.connect
def init_worker(**kwargs):
    """Worker 啟動時初始化"""
    from ..api.talent_controller import get_talent_service
    global scoring_service
    global talent_service 
    from ..database.connection import db_manager
    logging.basicConfig(level=logging.INFO)
    db_manager.connect()
    scoring_service = ScoringService()
    talent_service = get_talent_service()
    # if config.FIRST_TIME:
    #     scoring_service.wait_for_ollama()
    config.FIRST_TIME= False
    logging.info("✅ Scoring Worker 準備就緒")


@backend_service.task(name='tasks.run_score', max_retries=1)
def run_score(talent:Dict,resume_text,operator,errors):
    error = ""
    try:
        # AI 總結
        talent_obj = Talent(**talent)
        result_locked = talent_service.check_if_locked(talent_obj.source , talent_obj.source_id)
        
        # if result_locked.success :
        #     if result_locked.data["is_locked"] :
        #         e = "鎖定中無法重新評分"
        #         logging.error(e, exc_info=True)
        #         errors.append(e)
        #         return 
        # else:
        if result_locked.message =="找不到該人才資料" :
            print(result_locked.message)
            return


        # lock_result = talent_service.lock_talent(talent_obj.source , talent_obj.source_id)
        # if lock_result.success:
        #     print(lock_result.message)
        # else:
        #     print(lock_result.message)
        #     print(lock_result.error)
        logging.info(talent_obj.name +" AI 總結中")
        if not resume_text:
            from ..utils.outlook_helper import clean_outlook_mail_body 
            from bs4 import BeautifulSoup
            with open(talent_obj.msg_backup_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            soup = BeautifulSoup(html_content, 'html.parser')
            text = soup.get_text(separator='\n', strip=True)
            resume_text = clean_outlook_mail_body(mail_body=text).split("本人同意本履歷僅供符合")[0]
            if talent_obj.education_mode:
                education = talent_obj.education_mode+talent_obj.education_degree+talent_obj.education_status+" "+talent_obj.education_school+" "+talent_obj.education_department
                talent_obj.education_school = education
        else:
            talent_obj.description = scoring_service.summarize_resume(resume_text)
        
        # AI 評分 (重試 2 次)
        logging.info("AI 評分中")
        for i in range(2):
            try:
                err,result = scoring_service.verify_resume(
                    talent_obj.name ,
                    talent_obj.vacancy,
                    talent_obj.education_school,
                    f"{talent_obj.city},{talent_obj.district}",
                    talent_obj.age,
                    resume_text
                )
            
                
                # 更新 Talent
                talent_obj.score = result.total_score
                talent_obj.score_distance = result.distance_score
                talent_obj.score_experience = result.experience_score
                talent_obj.score_education = result.education_score
                talent_obj.score_age = result.age_score
                
                talent_obj.education_discipline = result.education_discipline
                talent_obj.education_status = result.education_status
                talent_obj.education_degree = result.education_degree
                talent_obj.education_department = result.education_department
                talent_obj.education_school = result.education_school
                talent_obj.education_mode = result.education_mode
                
                talent_obj.city = result.city
                talent_obj.district = result.district
                talent_obj.description = talent_obj.description
                talent_obj.invitation = result.invitation
                talent_obj.total_exp_years = result.total_exp_years
                talent_obj.current_company = result.current_company
                talent_obj.current_job_title = result.current_job_title
                
                if err:
                    errors.append(err)
                
                break
                
            except Exception as e:
                error_msg = traceback.format_exc()
                error = f"第{i}次評分失敗: {e}"
                logging.error(error+"\n\n"+error_msg, exc_info=True)
                if i == 2:  # 最後一次
                    errors.append(f"AI 評分失敗: {e}")
        if len(errors)!=0:
            print("發生錯誤",error)
        logging.info(
            f"[履歷評分] 總分={talent_obj.score} | 距離={talent_obj.score_distance} | "
            f"經歷={talent_obj.score_experience} | 學歷={talent_obj.score_education} | 年齡={talent_obj.score_age}"
        )
        lock_result = talent_service.unlock_talent(talent_obj.source , talent_obj.source_id)
        if lock_result.success:
            print(lock_result.message)
        else:
            print(lock_result.message)
            print(lock_result.error)
        request = {
            "edit":[
            {
                "source":talent_obj.source,
                "source_id":talent_obj.source_id,
                "updates":{
                    "current_status":"AI REVIEW" ,
                    "score":talent_obj.score,
                    "score_distance" : talent_obj.score_distance,
                    "score_experience" :talent_obj.score_experience,
                    "score_education": talent_obj.score_education,
                    "score_age":talent_obj.score_age,
                    "description":talent_obj.description,
                    "education_discipline":talent_obj.education_discipline,
                    "education_status":talent_obj.education_status,
                    "education_degree":talent_obj.education_degree,
                    "education_department":talent_obj.education_department,
                    "education_school":talent_obj.education_school,
                    "education_mode":talent_obj.education_mode,
                    "city":talent_obj.city,
                    "district":talent_obj.district,
                    "invitation":talent_obj.invitation,
                    "total_exp_years":talent_obj.total_exp_years,
                    "current_company":talent_obj.current_company,
                    "current_job_title":talent_obj.current_job_title}
            }]
            ,"operator":operator
        }
        request = TalentBatchUpdateRequest(**request)
        response_update = talent_service.update_talent_with_log(request)
        if response_update.success :
            logging.info("上傳成功")
        else:
            logging.error(response_update.error)
            logging.error(response_update.message)
        from .send_service import send_ai_result_notification 
        task = send_ai_result_notification.apply_async(
                            args=[talent_obj.to_dict(),errors],queue='mail_queue')

    except Exception as e:
        error_msg = traceback.format_exc()
        request = {
            "edit":[
            {
                "source":talent_obj.source,
                "source_id":talent_obj.source_id,
                "error_message":error,
                "updates":{
                    "current_status":"AI REVIEW-NOT PASS" if talent_obj.score<60 else "感興趣",
                    "score":talent_obj.score,
                    "score_distance" : talent_obj.score_distance,
                    "score_experience" :talent_obj.score_experience,
                    "score_education": talent_obj.score_education,
                    "score_age":talent_obj.score_age,
                    "description":talent_obj.description,
                    "education_discipline":talent_obj.education_discipline,
                    "education_status":talent_obj.education_status,
                    "education_degree":talent_obj.education_degree,
                    "education_department":talent_obj.education_department,
                    "education_school":talent_obj.education_school,
                    "education_mode":talent_obj.education_mode,
                    "city":talent_obj.city,
                    "district":talent_obj.district,
                    "invitation":talent_obj.invitation,
                    "total_exp_years":talent_obj.total_exp_years,
                    "current_company":talent_obj.current_company,
                    "current_job_title":talent_obj.current_job_title}
            }]
            ,"operator":operator
        }
        talent_service.update_talent_with_log(request)
        error = f"發生錯誤: {e}"
        logging.error(error+"\n\n"+error_msg, exc_info=True)
        talent_service.unlock_talent(talent_obj.source , talent_obj.source_id)
        errors.append(f"AI 處理失敗: {e}")

