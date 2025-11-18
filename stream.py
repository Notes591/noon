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
# 6) عرض البيانات + الكارت الحديث
# ====================================================================
while True:
    try:
        df = load_sheet()
        df_hist = load_history()

        if search_text:
            df = df[df.apply(lambda r: r.astype(str).str.contains(search_text, case=False).any(), axis=1)]

        with placeholder.container():
            st.subheader("🟦 عرض المنتجات – Modern Compact Cards")

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


                # ============== الكارت الجديد ==============
                html = f"""
                <div style="
                    border: 1px solid #dcdcdc;
                    padding: 12px;
                    border-radius: 12px;
                    margin-bottom: 15px;
                    background: #ffffff;
                    direction: rtl;
                    width: 60%;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
                    font-family: 'Arial';
                ">

                    <div style="
                        font-size: 17px;
                        font-weight: bold;
                        color: #1a73e8;
                        margin-bottom: 8px;
                    ">
                        📦 SKU الأساسي:
                        <span style="color:#000; font-weight:bold;">{sku_main}</span>
                    </div>

                    <div style="
                        font-size: 14px;
                        font-weight: bold;
                        margin-bottom: 10px;
                        color: #444;
                    ">
                        🏷️ الأسعار + آخر تحديث + النودجز
                    </div>

                    <div>
                """

                # LOOP المنافسين + منتجك
                for label, sku_col, price_col, nudge_col in sku_list:

                    sku_val = clean_sku_text(row.get(sku_col, ""))
                    price_val = row.get(price_col, "-")
                    raw_nudge = row.get(nudge_col, "-")

                    if raw_nudge and raw_nudge != "-":
                        nudge_show = " | ".join([n.strip() for n in raw_nudge.split("|") if n.strip()])
                    else:
                        nudge_show = "-"

                    # منتجك لون خاص
                    if sku_col == "SKU1":
                        change_html = ""
                        box_color = "#e8f0fe"
                    else:
                        change = get_last_change(df_hist, sku_val)
                        box_color = "#f7f7f7"

                        if change:
                            change_html = f"""
                            <div style="font-size:12px; margin-top:3px; color:#555;">
                                🔄 <b>{change['old']} → {change['new']}</b>
                                <div style="margin-top:2px;">📅 {change['time']}</div>
                            </div>
                            """
                        else:
                            change_html = "<div style='font-size:12px; margin-top:3px; color:#777;'>لا يوجد تغييرات</div>"

                    html += f"""
                        <div style="
                            background:{box_color};
                            border-radius:8px;
                            padding:10px;
                            margin-bottom:8px;
                            border:1px solid #e0e0e0;
                        ">
                            <div style="font-size:14px; font-weight:bold; color:#333;">
                                {label} 
                                <span style="color:#888; font-size:13px;">({sku_val})</span>
                            </div>

                            <div style="margin-top:4px; font-size:14px;">
                                💰 <b>السعر:</b> {price_val}
                            </div>

                            <div style="margin-top:3px; font-size:13px; color:#555;">
                                🔔 {nudge_show}
                            </div>

                            {change_html}
                        </div>
                    """

                html += "</div></div>"

                components.html(html, height=900, scrolling=False)

        last_update_placeholder.markdown(
            f"🕒 آخر تحديث: **{time.strftime('%Y-%m-%d %H:%M:%S')}**"
        )

    except Exception as e:
        st.error(f"❌ خطأ أثناء التحميل: {e}")

    time.sleep(refresh_rate)
