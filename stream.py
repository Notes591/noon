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
from datetime import datetime
import html

# -------------------------------------------------
# إعداد الصفحة
# -------------------------------------------------
st.set_page_config(page_title="Noon Prices – Dashboard", layout="wide")
st.title("📊 Noon Prices – Live Monitoring Dashboard")

# -------------------------------------------------
# تحسينات CSS — شكل حلو + مناسب للجوال
# -------------------------------------------------
st.markdown("""
<style>

/* للجوال */
@media (max-width:1024px){
    img{max-width:100% !important;height:auto !important;}
}

/* صندوق الإشعارات */
.notifications-wrapper{
    max-height:420px;
    overflow-y:auto;
    padding:8px;
    background:#f5f6f8;
    border:1px solid #ddd;
    border-radius:10px;
}

/* كارت الإشعار */
.notify-card{
    background:white;
    border:1px solid #ccc;
    padding:10px 12px;
    border-radius:10px;
    margin-bottom:10px;
    display:flex;
    gap:12px;
    direction:rtl;
    align-items:flex-start;
}

/* صورة */
.notify-img img{
    width:84px;
    border-radius:8px;
    object-fit:cover;
}

/* النص */
.notify-body{
    flex:1;
}
.notify-title{
    font-size:15px;
    font-weight:700;
    color:#007bff;
    margin-bottom:4px;
}
.notify-sku{
    font-size:13px;
    color:#555;
}
.notify-price{
    font-size:17px;
    font-weight:700;
    margin:6px 0;
}
.notify-time{
    font-size:13px;
    color:#888;
}

/* badge النودج */
.nudge-badge{
    display:inline-block;
    padding:4px 8px;
    border-radius:6px;
    font-weight:700;
    font-size:12px;
    margin-bottom:6px;
}

/* ارتفاع أقل للجوال */
@media (max-width:768px){
    .notifications-wrapper{
        max-height:340px;
    }
    .notify-card{
        padding:8px;
        gap:8px;
    }
    .notify-title{
        font-size:14px;
    }
    .notify-price{
        font-size:15px;
    }
}
</style>
""", unsafe_allow_html=True)

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
# تحويل SKU للينك
# -------------------------------------------------
def sku_to_link_html(sku):
    s = clean_sku_text(sku)
    url = f"https://www.noon.com/saudi-en/{s}/p/"
    return f'<a href="{url}" target="_blank" style="text-decoration:none;color:#007bff;font-weight:600">{s}</a>'

# -------------------------------------------------
# جلب sheet
# -------------------------------------------------
def load_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    client = gspread.authorize(creds)
    SID="1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk"
    ws=client.open_by_key(SID).worksheet("noon")

    data = ws.get_all_values()
    df = pd.DataFrame(data[1:],columns=data[0])

    for c in ["SKU1","SKU2","SKU3","SKU4","SKU5","SKU6"]:
        df[c]=df[c].apply(clean_sku_text)

    return df

# -------------------------------------------------
# history
# -------------------------------------------------
def load_history():
    creds = Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    client = gspread.authorize(creds)
    SID="1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk"

    try:
        ws=client.open_by_key(SID).worksheet("history")
    except:
        return pd.DataFrame()

    data=ws.get_all_values()
    if len(data)<=1:
        return pd.DataFrame()

    df=pd.DataFrame(data[1:],columns=data[0])
    df["SKU_clean"]=df["SKU"].apply(clean_sku_text)
    df["SKU_lower"]=df["SKU_clean"].str.lower()
    df["DateTime"]=pd.to_datetime(df["DateTime"],errors="coerce")
    return df

# -------------------------------------------------
# تحويل سعر
# -------------------------------------------------
def price_to_float(s):
    if s is None: return None
    s=str(s).strip().replace(",",".")
    s=re.sub(r"[^\d\.\-]","",s)
    try: return float(s)
    except: return None

# -------------------------------------------------
# آخر تغيير
# -------------------------------------------------
def get_last_change(hist,sku):
    if hist.empty: return None
    s=clean_sku_text(sku).lower()
    r=hist[hist["SKU_lower"]==s]
    if r.empty: return None
    r=r.sort_values("DateTime")
    last=r.iloc[-1]
    return {"old":last["Old Price"],"new":last["New Price"],"time":str(last["DateTime"])}

# -------------------------------------------------
# نودج
# -------------------------------------------------
def format_nudge_html(n):
    if not n: return ""
    n=str(n).strip()
    if n.lower().startswith("sold"):
        return f'<span class="nudge-badge" style="background:#ffcc80;">🔥 {html.escape(n)}</span>'
    return f'<span class="nudge-badge" style="background:#fff3cd;">🟨 {html.escape(n)}</span>'

# -------------------------------------------------
# نودج حسب SKU
# -------------------------------------------------
def find_nudge_for_sku(row,sku):
    s=clean_sku_text(sku)
    for i in range(1,7):
        if clean_sku_text(row.get(f"SKU{i}",""))==s:
            return row.get(f"Nudge{i}","")
    return ""

