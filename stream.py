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

st.set_page_config(page_title="Noon Prices – Live Monitoring Dashboard", layout="wide")
st.title("📊 Noon Prices – Live Monitoring Dashboard")

# ================================================
# تنظيف SKU
# ================================================
def clean_sku_text(x):
    if not x:
        return ""
    x = str(x).strip()
    x = re.sub(r"[\u200B-\u200F\u202A-\u202E\uFEFF]", "", x)

    m = re.search(r"\(([A-Za-z0-9]+)\)", x)
    if m:
        return m.group(1)

    parts = re.findall(r"[A-Za-z0-9]{6,}", x)
    if parts:
        parts.sort(key=len, reverse=True)
        return parts[0]

    return x


# ================================================
# تحميل sheet
# ================================================
def load_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    client = gspread.authorize(creds)

    SH = "1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk"
    ws = client.open_by_key(SH).worksheet("noon")

    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])

    df.columns = (
        df.columns.str.strip().str.replace(
            r"[\u200B-\u200F\u202A-\u202E\uFEFF]", "", regex=True
        )
    )

    for c in ["SKU1", "SKU2", "SKU3", "SKU4", "SKU5", "SKU6"]:
        if c in df.columns:
            df[c] = df[c].apply(clean_sku_text)

    return df


# ================================================
# تحميل history
# ================================================
def load_history():
    creds = Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    client = gspread.authorize(creds)

    SH = "1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk"

    try:
        ws = client.open_by_key(SH).worksheet("history")
    except:
        return pd.DataFrame()

    data = ws.get_all_values()
    if len(data) < 2:
        return pd.DataFrame()

    df = pd.DataFrame(data[1:], columns=data[0])
    df.columns = (
        df.columns.str.strip().str.replace(
            r"[\u200B-\u200F\u202A-\u202E\uFEFF]", "", regex=True
        )
    )

    df["SKU"] = df["SKU"].astype(str)
    df["SKU_clean"] = df["SKU"].apply(clean_sku_text)
    df["SKU_lower"] = df["SKU_clean"].str.lower().str.strip()
    df["DateTime"] = pd.to_datetime(df["DateTime"], errors="coerce")

    return df


# ================================================
# Smart Matching
# ================================================
def get_last_change(df_hist, sku):
    if df_hist.empty:
        return None

    sku_clean = clean_sku_text(sku).lower().strip()
    if not sku_clean:
        return None

    # full match
    rows = df_hist[df_hist["SKU_lower"] == sku_clean]
    if not rows.empty:
        last = rows.sort_values("DateTime").iloc[-1]
        return last.to_dict()

    # contains
    rows = df_hist[df_hist["SKU_lower"].str.contains(sku_clean)]
    if not rows.empty:
        last = rows.sort_values("DateTime").iloc[-1]
        return last.to_dict()

    # startswith
    rows = df_hist[df_hist["SKU_lower"].str.startswith(sku_clean[:6])]
    if not rows.empty:
        last = rows.sort_values("DateTime").iloc[-1]
        return last.to_dict()

    # endswith
    rows = df_hist[df_hist["SKU_lower"].str.endswith(sku_clean[-6:])]
    if not rows.empty:
        last = rows.sort_values("DateTime").iloc[-1]
        return last.to_dict()

    return None


# ================================================
# إعداد الواجهة
# ================================================
st.sidebar.header("⚙️ الإعدادات")
refresh_rate = st.sidebar.slider("⏱ معدل التحديث (ثوانٍ)", 5, 300, 30)
search_text = st.sidebar.text_input("🔍 البحث عن SKU")
placeholder = st.empty()
last_update = st.sidebar.empty()


# =========================================================
# THE OLD CARD EXACT + new info in compressed row
# =========================================================
while True:
    try:
        df = load_sheet()
        df_hist = load_history()

        if search_text:
            df = df[
                df.apply(
                    lambda r: r.astype(str).str.contains(search_text, case=False).any(),
                    axis=1,
                )
            ]

        with placeholder.container():
            st.subheader("🟦 عرض المنتجات – شكل الكارت القديم EXACT")

            for idx, row in df.iterrows():

                sku_main = row["SKU1"]
                if not sku_main:
                    continue

                # قائمة المنافسين بالألوان EXACT
                sku_list = [
                    ("🟦 سعر منتجك", "SKU1", "Price1", "Nudge1"),
                    ("🟨 المنافس 1", "SKU2", "Price2", "Nudge2"),
                    ("🟧 المنافس 2", "SKU3", "Price3", "Nudge3"),
                    ("🟥 المنافس 3", "SKU4", "Price4", "Nudge4"),
                    ("🟩 المنافس 4", "SKU5", "Price5", "Nudge5"),
                    ("🟪 المنافس 5", "SKU6", "Price6", "Nudge6"),
                ]

                # كارت EXACT قديم
                html = f"""
                <div style="
                    border:1px solid #ccc;
                    padding:15px;
                    border-radius:10px;
                    margin-bottom:20px;
                    width:90%;
                    background:white;
                    direction:rtl;
                    font-size:17px;
                ">
                    <h3>📦 <b>SKU الأساسي:</b> {sku_main}</h3>
                    <br>
                """

                # ===================================================
                # LOOP = نفس الكارت القديم EXACT
                # وأضاف البيانات الجديدة في سطر واحد
                # ===================================================
                for label, sku_col, price_col, nudge_col in sku_list:

                    sku_val = clean_sku_text(row.get(sku_col, ""))
                    price_val = row.get(price_col, "-")
                    nudge_raw = row.get(nudge_col, "-")

                    # تجهيز النودج
                    if nudge_raw and nudge_raw != "-":
                        nudge_text = "🔔 " + " | ".join(
                            [x.strip() for x in nudge_raw.split("|") if x.strip()]
                        )
                    else:
                        nudge_text = ""

                    # competitor only
                    if sku_col == "SKU1":
                        change_text = ""
                    else:
                        ch = get_last_change(df_hist, sku_val)
                        if ch:
                            old_p = ch["Old Price"]
                            new_p = ch["New Price"]

                            # لون السهم
                            if float(new_p) > float(old_p):
                                arrow = "🔺"
                            elif float(new_p) < float(old_p):
                                arrow = "🟢"
                            else:
                                arrow = "➡️"

                            change_text = (
                                f"{arrow} {old_p}→{new_p} | 📅 {ch['DateTime']}"
                            )
                        else:
                            change_text = ""

                    # ---- السطر النهائي المضغوط ----
                    line = f"{label} ({sku_val}): {price_val}"

                    details = " | ".join(
                        [x for x in [nudge_text, change_text] if x.strip() != ""]
                    )

                    if details:
                        line += " | " + details

                    html += f"{line}<br>"

                html += "</div>"

                components.html(html, height=None, scrolling=True)

        last_update.markdown(
            f"🕒 آخر تحديث: **{time.strftime('%Y-%m-%d %H:%M:%S')}**"
        )

    except Exception as e:
        st.error(f"❌ خطأ: {e}")

    time.sleep(refresh_rate)
