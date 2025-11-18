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
from datetime import datetime, timedelta
import html

# إعداد الصفحة
st.set_page_config(page_title="Noon Prices Dashboard", layout="wide")
st.title("📊 Noon Prices – Live Monitoring Dashboard")


# ============================================================
# تنظيف SKU
# ============================================================
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


# ============================================================
# تحميل شيت المنتجات
# ============================================================
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
    df.columns = df.columns.str.strip()

    for c in ["SKU1","SKU2","SKU3","SKU4","SKU5","SKU6"]:
        df[c] = df[c].apply(clean_sku_text)

    return df


# ============================================================
# تحميل history
# ============================================================
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
    if len(data) <= 1:
        return pd.DataFrame()

    df = pd.DataFrame(data[1:], columns=data[0])
    df["SKU_clean"] = df["SKU"].apply(clean_sku_text)
    df["SKU_lower"] = df["SKU_clean"].str.lower().str.replace(" ","")
    df["DateTime"] = pd.to_datetime(df["DateTime"], errors="coerce")

    return df


# ============================================================
# آخر تغيير للـ SKU
# ============================================================
def get_last_change(df_hist, sku):
    if df_hist.empty:
        return None
    sku_clean = clean_sku_text(sku).lower().strip()
    rows = df_hist[df_hist["SKU_lower"] == sku_clean]

    if rows.empty:
        rows = df_hist[df_hist["SKU_lower"].str.contains(sku_clean)]

    if rows.empty:
        return None

    rows = rows.sort_values("DateTime")
    last = rows.iloc[-1]

    return {
        "old": last["Old Price"],
        "new": last["New Price"],
        "change": last["Change"],
        "time": str(last["DateTime"])
    }


# ============================================================
# تحويل السعر ل float
# ============================================================
def price_to_float(s):
    if not s:
        return None
    s = str(s)
    cleaned = re.sub(r"[^\d\.\-]", "", s)
    try:
        return float(cleaned)
    except:
        return None


# ============================================================
# واجهة الإعدادات
# ============================================================
st.sidebar.header("⚙️ الإعدادات")
refresh_rate = st.sidebar.slider("⏱ التحديث كل (ثواني)", 5, 300, 15)
search_text = st.sidebar.text_input("🔍 بحث SKU")

placeholder = st.empty()
last_update_widget = st.sidebar.empty()


