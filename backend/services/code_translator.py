import pandas as pd
from geopy.distance import geodesic
import math


df = pd.read_excel("C:/Users/rchang4/auto_resume/1050429_行政區經緯度.ods", engine="odf")
df_Lab = pd.read_excel("C:/Users/rchang4/auto_resume/公司經緯度.xlsx")
df_tw = pd.read_excel("C:/Users/rchang4/auto_resume/taiwan_zipcode_clean.xlsx")

def search(code):
    
    location = df_tw[df_tw["郵遞區號"]==int(code)]
    city = location["縣市"].iloc[0]
    district = location["區"].iloc[0]
    return city ,district

def distance_search(Lab,vacnacy,code):
    lab = df_Lab[df_Lab["實驗室"]==Lab] 
    lab_Longitude = lab["經度"].iloc[0]
    lab_Latitude = lab["緯度"].iloc[0]
    code_cor = df[df["3碼郵遞區號"]==int(code)]
    code_Longitude = code_cor["中心點經度"].iloc[0]
    code_Latitude = code_cor["中心點緯度"].iloc[0]
    point1 = (lab_Latitude,lab_Longitude)
    point2 = (code_Latitude, code_Longitude)
    distance = geodesic(point1, point2).km
    return  math.exp(-distance / 150)

def code_district(code):
    search_code = str(code).strip()
    condition = df["3碼郵遞區號"].astype(str).str.strip() == search_code
    
    # 安全防護：先確認到底有沒有找到這個代碼，避免空表格硬撈 iloc[0] 崩潰
    matched_rows = df[condition]
    if not matched_rows.empty:
        return matched_rows["行政區名"].iloc[0]
    else:
        return f"未知區域 ({search_code})"
def district_to_code(city,district):
    df_dis = df_tw[df_tw["縣市"]==city]
    code = df_dis[df_dis["區"]==district]["郵遞區號"].iloc[0]
    return code
# df_jd = pd.read_excel("C:/Users/rchang4/auto_resume/job_description.xlsx")
# distance_search(df_jd,"RF測試工程師 (新竹科學園區)",300)