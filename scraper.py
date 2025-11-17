import time
import datetime
import re
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from gsheets_client import open_sheet_from_service_account

# Google Sheet details
SPREADSHEET_ID = "1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk"
SHEET_NAME = "noon"

# اسم الملف اللي GitHub Actions بيصنعه
SERVICE_ACCOUNT_JSON = "service-account.json"

# Columns
SKU_COLS   = [1, 2, 3, 4, 5, 6]
PRICE_COLS = [7, 8, 9, 10, 11, 12]
LAST_UPDATE_COL = 13

PAGE_WAIT_SECONDS = 2


def parse_old_price(cell_value):
    if not cell_value:
        return None
    s = str(cell_value)
    if "|" in s:
        first = s.split("|", 1)[0].strip()
    else:
        first = s.strip()
    try:
        return float(re.sub(r"[^\d.]", "", first))
    except:
        return None


def get_product_info(driver, sku):
    url = f"https://www.noon.com/saudi-en/{sku}/p/"
    try:
        driver.get(url)
        time.sleep(PAGE_WAIT_SECONDS)
    except:
        return None, "-"

    price = None
    try:
        elem = driver.find_element(By.CSS_SELECTOR,
            'span.PriceOfferV2-module-scss-module__dHtRPW__priceNowText')
        price = float(re.sub(r"[^\d.]", "", elem.text))
    except:
        price = None

    nudges = "-"
    try:
        elems = driver.find_elements(
            By.CSS_SELECTOR,
            'div.Nudges-module-scss-module__dNOKTG__nudgeText'
        )
        items = [e.text.strip() for e in elems if e.text.strip()]
        if items:
            nudges = " | ".join(items)
    except:
        pass

    return price, nudges


def build_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def main():
    print("Starting Noon scraper…")

    ws = open_sheet_from_service_account(
        SERVICE_ACCOUNT_JSON, SPREADSHEET_ID, SHEET_NAME
    )

    all_rows = ws.get_all_values()
    if len(all_rows) < 1:
        print("Sheet empty.")
        return

    driver = build_driver()

    for r in range(2, len(all_rows) + 1):

        row_values = ws.row_values(r)
        while len(row_values) < LAST_UPDATE_COL:
            row_values.append("")

        for i in range(6):

            sku_col = SKU_COLS[i]
            price_col = PRICE_COLS[i]

            sku = row_values[sku_col - 1].strip() if len(row_values) >= sku_col else ""
            if not sku:
                continue

            price, nudges = get_product_info(driver, sku)

            old_cell = row_values[price_col - 1] if len(row_values) >= price_col else ""
            old_price = parse_old_price(old_cell)

            change = "-"

            if price is not None:
                if old_price not in [None, 0] and price != old_price:
                    diff = price - old_price
                    diff_str = str(int(diff)) if diff.is_integer() else f"{diff:.2f}"

                    if diff > 0:
                        change = f"↑ (+{diff_str})"
                    else:
                        change = f"↓ ({diff_str})"

                final = f"{price} | {change} | {nudges}"
                ws.update_cell(r, price_col, final)

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws.update_cell(r, LAST_UPDATE_COL, now)

    driver.quit()
    print("Done.")


if __name__ == "__main__":
    main()
