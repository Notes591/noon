import sys
import os
import time
import datetime
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components
import re

# إعداد صفحة Streamlit
st.set_page_config(page_title="Noon Prices Dashboard", layout="wide")
st.title("📊 Noon Prices – Live Monitoring Dashboard")


# ============= 🔥 تنظيف أي SKU من الحروف المخفية + المسافات ============
def clean_sku_text(x):
    if x is None:
        return ""
    x = str(x)
    x = re.sub(r"[\u200B-\u200F\u202A-\u202E\uFEFF]", "", x)
    return x.strip()


# ================== تحميل الشيت الأساسي ==================
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
    
    for col in ["SKU1", "SKU2", "SKU3", "SKU4", "SKU5", "SKU6"]:
        if col in df.columns:
            df[col] = df[col].apply(clean_sku_text)

    return df


# ================== تحميل شيت history (الإصدار الإصلاحي الكامل) ==================
def load_history():
    creds = Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )

    client = gspread.authorize(creds)
    SPREADSHEET_ID = "1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk"

    try:
        ws = client.open_by_key(SPREADSHEET_ID).worksheet("history")
    except:
        return pd.DataFrame()

    data = ws.get_all_values()
    if len(data) < 2:
        return pd.DataFrame()

    df = pd.DataFrame(data[1:], columns=data[0])

    # استخراج النص من hyperlink
    def extract_hyperlink_text(x):
        x = str(x).strip()
        if x.startswith("=") and "HYPERLINK" in x.upper():
            parts = x.split('"')
            if len(parts) >= 4:
                return parts[-2]
        return x

    def canon_alnum(s):
        if s is None:
            return ""
        s = str(s).lower()
        return re.sub(r"[^0-9a-z]", "", s)

    df["SKU"] = df["SKU"].apply(lambda x: clean_sku_text(extract_hyperlink_text(x)))
    df["SKU_lower"] = df["SKU"].str.strip().str.lower()
    df["SKU_canon"] = df["SKU"].apply(canon_alnum)

    return df


# =========== استخراج آخر تغيير من history (مطابقة شديدة الذكاء) ===========
def get_last_change(df_hist, sku):
    if df_hist.empty or not sku:
        return None

    sku_clean = clean_sku_text(sku)
    sku_lower = sku_clean.lower().strip()
    sku_canon = re.sub(r"[^0-9a-z]", "", sku_lower)

    # 1) تطابق مباشر
    rows = df_hist[df_hist["SKU_lower"] == sku_lower]

    # 2) تطابق على النسخة الموجزة (بدون رموز)
    if rows.empty:
        rows = df_hist[df_hist["SKU_canon"] == sku_canon]

    # 3) تطابق احتوائي (contains)
    if rows.empty:
        mask1 = df_hist["SKU"].str.contains(re.escape(sku_clean), case=False, na=False)
        rows = df_hist[mask1]

    # 4) تطابق احتوائي على النسخة الموجزة
    if rows.empty:
        mask2 = df_hist["SKU_canon"].str.contains(sku_canon, na=False)
        rows = df_hist[mask2]

    if rows.empty:
        return None

    rows = rows.copy()
    rows["DateTime"] = pd.to_datetime(rows["DateTime"], errors="coerce")
    rows = rows.sort_values("DateTime")

    last = rows.iloc[-1]

    return {
        "old": last.get("Old Price", ""),
        "new": last.get("New Price", ""),
        "change": last.get("Change", ""),
        "time": str(last.get("DateTime", ""))
    }


# Sidebar
st.sidebar.header("⚙️ الإعدادات")

refresh_rate = st.sidebar.slider("⏱ معدل التحديث (ثواني)", 5, 300, 30)
search_text = st.sidebar.text_input("🔍 البحث عن SKU")

st.sidebar.markdown("---")
placeholder = st.empty()
last_update_placeholder = st.sidebar.empty()


# =============== عرض الصفحة ==================
while True:
    try:
        df = load_sheet()
        df_hist = load_history()

        if search_text:
            df = df[df.apply(lambda row: row.astype(str).str.contains(search_text, case=False).any(), axis=1)]

        with placeholder.container():
            st.subheader("🟦 عرض المنتجات بطريقة الكروت – Cards View")

            for idx, row in df.iterrows():
                sku_main = clean_sku_text(row.get("SKU1", ""))
                if sku_main == "":
                    continue

                sku_list = [
                    ("سعر منتجك", "SKU1", "Price1"),
                    ("المنافس 1", "SKU2", "Price2"),
                    ("المنافس 2", "SKU3", "Price3"),
                    ("المنافس 3", "SKU4", "Price4"),
                    ("المنافس 4", "SKU5", "Price5"),
                    ("المنافس 5", "SKU6", "Price6"),
                ]

                html = f"""
                <div style="border:1px solid #ccc; padding:20px; border-radius:12px;
                            margin-bottom:20px; background:#fff; direction:rtl;
                            font-family:'Tajawal', sans-serif;">
                    <h2>📦 <b>SKU الأساسي:</b> 
                        <span style="color:#007bff;">{sku_main}</span>
                    </h2>

                    <h3>🏷️ <b>الأسعار + آخر تغيير:</b></h3>

                    <ul style="font-size:18px; line-height:1.9; list-style:none; padding:0;">
                """

                for label, sku_col, price_col in sku_list:

                    sku_val = clean_sku_text(row.get(sku_col, ""))
                    price_val = row.get(price_col, "")

                    change_data = get_last_change(df_hist, sku_val)

                    if change_data:
                        change_html = f"""
                        <div style='font-size:15px; margin-top:2px;'>
                            🔄 <b>آخر تغيير:</b> {change_data['old']} → {change_data['new']}
                            <br>📅 <b>الوقت:</b> {change_data['time']}
                        </div>
                        """
                    else:
                        change_html = "<div style='font-size:14px; color:#888;'>لا يوجد تغييرات مسجلة</div>"

                    html += f"""
                        <li>
                            <b>{label} ({sku_val}):</b> {price_val}
                            {change_html}
                        </li>
                    """

                html += "</ul></div>"

                components.html(html, height=520)

        last_update_placeholder.markdown(
            f"🕒 آخر تحديث: **{time.strftime('%Y-%m-%d %H:%M:%S')}**"
        )

    except Exception as e:
        st.error(f"❌ خطأ أثناء التحميل: {e}")

    time.sleep(refresh_rate)
