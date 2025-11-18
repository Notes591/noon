import sys
import os
import time
import datetime
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components

# إعداد صفحة Streamlit
st.set_page_config(page_title="Noon Prices Dashboard", layout="wide")
st.title("📊 Noon Prices – Live Monitoring Dashboard")


# ================== تحميل الشيت الأساسي ==================
def load_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )

    client = gspread.authorize(creds)

    SPREADSHEET_ID = "1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk"
    SHEET_NAME = "noon"

    ws = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    data = ws.get_all_values()

    df = pd.DataFrame(data[1:], columns=data[0])
    return df


# ================== تحميل شيت history ==================
def load_history():
    creds = Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )

    client = gspread.authorize(creds)
    SPREADSHEET_ID = "1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk"

    try:
        ws = client.open_by_key(SPREADSHEET_ID).worksheet("history")
    except:
        return pd.DataFrame()

    data = ws.get_all_values()
    if len(data) < 2:
        return pd.DataFrame()

    df = pd.DataFrame(data[1:], columns=data[0])

    # 🔥 أقوى تعديل: استخراج SKU حتى لو خلية Hyperlink
    def clean_sku(x):
        x = str(x).strip()
        if x.startswith("=") and "HYPERLINK" in x:
            # استخراج النص بين آخر علامتي اقتباس
            parts = x.split('"')
            if len(parts) >= 4:
                return parts[-2]  # النص النهائي
        return x

    df["SKU"] = df["SKU"].apply(clean_sku)

    return df


# =========== استخراج آخر تغيير من history ===========
def get_last_change(df_hist, sku):
    if df_hist.empty or not sku:
        return None

    sku = str(sku).strip()

    # فلترة السجلات
    rows = df_hist[df_hist["SKU"].astype(str).str.strip() == sku]
    if rows.empty:
        return None

    # ترتيب حسب الوقت
    rows["DateTime"] = pd.to_datetime(rows["DateTime"], errors="coerce")
    rows = rows.sort_values("DateTime")

    last = rows.iloc[-1]

    return {
        "old": last["Old Price"],
        "new": last["New Price"],
        "change": last["Change"],
        "time": str(last["DateTime"])
    }


# Sidebar
st.sidebar.header("⚙️ الإعدادات")

refresh_rate = st.sidebar.slider("⏱ معدل التحديث (ثواني)", 5, 300, 30)
search_text = st.sidebar.text_input("🔍 البحث عن SKU")

st.sidebar.markdown("---")
placeholder = st.empty()
last_update_placeholder = st.sidebar.empty()


# =============== عرض الصفحة ==================
while True:
    try:
        df = load_sheet()
        df_hist = load_history()

        # فلترة حسب البحث
        if search_text:
            df = df[df.apply(lambda row: row.astype(str).str.contains(search_text, case=False).any(), axis=1)]

        with placeholder.container():
            st.subheader("🟦 عرض المنتجات بطريقة الكروت – Cards View")

            for idx, row in df.iterrows():
                sku_main = row.get("SKU1", "").strip()
                if sku_main == "":
                    continue

                # كل المنافسين
                sku_list = [
                    ("سعر منتجك", "SKU1", "Price1"),
                    ("المنافس 1", "SKU2", "Price2"),
                    ("المنافس 2", "SKU3", "Price3"),
                    ("المنافس 3", "SKU4", "Price4"),
                    ("المنافس 4", "SKU5", "Price5"),
                    ("المنافس 5", "SKU6", "Price6"),
                ]

                # ========== HTML CARD ==========
                html = f"""
                <div style="border:1px solid #ccc; padding:20px; border-radius:12px;
                            margin-bottom:20px; background:#fff; direction:rtl;
                            font-family:'Tajawal', sans-serif;">
                    <h2>📦 <b>SKU الأساسي:</b> <span style="color:#007bff;">{sku_main}</span></h2>

                    <h3>🏷️ <b>الأسعار + آخر تغيير:</b></h3>

                    <ul style="font-size:18px; line-height:1.9; list-style:none; padding:0;">
                """

                # === عرض المنافسين ===
                for label, sku_col, price_col in sku_list:

                    sku_val = str(row.get(sku_col, "")).strip()
                    price_val = row.get(price_col, "")

                    # جلب آخر تغيير
                    change_data = get_last_change(df_hist, sku_val)

                    if change_data:
                        change_html = f"""
                        <div style='font-size:15px; margin-top:2px;'>
                            🔄 <b>آخر تغيير:</b> {change_data['old']} → {change_data['new']}
                            <br>📅 <b>الوقت:</b> {change_data['time']}
                        </div>
                        """
                    else:
                        change_html = "<div style='font-size:14px; color:#888;'>لا يوجد تغييرات مسجلة</div>"

                    html += f"""
                        <li>
                            <b>{label} ({sku_val}):</b> {price_val}
                            {change_html}
                        </li>
                    """

                html += "</ul></div>"

                components.html(html, height=520)

        # آخر تحديث
        last_update_placeholder.markdown(
            f"🕒 آخر تحديث: **{time.strftime('%Y-%m-%d %H:%M:%S')}**"
        )

    except Exception as e:
        st.error(f"❌ خطأ أثناء التحميل: {e}")

    time.sleep(refresh_rate)
