import sys
import os
import time
import datetime
import re
import traceback
import streamlit as st
import pandas as pd
import gspread
import unicodedata
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components

# ================== إعداد واجهة Streamlit ==================
st.set_page_config(page_title="Noon Prices – Auto Monitoring", layout="wide")
st.title("📊 Noon Prices – Auto Monitoring (Developed Version)")

# ================== تنظيف SKU ==================
def clean_sku(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = s.strip().replace("\u200f","").replace("\u200e","").replace("\n","").replace("\r","")
    s = s.replace(" ", "")
    return s

# ================== استخراج SKU من سطر المنتج ==================
def extract_sku_from_text(text):
    possible = re.findall(r"[A-Za-z0-9]{10,}", str(text))
    if possible:
        return clean_sku(possible[0])
    return ""

# ================== تحميل الشيت الأساسي ==================
def load_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    client = gspread.authorize(creds)
    ws = client.open_by_key("1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk").worksheet("noon")

    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

# ================== تحميل history ==================
def load_history():
    creds = Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    client = gspread.authorize(creds)

    try:
        ws = client.open_by_key("1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk").worksheet("history")
    except:
        return pd.DataFrame()

    data = ws.get_all_values()
    if len(data) < 2:
        return pd.DataFrame()

    df = pd.DataFrame(data[1:], columns=data[0])
    df["SKU_clean"] = df["SKU"].apply(clean_sku)
    return df

# ================== آخر تحديث للسعر ==================
def get_last_change(df_hist, sku):
    sku = clean_sku(sku)
    if df_hist.empty or sku == "":
        return None

    rows = df_hist[df_hist["SKU_clean"] == sku]
    if rows.empty:
        return None

    last = rows.tail(1).iloc[0]
    return {
        "old": last["Old Price"],
        "new": last["New Price"],
        "change": last["Change"],
        "time": last["DateTime"]
    }

# ================== Sidebar ==================
st.sidebar.header("⚙️ الإعدادات")
refresh_rate = st.sidebar.slider("⏱ معدل التحديث (ثواني)", 5, 300, 30)
search_text = st.sidebar.text_input("🔍 البحث عن SKU")
st.sidebar.markdown("---")

placeholder = st.empty()
last_update_placeholder = st.sidebar.empty()

# ================== تشغيل ==================
while True:
    try:
        df = load_sheet()
        df_hist = load_history()

        # فلترة البحث
        if search_text:
            df = df[df.apply(lambda row: row.astype(str).str.contains(search_text, case=False).any(), axis=1)]

        with placeholder.container():

            st.subheader("🟦 عرض المنتجات (نسخة مطوّرة)")

            for idx, row in df.iterrows():

                sku_main = clean_sku(row.get("SKU1", ""))

                if sku_main == "":
                    continue

                # قائمة المنافسين
                competitors = [
                    ("سعر منتجك", "SKU1", "Price1", row.get("details1", "")),
                    ("المنافس 1", "SKU2", "Price2", row.get("details2", "")),
                    ("المنافس 2", "SKU3", "Price3", row.get("details3", "")),
                    ("المنافس 3", "SKU4", "Price4", row.get("details4", "")),
                    ("المنافس 4", "SKU5", "Price5", row.get("details5", "")),
                    ("المنافس 5", "SKU6", "Price6", row.get("details6", "")),
                ]

                html = f"""
                <div style="border:1px solid #ccc; padding:20px; border-radius:12px; margin-bottom:20px; background:#fff; direction:rtl;">
                    <h2>📦 <b>SKU الأساسي:</b> <span style='color:#007bff;'>{sku_main}</span></h2>
                    <div style="height:1px; background:#ddd; margin:10px 0;"></div>
                    <h3>🏷️ الأسعار + آخر تغيير:</h3>
                    <ul style="font-size:18px; list-style:none; padding:0;">
                """

                # ================== عرض كل منافس ==================
                for label, sku_col, price_col, detail in competitors:

                    sku_val = clean_sku(row.get(sku_col, ""))
                    price_val = row.get(price_col, "")

                    # استخراج SKU من تفاصيل Noon لو الشيت فاضي
                    if sku_val == "":
                        extracted = extract_sku_from_text(detail)
                        if extracted:
                            sku_val = extracted

                    # الآن جلب آخر تغيير
                    change_data = get_last_change(df_hist, sku_val)

                    if change_data:
                        change_html = f"""
                        <div style='font-size:15px; color:#444;'>
                            🔄 <b>آخر تغيير:</b> {change_data['old']} → {change_data['new']}<br>
                            📅 <b>الوقت:</b> {change_data['time']}
                        </div>
                        """
                    else:
                        change_html = "<div style='font-size:14px; color:#888;'>لا يوجد تغييرات مسجلة</div>"

                    html += f"""
                        <li><b>{label} ({sku_val}):</b> {price_val}
                            {change_html}
                        </li>
                    """

                html += "</ul></div>"

                components.html(html, height=550)

            st.subheader("📋 جدول البيانات")
            st.dataframe(df)

            st.subheader("📉 سجل تغييرات الأسعار – History")
            st.dataframe(df_hist)

        last_update_placeholder.markdown(
            f"🕒 آخر تحديث: **{time.strftime('%Y-%m-%d %H:%M:%S')}**"
        )

    except Exception as e:
        st.error(f"❌ خطأ: {e}")

    time.sleep(refresh_rate)
