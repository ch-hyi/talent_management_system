from ..parser.parser_ocr import parse_resume
from celery import Celery
from celery.signals import worker_process_init
import logging
from ..repositories.talent_repository import TalentRepository
from ..config import REDIS_URL

backend_service = Celery(
    "mail_scoring_system",
    broker_url=REDIS_URL,
    result_backend=REDIS_URL,
)

talent_repo = None

@worker_process_init.connect
def init_worker(**kwargs):
    from ..database.connection import db_manager
    db_manager.connect()
    global talent_repo 
    talent_repo = TalentRepository()
    logging.basicConfig(
        level=logging.INFO
    )
    logging.info(
        "Resume Parser Worker Ready"
    )

@backend_service.task(name='tasks.ocr_service', max_retries=1)
def run_ocr(file_path,username):
    
    result_json = parse_resume(file_path)
    talent_repo.upload_ocr_result(file_path,username,result_json)
    return result_json
