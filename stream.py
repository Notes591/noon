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

# السماح للصوت بعد أول ضغطة
st.markdown("""
<script>
document.addEventListener("click", function() {
    localStorage.setItem("sound_enabled", "1");
});
</script>
""", unsafe_allow_html=True)

# -------------------------------------------------
# صوت التنبيه Base64
# -------------------------------------------------
AUDIO_BASE64 = """
SUQzAwAAAAAAF1RTU0UAAAAPAAADTGF2ZjU2LjQwLjEwMQAAAAAAAAAAAAAA//uQZAAAAAAD
6wAABEV4dGVuc2libGUgQWxhcm0gMQAAACgAAABkYXRhAAAAAICAgICAgICAgICAgICAgICA
gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC
AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg
ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA
gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIC
AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg
AAAA//uQZAAAAAABgIAAABAAAAAIAAAAAExBTUUzLjk1LjIAAAAAAAAAAAAAAAAAAAAAAAAA
"""

def inject_audio_listener():
    js = f"""
    <script>
    window.addEventListener("message", (event) => {{
        if (event.data.event === "PLAY_SOUND" && localStorage.getItem("sound_enabled")) {{
            var audio = new Audio("data:audio/mp3;base64,{AUDIO_BASE64}");
            audio.volume = 1.0;
            audio.play();
        }}
    }});
    </script>
    """
    st.markdown(js, unsafe_allow_html=True)

# -------------------------------------------------
# تنظيف SKU
# -------------------------------------------------
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
        return max(parts, key=len)
    return x

# -------------------------------------------------
# تحميل Sheet الرئيسية
# -------------------------------------------------
def load_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    client = gspread.authorize(creds)

    SID = "1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk"
    ws = client.open_by_key(SID).worksheet("noon")

    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    df.columns = df.columns.str.strip()

    for col in ["SKU1","SKU2","SKU3","SKU4","SKU5","SKU6"]:
        if col in df.columns:
            df[col] = df[col].apply(clean_sku_text)

    return df

# -------------------------------------------------
# تحميل history
# -------------------------------------------------
def load_history():
    creds = Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    client = gspread.authorize(creds)

    SID = "1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk"

    try:
        ws = client.open_by_key(SID).worksheet("history")
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

# -------------------------------------------------
# تحويل السعر إلى float
# -------------------------------------------------
def price_to_float(s):
    if s is None:
        return None
    text = str(s).strip()
    if text == "":
        return None
    text = text.replace(",", ".")
    cleaned = re.sub(r"[^\d\.\-]", "", text)
    try:
        return float(cleaned)
    except:
        return None

# -------------------------------------------------
# الحصول على آخر تغيير
# -------------------------------------------------
def get_last_change(hist, sku):
    if hist.empty:
        return None

    sku_clean = clean_sku_text(sku).lower()
    r = hist[hist["SKU_lower"] == sku_clean]

    if r.empty:
        r = hist[hist["SKU_lower"].str.contains(sku_clean)]

    if r.empty:
        return None

    r = r.sort_values("DateTime")
    last = r.iloc[-1]

    return {
        "old": last["Old Price"],
        "new": last["New Price"],
        "time": str(last["DateTime"])
    }

# -------------------------------------------------
# إعدادات جانبية
# -------------------------------------------------
st.sidebar.header("⚙️ الإعدادات")
refresh_rate = st.sidebar.slider("⏱ التحديث (ثواني)", 5, 300, 15)
search = st.sidebar.text_input("🔍 بحث SKU")

placeholder = st.empty()
last_update_widget = st.sidebar.empty()

inject_audio_listener()

