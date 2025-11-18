import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re


# ========================================================
# CLEAN SKU
# ========================================================
def clean_sku_text(txt):
    if not txt:
        return ""
    return re.sub(r"[^A-Za-z0-9\-]", "", txt).strip()


# ========================================================
# LOAD GOOGLE SHEET
# ========================================================
def load_sheet(spreadsheet_id, sheet_name, creds):
    client = gspread.authorize(creds)
    sh = client.open_by_key(spreadsheet_id)

    # MAIN SHEET
    ws = sh.worksheet(sheet_name)
    df = pd.DataFrame(ws.get_all_records())

    # HISTORY SHEET
    try:
        ws_hist = sh.worksheet("history")
        df_hist = pd.DataFrame(ws_hist.get_all_records())
    except:
        df_hist = pd.DataFrame(columns=["SKU", "Old Price", "New Price", "Change", "DateTime"])

    # normalize SKU in history
    if "SKU" in df_hist.columns:
        df_hist["SKU_clean"] = df_hist["SKU"].astype(str).apply(clean_sku_text)
        df_hist["SKU_lower"] = df_hist["SKU_clean"].str.lower()
    else:
        df_hist["SKU_lower"] = ""

    return df, df_hist


# ========================================================
# GET LAST PRICE CHANGE
# ========================================================
def get_last_change(df_hist, sku):
    try:
        sku_clean = clean_sku_text(sku).lower()
        rows = df_hist[df_hist["SKU_lower"] == sku_clean]

        if rows.empty:
            return None

        row = rows.iloc[-1]

        return {
            "old": row["Old Price"],
            "new": row["New Price"],
            "time": row["DateTime"]
        }
    except:
        return None


# ========================================================
# STREAMLIT UI
# ========================================================
st.set_page_config(page_title="Noon Monitor", layout="wide")
st.title("🟡 Noon Price Monitor — Stream View")


# SIDEBAR
st.sidebar.title("Settings")

spreadsheet_id = st.sidebar.text_input("Spreadsheet ID",
                                       "1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk")
sheet_name = st.sidebar.text_input("Sheet Name", "noon")

json_file = st.sidebar.file_uploader("Upload service JSON", type=["json"])

if not json_file:
    st.warning("ارفع ملف JSON للاستمرار")
    st.stop()

creds = Credentials.from_service_account_info(
    json_file.getvalue(),
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)


# LOAD DATA
df, df_hist = load_sheet(spreadsheet_id, sheet_name, creds)

if df.empty:
    st.error("❌ No data found in sheet.")
    st.stop()


# ========================================================
# DEFINE COLUMNS
# ========================================================
sku_cols = ["SKU1", "SKU2", "SKU3", "SKU4", "SKU5", "SKU6"]
price_cols = ["Price1", "Price2", "Price3", "Price4", "Price5", "Price6"]
nudge_cols = ["Nudge1", "Nudge2", "Nudge3", "Nudge4", "Nudge5", "Nudge6"]


# ========================================================
# DISPLAY BLOCKS
# ========================================================
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
        raw_nudge = row.get(nudge_col, "-")

        # NUDGE FIX
        if raw_nudge and raw_nudge != "-":
            nudge_clean = " | ".join(
                [x.strip() for x in str(raw_nudge).split("|") if x.strip()]
            )
        else:
            nudge_clean = "-"

        # HISTORY
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

        # UI BLOCK (unchanged design)
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
