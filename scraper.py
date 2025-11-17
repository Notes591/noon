# scraper.py
import time
import datetime
import re
import os
import traceback

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from gsheets_client import open_sheet_from_service_account

# ---------- CONFIG ----------
# Use the spreadsheet id (from the URL you shared)
SPREADSHEET_ID = "1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk"
SHEET_NAME = "noon"

# Local service account JSON filename (you uploaded this file)
SERVICE_ACCOUNT_JSON = "notesapp-471512-2e10b35736e3.json"

# Fixed column layout (1-based columns)
SKU_COLS   = [1, 2, 3, 4, 5, 6]
PRICE_COLS = [7, 8, 9, 10, 11, 12]
LAST_UPDATE_COL = 13

# Timeouts and waits
PAGE_WAIT_SECONDS = 2         # wait after opening product page
LOOP_SLEEP_SECONDS = 5        # wait in case of exceptions to avoid tight loop
# ----------------------------

def parse_old_price(cell_value):
    """
    Extract old price from a cell that might be like:
    "120 | ↑ (+20) | Selling out fast"
    Returns float price or None
    """
    if not cell_value:
        return None
    s = str(cell_value)
    if "|" in s:
        first = s.split("|", 1)[0].strip()
    else:
        first = s.strip()
    # remove non-digit characters except dot
    try:
        p = float(re.sub(r"[^\d.]", "", first))
        return p
    except:
        return None

def get_product_info(driver, sku):
    """
    Visit noon product URL for SKU and read price and nudges.
    Returns (price_float_or_None, nudges_string)
    """
    url = f"https://www.noon.com/saudi-en/{sku}/p/"
    try:
        driver.get(url)
        time.sleep(PAGE_WAIT_SECONDS)
    except Exception as e:
        return None, "-"

    # PRICE
    price = None
    try:
        price_el = driver.find_element(
            By.CSS_SELECTOR,
            'span.PriceOfferV2-module-scss-module__dHtRPW__priceNowText'
        )
        price_text = price_el.text
        price = float(re.sub(r"[^\d.]", "", price_text))
    except:
        # try alternative selectors if page layout differs (graceful fallback)
        try:
            price_el = driver.find_element(By.CSS_SELECTOR, 'span.price')
            price_text = price_el.text
            price = float(re.sub(r"[^\d.]", "", price_text))
        except:
            price = None

    # NUDGES (all occurrences joined with pipe)
    nudges = "-"
    try:
        nudge_elements = driver.find_elements(
            By.CSS_SELECTOR,
            'div.Nudges-module-scss-module__dNOKTG__nudgeText'
        )
        nudges_list = [n.text.strip() for n in nudge_elements if n.text.strip()]
        if nudges_list:
            nudges = " | ".join(nudges_list)
    except:
        nudges = "-"

    return price, nudges

def build_driver(headless=True):
    options = webdriver.ChromeOptions()
    # Recommended options for headless on servers/GitHub Actions
    if headless:
        # For modern Chrome:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def main():
    print("Starting Noon scraper → Google Sheets")
    ws = open_sheet_from_service_account(SERVICE_ACCOUNT_JSON, SPREADSHEET_ID, SHEET_NAME)

    while True:
        try:
            # load the sheet content; we'll operate row by row
            all_values = ws.get_all_values()
            # ensure at least header exists
            if len(all_values) < 1:
                print("Sheet is empty or headers missing.")
                time.sleep(LOOP_SLEEP_SECONDS)
                continue

            # start browser once per loop
            driver = build_driver(headless=True)

            # iterate rows starting from row 2
            for r_index in range(2, len(all_values) + 1):
                # for safety, re-fetch row values from sheet (so partial updates are accurate)
                row_values = ws.row_values(r_index)
                # ensure row has enough columns; pad if necessary
                while len(row_values) < LAST_UPDATE_COL:
                    row_values.append("")

                # process each SKU column
                for i in range(6):
                    sku_col = SKU_COLS[i]
                    price_col = PRICE_COLS[i]

                    sku_val = row_values[sku_col - 1].strip() if len(row_values) >= sku_col else ""
                    if not sku_val:
                        # skip empty SKU
                        continue

                    # fetch product info
                    price, nudges = get_product_info(driver, sku_val)

                    # read old cell value
                    old_cell = row_values[price_col - 1] if len(row_values) >= price_col else ""
                    old_price = parse_old_price(old_cell)

                    # determine change string
                    change = "-"
                    if price is not None:
                        if old_price not in [None, 0] and price != old_price:
                            diff = price - old_price
                            # format diff with no excessive decimals:
                            if float(diff).is_integer():
                                diff_str = str(int(diff))
                            else:
                                diff_str = f"{diff:.2f}"
                            if diff > 0:
                                change = f"↑ (+{diff_str})"
                            elif diff < 0:
                                # diff_str already negative? we used raw diff; ensure sign inside parentheses
                                change = f"↓ ({diff_str})" if diff_str.startswith("-") else f"↓ (-{diff_str})"
                        elif old_price in [None, 0]:
                            change = "-"
                        else:
                            change = "-"

                        final_text = f"{price} | {change} | {nudges}"
                        try:
                            ws.update_cell(r_index, price_col, final_text)
                        except Exception as e:
                            # fallback: batch update
                            ws.update(r_index, price_col, final_text)

                # update last update cell for this row
                now_text = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                try:
                    ws.update_cell(r_index, LAST_UPDATE_COL, now_text)
                except Exception:
                    ws.update(r_index, LAST_UPDATE_COL, now_text)

            driver.quit()
            print(f"Scan complete. Sleeping...")

            # (If run interactively you'd want to sleep for a long interval; when using GitHub Actions this loop ends)
            # For local testing, sleep for desired interval:
            time.sleep(60 * 10)  # default 10 minutes between full scans (adjust as you wish)

        except Exception as exc:
            print("Error in main loop:", str(exc))
            traceback.print_exc()
            try:
                driver.quit()
            except:
                pass
            time.sleep(LOOP_SLEEP_SECONDS)

if __name__ == "__main__":
    main()
