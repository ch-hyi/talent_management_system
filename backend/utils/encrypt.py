# generate_password.py
import streamlit_authenticator as stauth

# 生成密碼 hash
passwords = ['password123', 'password456']
hashed_passwords = stauth.Hasher(passwords).generate()

for i, hashed in enumerate(hashed_passwords):
    print(f"Password {i+1}: {hashed}")