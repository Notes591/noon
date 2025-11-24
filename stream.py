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

# ----------------------------------------------
# 📱 CSS دعم كامل للجوال + إصلاح الإشعارات
# ----------------------------------------------
st.markdown("""
<style>

/* ---------  العرض العام للجوال  ---------- */
@media (max-width: 768px) {

    /* الكروت الرئيسية للمنتج */
    div[style*="border:1px solid #ddd"] {
        width: 100% !important;
        padding: 12px !important;
        margin: 10px 0 !important;
    }

    /* كروت المنافسين */
    div[style*="background:#fafafa"] {
        padding: 10px !important;
        margin: 8px 0 !important;
    }

    /* صورة المنتج داخل الكرت */
    img {
        max-width: 100% !important;
        height: auto !important;
    }

    /* عناوين المنتجات */
    h2, h3 {
        font-size: 18px !important;
        line-height: 1.4 !important;
    }

    /* السعر الأساسي */
    span[style*="font-size:36px"] {
        font-size: 26px !important;
    }

    /* سعر المنافس */
    span[style*="font-size:26px"] {
        font-size: 20px !important;
    }

    /* النودجات 🔥🟨 */
    div[style*="background:#fff3cd"],
    div[style*="background:#ffcc80"]{
        font-size: 14px !important;
        padding: 4px 6px !important;
    }

    /* ===== إصلاح Notifications بالكامل ===== */

    /* الصندوق الأساسي */
    div[style*="border-left:5px solid"] {
        display: block !important;
        width: 100% !important;
    }

    /* أي child داخله يصبح عمودي */
    div[style*="border-left:5px solid"] * {
        float: none !important;
        display: block !important;
    }

    /* صورة SKU داخل الإشعار */
    div[style*="border-left:5px solid"] img {
        width: 110px !important;
        height: auto !important;
        margin: 0 auto 10px auto !important;
    }

    /* مساحات داخلية للإشعار */
    div[style*="border-left:5px solid"] > div {
        margin: 0 !important;
    }

    /* أسعار داخل الإشعار */
    div[style*="font-size:20px"] {
        text-align: center !important;
    }

    /* iframe الخاص components.html */
    iframe {
        height: auto !important;
        min-height: 160px !important;
    }
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
# ★★ تنسيق النودجات (🔥 و 🟨)
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
        <div style="
            background:#ffcc80;
            color:#000;
            padding:6px 10px;
            border-radius:6px;
            font-weight:bold;
            width:max-content;
            font-size:18px;
            margin-top:6px;
            display:inline-block;
        ">
            🔥 {esc}
        </div>
        """
    esc = html.escape(s)
    return f"""
    <div style="
        background:#fff3cd;
        color:#000;
        padding:4px 8px;
        border-radius:6px;
        font-weight:bold;
        width:max-content;
        font-size:18px;
        margin-top:6px;
        display:inline-block;
    ">
        🟨 {esc}
    </div>
    """

# -------------------------------------------------
# تحديد أي نودج تابع لأي SKU
# -------------------------------------------------
def find_nudge_for_sku_in_row(row, sku_to_find):
    if not sku_to_find:
        return ""
    sku_clean = clean_sku_text(sku_to_find).strip()
    if sku_clean == "":
        return ""
    sku_cols = ["SKU1","SKU2","SKU3","SKU4","SKU5","SKU6"]
    for idx, col in enumerate(sku_cols, start=1):
        val = row.get(col, "")
        if clean_sku_text(val) == sku_clean:
            nudge_col = f"Nudge{idx}"
            return row.get(nudge_col, "")
    return ""

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
            # 🔔 آخر التغييرات (Notifications)
            # -----------------------------
            st.subheader("🔔 آخر التغييرات (Notifications)")

            if not hist.empty:
                recent = hist.sort_values("DateTime", ascending=False).head(5).reset_index(drop=True)
                for i, r in recent.iterrows():
                    sku_html = sku_to_link_html(r.get("SKU", ""))
                    oldp = html.escape(str(r["Old Price"]))
                    newp = html.escape(str(r["New Price"]))
                    time_ = html.escape(str(r["DateTime"]))
                    main_sku = ""
                    my_price = ""
                    product_name = ""
                    nudge_html = ""
                    image_url = ""
                    try:
                        sku_clean_search = clean_sku_text(str(r["SKU"]))
                        match = df[df.apply(lambda row: sku_clean_search in [
                            clean_sku_text(row.get(c,"")) for c in
                            ["SKU1","SKU2","SKU3","SKU4","SKU5","SKU6"]
                        ], axis=1)]
                        if not match.empty:
                            matched_row = match.iloc[0]
                            main_sku = matched_row.get("SKU1", "")
                            my_price = matched_row.get("Price1", "")
                            product_name = matched_row.get("ProductName", "")
                            nudge_val = find_nudge_for_sku_in_row(matched_row, sku_clean_search)
                            nudge_html = format_nudge_html(nudge_val)
                            image_url = matched_row.get("Image url", "").strip()
                    except Exception:
                        pass

                    of = price_to_float(oldp)
                    nf = price_to_float(newp)
                    arrow = "➡️"
                    if of is not None and nf is not None:
                        if nf > of:
                            arrow = "🔺"
                        elif nf < of:
                            arrow = "🔻"
                    dir_arrow = "→"
                    if of is not None and nf is not None and nf < of:
                        dir_arrow = "←"

                    my_info_html = ""
                    if my_price:
                        my_info_html = (
                            " — <span style='color:#28a745;'>سعري: "
                            + html.escape(str(my_price))
                            + " — SKU: " + sku_to_link_html(main_sku)
                            + (" — " + html.escape(product_name) if product_name else "")
                            + "</span>"
                        )

                    img_html = ""
                    if image_url:
                        img_html = f"""
                        <div style='float:left; margin-left:10px;'>
                            <img src="{html.escape(image_url)}" style="width:80px; height:auto; border-radius:6px;">
                        </div>
                        """

                    notify_html = f"""
                    <div style='padding:10px; border-left:5px solid #007bff; margin-bottom:15px;
                                background:white; border-radius:8px; direction:rtl; font-size:18px; overflow:hidden;'>

                        {img_html}

                        <div style='margin-right:90px;'>

                            <div style='display:flex; justify-content:space-between; align-items:center;'>
                                <div><b>SKU:</b> {sku_html}</div>
                                <div style='font-weight:700; text-align:right;'>
                                    <span style='color:#007bff;'>
                                        {html.escape(product_name) if product_name else 'SKU الأساسي: ' + sku_to_link_html(main_sku)}
                                    </span>
                                    {my_info_html}
                                </div>
                            </div>

                            <div style='font-size:20px; font-weight:700; margin-top:5px;'>
                                {oldp} {dir_arrow} {newp} {arrow}
                            </div>

                            {nudge_html}

                            <div style='color:#777;'>📅 {time_}</div>

                        </div>
                    </div>
                    """

                    components.html(notify_html, height=120, scrolling=False)

            # -----------------------------
            # عرض المنتجات والمنافسين
            # -----------------------------
            st.subheader("📦 أسعار المنتجات والمنافسين")
            colors = ["#007bff", "#ff8800", "#ff4444", "#28a745", "#6f42c1"]

            for idx, row in df.iterrows():
                sku_main = row.get("SKU1", "")
                if not sku_main:
                    continue

                product_name = row.get("ProductName", "")
                image_url = row.get("Image url", "").strip()

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
                    card += f"<h2>🔵 {html.escape(product_name)} — SKU الأساسي: <span style='color:#007bff'>{sku_to_link_html(sku_main)}</span></h2>"
                else:
                    card += f"<h2>🔵 SKU الأساسي: <span style='color:#007bff'>{sku_to_link_html(sku_main)}</span></h2>"

                main_price = row.get("Price1","")
                main_nudge_html = format_nudge_html(row.get("Nudge1",""))

                img_html_card = ""
                if image_url:
                    img_html_card = f'<img src="{html.escape(image_url)}" style="max-width:150px; height:auto; border-radius:8px; margin-bottom:10px;">'

                card += f"""
                    {img_html_card}
                    <b style='font-size:24px;'>💰 سعر منتجك:</b><br>
                    <span style='font-size:36px; font-weight:bold;'>{main_price}</span>
                    <br>{main_nudge_html}
                    <br><span style='color:#666;'>لا يوجد تغيير لمنتجك</span>
                    <hr>
                """

                competitors = [
                    ("منافس1", row.get("SKU2",""), row.get("Price2",""), row.get("Nudge2",""), colors[0]),
                    ("منافس2", row.get("SKU3",""), row.get("Price3",""), row.get("Nudge3",""), colors[1]),
                    ("منافس3", row.get("SKU4",""), row.get("Price4",""), row.get("Nudge4",""), colors[2]),
                    ("منافس4", row.get("SKU5",""), row.get("Price5",""), row.get("Nudge5",""), colors[3]),
                    ("منافس5", row.get("SKU6",""), row.get("Price6",""), row.get("Nudge6",""), colors[4]),
                ]

                for cname, skuX, priceX, nudgeX, colorX in competitors:
                    if not skuX or str(skuX).strip() == "":
                        continue

                    sku_clean = clean_sku_text(skuX)
                    ch_html_block = ch_html(sku_clean)
                    nudge_html_block = format_nudge_html(nudgeX)

                    card += f"""
                    <div style="
                        border:1px solid #ccc;
                        padding:15px;
                        border-radius:10px;
                        margin-bottom:15px;
                        background:#fafafa;
                        direction:rtl;
                    ">
                        <h3 style="color:{colorX};">{cname} — SKU: {sku_to_link_html(sku_clean)}</h3>
                        <div style="font-size:26px; font-weight:bold;">
                            💰 السعر: {priceX}
                        </div>
                        {nudge_html_block}
                        <div style="margin-top:8px;">
                            {ch_html_block}
                        </div>
                    </div>
                    """

                card += "</div>"
                components.html(card, height=900, scrolling=True)

        last_update_widget.write(
            "⏳ آخر تحديث: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        time.sleep(refresh_rate)

    except Exception as e:
        st.error(f"❌ خطأ: {e}")
        time.sleep(refresh_rate)