# -------------------------------------------------
# Sidebar
# -------------------------------------------------
refresh = st.sidebar.slider("⏱ تحديث (ثواني)",5,180,15)
search = st.sidebar.text_input("🔍 بحث SKU")

placeholder=st.empty()

# -------------------------------------------------
# LOOP
# -------------------------------------------------
while True:
    try:
        df = load_sheet()
        hist=load_history()

        if search:
            df=df[df.apply(lambda r: r.astype(str).str.contains(search,case=False).any(),axis=1)]

        with placeholder.container():

            # ========================
            # الإشعارات
            # ========================
            st.subheader("🔔 آخر تغييرات الأسعار")
            st.markdown("<div class='notifications-wrapper'>",unsafe_allow_html=True)

            if not hist.empty:
                recent = hist.sort_values("DateTime",ascending=False).head(10)
                for _,r in recent.iterrows():

                    sku=r["SKU"]
                    product=""
                    price_mine=""
                    nudge_html=""
                    image=""

                    match=df[df.apply(lambda row: clean_sku_text(sku) in
                        [clean_sku_text(row.get(c,"")) for c in ["SKU1","SKU2","SKU3","SKU4","SKU5","SKU6"]],axis=1)]
                    if not match.empty:
                        row0=match.iloc[0]
                        product=row0.get("ProductName","")
                        price_mine=row0.get("Price1","")
                        image=row0.get("Image url","").strip()
                        nudge_html=format_nudge_html(find_nudge_for_sku(row0,sku))

                    old=str(r["Old Price"])
                    new=str(r["New Price"])
                    of=price_to_float(old)
                    nf=price_to_float(new)

                    arrow="➡️"
                    if of is not None and nf is not None:
                        if nf>of: arrow="🔺"
                        elif nf<of: arrow="🔻"

                    dir="→"
                    if of is not None and nf is not None and nf<of:
                        dir="←"

                    img_box=""
                    if image:
                        img_box=f"""
                        <div class='notify-img'><img src="{image}"></div>
                        """

                    html_notify=f"""
                    <div class='notify-card'>
                        {img_box}
                        <div class='notify-body'>
                            <div class='notify-title'>{html.escape(product) if product else sku_to_link_html(sku)}</div>
                            <div class='notify-sku'>SKU: {sku_to_link_html(sku)}</div>
                            <div class='notify-price'>{old} {dir} {new} {arrow}</div>
                            {nudge_html}
                            <div class='notify-time'>📅 {r["DateTime"]}</div>
                        </div>
                    </div>
                    """
                    st.markdown(html_notify,unsafe_allow_html=True)

            st.markdown("</div>",unsafe_allow_html=True)

            # ========================
            # المنتجات
            # ========================
            st.subheader("📦 أسعار المنتجات")

            for _,row in df.iterrows():
                sku=row["SKU1"]
                if not sku: continue

                name=row.get("ProductName","")
                image=row.get("Image url","").strip()
                price=row.get("Price1","")

                card=f"""
                <div style='
                    border:1px solid #ddd;
                    border-radius:12px;
                    padding:20px;
                    margin-bottom:20px;
                    background:white;
                    direction:rtl;
                '>
                """

                if name:
                    card+=f"<h2>🔵 {html.escape(name)} — {sku_to_link_html(sku)}</h2>"
                else:
                    card+=f"<h2>{sku_to_link_html(sku)}</h2>"

                if image:
                    card+=f"<img src='{image}' style='max-width:180px;border-radius:8px;margin-bottom:10px;'>"

                card+=f"<div style='font-size:28px;font-weight:700;'>💰 سعر منتجك: {price}</div><hr>"

                # منافسين
                for i in range(2,7):
                    skuX=row.get(f"SKU{i}","")
                    if not skuX: continue

                    priceX=row.get(f"Price{i}","")
                    nudgeX=format_nudge_html(row.get(f"Nudge{i}",""))
                    ch=get_last_change(hist,skuX)

                    if ch:
                        oldc=str(ch["old"])
                        newc=str(ch["new"])
                        arrow="➡️"
                        if price_to_float(newc)>price_to_float(oldc): arrow="🔺"
                        if price_to_float(newc)<price_to_float(oldc): arrow="🔻"

                        cmp_html=f"""
                        🔄 {oldc} → {newc} {arrow}
                        <br><span style='font-size:13px;color:#888;'>📅 {ch["time"]}</span>
                        """
                    else:
                        cmp_html="<span style='color:#888;'>لا يوجد تاريخ تغييرات</span>"

                    card+=f"""
                    <div style='
                        background:#fafafa;
                        padding:12px;
                        margin-bottom:10px;
                        border-radius:10px;
                    '>
                        <b>منافس:</b> {sku_to_link_html(skuX)}<br>
                        💰 السعر: {priceX}<br>
                        {nudgeX}<br>
                        {cmp_html}
                    </div>
                    """

                card+="</div>"
                st.markdown(card,unsafe_allow_html=True)

        st.sidebar.write("🕒 آخر تحديث:",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        time.sleep(refresh)

    except Exception as e:
        st.error("❌ "+str(e))
        time.sleep(refresh)
