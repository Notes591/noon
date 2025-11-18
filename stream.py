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

	# إصلاح أسماء الأعمدة
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

	# تنظيف الأعمدة
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

		# البحث
        if search_text:
            df = df[df.apply(lambda r: r.astype(str).str.contains(search_text, case=False).any(), axis=1)]

        with placeholder.container():
            st.subheader("🟦 عرض المنتجات – Cards View")

            for idx, row in df.iterrows():

                sku_main = row["SKU1"]
                if not sku_main:
                    continue

                sku_list = [
                    ("سعر منتجك", "SKU1", "Price1", "Nudge1"),
                    ("المنافس 1", "SKU2", "Price2", "Nudge2"),
                    ("المنافس 2", "SKU3", "Price3", "Nudge3"),
                    ("المنافس 3", "SKU4", "Price4", "Nudge4"),
                    ("المنافس 4", "SKU5", "Price5", "Nudge5"),
                    ("المنافس 5", "SKU6", "Price6", "Nudge6"),
                ]

                html = f"""
                <div style="
                    border:1px solid #e3e3e3;
                    padding:15px;
                    border-radius:10px;
                    margin-bottom:18px;
                    background:#ffffff;
                    direction:rtl;
                    width:90%;
                    box-shadow:0 1px 4px rgba(0,0,0,0.05);
                ">
                    <h2 style="font-size:20px; margin-bottom:10px; color:#333;">
                        📦 <b>SKU الأساسي:</b>
                        <span style="color:#007bff;">{sku_main}</span>
                    </h2>

                    <h3 style="font-size:16px; margin:5px 0 12px 0; color:#555;">
                        🏷️ <b>الأسعار + آخر تغيير + النودجز:</b>
                    </h3>

                    <ul style="font-size:15px; line-height:1.6; list-style:none; padding:0; margin:0;">
                """

                for label, sku_col, price_col, nudge_col in sku_list:

                    sku_val = row.get(sku_col, "")
                    price_val = row.get(price_col, "")
                    raw_nudge = row.get(nudge_col, "-")

                    sku_val = clean_sku_text(sku_val)

                    if raw_nudge and raw_nudge != "-":
                        nudge_show = " | ".join([n.strip() for n in raw_nudge.split("|") if n.strip()])
                    else:
                        nudge_show = "-"

                    if sku_col == "SKU1":
                        change_html = ""
                    else:
                        change = get_last_change(df_hist, sku_val)
                        if change:
                            change_html = f"""
                            <div style="font-size:13px; margin-top:3px;">
                                🔄 <b>آخر تغيير:</b> {change['old']} → {change['new']}
                                <br>📅 <b>الوقت:</b> {change['time']}
                            </div>
                            """
                        else:
                            change_html = "<div style='font-size:12px; color:#777;'>لا يوجد تغييرات مسجلة</div>"

                    html += f"""
                        <li style="margin-bottom:12px; padding-bottom:10px; border-bottom:1px solid #f0f0f0;">
                            <div style="font-size:15px; font-weight:bold; color:#222;">
                                {label} <span style="color:#888; font-weight:normal;">({sku_val})</span>
                            </div>

                            <div style="margin-top:4px; font-size:15px;">
                                💰 <b>السعر:</b>
                                <span style="color:#2c3e50; font-weight:bold;">{price_val}</span>
                            </div>

                            <div style="color:#666; margin-top:3px; font-size:14px;">
                                🔔 {nudge_show}
                            </div>

                            {change_html}
                        </li>
                    """

                html += "</ul></div>"

                # ============ عرض الكارت بدون Scroll + ارتفاع كبير ============
                components.html(html, height=2500, scrolling=False)

        last_update_placeholder.markdown(
            f"🕒 آخر تحديث: **{time.strftime('%Y-%m-%d %H:%M:%S')}**"
        )

    except Exception as e:
        st.error(f"❌ خطأ أثناء التحميل: {e}")

    time.sleep(refresh_rate)
