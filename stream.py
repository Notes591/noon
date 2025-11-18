import sys
import os
import time
import datetime
import re
import traceback
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components

# إعداد صفحة Streamlit
st.set_page_config(
    page_title="Noon Prices Dashboard",
    layout="wide",
)

st.title("📊 Noon Prices – Live Monitoring Dashboard")


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
    return df


# ================== تحميل شيت التاريخ ==================
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
    return df


# استخراج آخر تغيير لسكيو1 فقط
def get_last_change(df_hist, sku):
    if df_hist.empty:
        return None

    rows = df_hist[df_hist["SKU"] == sku]
    if rows.empty:
        return None

    last = rows.tail(1).iloc[0]

    return {
        "old": last["Old Price"],
        "new": last["New Price"],
        "change": last["Change"],
        "time": last["DateTime"]
    }


# Sidebar
st.sidebar.header("⚙️ الإعدادات")

refresh_rate = st.sidebar.slider(
    "⏱ معدل التحديث (ثواني)",
    5, 300, 30
)

search_text = st.sidebar.text_input("🔍 البحث عن SKU")

placeholder = st.empty()
last_update_placeholder = st.sidebar.empty()


def highlight_changes(val):
    val = str(val)
    if "↑" in val:
        return "background-color: #d1ffd1;"
    if "↓" in val:
        return "background-color: #ffd1d1;"
    return ""


while True:
    try:
        df = load_sheet()
        df_hist = load_history()

        if search_text:
            df = df[df.apply(lambda row: row.astype(str).str.contains(search_text, case=False).any(), axis=1)]
            df_hist = df_hist[df_hist.apply(lambda row: row.astype(str).str.contains(search_text, case=False).any(), axis=1)]

        styled_df = df.style.applymap(highlight_changes)

        with placeholder.container():

            st.subheader("🟦 عرض المنتجات بطريقة الكروت – Cards View")

            for idx, row in df.iterrows():

                sku_main = row.get("SKU1", "").strip()
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
                <div style="
                    border:1px solid #cccccc;
                    padding:20px;
                    border-radius:12px;
                    margin-bottom:20px;
                    background:#ffffff;
                    direction:rtl;
                    font-family:'Tajawal', sans-serif;
                ">
                    <h2 style="margin:0 0 10px; font-size:24px;">
                        📦 <b>الـSKU الأساسي:</b>
                        <span style="color:#007bff;">{sku_main}</span>
                    </h2>

                    <div style="height:1px; background:#ddd; margin:10px 0;"></div>

                    <h3 style="margin:10px 0; font-size:20px;">🏷️ <b>الأسعار + آخر تغيير:</b></h3>

                    <ul style="font-size:18px; line-height:1.9; list-style:none; padding:0;">
                """

                for label, sku_col, price_col in sku_list:
                    sku_val = row.get(sku_col, "")
                    price_val = row.get(price_col, "")

                    # 🔥 التعديل المهم — نستخدم آخر تغيير للـ SKU1 فقط
                    change_data = get_last_change(df_hist, sku_main)

                    if change_data:
                        change_html = f"""
                        <div style='font-size:15px; margin-top:3px; color:#555;'>
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

                html += f"""
                    </ul>

                    <p style="margin-top:15px; font-size:16px;">
                        📅 <b>آخر تحديث:</b> {row.get('Last Update','')}
                    </p>
                </div>
                """

                components.html(html, height=480)

            st.subheader("📋 الجدول الأصلي")
            st.dataframe(styled_df, use_container_width=True)

            st.subheader("📉 سجل تغييرات الأسعار – History")

            if df_hist.empty:
                st.info("لا يوجد تغييرات مسجلة حتى الآن.")
            else:
                st.dataframe(df_hist, use_container_width=True)

        last_update_placeholder.markdown(
            f"🕒 آخر تحديث: **{time.strftime('%Y-%m-%d %H:%M:%S')}**"
        )

    except Exception as e:
        st.error(f"❌ خطأ أثناء تحميل الشيت: {e}")

    time.sleep(refresh_rate)
