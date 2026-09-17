from typing import Dict, Any
from pathlib import Path
from api_client import UserAPI

class AuthConfigGenerator:
    """從數據庫生成 Streamlit Authenticator 配置"""
    
    @staticmethod
    def generate_config() -> Dict[str, Any]:
        """
        從數據庫生成認證配置
        
        Returns:
            Streamlit Authenticator 配置字典
        """
        
        try:
            users = UserAPI.auth().data
            # 構建 credentials
            credentials = {}
            for user in users:
                credentials[user['user_account']] = {
                    "name": user['user_name'],
                    "email": user['user_email'],
                    "password": user['password_hash'],  # bcrypt 哈希
                    "role": user['user_role']
                }
            
            # 完整配置
            config = {
                "credentials": {
                    "usernames": credentials
                },
                "cookie": {
                    "expiry_days": 1,
                    "key": "hr_auth_cookie_signature_key",  # 建議從環境變量讀取
                    "name": "hr_automation_session"
                }
            }
            
            return config
        except Exception as e:
            print("發生錯誤"+ str(e))
    
    @staticmethod
    def login(user_account) :
        result = UserAPI.login(user_account)
        return result