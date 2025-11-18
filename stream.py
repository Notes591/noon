import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re

# -------------------------
# Clean SKU
# -------------------------
def clean_sku_text(txt):
    if not txt:
        return ""
    return re.sub(r"[^A-Za-z0-9\-]", "", txt)

# -------------------------
# Load Google Sheet
# -------------------------
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

# -------------------------
# Last Price Change
# -------------------------
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

# -------------------------
# Streamlit UI
# -------------------------
st.set_page_config(page_title="Noon Monitor", layout="wide")
st.title("🟡 Noon Price Monitor — Stream View")

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

# -------------------------
# Load Data
# -------------------------
df, df_hist = load_sheet(spreadsheet_id, sheet_name, creds)

if df.empty:
    st.error("No data found in sheet.")
    st.stop()

# -------------------------
# Columns
# -------------------------
sku_cols = ["SKU1", "SKU2", "SKU3", "SKU4", "SKU5", "SKU6"]
price_cols = ["Price1", "Price2", "Price3", "Price4", "Price5", "Price6"]
nudge_cols = ["Nudge1", "Nudge2", "Nudge3", "Nudge4", "Nudge5", "Nudge6"]

# -------------------------
# Show Each Product Row
# -------------------------
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
        nudge_val_raw = row.get(nudge_col, "-")

        # -------------------------
        # Fix Nudge Format (same UI as your original)
        # -------------------------
        if nudge_val_raw and nudge_val_raw != "-":
            nudge_clean = " | ".join(
                [x.strip() for x in str(nudge_val_raw).split("|") if x.strip()]
            )
        else:
            nudge_clean = "-"

        # -------------------------
        # Last Change
        # -------------------------
        change_data = get_last_change(df_hist, sku_val)
        if change_data:
            change_html = f"""
            <div style="font-size:13px; color:#777;">
                🔄 آخر تغيير: {change_data['old']} → {change_data['new']}<br>
                ⏱ {change_data['time']}
            </div>
            """
        else:
            change_html = "<div style='color:#777;'>لا يوجد تغييرات مسجلة</div>"

        # -------------------------
        # Final Block (Same UI)
        # -------------------------
        st.markdown(f"""
        <li>
            <b>{label} ({sku_val}):</b>
            <span style="color:#2c3e50; font-weight:bold;">{price_val}</span>
            <br>
            <span style="color:#555;">{nudge_clean}</span>
            {change_html}
        </li>
        """, unsafe_allow_html=True)

    st.write("------")
