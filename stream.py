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


st.set_page_config(page_title="Noon Prices – Live Monitoring Dashboard", layout="wide")
st.title("📊 Noon Prices – Live Monitoring Dashboard")


# ====================================================================
# تنظيف SKU
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
# تحميل شيت البيانات الرئيسي
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

    df.columns = df.columns.str.strip().str.replace(r"[\u200B-\u200F\u202A-\u202E\uFEFF]", "", regex=True)

    for col in ["SKU1", "SKU2", "SKU3", "SKU4", "SKU5", "SKU6"]:
        if col in df.columns:
            df[col] = df[col].apply(clean_sku_text)

    return df


# ====================================================================
# تحميل history
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

    df.columns = df.columns.str.strip().str.replace(r"[\u200B-\u200F\u202A-\u202E\uFEFF]", "", regex=True)

    df["SKU"] = df["SKU"].astype(str)
    df["SKU_clean"] = df["SKU"].apply(clean_sku_text)
    df["SKU_lower"] = df["SKU_clean"].str.lower().str.replace(" ", "")
    df["DateTime"] = pd.to_datetime(df["DateTime"], errors="coerce")

    return df


# ====================================================================
# الحصول على آخر تغيير
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
        return {
            "old": last["Old Price"],
            "new": last["New Price"],
            "change": last["Change"],
            "time": str(last["DateTime"])
        }

    rows = df_hist[df_hist["SKU_lower"].str.contains(sku_clean)]
    if not rows.empty:
        rows = rows.sort_values("DateTime")
        last = rows.iloc[-1]
        return {
            "old": last["Old Price"],
            "new": last["New Price"],
            "change": last["Change"],
            "time": str(last["DateTime"])
        }

    return None


def price_to_float(s):
    if s is None:
        return None
    s = str(s).strip()
    if s == "":
        return None
    cleaned = re.sub(r"[^\d\.\-]", "", s)
    parts = cleaned.split('.')
    if len(parts) > 2:
        cleaned = parts[0] + '.' + ''.join(parts[1:])
    try:
        return float(cleaned)
    except:
        return None


# ====================================================================
# إعدادات واجهة Streamlit
# ====================================================================
st.sidebar.header("⚙️ الإعدادات")
refresh_rate = st.sidebar.slider("⏱ معدل التحديث (ثواني)", 5, 300, 30)
search_text = st.sidebar.text_input("🔍 البحث عن SKU")

placeholder = st.empty()
last_update_placeholder = st.sidebar.empty()


