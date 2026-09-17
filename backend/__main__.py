"""
Backend 套件的執行入口
當執行 python -m backend 時會執行這個檔案
"""
import uvicorn

print()
print("=" * 60)
print("🚀 啟動人才管理系統 API 伺服器")
print("=" * 60)
print(f"📡 伺服器位址: http://localhost:8000")
print(f"📚 API 文件: http://localhost:8000/docs")
print(f"🔧 選項資料: http://localhost:8000/api/options")
print("=" * 60)
print()


uvicorn.run(
    "backend.app:app",
    host="0.0.0.0",
    port=8000,
    reload=True,
    reload_dirs=["backend"],  # 只監控 backend
    log_level="debug",
    access_log=True,
)