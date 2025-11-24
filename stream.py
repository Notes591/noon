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

# ====== FIX: دعم الجوال + إشعارات Scroll ======
st.markdown("""
<style>
/* Mobile responsiveness */
@media (max-width: 768px) {
    body, p, div, span { font-size: 14px !important; }
    h1, h2 { font-size: 18px !important; }
    h3 { font-size: 16px !important; }
    img { max-width: 100% !important; height: auto !important; }
}

/* Notifications scroll box */
.notify-scroll {
    max-height: 600px;
    overflow-y: auto;
    padding-right: 10px;
}
</style>
""", unsafe_allow_html=True)

# السماح بالصوت بعد أول ضغطة
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
ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgAAAA
//uQZAAAAAABgIAAABAAAAAIAAAAAExBTUUzLjk1LjIAAAAAAAAAAAAAAAAAAAAAAAAA
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
# تحويل SKU إلى رابط HTML قابل للنقر
# -------------------------------------------------
def sku_to_link_html(sku):
    sku_clean = clean_sku_text(sku)
    if not sku_clean:
        return html.escape(str(sku))
    url = f"https://www.noon.com/saudi-en/{sku_clean}/p/"
    display = html.escape(sku_clean)
    return f'<a href="{url}" target="_blank" rel="noopener" style="color:#007bff; font-weight:bold; text-decoration:none;">{display}</a>'

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
# تنسيق النودجات
# ============================================================
def format_nudge_html(nudge_text):
    if nudge_text is None:
        return ""
    s = str(nudge_text).strip()
    if s == "" or s == "-":
        return ""
    lower_s = s.lower()
    if "sold recently" in lower_s or re.search(r"\d+\s*\+?\s*sold", lower_s):
        esc = html.escape(s)
        return f"""
        <div style="background:#ffcc80;color:#000;padding:6px 10px;border-radius:6px;
                    font-weight:bold;width:max-content;font-size:18px;margin-top:6px;display:inline-block;">
            🔥 {esc}
        </div>
        """
    esc = html.escape(s)
    return f"""
    <div style="background:#fff3cd;color:#000;padding:4px 8px;border-radius:6px;
                font-weight:bold;width:max-content;font-size:18px;margin-top:6px;display:inline-block;">
        🟨 {esc}
    </div>
    """

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

            # -----------------------------
            # 🔔 الإشعارات مع Scroll
            # -----------------------------
            st.subheader("🔔 آخر التغييرات (Notifications)")

            st.markdown("<div class='notify-scroll'>", unsafe_allow_html=True)

            if not hist.empty:
                recent = hist.sort_values("DateTime", ascending=False).reset_index(drop=True)

                for i, r in recent.iterrows():
                    sku_html = sku_to_link_html(r.get("SKU", ""))
                    oldp = html.escape(str(r["Old Price"]))
                    newp = html.escape(str(r["New Price"]))
                    time_ = html.escape(str(r["DateTime"]))

                    notify_html = f"""
                    <div style='padding:10px; border-left:5px solid #007bff; margin-bottom:15px;
                                background:white; border-radius:8px; direction:rtl; font-size:18px;'>
                        <div><b>SKU:</b> {sku_html}</div>
                        <div style='font-size:20px; font-weight:700; margin-top:5px;'>
                            {oldp} → {newp}
                        </div>
                        <div style='color:#777;'>📅 {time_}</div>
                    </div>
                    """
                    components.html(notify_html, height=160, scrolling=False)

            st.markdown("</div>", unsafe_allow_html=True)

            # -----------------------------
            # عرض المنتجات
            # -----------------------------
            st.subheader("📦 أسعار المنتجات والمنافسين")

            for idx, row in df.iterrows():
                sku_main = row.get("SKU1", "")
                if not sku_main:
                    continue

                product_name = row.get("ProductName", "")
                image_url = row.get("Image url", "").strip()
                main_price = row.get("Price1","")

                card = f"""
                <div style="border:1px solid #ddd;border-radius:12px;padding:20px;margin-bottom:20px;background:white;direction:rtl;width:100%;">
                    <h2>🔵 {html.escape(product_name)} — {sku_to_link_html(sku_main)}</h2>
                    <img src="{html.escape(image_url)}" style="max-width:150px;border-radius:8px;">
                    <div style='font-size:32px;font-weight:bold;'>💰 {main_price}</div>
                </div>
                """

                components.html(card, height=400, scrolling=True)

        last_update_widget.write("⏳ آخر تحديث: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        time.sleep(refresh_rate)

    except Exception as e:
        st.error(f"❌ خطأ: {e}")
        time.sleep(refresh_rate)