# ====================================================================
# LOOP
# ====================================================================
while True:
    try:

        df = load_sheet()
        df_hist = load_history()

        if search_text:
            df = df[df.apply(lambda r: r.astype(str).str.contains(search_text, case=False).any(), axis=1)]

        with placeholder.container():

            # ============================================================
            # 🔔 قسم التغييرات — مع إصلاح HTML الكامل
            # ============================================================
            st.subheader("🔔 التغييرات الأخيرة (آخر 10 تغييرات)")

            if not df_hist.empty:

                recent_changes = df_hist.sort_values("DateTime", ascending=False).head(10)
                recent_changes = recent_changes.reset_index(drop=True)

                st.markdown("<div style='max-height:450px; overflow-y:auto; direction:rtl;'>",
                            unsafe_allow_html=True)

                for idx, change in recent_changes.iterrows():

                    sku = html.escape(str(change["SKU"]))
                    old_p = html.escape(str(change["Old Price"]))
                    new_p = html.escape(str(change["New Price"]))
                    time_c = html.escape(str(change["DateTime"]))

                    change_id = f"{sku}_{time_c}"

                    try:
                        of = float(str(change["Old Price"]).replace(",", "").replace("SAR", ""))
                        nf = float(str(change["New Price"]).replace(",", "").replace("SAR", ""))
                        arrow = "🔺" if nf > of else "🔻" if nf < of else "➡️"
                    except:
                        arrow = "➡️"

                    bg = "#ffdddd" if idx == 0 else "#ffffff"
                    border = "#ff4444" if idx == 0 else "#dddddd"

                    st.markdown(f"""
                    <div id="{change_id}" onclick="markSeen('{change_id}')"
                        style="
                            background:{bg};
                            border:2px solid {border};
                            border-radius:10px;
                            padding:15px;
                            margin-bottom:10px;
                            cursor:pointer;
                            direction:rtl;
                            font-size:20px;
                            width:95%;
                        ">
                        <b>SKU:</b> {sku}<br>
                        <b>من:</b> {old_p} → <b>إلى:</b> {new_p} {arrow}<br>
                        <span style='color:#666;'>📅 {time_c}</span>
                    </div>

                    <script>
                    function playAlertSound(){{
                        var audio = new Audio('/beep.mp3');
                        audio.volume = 1.0;
                        audio.play();
                    }}

                    document.addEventListener("DOMContentLoaded", function(){{
                        var id = "{change_id}";
                        var seen = localStorage.getItem(id);

                        if ({idx} === 0 && seen !== "seen") {{
                            playAlertSound();
                        }}

                        if (seen === "seen") {{
                            var c = document.getElementById(id);
                            if (c){{
                                c.style.background = "#ffffff";
                                c.style.borderColor = "#dddddd";
                            }}
                        }}
                    }});

                    function markSeen(id){{
                        localStorage.setItem(id, "seen");
                        var c = document.getElementById(id);
                        if (c){{
                            c.style.background = "#ffffff";
                            c.style.borderColor = "#dddddd";
                        }}
                    }}
                    </script>
                    """, unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)

            else:
                st.info("لا يوجد تغييرات مسجلة بعد.")


            # ============================================================
            # 🟦 الكروت — بدون تغيير
            # ============================================================
            st.subheader("🟦 عرض المنتجات – Cards View")

            for idx, row in df.iterrows():

                sku_main = row["SKU1"]
                if not sku_main:
                    continue

                def change_html(sku):
                    ch = get_last_change(df_hist, sku)
                    if ch:
                        old = ch["old"]
                        new = ch["new"]
                        time_str = ch["time"]

                        old_f = price_to_float(old)
                        new_f = price_to_float(new)

                        if old_f is not None and new_f is not None:
                            arrow = "🔺" if new_f > old_f else "🔻" if new_f < old_f else "➡️"
                        else:
                            arrow = "➡️"

                        return f"""
                        <span style='font-size:22px; font-weight:bold; color:#000;'>
                            🔄 من <b>{old}</b> إلى <b>{new}</b> {arrow}
                            <br><span style='font-size:18px; color:#444;'>📅 {time_str}</span>
                        </span>
                        """

                    return "<span style='font-size:16px; color:#777;'>لا يوجد تغييرات</span>"

                card = f"""
                <div style="
                    border:1px solid #ddd;
                    padding:20px;
                    border-radius:12px;
                    margin-bottom:20px;
                    background:#fff;
                    width:70%;
                    direction:rtl;
                ">
                    <h2>📦 <b>SKU الأساسي:</b> <span style='color:#007bff'>{sku_main}</span></h2>

                    <h3>🏷️ <b>الأسعار + آخر تغيير:</b></h3>

                    <ul style="list-style:none; font-size:20px;">
                        <li>🟦 <b>سعر منتجك:</b> {row.get("Price1","")}<br>
                            <span style='color:#666;'>لا يوجد تغيير لمنتجك</span>
                        </li>
                        <li>🟨 منافس1: {row.get("Price2","")}<br>{change_html(row.get("SKU2",""))}</li>
                        <li>🟧 منافس2: {row.get("Price3","")}<br>{change_html(row.get("SKU3",""))}</li>
                        <li>🟥 منافس3: {row.get("Price4","")}<br>{change_html(row.get("SKU4",""))}</li>
                        <li>🟩 منافس4: {row.get("Price5","")}<br>{change_html(row.get("SKU5",""))}</li>
                        <li>🟪 منافس5: {row.get("Price6","")}<br>{change_html(row.get("SKU6",""))}</li>
                    </ul>
                </div>
                """

                components.html(card, height=1250, scrolling=False)

        ksa_time = datetime.utcnow() + timedelta(hours=3)
        last_update_placeholder.markdown(
            f"🕒 آخر تحديث (KSA): **{ksa_time.strftime('%Y-%m-%d %H:%M:%S')}**"
        )

    except Exception as e:
        st.error(f"❌ خطأ: {e}")

    time.sleep(refresh_rate)
