import streamlit as st
import pandas as pd
import time
import gspread
from google.oauth2.service_account import Credentials

# إعداد صفحة Streamlit
st.set_page_config(
    page_title="Noon Prices Dashboard",
    layout="wide",
)

st.title("📊 Noon Prices – Live Monitoring Dashboard")

# تحميل Google Sheet
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


# Sidebar إعدادات
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

# Placeholder
placeholder = st.empty()
last_update_placeholder = st.sidebar.empty()


# تلوين السعر بناءً على الزيادة والنقصان
def highlight_changes(val):
    val = str(val)
    if "↑" in val:
        return "background-color: #d1ffd1;"
    if "↓" in val:
        return "background-color: #ffd1d1;"
    return ""


# التحديث التلقائي
while True:
    try:
        df = load_sheet()

        # بحث
        if search_text:
            df = df[df.apply(lambda row: row.astype(str).str.contains(search_text, case=False).any(), axis=1)]

        # عرض المتغير فقط
        if show_only_changed:
            df = df[df.astype(str).apply(lambda row: "↑" in "".join(row) or "↓" in "".join(row), axis=1)]

        # تلوين
        styled_df = df.style.applymap(highlight_changes)

        # --------------------------
        # 🎴 عرض المنتجات بطريقة كروت Cards
        # --------------------------
        with placeholder.container():

            st.subheader("🟦 عرض المنتجات بطريقة الكروت – Cards View")

            for idx, row in df.iterrows():
                st.markdown(f"""
                <div style="
                    border:1px solid #ccc;
                    padding:20px;
                    border-radius:12px;
                    margin-bottom:15px;
                    background:#fdfdfd;
                    box-shadow:0 2px 6px rgba(0,0,0,0.05);
                ">
                    <h2 style="margin-bottom:5px;">📦 SKU:
                        <span style="color:#007bff;">{row.get('SKU', '')}</span>
                    </h2>

                    <p style="font-size:18px;"><b>اسم المنتج:</b> {row.get('Title', '')}</p>

                    <p style="font-size:18px; margin:4px 0;"><b>💰 السعر الحالي:</b> 
                        <span style="color:#28a745; font-weight:bold;">{row.get('Current Price', '')}</span>
                    </p>

                    <p style="font-size:18px; margin:4px 0;"><b>💵 السعر السابق:</b> {row.get('Old Price', '')}</p>

                    <p style="font-size:18px; margin:4px 0;"><b>📉 الزيادة/النقصان:</b> 
                        <span style="color:#d00;">{row.get('Change', '')}</span>
                    </p>

                    <p><b>📅 آخر تحديث:</b> {row.get('Last Update', '')}</p>
                </div>
                """, unsafe_allow_html=True)

            # --------------------------
            # 📋 عرض الجدول الأصلي
            # --------------------------
            st.subheader("📋 الجدول الأصلي")
            st.dataframe(styled_df, use_container_width=True)

        # تحديث الوقت
        last_update_placeholder.markdown(
            f"🕒 آخر تحديث: **{time.strftime('%Y-%m-%d %H:%M:%S')}**"
        )

    except Exception as e:
        st.error(f"❌ خطأ أثناء تحميل الشيت: {e}")

    time.sleep(refresh_rate)
