import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time

# ======================
# إعداد الصفحة
# ======================
st.set_page_config(
    page_title="Noon Sheet Viewer",
    layout="wide"
)

st.title("📊 Noon Prices – Live Google Sheet Viewer")

# ======================
# تحميل JSON تلقائياً
# ======================
def auto_find_json():
    import os
    for f in os.listdir('.'):
        if f.endswith('.json'):
            return f
    return None

json_file = auto_find_json()

if not json_file:
    st.error("❌ لم يتم العثور على ملف JSON بجانب الملف")
    st.stop()

# ======================
# الاتصال بشيت Google
# ======================
SPREADSHEET_ID = "1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk"
SHEET_NAME = "noon"

def load_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_file(json_file, scopes=scopes)
    client = gspread.authorize(creds)
    ws = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])   # أول صف = عناوين
    return df

# ======================
# تحديث تلقائي كل X ثواني
# ======================

refresh_rate = st.sidebar.slider("⏱ معدل التحديث (ثواني)", 5, 120, 10)

placeholder = st.empty()

while True:
    try:
        df = load_sheet()
        placeholder.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"❌ خطأ أثناء تحميل الشيت: {e}")

    time.sleep(refresh_rate)
