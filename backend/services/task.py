# tasks.py
from celery import Celery
from typing import List
from ..models.talent import Talent
from ..config import REDIS_URL

# Celery 配置
backend_service = Celery('mail_scoring_system',
        broker_url=REDIS_URL,
        result_backend=REDIS_URL,  
             )

# 任務路由
backend_service.conf.task_routes = {
    'tasks.send_ai_result_notification': {'queue': 'mail_queue'},
    'tasks.cancel_meeting': {'queue': 'mail_queue'},
    'tasks.create_meeting': {'queue': 'mail_queue'},
    'tasks.send_status_update': {'queue': 'mail_queue'},
    'tasks.run_score': {'queue': 'scoring_queue'},
    'tasks.ocr': {'queue': 'ocr_queue'}
}

# ===== 任務定義 =====

# @backend_service.task(name='tasks.run_score')
# def run_score(talent:Talent,resume_text,errors):
#     """
#     評分任務
#     - 由 scoring_service.py 實作
#     """
#     pass

# @backend_service.task(name='tasks.send_status_update', bind=True, max_retries=3)
# def send_status_update(self, to, talent, stage_info, reply_warning, warning_text=""):
#     pass

# @backend_service.task(name='tasks.create_meeting', bind=True, max_retries=3)
# def create_meeting(self, mail_item, talent, meeting_time, location, 
#                    title, duration, recipients, html_content):
#     """
#     發送郵件任務
#     - 由 mail_sender.py 實作
#     """
#     pass

# @backend_service.task(name='tasks.cancel_meeting', bind=True, max_retries=3)
# def cancel_meeting(self, meeting_id):
#     """
#     發送郵件任務
#     - 由 mail_sender.py 實作
#     """
#     pass

# @backend_service.task(name='tasks.send_ai_result_notification')
# def send_ai_result_notification(talent: Talent, errors: List[str]):
#     """
#     發送評分結果郵件
#     - 由 mail_sender.py 實作
#     """
#     pass