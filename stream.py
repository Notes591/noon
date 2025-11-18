with placeholder.container():

    st.subheader("🟦 عرض المنتجات بطريقة الكروت – Cards View")

    for idx, row in df.iterrows():

        sku_main = row.get("SKU1", "").strip()
        if sku_main == "":
            continue

        comp_list = [
            ("🟨 المنافس 1", "SKU2", "Price2"),
            ("🟧 المنافس 2", "SKU3", "Price3"),
            ("🟥 المنافس 3", "SKU4", "Price4"),
            ("🟩 المنافس 4", "SKU5", "Price5"),
            ("🟪 المنافس 5", "SKU6", "Price6"),
        ]

        html = f"""
        <div style="
            border:1px solid #ccc;
            padding:15px;
            border-radius:10px;
            margin-bottom:15px;
            background:#fff;
            direction:rtl;
            font-family:'Tajawal', sans-serif;
        ">
            <h2 style="margin:0 0 8px; font-size:22px;">
                📦 <b>الـSKU الأساسي:</b>
                <span style="color:#007bff;">{sku_main}</span>
            </h2>

            <div style="height:1px; background:#ddd; margin:8px 0;"></div>

            <h3 style="margin:5px 0; font-size:18px;">🏷️ الأسعار + آخر تغيير:</h3>

            <ul style="list-style:none; padding:0; margin:0;">
        """

        # 🟦 منتجك الأساسي
        price_main = row.get("Price1", "")
        ch = get_last_change(df_hist, sku_main)

        html += f"""
            <li style="margin:4px 0;">
                🟦 <b>سعر منتجك:</b> {price_main}
        """

        if ch:
            html += f"""
                <div style='font-size:14px; color:#555; margin-top:2px;'>
                    🔄 آخر تغيير: {ch['old']} → {ch['new']} ({ch['change']})
                    <br>📅 {ch['time']}
                </div>
            """
        else:
            html += "<div style='font-size:13px; color:#999;'>لا يوجد تغييرات مسجلة</div>"

        html += "</li>"

        # 🟨🟧🟥🟩🟪 المنافسين
        for label, sku_col, price_col in comp_list:

            sku_val = row.get(sku_col, "").strip()
            price_val = row.get(price_col, "")

            html += f"""
                <li style="margin:4px 0;">
                    {label} ({sku_val}): {price_val}
            """

            ch = get_last_change(df_hist, sku_val)
            if ch:
                html += f"""
                    <div style='font-size:14px; color:#555; margin-top:2px;'>
                        🔄 آخر تغيير: {ch['old']} → {ch['new']} ({ch['change']})
                        <br>📅 {ch['time']}
                    </div>
                """
            else:
                html += "<div style='font-size:13px; color:#999;'>لا يوجد تغييرات مسجلة</div>"

            html += "</li>"

        html += f"""
            </ul>

            <p style="margin-top:10px; font-size:14px;">
                📅 <b>آخر تحديث:</b> {row.get('Last Update','')}
            </p>
        </div>
        """

        components.html(html)
