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
import base64
import html

# ----------------------------------------------
# إعداد الصفحة
# ----------------------------------------------
st.set_page_config(page_title="Noon Prices – Dashboard", layout="wide")
st.title("📊 Noon Prices – Live Monitoring Dashboard")


# ============================================================
# صوت Base64 (تنبيه قوي)
# ============================================================
AUDIO_BASE64 = """
SUQzAwAAAAAAF1RTU0UAAAAPAAADTGF2ZjU2LjQwLjEwMQAAAAAAAAAAAAAA//tQxAADB6w
...
(سيتم وضع ملف Base64 كامل هنا لاحقاً)
"""

# لتسهيل التشغيل
def play_sound():
    audio_tag = f"""
    <audio autoplay>
        <source src="data:audio/mp3;base64,{AUDIO_BASE64}" type="audio/mp3">
    </audio>
    """
    st.markdown(audio_tag, unsafe_allow_html=True)


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
# تحميل بيانات NOON
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
# آخر تغيير
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
# تحويل price إلى رقم
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
# إعدادات جانبية
# ============================================================
st.sidebar.header("⚙️ الإعدادات")
refresh_rate = st.sidebar.slider("⏱ التحديث كل (ثانية)", 5, 300, 15)
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

        # بحث
        if search_text:
            df = df[df.apply(lambda r: r.astype(str).str.contains(search_text, case=False).any(), axis=1)]

        with placeholder.container():

            # ============================================================
            # 🔔 آخر التغييرات (داخل Scroll لا يأخذ مساحة)
            # ============================================================
            st.subheader("🔔 التغييرات الأخيرة (داخل Scroll)")

            if not hist.empty:

                recent = hist.sort_values("DateTime", ascending=False).head(10)
                recent = recent.reset_index(drop=True)

                # Scroll
                st.markdown("""
                <div style="
                    max-height:300px;
                    overflow-y:scroll;
                    direction:rtl;
                    padding-right:10px;
                    border:1px solid #ddd;
                    border-radius:10px;
                    background:#fafafa;
                ">
                """, unsafe_allow_html=True)

                for i, change in recent.iterrows():

                    sku = html.escape(str(change["SKU"]))
                    old_p = html.escape(str(change["Old Price"]))
                    new_p = html.escape(str(change["New Price"]))
                    time_c = html.escape(str(change["DateTime"]))

                    # حساب السهم
                    arrow = "➡️"
                    of = price_to_float(old_p)
                    nf = price_to_float(new_p)
                    if of is not None and nf is not None:
                        if nf > of: arrow = "🔺"
                        elif nf < of: arrow = "🔻"

                    change_id = f"{sku}_{time_c}"

                    bg = "#fff"
                    border = "#ccc"

                    st.markdown(f"""
                    <div onclick="markSeen('{change_id}')"
                        style="
                            background:{bg};
                            border:2px solid {border};
                            border-radius:10px;
                            padding:12px;
                            margin-bottom:10px;
                            cursor:pointer;
                            font-size:20px;
                            direction:rtl;
                        ">
                        <b>SKU:</b> {sku}<br>
                        <b>من:</b> {old_p} → <b>إلى:</b> {new_p} {arrow}<br>
                        <span style='color:#666;'>📅 {time_c}</span>
                    </div>

                    <script>
                    document.addEventListener("DOMContentLoaded", function(){{
                        var seen = localStorage.getItem("{change_id}");
                        if ({i} === 0 && !seen) {{
                            // سيشغل صوت Base64 عبر Streamlit
                            window.parent.postMessage({{'event':'PLAY_SOUND'}}, '*');
                        }}
                    }});
                    function markSeen(id){{
                        localStorage.setItem(id, "seen");
                    }}
                    </script>
                    """, unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)

            else:
                st.warning("لا يوجد تغييرات حتى الآن.")


            # ============================================================
            # 🎯 تشغيل الصوت (من Streamlit)
            # ============================================================
            sound_script = """
            <script>
            window.addEventListener("message", (event) => {
                if (event.data.event === "PLAY_SOUND") {
                    var audio = new Audio("data:audio/mp3;base64,""" + AUDIO_BASE64 + """");
                    audio.volume = 1.0;
                    audio.play();
                }
            });
            </script>
            """
            st.markdown(sound_script, unsafe_allow_html=True)


            # ============================================================
            # 🟦 الكروت (تكبير المنافس + لون)
            # ============================================================
            st.subheader("📦 أسعار المنتجات والمنافسين")

            color_map = {
                "منافس1": "#007bff",
                "منافس2": "#ff8800",
                "منافس3": "#ff4444",
                "منافس4": "#28a745",
                "منافس5": "#6f42c1"
            }

            for _, row in df.iterrows():

                sku_main = row["SKU1"]
                if not sku_main:
                    continue

                def change_html(sku):
                    ch = get_last_change(hist, sku)
                    if not ch:
                        return "<span style='color:#777;'>لا يوجد تغييرات</span>"

                    old = ch["old"]
                    new = ch["new"]
                    time_ = ch["time"]

                    arrow = "➡️"
                    old_f = price_to_float(old)
                    new_f = price_to_float(new)
                    if old_f and new_f:
                        if new_f > old_f: arrow = "🔺"
                        elif new_f < old_f: arrow = "🔻"

                    return f"""
                        <span style='font-size:22px; font-weight:600; color:#000;'>
                           🔄 {old} → {new} {arrow}<br>
                           <span style='font-size:17px; color:#444;'>📅 {time_}</span>
                        </span>
                    """

                card_html = f"""
                <div style="
                    border:1px solid #ddd;
                    padding:20px;
                    border-radius:12px;
                    margin-bottom:25px;
                    background:#fff;
                    width:70%;
                    direction:rtl;
                ">

                    <h2>🔵 SKU الأساسي: <span style='color:#007bff'>{sku_main}</span></h2>

                    <br><b style='font-size:23px;'>💰 سعر منتجك:</b><br>
                    <span style='font-size:36px; font-weight:bold; color:#000;'>{row.get("Price1","")}</span>
                    <br><span style='color:#777;'>لا يوجد تغيير لمنتجك</span>

                    <hr>

                    <ul style="list-style:none; font-size:22px;">

                        <li>
                            <b style='color:{color_map["منافس1"]}; font-size:26px;'>🟦 منافس1:</b><br>
                            <span style='font-size:34px; font-weight:bold;'>{row.get("Price2","")}</span><br>
                            {change_html(row.get("SKU2",""))}
                        </li><br>

                        <li>
                            <b style='color:{color_map["منافس2"]}; font-size:26px;'>🟧 منافس2:</b><br>
                            <span style='font-size:34px; font-weight:bold;'>{row.get("Price3","")}</span><br>
                            {change_html(row.get("SKU3",""))}
                        </li><br>

                        <li>
                            <b style='color:{color_map["منافس3"]}; font-size:26px;'>🟥 منافس3:</b><br>
                            <span style='font-size:34px; font-weight:bold;'>{row.get("Price4","")}</span><br>
                            {change_html(row.get("SKU4",""))}
                        </li><br>

                        <li>
                            <b style='color:{color_map["منافس4"]}; font-size:26px;'>🟩 منافس4:</b><br>
                            <span style='font-size:34px; font-weight:bold;'>{row.get("Price5","")}</span><br>
                            {change_html(row.get("SKU5",""))}
                        </li><br>

                        <li>
                            <b style='color:{color_map["منافس5"]}; font-size:26px;'>🟪 منافس5:</b><br>
                            <span style='font-size:34px; font-weight:bold;'>{row.get("Price6","")}</span><br>
                            {change_html(row.get("SKU6",""))}
                        </li>

                    </ul>

                </div>
                """

                components.html(card_html, height=1350, scrolling=False)


        # ============================================================
        # وقت السعودية
        # ============================================================
        ksa = datetime.utcnow() + timedelta(hours=3)
        last_update_widget.markdown(
            f"🕒 آخر تحديث (KSA): **{ksa.strftime('%Y-%m-%d %H:%M:%S')}**"
        )

    except Exception as e:
        st.error(f"❌ خطأ: {e}")

    time.sleep(refresh_rate)
