import streamlit as st
import pandas as pd
import time
import gspread
from google.oauth2.service_account import Credentials

# -----------------------------
# إعداد صفحة Streamlit
# -----------------------------
st.set_page_config(
    page_title="Noon Prices Dashboard",
    layout="wide",
)

st.title("📊 Noon Prices – Live Monitoring Dashboard")


# -----------------------------
# تحميل Google Sheet
# -----------------------------
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


# -----------------------------
# أدوات Sidebar
# -----------------------------
st.sidebar.header("⚙️ الإعدادات")

refresh_rate = st.sidebar.slider(
    "⏱ معدل التحديث (ثواني)",
    5, 300, 30
)

search_text = st.sidebar.text_input(
    "🔍 البحث عن SKU"
)

show_only_changed = st.sidebar.checkbox(
    "عرض الأسعار التي تغيّرت فقط",
    value=False
)

st.sidebar.markdown("---")
st.sidebar.write("Developed for Noon Monitoring 🚀")


# -----------------------------
# Placeholder للبيانات
# -----------------------------
placeholder = st.empty()

last_update_placeholder = st.sidebar.empty()


# -----------------------------
# حلقة تحديث تلقائي
# -----------------------------
while True:
    try:
        df = load_sheet()

        # -----------------------------
        # تنظيف البيانات
        # -----------------------------
        if search_text:
            df = df[df.apply(lambda row: row.astype(str).str.contains(search_text, case=False).any(), axis=1)]

        if show_only_changed:
            df = df[df.astype(str).apply(lambda row: "↑" in "".join(row) or "↓" in "".join(row), axis=1)]

        # -----------------------------
        # تلوين الأسعار
        # -----------------------------
        def highlight_changes(val):
            val = str(val)
            if "↑" in val:
                return "background-color: #d1ffd1;"  # أخضر بسيط
            if "↓" in val:
                return "background-color: #ffd1d1;"  # أحمر بسيط
            return ""

        styled_df = df.style.applymap(highlight_changes)

        # -----------------------------
        # عرض البيانات
        # -----------------------------
        placeholder.dataframe(styled_df, use_container_width=True)

        # تحديث الوقت
        last_update_placeholder.markdown(
            f"🕒 آخر تحديث: **{time.strftime('%Y-%m-%d %H:%M:%S')}**"
        )

    except Exception as e:
        st.error(f"❌ خطأ أثناء تحميل الشيت: {e}")

    time.sleep(refresh_rate)
