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
# تحسينات CSS — شكل جميل + مناسب للجوال
# -------------------------------------------------
st.markdown("""
<style>

/* للجوال */
@media (max-width:1024px){
    img{max-width:100% !important;height:auto !important;}
}

/* صندوق الإشعارات */
.notifications-wrapper{
    max-height:450px;
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
    padding:12px 14px;
    border-radius:10px;
    margin-bottom:10px;
    display:flex;
    gap:14px;
    direction:rtl;
    align-items:flex-start;
}

/* الصورة */
.notify-img img{
    width:90px;
    border-radius:8px;
    object-fit:cover;
}

/* المحتوى */
.notify-body{
    flex:1;
}
.notify-title{
    font-size:17px;
    font-weight:700;
    color:#007bff;
    margin-bottom:4px;
}
.notify-sku{
    font-size:14px;
    color:#555;
}
.notify-price{
    font-size:18px;
    font-weight:700;
    margin:6px 0;
}
.notify-time{
    font-size:13px;
    color:#888;
}

/* قسم سعري */
.my-price-box{
    padding:6px;
    background:#eef8ee;
    border-radius:8px;
    margin-top:4px;
    font-size:15px;
}

/* المنافسين */
.comp-box{
    padding:5px 0;
    font-size:14px;
    border-bottom:1px dashed #ccc;
}
.comp-box:last-child{
    border-bottom:0;
}

/* Badge النودج */
.nudge-badge{
    display:inline-block;
    padding:4px 8px;
    border-radius:6px;
    font-weight:700;
    font-size:12px;
    margin-top:4px;
}

/* للجوال */
@media (max-width:768px){
    .notify-img img{width:70px;}
    .notifications-wrapper{max-height:350px;}
    .notify-price{font-size:16px;}
}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------
# تنظيف SKU
# -------------------------------------------------
def clean_sku_text(x):
    if not x:
        return ""
    x=str(x).strip()
    x=re.sub(r"[\u200B-\u200F\u202A-\u202E\uFEFF]","",x)
    m=re.search(r"\(([A-Za-z0-9]+)\)",x)
    if m:
        return m.group(1)
    parts=re.findall(r"[A-Za-z0-9]{6,}",x)
    if parts:
        return max(parts,key=len)
    return x

# -------------------------------------------------
# SKU → لينك
# -------------------------------------------------
def sku_to_link_html(sku):
    s=clean_sku_text(sku)
    url=f"https://www.noon.com/saudi-en/{s}/p/"
    return f'<a href="{url}" target="_blank" style="text-decoration:none;color:#007bff;font-weight:600">{s}</a>'

# -------------------------------------------------
# Sheet
# -------------------------------------------------
def load_sheet():
    creds=Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    client=gspread.authorize(creds)
    ws=client.open_by_key("1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk").worksheet("noon")

    data=ws.get_all_values()
    df=pd.DataFrame(data[1:],columns=data[0])

    for c in ["SKU1","SKU2","SKU3","SKU4","SKU5","SKU6"]:
        df[c]=df[c].apply(clean_sku_text)

    return df

# -------------------------------------------------
# History
# -------------------------------------------------
def load_history():
    creds=Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    client=gspread.authorize(creds)

    try:
        ws=client.open_by_key("1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk").worksheet("history")
    except:
        return pd.DataFrame()

    data=ws.get_all_values()
    if len(data)<=1: return pd.DataFrame()

    df=pd.DataFrame(data[1:],columns=data[0])
    df["SKU_clean"]=df["SKU"].apply(clean_sku_text)
    df["SKU_lower"]=df["SKU_clean"].str.lower()
    df["DateTime"]=pd.to_datetime(df["DateTime"],errors="coerce")
    return df

# -------------------------------------------------
# Price to float
# -------------------------------------------------
def price_to_float(s):
    if s is None:return None
    s=str(s).strip().replace(",",".")
    s=re.sub(r"[^\d\.\-]","",s)
    try:return float(s)
    except:return None

# -------------------------------------------------
# آخر تغيير
# -------------------------------------------------
def get_last_change(hist,sku):
    if hist.empty:return None
    s=clean_sku_text(sku).lower()
    r=hist[hist["SKU_lower"]==s]
    if r.empty:return None
    r=r.sort_values("DateTime")
    last=r.iloc[-1]
    return {"old":last["Old Price"],"new":last["New Price"],"time":str(last["DateTime"])}

# -------------------------------------------------
# نودج
# -------------------------------------------------
def format_nudge_html(n):
    if not n:return ""
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
refresh=st.sidebar.slider("⏱ تحديث (ثواني)",5,180,15)
search=st.sidebar.text_input("🔍 بحث SKU")

placeholder=st.empty()

# -------------------------------------------------
# LOOP
# -------------------------------------------------
while True:
    try:
        df=load_sheet()
        hist=load_history()

        if search:
            df=df[df.apply(lambda r:r.astype(str).str.contains(search,case=False).any(),axis=1)]

        with placeholder.container():

            # ========================
            # 🔔 الإشعارات
            # ========================
            st.subheader("🔔 آخر تغييرات الأسعار")
            st.markdown("<div class='notifications-wrapper'>",unsafe_allow_html=True)

            if not hist.empty:
                recent=hist.sort_values("DateTime",ascending=False).head(10)

                for _,r in recent.iterrows():
                    sku=r["SKU"]
                    sku_clean=clean_sku_text(sku)

                    # البحث عن الصف المرتبط
                    match=df[df.apply(lambda row: sku_clean in
                        [clean_sku_text(row.get(c,"")) for c in ["SKU1","SKU2","SKU3","SKU4","SKU5","SKU6"]],axis=1)]

                    product=""
                    price_mine=""
                    image=""
                    nudge_html=""
                    competitors_html=""

                    if not match.empty:
                        row0=match.iloc[0]
                        product=row0.get("ProductName","")
                        price_mine=row0.get("Price1","")
                        image=row0.get("Image url","").strip()
                        nudge_html=format_nudge_html(find_nudge_for_sku(row0,sku))

                        # 🔥 منافسين كلهم بالصف
                        for i in range(2,7):
                            skuX=row0.get(f"SKU{i}","")
                            if not skuX:continue

                            priceX=row0.get(f"Price{i}","")
                            ch=get_last_change(hist,skuX)
                            nudgeX=format_nudge_html(row0.get(f"Nudge{i}",""))

                            line=f"<b>{sku_to_link_html(skuX)}</b> — 💰 {priceX}"

                            if ch:
                                o=str(ch["old"])
                                n1=str(ch["new"])
                                arrow="➡️"
                                if price_to_float(n1)>price_to_float(o):arrow="🔺"
                                if price_to_float(n1)<price_to_float(o):arrow="🔻"
                                line+=f" | 🔄 {o} → {n1} {arrow}"

                            competitors_html+=f"<div class='comp-box'>{line} {nudgeX}</div>"

                    old=str(r["Old Price"])
                    new=str(r["New Price"])
                    of=price_to_float(old)
                    nf=price_to_float(new)

                    arrow="➡️"
                    col="#6c757d"
                    if of is not None and nf is not None:
                        if nf>of:
                            arrow="🔺";col="#dc3545"
                        elif nf<of:
                            arrow="🔻";col="#28a745"

                    dir="→"
                    if of is not None and nf is not None and nf<of:
                        dir="←"

                    img_box=""
                    if image:
                        img_box=f"<div class='notify-img'><img src='{image}'></div>"

                    notify=f"""
                    <div class='notify-card'>
                        {img_box}
                        <div class='notify-body'>

                            <div class='notify-title'>
                                {html.escape(product) if product else sku_to_link_html(sku)}
                            </div>

                            <div class='notify-sku'>SKU: {sku_to_link_html(sku)}</div>

                            <div class='notify-price' style='color:{col};'>
                                {old} {dir} {new} {arrow}
                            </div>

                            {nudge_html}

                            <div class='my-price-box'>
                                💰 <b>سعري:</b> {price_mine}
                            </div>

                            <div style='margin-top:6px;'>
                                {competitors_html}
                            </div>

                            <div class='notify-time'>📅 {r["DateTime"]}</div>

                        </div>
                    </div>
                    """
                    st.markdown(notify,unsafe_allow_html=True)

            st.markdown("</div>",unsafe_allow_html=True)

            # ========================
            # المنتجات
            # ========================
            st.subheader("📦 أسعار المنتجات")

            for _,row in df.iterrows():
                sku=row.get("SKU1","")
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

                card+=f"<h2>🔵 {html.escape(name)} — {sku_to_link_html(sku)}</h2>"

                if image:
                    card+=f"<img src='{image}' style='max-width:180px;border-radius:8px;margin-bottom:10px;'>"

                card+=f"<div style='font-size:28px;font-weight:700;'>💰 سعر منتجك: {price}</div><hr>"

                # منافسين
                for i in range(2,7):
                    skuX=row.get(f"SKU{i}","")
                    if not skuX:continue

                    priceX=row.get(f"Price{i}","")
                    nudgeX=format_nudge_html(row.get(f"Nudge{i}",""))
                    ch=get_last_change(hist,skuX)

                    if ch:
                        old=str(ch["old"])
                        newc=str(ch["new"])
                        arrow="➡️"
                        if price_to_float(newc)>price_to_float(old):arrow="🔺"
                        if price_to_float(newc)<price_to_float(old):arrow="🔻"

                        histHtml=f"""
                        🔄 {old} → {newc} {arrow}
                        <br><span style='font-size:13px;color:#888;'>📅 {ch["time"]}</span>
                        """
                    else:
                        histHtml="<span style='color:#888;'>لا يوجد تاريخ تغييرات</span>"

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
                        {histHtml}
                    </div>
                    """

                card+="</div>"
                st.markdown(card,unsafe_allow_html=True)

        st.sidebar.write("🕒 آخر تحديث:",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        time.sleep(refresh)

    except Exception as e:
        st.error("❌ "+str(e))
        time.sleep(refresh)
