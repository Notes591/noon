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
st.set_page_config(page_title="Noon Prices – Live Monitoring Dashboard", layout="wide")
st.title("📊 Noon Prices – Live Monitoring Dashboard")

# ====================================================================
# 1) تنظيف SKU
# ====================================================================
def clean_sku_text(x):
    if not x:
        return ""
    x = str(x).strip()

    x = re.sub(r"[\u200B-\u200F\u202A-\u202E\uFEFF]", "", x)

    m = re.search(r"\(([A-Za-z0-9]+)\)", x)
    if m:
        return m.group(1).strip()

    parts = re.findall(r"[A-Za-z0-9]{6,}", x)
    if parts:
        parts.sort(key=len, reverse=True)
        return parts[0]

    return x.strip()


# ====================================================================
# 2) تحميل الشيت الرئيسي + تنظيف أسماء الأعمدة
# ====================================================================
def load_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    client = gspread.authorize(creds)

    SHEET_ID = "1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk"
    ws = client.open_by_key(SHEET_ID).worksheet("noon")

    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])

    df.columns = (
        df.columns
        .str.strip()
        .str.replace(r"[\u200B-\u200F\u202A-\u202E\uFEFF]", "", regex=True)
    )

    for col in ["SKU1","SKU2","SKU3","SKU4","SKU5","SKU6"]:
        if col in df.columns:
            df[col] = df[col].apply(clean_sku_text)

    return df


# ====================================================================
# 3) تحميل history + تنظيف الأعمدة
# ====================================================================
def load_history():
    creds = Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    client = gspread.authorize(creds)

    SHEET_ID = "1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk"

    try:
        ws = client.open_by_key(SHEET_ID).worksheet("history")
    except:
        return pd.DataFrame()

    data = ws.get_all_values()
    if len(data) < 2:
        return pd.DataFrame()

    df = pd.DataFrame(data[1:], columns=data[0])

    df.columns = (
        df.columns
        .str.strip()
        .str.replace(r"[\u200B-\u200F\u202A-\u202E\uFEFF]", "", regex=True)
    )

    df["SKU"] = df["SKU"].astype(str)
    df["SKU_clean"] = df["SKU"].apply(clean_sku_text)
    df["SKU_lower"] = df["SKU_clean"].str.lower().str.strip()
    df["DateTime"] = pd.to_datetime(df["DateTime"], errors="coerce")

    return df


# ====================================================================
# 4) Smart Matching للمنافسين
# ====================================================================
def get_last_change(df_hist, sku):
    if df_hist.empty:
        return None

    sku_clean = clean_sku_text(sku).lower().strip()
    if not sku_clean:
        return None

    rows = df_hist[df_hist["SKU_lower"] == sku_clean]
    if not rows.empty:
        rows = rows.sort_values("DateTime")
        last = rows.iloc[-1]
        return {"old": last["Old Price"], "new": last["New Price"], "change": last["Change"], "time": str(last["DateTime"])}

    rows = df_hist[df_hist["SKU_lower"].str.contains(sku_clean)]
    if not rows.empty:
        rows = rows.sort_values("DateTime")
        last = rows.iloc[-1]
        return {"old": last["Old Price"], "new": last["New Price"], "change": last["Change"], "time": str(last["DateTime"])}

    rows = df_hist[df_hist["SKU_lower"].str.startswith(sku_clean[:6])]
    if not rows.empty:
        rows = rows.sort_values("DateTime")
        last = rows.iloc[-1]
        return {"old": last["Old Price"], "new": last["New Price"], "change": last["Change"], "time": str(last["DateTime"])}

    rows = df_hist[df_hist["SKU_lower"].str.endswith(sku_clean[-6:])]
    if not rows.empty:
        rows = rows.sort_values("DateTime")
        last = rows.iloc[-1]
        return {"old": last["Old Price"], "new": last["New Price"], "change": last["Change"], "time": str(last["DateTime"])}

    return None


# ====================================================================
# 5) Streamlit UI
# ====================================================================
st.sidebar.header("⚙️ الإعدادات")
refresh_rate = st.sidebar.slider("⏱ معدل التحديث (ثواني)", 5, 300, 30)
search_text = st.sidebar.text_input("🔍 البحث عن SKU")

placeholder = st.empty()
last_update_placeholder = st.sidebar.empty()


# ====================================================================
# 6) عرض البيانات
# ====================================================================
while True:
    try:
        df = load_sheet()
        df_hist = load_history()

        if search_text:
            df = df[df.apply(lambda r: r.astype(str).str.contains(search_text, case=False).any(), axis=1)]

        with placeholder.container():

            st.subheader("🟦 عرض المنتجات – Cards View")

            for idx, row in df.iterrows():

                sku_main = row["SKU1"]
                if not sku_main:
                    continue

                # ========= شكل الكارت الذي طلبته =========
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

                </div>
                """

                components.html(html_card, height=420, scrolling=False)

        last_update_placeholder.markdown(
            f"🕒 آخر تحديث: **{time.strftime('%Y-%m-%d %H:%M:%S')}**"
        )

    except Exception as e:
        st.error(f"❌ خطأ أثناء التحميل: {e}")

    time.sleep(refresh_rate)