# ============================================================
# LOOP
# ============================================================
while True:
    try:
        df = load_sheet()
        hist = load_history()

        if search:
            df = df[df.apply(lambda r: r.astype(str).str.contains(search, case=False).any(), axis=1)]

        with placeholder.container():

            # -------------------------------------------------
            # 🔔 الإشعارات
            # -------------------------------------------------
            st.subheader("🔔 آخر التغييرات (Notifications)")

            if not hist.empty:
                recent = hist.sort_values("DateTime", ascending=False).head(5).reset_index(drop=True)

                for i, r in recent.iterrows():

                    sku  = html.escape(str(r["SKU"]))
                    oldp = html.escape(str(r["Old Price"]))
                    newp = html.escape(str(r["New Price"]))
                    time_ = html.escape(str(r["DateTime"]))

                    main_sku = ""
                    my_price = ""
                    product_name = ""

                    try:
                        match = df[df.apply(lambda row: sku in row.astype(str).values, axis=1)]
                        if not match.empty:
                            main_sku = match.iloc[0].get("SKU1", "")
                            my_price = match.iloc[0].get("Price1", "")
                            product_name = match.iloc[0].get("ProductName", "")
                    except:
                        pass
                    # تحويل للنقاط (float)
                    of = price_to_float(oldp)
                    nf = price_to_float(newp)

                    # سهم الزيادة/النقص
                    arrow = "➡️"
                    if of is not None and nf is not None:
                        if nf > of:
                            arrow = "🔺"
                        elif nf < of:
                            arrow = "🔻"

                    # السهم بين السعرين (يمين أو يسار)
                    dir_arrow = "→"
                    if of is not None and nf is not None and nf < of:
                        dir_arrow = "←"

                    # 🔥 تعديل الإشعار — إضافة سعري + SKU + المنتج
                    my_info_html = ""
                    if my_price:
                        my_info_html = (
                            " — <span style='color:#28a745;'>سعري: "
                            + html.escape(str(my_price))
                            + " — SKU: " + html.escape(str(main_sku))
                            + (" — " + html.escape(product_name) if product_name else "")
                            + "</span>"
                        )

                    notify_html = f"""
                    <div style='padding:10px; border-left:5px solid #007bff; margin-bottom:15px;
                                background:white; border-radius:8px; direction:rtl; font-size:18px;'>

                        <div style='display:flex; justify-content:space-between; align-items:center;'>

                            <div><b>SKU:</b> {sku}</div>

                            <div style='font-weight:700; text-align:right;'>
                                <span style='color:#007bff;'>
                                    {html.escape(product_name) if product_name else 'SKU الأساسي: ' + html.escape(main_sku)}
                                </span>
                                {my_info_html}
                            </div>

                        </div>

                        <div style='font-size:20px; font-weight:700; margin-top:5px;'>
                            {oldp} {dir_arrow} {newp} {arrow}
                        </div>

                        <div style='color:#777;'>📅 {time_}</div>

                    </div>
                    """

                    components.html(notify_html, height=170, scrolling=False)

            # -------------------------------------------------
            # قسم عرض المنتجات
            # -------------------------------------------------
            st.subheader("📦 أسعار المنتجات والمنافسين")

            colors = ["#007bff", "#ff8800", "#ff4444", "#28a745", "#6f42c1"]

            for idx, row in df.iterrows():

                sku_main = row.get("SKU1", "")
                if not sku_main:
                    continue

                product_name = row.get("ProductName", "")

                # تغيير المنافسين
                def ch_html(sku):
                    if not sku or str(sku).strip() == "":
                        return "<span style='color:#777;'>لا يوجد SKU للمنافس</span>"

                    ch = get_last_change(hist, sku)
                    if not ch:
                        return "<span style='color:#777;'>لا يوجد تغييرات</span>"

                    old = ch["old"]
                    new = ch["new"]
                    time_ = ch["time"]

                    of = price_to_float(old)
                    nf = price_to_float(new)

                    arrow = "➡️"
                    if of is not None and nf is not None:
                        if nf > of:
                            arrow = "🔺"
                        elif nf < of:
                            arrow = "🔻"

                    dir_arrow = "→"
                    if of is not None and nf is not None and nf < of:
                        dir_arrow = "←"

                    return f"""
                        <span style='font-size:20px; font-weight:600;'>
                            🔄 {old} {dir_arrow} {new} {arrow}<br>
                            <span style='font-size:16px; color:#444;'>📅 {time_}</span>
                        </span>
                    """

                # كارت المنتج
                card = f"""
                <div style="
                    border:1px solid #ddd;
                    border-radius:12px;
                    padding:20px;
                    margin-bottom:20px;
                    background:white;
                    direction:rtl;
                    width:70%;
                ">
                """

                if product_name:
                    card += f"<h2>🔵 {html.escape(product_name)} — SKU الأساسي: <span style='color:#007bff'>{sku_main}</span></h2>"
                else:
                    card += f"<h2>🔵 SKU الأساسي: <span style='color:#007bff'>{sku_main}</span></h2>"

                card += f"""
                    <b style='font-size:24px;'>💰 سعر منتجك:</b><br>
                    <span style='font-size:36px; font-weight:bold;'>{row.get("Price1","")}</span>
                    <br><span style='color:#666;'>لا يوجد تغيير لمنتجك</span>
                    <hr>
                """

                competitors = [
                    ("منافس1", row.get("SKU2",""), row.get("Price2",""), colors[0]),
                    ("منافس2", row.get("SKU3",""), row.get("Price3",""), colors[1]),
                    ("منافس3", row.get("SKU4",""), row.get("Price4",""), colors[2]),
                    ("منافس4", row.get("SKU5",""), row.get("Price5",""), colors[3]),
                    ("منافس5", row.get("SKU6",""), row.get("Price6",""), colors[4]),
                ]

                for name, sku_c, price, clr in competitors:
                    card += f"""
                    <div style='margin-bottom:18px;'>
                        <b style='font-size:28px; color:{clr};'>{name}:</b><br>
                        <span style='font-size:34px; font-weight:bold;'>{price}</span><br>
                        {ch_html(sku_c)}
                    </div>
                    """

                card += "</div>"

                components.html(card, height=1300, scrolling=False)
        # -------------------------------------------------
        # تحديث توقيت السعودية في الـ Sidebar
        # -------------------------------------------------
        ksa = datetime.utcnow() + timedelta(hours=3)
        last_update_widget.markdown(
            f"🕒 آخر تحديث (KSA): **{ksa.strftime('%Y-%m-%d %H:%M:%S')}**"
        )

    except Exception as e:
        st.error(f"❌ خطأ في التشغيل: {e}")

    time.sleep(refresh_rate)
