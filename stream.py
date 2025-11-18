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

# ----------------------------------------------------------------------
# 1) استخراج SKU الحقيقي بشكل صحيح 100%
# ----------------------------------------------------------------------
def clean_sku_text(x):
    """Extract ONLY the real SKU code from any messy text."""
    if x is None:
        return ""
    x = str(x).strip()

    # إزالة الحروف المخفية
    x = re.sub(r"[\u200B-\u200F\u202A-\u202E\uFEFF]", "", x)

    # 1) إذا SKU داخل أقواس → نعطيه الأولوية
    m = re.search(r"\(([A-Za-z0-9]+)\)", x)
    if m:
        return m.group(1).strip()

    # 2) نبحث عن جميع المقاطع التي تحتوي أرقام + حروف
    parts = re.findall(r"[A-Za-z0-9]{8,}", x)
    if parts:
        # نرجّح أطول مقطع = هو SKU الحقيقي
        parts.sort(key=len, reverse=True)
        return parts[0]

    return ""

# ----------------------------------------------------------------------
# 2) تحميل الشيت الأساسي
# ----------------------------------------------------------------------
def load_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    client = gspread.authorize(creds)

    SPREADSHEET_ID = "1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk"
    ws = client.open_by_key(SPREADSHEET_ID).worksheet("noon")

    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])

    # تنظيف SKU
    for col in ["SKU1", "SKU2", "SKU3", "SKU4", "SKU5", "SKU6"]:
        if col in df.columns:
            df[col] = df[col].apply(clean_sku_text)

    return df

# ----------------------------------------------------------------------
# 3) تحميل شيت history + تنظيف قوي
# ----------------------------------------------------------------------
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

    # استخراج SKU الحقيقي فقط
    df["SKU"] = df["SKU"].apply(clean_sku_text)

    df["SKU_lower"] = df["SKU"].str.lower().str.strip()

    # تنظيف وقت التاريخ
    df["DateTime"] = pd.to_datetime(df["DateTime"], errors="coerce")

    return df

# ----------------------------------------------------------------------
# 4) مطابقة SKU بشكل صحيح STRICT – بدون contains
# ----------------------------------------------------------------------
def get_last_change(df_hist, sku):
    """Return exact last change for EXACT SKU match ONLY."""
    sku = clean_sku_text(sku)
    if not sku or df_hist.empty:
        return None

    sku_lower = sku.lower().strip()

    # تطابق حقيقي فقط
    rows = df_hist[df_hist["SKU_lower"] == sku_lower]

    if rows.empty:
        return None

    rows = rows.sort_values("DateTime")
    last = rows.iloc[-1]

    return {
        "old": last.get("Old Price", ""),
        "new": last.get("New Price", ""),
        "change": last.get("Change", ""),
        "time": str(last.get("DateTime", ""))
    }

# ----------------------------------------------------------------------
# 5) واجهة Streamlit
# ----------------------------------------------------------------------
st.sidebar.header("⚙️ الإعدادات")
refresh_rate = st.sidebar.slider("⏱ معدل التحديث (ثواني)", 5, 300, 30)
search_text = st.sidebar.text_input("🔍 البحث عن SKU")

placeholder = st.empty()
last_update_placeholder = st.sidebar.empty()

# ----------------------------------------------------------------------
# 6) عرض الصفحة
# ----------------------------------------------------------------------
while True:
    try:
        df = load_sheet()
        df_hist = load_history()

        if search_text:
            df = df[df.apply(lambda row: row.astype(str).str.contains(search_text, case=False).any(), axis=1)]

        with placeholder.container():
            st.subheader("🟦 عرض المنتجات – Cards View")

            for idx, row in df.iterrows():

                sku_main = row.get("SKU1", "")
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
                            margin-bottom:20px; background:#fff; direction:rtl;">
                    <h2>📦 <b>SKU الأساسي:</b>
                        <span style="color:#007bff;">{sku_main}</span>
                    </h2>

                    <h3>🏷️ <b>الأسعار + آخر تغيير لكل SKU:</b></h3>

                    <ul style="font-size:18px; line-height:1.9; list-style:none; padding:0;">
                """

                for label, sku_col, price_col in sku_list:

                    sku_val = row.get(sku_col, "")
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

                components.html(html, height=540)

        last_update_placeholder.markdown(
            f"🕒 آخر تحديث: **{time.strftime('%Y-%m-%d %H:%M:%S')}**"
        )

    except Exception as e:
        st.error(f"❌ خطأ أثناء التحميل: {e}")

    time.sleep(refresh_rate)
