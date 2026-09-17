"""
FastAPI 應用程式定義
"""
import sys
import os

# ✅ 動態路徑處理
current_dir = os.path.dirname(os.path.abspath(__file__))

if __package__ is None or __package__ == '':
    # 直接執行時使用絕對路徑
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from api.talent_controller import router as talent_router
    from api.log_controller import router as log_router
    from .api.user_controller import router as user_router
    from .api.lab_controller import router as lab_router
    from .api.settings_controller import router as settings_router
    from repositories.talent_repository import TalentRepository
else: 
    # 作為套件被 import 時使用相對路徑
    from .api.talent_controller import router as talent_router
    from .api.log_controller import router as log_router
    from .api.user_controller import router as user_router
    from .api.vacancy_controller import router as vacancy_router
    from .api.lab_controller import router as lab_router
    from .api.settings_controller import router as settings_router
    from .repositories.talent_repository import TalentRepository
from .repositories.log_repository import LogRepository
from fastapi import FastAPI , APIRouter
from contextlib import asynccontextmanager
from .database.connection import db_manager 
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import traceback
import logging
from .config import STREAMLIT_URL
# ==========================================
# 全域變數 (啟動時載入) 
# ==========================================

FILTER_OPTIONS = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理"""
    global FILTER_OPTIONS
    global SELECT_OPTIONS
    db_manager.connect()
    print("🚀 載入靜態資料...")
    
    talent_repo = TalentRepository()
    log_repo = LogRepository()
    
    FILTER_OPTIONS = {
        "cities": talent_repo.get_distinct_values("city"),
        "vacancies": talent_repo.get_distinct_values("vacancy"),
        "statuses": talent_repo.get_distinct_values("current_status"),
    }
    opts = talent_repo.get_options()
    SELECT_OPTIONS = {
        "city": opts["city"],
        "district":opts["district"],
        "discipline":opts["discipline"],
        "gender":opts["gender"],
        "source":opts["source"],
        "status":opts["status"],
        "education_status":opts["education_status"],
        "education_mode":opts["education_mode"],
        "education_degree":opts["education_degree"],
        "vacancies" :opts["vacancies"]
    }
    
    print(f"✅ 已載入 {len(SELECT_OPTIONS)} 個欄位選項")
    

    
    yield
    db_manager.close()
    print("🛑 應用程式關閉")
 
# ==========================================
# FastAPI 應用程式
# ==========================================

app = FastAPI(
    title="Talents System API",
    version="1.0.0",
    lifespan=lifespan,
    debug=True
)

# 在 include_router 之後立即檢查


app.include_router(talent_router)
app.include_router(log_router)
app.include_router(user_router)
app.include_router(vacancy_router)
app.include_router(lab_router)
app.include_router(settings_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=STREAMLIT_URL,  # Streamlit 預設端口
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


logger = logging.getLogger(__name__)

# ✅ 全域異常處理器（只需要加這一段！）
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """捕獲所有未處理的異常"""
    
    error_traceback = traceback.format_exc()
    
    logger.error("=" * 80)
    logger.error(f"❌ 全域異常捕獲")
    logger.error(f"路徑: {request.url.path}")
    logger.error(f"方法: {request.method}")
    logger.error(f"異常類型: {type(exc).__name__}")
    logger.error(f"異常訊息: {str(exc)}")
    logger.error(f"完整堆疊:\n{error_traceback}")
    logger.error("=" * 80)
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": str(exc),
            "error_type": type(exc).__name__,
            "traceback": error_traceback,
            "path": str(request.url),
            "method": request.method
        }
    )


@app.get("/")
async def root():
    """根端點"""
    return {
        "message": "人才管理系統 API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/api/options")
async def get_options():
    """從記憶體回傳選項（超快）"""
    return FILTER_OPTIONS

async def get_select_options():
    return SELECT_OPTIONS