# ============================================================
# LOOP
# ============================================================
while True:
    try:

        df = load_sheet()
        hist = load_history()

        if search_text:
            df = df[df.apply(lambda r: r.astype(str).str.contains(search_text, case=False).any(), axis=1)]

        with placeholder.container():

            # ============================================================
            # 🔔 قسم التغييرات (بدون لون – أحدث تغيير في الأعلى)
            # ============================================================
            st.subheader("🔔 آخر التغييرات (آخر 10)")

            if not hist.empty:

                recent = hist.sort_values("DateTime", ascending=False).head(10).reset_index(drop=True)

                st.markdown("<div style='max-height:420px; overflow-y:auto; direction:rtl;'>",
                            unsafe_allow_html=True)

                for i, row in recent.iterrows():

                    sku = html.escape(str(row["SKU"]))
                    old_p = html.escape(str(row["Old Price"]))
                    new_p = html.escape(str(row["New Price"]))
                    time_c = html.escape(str(row["DateTime"]))

                    arrow = "➡️"
                    old_f = price_to_float(old_p)
                    new_f = price_to_float(new_p)
                    if old_f is not None and new_f is not None:
                        if new_f > old_f: arrow = "🔺"
                        elif new_f < old_f: arrow = "🔻"

                    change_id = f"{sku}_{time_c}"

                    html_block = f"""
                    <div id="{change_id}" onclick="markSeen('{change_id}')" 
                        style="
                            background:#fff;
                            border:2px solid #ddd;
                            border-radius:10px;
                            padding:15px;
                            margin-bottom:10px;
                            cursor:pointer;
                            direction:rtl;
                            font-size:20px;
                        ">
                        <b>SKU:</b> {sku}<br>
                        <b>من:</b> {old_p} → <b>إلى:</b> {new_p} {arrow}<br>
                        <span style='color:#666;'>📅 {time_c}</span>
                    </div>

                    <script>
                    function playAlertSound(){{
                        var audio = new Audio("beep.mp3");
                        audio.volume = 1.0;
                        audio.play();
                    }}

                    document.addEventListener("DOMContentLoaded", function(){{
                        var seen = localStorage.getItem("{change_id}");
                        if ({i} === 0 && seen !== "seen") {{
                            playAlertSound();
                        }}
                    }});

                    function markSeen(id){{
                        localStorage.setItem(id, "seen");
                    }}
                    </script>
                    """

                    st.markdown(html_block, unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)

            else:
                st.info("لا توجد تغييرات بعد.")

            # ============================================================
            # 🟦 كروت المنتجات — الأسعار كبيرة وواضحة
            # ============================================================
            st.subheader("🟦 المنتجات – Cards View")

            for _, row in df.iterrows():

                sku_main = row["SKU1"]
                if not sku_main:
                    continue

                def change_html(sku):
                    ch = get_last_change(hist, sku)
                    if not ch:
                        return "<span style='color:#777;'>لا يوجد تغييرات</span>"

                    old, new = ch["old"], ch["new"]
                    time_ = ch["time"]

                    old_f = price_to_float(old)
                    new_f = price_to_float(new)
                    arrow = "➡️"
                    if old_f is not None and new_f is not None:
                        if new_f > old_f: arrow = "🔺"
                        elif new_f < old_f: arrow = "🔻"

                    return f"""
                        <span style='font-size:22px; font-weight:bold; color:#000;'>
                            🔄 من <b>{old}</b> إلى <b>{new}</b> {arrow}<br>
                            <span style='font-size:18px; color:#444;'>📅 {time_}</span>
                        </span>
                    """

                card_html = f"""
                <div style="
                    border:1px solid #ddd;
                    padding:20px;
                    border-radius:14px;
                    margin-bottom:25px;
                    background:#fff;
                    width:70%;
                    direction:rtl;
                ">

                    <h2>📦 <b>SKU الأساسي:</b> 
                        <span style='color:#007bff'>{sku_main}</span>
                    </h2>

                    <h3>🏷️ الأسعار + آخر تغيير:</h3>

                    <ul style="list-style:none; font-size:20px;">

                        <li>
                            🟦 <b>سعر منتجك:</b><br>
                            <span style='font-size:36px; font-weight:bold; color:#000;'>
                                {row.get("Price1","")}
                            </span><br>
                            <span style='color:#666;'>لا يوجد تغيير لمنتجك</span>
                        </li>

                        <li>
                            🟨 منافس1 ({row.get("SKU2","")}):<br>
                            <span style='font-size:36px; font-weight:bold; color:#000;'>
                                {row.get("Price2","")}
                            </span><br>{change_html(row.get("SKU2",""))}
                        </li>

                        <li>
                            🟧 منافس2 ({row.get("SKU3","")}):<br>
                            <span style='font-size:36px; font-weight:bold; color:#000;'>
                                {row.get("Price3","")}
                            </span><br>{change_html(row.get("SKU3",""))}
                        </li>

                        <li>
                            🟥 منافس3 ({row.get("SKU4","")}):<br>
                            <span style='font-size:36px; font-weight:bold; color:#000;'>
                                {row.get("Price4","")}
                            </span><br>{change_html(row.get("SKU4",""))}
                        </li>

                        <li>
                            🟩 منافس4 ({row.get("SKU5","")}):<br>
                            <span style='font-size:36px; font-weight:bold; color:#000;'>
                                {row.get("Price5","")}
                            </span><br>{change_html(row.get("SKU5",""))}
                        </li>

                        <li>
                            🟪 منافس5 ({row.get("SKU6","")}):<br>
                            <span style='font-size:36px; font-weight:bold; color:#000;'>
                                {row.get("Price6","")}
                            </span><br>{change_html(row.get("SKU6",""))}
                        </li>

                    </ul>
                </div>
                """

                components.html(card_html, height=1350, scrolling=False)


        # وقت السعودية
        ksa = datetime.utcnow() + timedelta(hours=3)
        last_update_widget.markdown(f"🕒 آخر تحديث (KSA): **{ksa.strftime('%Y-%m-%d %H:%M:%S')}**")

    except Exception as e:
        st.error(f"❌ خطأ: {e}")

    time.sleep(refresh_rate)
