import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re


# ==========================================
#        CLEAN SKU
# ==========================================
def clean_sku_text(txt):
    if not txt:
        return ""
    return re.sub(r"[^A-Za-z0-9\-]", "", txt)


# ==========================================
#     LOAD GOOGLE SHEET
# ==========================================
def load_sheet(spreadsheet_id, sheet_name, creds):
    client = gspread.authorize(creds)
    sh = client.open_by_key(spreadsheet_id)

    ws = sh.worksheet(sheet_name)
    df = pd.DataFrame(ws.get_all_records())

    try:
        ws_hist = sh.worksheet("history")
        df_hist = pd.DataFrame(ws_hist.get_all_records())
    except:
        df_hist = pd.DataFrame(columns=["SKU", "Old Price", "New Price", "Change", "DateTime"])

    return df, df_hist


# ==========================================
#     LAST PRICE CHANGE
# ==========================================
def get_last_change(df_hist, sku):
    try:
        df = df_hist[df_hist["SKU"] == sku]
        if df.empty:
            return None
        row = df.iloc[-1]
        return {
            "old": row["Old Price"],
            "new": row["New Price"],
            "time": row["DateTime"]
        }
    except:
        return None


# ==========================================
#              STREAMLIT UI
# ==========================================
st.set_page_config(page_title="Noon Monitor", layout="wide")
st.title("🟡 Noon Price Monitor — Stream View")


# ==========================================
#   USER CONFIG
# ==========================================
st.sidebar.title("Settings")

spreadsheet_id = st.sidebar.text_input("Spreadsheet ID", "1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk")
sheet_name = st.sidebar.text_input("Sheet Name", "noon")

json_file = st.sidebar.file_uploader("Upload service JSON", type=["json"])

if not json_file:
    st.warning("ارفع ملف JSON للاستمرار")
    st.stop()

creds = Credentials.from_service_account_info(
    json_file.getvalue(),
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)


# ==========================================
#         LOAD DATA
# ==========================================
df, df_hist = load_sheet(spreadsheet_id, sheet_name, creds)

if df.empty:
    st.error("No data found in sheet.")
    st.stop()


# ==========================================
#        SHOW PRODUCTS
# ==========================================
sku_cols = ["SKU1", "SKU2", "SKU3", "SKU4", "SKU5", "SKU6"]
price_cols = ["Price1", "Price2", "Price3", "Price4", "Price5", "Price6"]
nudge_cols = ["Nudge1", "Nudge2", "Nudge3", "Nudge4", "Nudge5", "Nudge6"]

for idx, row in df.iterrows():

    st.markdown(f"### 🔷 **Product Row {idx+1}**")
    st.write("---")

    for label, sku_col, price_col, nudge_col in zip(
        ["A", "B", "C", "D", "E", "F"],
        sku_cols, price_cols, nudge_cols
    ):

        sku_val = clean_sku_text(row.get(sku_col, ""))
        if not sku_val:
            continue

        price_val = row.get(price_col, "")
        nudge_val = row.get(nudge_col, "-")

        # ================================
        #  تنظيم النودجز + sold recently
        # ================================
        if nudge_val and nudge_val != "-":

            parts = [x.strip() for x in nudge_val.split("|") if x.strip()]

            nudge_html = "<br>".join([f"🔸 {x}" for x in parts])

        else:
            nudge_html = "<span style='color:#777;'>— لا يوجد —</span>"

        # آخر تغيير
        change_data = get_last_change(df_hist, sku_val)
        if change_data:
            change_html = f"""
            <div style="font-size:14px; margin-top:5px; color:#333;">
                🔄 <b>التحرك الأخير:</b> {change_data['old']} → {change_data['new']}<br>
                ⏱️ {change_data['time']}
            </div>
            """
        else:
            change_html = "<div style='color:#777;'>لا يوجد تغييرات</div>"

        # ================================
        #     DISPLAY BLOCK
        # ================================
        st.markdown(f"""
        <div style="padding:12px; margin-bottom:12px; border-radius:10px; background:#f8f9fa;">
        
            <b style="font-size:18px;">🟦 المنافس {label} — {sku_val}</b><br><br>

            <b>💰 السعر:</b>
            <span style="font-size:18px; font-weight:bold; color:#2c3e50;">
                {price_val}
            </span>

            <br><br>

            <b>📌 النودجز:</b><br>
            <div style="margin-right:10px; font-size:15px;">
                {nudge_html}
            </div>

            {change_html}

        </div>
        """, unsafe_allow_html=True)

    st.write("------")
