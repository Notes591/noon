import streamlit as st
import pandas as pd
import time
import gspread
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components

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

    ws = client.open_by_key(SPREADSHEET_ID).worksheet("noon")
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])

    ws2 = client.open_by_key(SPREADSHEET_ID).worksheet("history")
    hdata = ws2.get_all_values()
    df_hist = pd.DataFrame(hdata[1:], columns=hdata[0])

    return df, df_hist


# Sidebar
st.sidebar.header("⚙️ الإعدادات")

refresh_rate = st.sidebar.slider(
    "⏱ معدل التحديث (ثواني)",
    5, 300, 30
)

search_text = st.sidebar.text_input("🔍 البحث عن SKU")

st.sidebar.markdown("---")
placeholder = st.empty()
last_update_placeholder = st.sidebar.empty()


# استخراج آخر تغيير للـ SKU من history
def get_last_change(df_hist, sku):
    if sku is None or sku.strip() == "":
        return None
    dfx = df_hist[df_hist["SKU"] == sku]
    if len(dfx) == 0:
        return None
    last = dfx.iloc[-1]
    return {
        "old": last["Old Price"],
        "new": last["New Price"],
        "change": last["Change"],
        "time": last["DateTime"]
    }


# تلوين تغييرات السعر في الجدول
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
        df, df_hist = load_sheet()

        if search_text:
            df = df[df.apply(lambda row: row.astype(str).str.contains(search_text, case=False).any(), axis=1)]

        styled_df = df.style.applymap(highlight_changes)

        with placeholder.container():

            st.subheader("🟦 عرض المنتجات بطريقة الكروت – Cards View")

            for idx, row in df.iterrows():

                sku_main = row.get("SKU1", "").strip()
                if sku_main == "":
                    continue

                # الأسعار
                price1 = row.get("Price1", "")
                price2 = row.get("Price2", "")
                price3 = row.get("Price3", "")
                price4 = row.get("Price4", "")
                price5 = row.get("Price5", "")
                price6 = row.get("Price6", "")

                # قائمة المنافسين
                comp_list = [
                    ("🟨 المنافس 1", "SKU2", "Price2"),
                    ("🟧 المنافس 2", "SKU3", "Price3"),
                    ("🟥 المنافس 3", "SKU4", "Price4"),
                    ("🟩 المنافس 4", "SKU5", "Price5"),
                    ("🟪 المنافس 5", "SKU6", "Price6"),
                ]

                # بناء الكارت HTML
                html = f"""
                <div style="
                    border:1px solid #cccccc;
                    padding:15px;
                    border-radius:10px;
                    margin-bottom:15px;
                    background:#ffffff;
                    direction:rtl;
                    font-family:'Tajawal', sans-serif;
                    line-height:1.4;
                    font-size:16px;
                ">
                    <h2 style="margin:0 0 5px; font-size:22px;">
                        📦 <b>الـSKU الأساسي:</b>
                        <span style="color:#007bff;">{sku_main}</span>
                    </h2>

                    <div style="height:1px; background:#ddd; margin:6px 0;"></div>

                    <h3 style="margin:5px 0; font-size:18px;">🏷️ <b>الأسعار + آخر تغيير:</b></h3>

                    <ul style="font-size:16px; line-height:1.5; list-style:none; padding:0; margin:0;">
                        <li style="margin:3px 0;">
                            🟦 <b>سعر منتجك:</b> {price1}
                """

                # إضافة آخر تغيير للمنتج الأساسي
                ch = get_last_change(df_hist, sku_main)
                if ch:
                    html += f"""
                    <div style='font-size:14px; margin-top:2px; color:#444;'>
                        🔄 آخر تغيير: {ch['old']} → {ch['new']}  ({ch['change']})
                        <br>📅 {ch['time']}
                    </div>
                    """
                else:
                    html += "<div style='font-size:13px; color:#999;'>لا يوجد تغييرات مسجلة</div>"

                html += "</li>"

                # المنافسين
                for label, sku_col, price_col in comp_list:
                    sku_val = row.get(sku_col, "").strip()
                    price_val = row.get(price_col, "")

                    html += f"""
                    <li style="margin:5px 0;">
                        {label} ({sku_val}): {price_val}
                    """

                    ch = get_last_change(df_hist, sku_val)
                    if ch:
                        html += f"""
                        <div style='font-size:14px; margin-top:2px; color:#444;'>
                            🔄 آخر تغيير: {ch['old']} → {ch['new']}  ({ch['change']})
                            <br>📅 {ch['time']}
                        </div>
                        """
                    else:
                        html += "<div style='font-size:13px; color:#999;'>لا يوجد تغييرات مسجلة</div>"

                    html += "</li>"

                html += f"""
                    </ul>

                    <p style="margin-top:8px; font-size:14px;">
                        📅 <b>آخر تحديث:</b> {row.get('Last Update','')}
                    </p>
                </div>
                """

                components.html(html)

            # الجدول الأصلي
            st.subheader("📋 الجدول الأصلي")
            st.dataframe(styled_df, use_container_width=True)

        last_update_placeholder.markdown(
            f"🕒 آخر تحديث: **{time.strftime('%Y-%m-%d %H:%M:%S')}**"
        )

    except Exception as e:
        st.error(f"❌ خطأ أثناء تحميل الشيت: {e}")

    time.sleep(refresh_rate)
