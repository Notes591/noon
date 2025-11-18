import streamlit as st
import pandas as pd
import time
import gspread
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components

# إعداد صفحة Streamlit
st.set_page_config(
    page_title="Noon Prices Dashboard",
    layout="wide",
)

st.title("📊 Noon Prices – Live Monitoring Dashboard")

# تحميل Google Sheet
def load_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )

    client = gspread.authorize(creds)

    SPREADSHEET_ID = "1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk"
    SHEET_NAME = "noon"

    ws = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    data = ws.get_all_values()

    df = pd.DataFrame(data[1:], columns=data[0])
    return df


# Sidebar
st.sidebar.header("⚙️ الإعدادات")

refresh_rate = st.sidebar.slider(
    "⏱ معدل التحديث (ثواني)",
    5, 300, 30
)

search_text = st.sidebar.text_input("🔍 البحث عن SKU")

st.sidebar.markdown("---")
placeholder = st.empty()
last_update_placeholder = st.sidebar.empty()


# التحديث التلقائي
while True:
    try:
        df = load_sheet()

        if search_text:
            df = df[df.apply(lambda row: row.astype(str).str.contains(search_text, case=False).any(), axis=1)]


        with placeholder.container():

            st.subheader("🟦 عرض المنتجات بطريقة الكروت – Cards View")

            for idx, row in df.iterrows():

                sku_main = row.get("SKU1", "").strip()
                if sku_main == "":
                    continue

                html_card = f"""
                <div style="
                    border:1px solid #cccccc;
                    padding:20px;
                    border-radius:12px;
                    margin-bottom:20px;
                    background:#ffffff;
                    direction:rtl;
                    font-family:'Tajawal', sans-serif;
                    width:70%;
                    box-shadow:0 1px 6px rgba(0,0,0,0.08);
                ">
                    <h2 style="margin:0 0 10px; font-size:22px;">
                        📦 <b>الـSKU الأساسي:</b>
                        <span style="color:#007bff;">{sku_main}</span>
                    </h2>

                    <div style="height:1px; background:#ddd; margin:10px 0;"></div>

                    <h3 style="margin:10px 0; font-size:18px;">🏷️ <b>الأسعار:</b></h3>

                    <ul style="font-size:16px; line-height:2; list-style:none; padding:0;">

                        <li>🟦 <b>سعر منتجك:</b> {row.get("Price1","")}</li>

                        <li>🟨 <b>المنافس 1 ({row.get("SKU2","")}):</b> {row.get("Price2","")}</li>

                        <li>🟧 <b>المنافس 2 ({row.get("SKU3","")}):</b> {row.get("Price3","")}</li>

                        <li>🟥 <b>المنافس 3 ({row.get("SKU4","")}):</b> {row.get("Price4","")}</li>

                        <li>🟩 <b>المنافس 4 ({row.get("SKU5","")}):</b> {row.get("Price5","")}</li>

                        <li>🟪 <b>المنافس 5 ({row.get("SKU6","")}):</b> {row.get("Price6","")}</li>
                    </ul>

                    <p style="margin-top:15px; font-size:14px; color:#555;">
                        📅 <b>آخر تحديث:</b> {row.get('Last Update','')}
                    </p>
                </div>
                """

                components.html(html_card, height=420)

        last_update_placeholder.markdown(
            f"🕒 آخر تحديث: **{time.strftime('%Y-%m-%d %H:%M:%S')}**"
        )

    except Exception as e:
        st.error(f"❌ خطأ أثناء تحميل الشيت: {e}")

    time.sleep(refresh_rate)
