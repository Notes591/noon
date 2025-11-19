# noon_scraper_playwright.py
# Playwright version of the Noon price monitor (console script, no GUI).
# Behavior mirrors original selenium script: reads SKUs from Google Sheet, fetches price/nudges,
# updates sheet, saves history.

import os
import sys
import time
import datetime
import re
import traceback
import signal

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import gspread
from google.oauth2.service_account import Credentials

# ------------- Config / Defaults -------------
DEFAULT_SPREADSHEET_ID = "1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk"
DEFAULT_SHEET_NAME = "noon"
DEFAULT_INTERVAL_MIN = 5.0

# env overrides
SA_FILE_ENV = os.environ.get("NOON_SA_FILE", "").strip()
SPREADSHEET_ID = os.environ.get("NOON_SPREADSHEET_ID", DEFAULT_SPREADSHEET_ID).strip()
SHEET_NAME = os.environ.get("NOON_SHEET_NAME", DEFAULT_SHEET_NAME).strip()
INTERVAL_MIN = float(os.environ.get("NOON_INTERVAL_MIN", DEFAULT_INTERVAL_MIN))

# Columns mapping (same as original)
SKU_COLS = [1, 2, 3, 4, 5, 6]
PRICE_COLS = [7, 8, 9, 10, 11, 12]
NUDGE_COLS = [13, 14, 15, 16, 17, 18]
LAST_UPDATE_COL = 19

STOP = False

def signal_handler(sig, frame):
    global STOP
    print("\n[INFO] Received termination signal — shutting down gracefully...")
    STOP = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ------------- Utilities -------------
def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg):
    print(f"[{now_str()}] {msg}")

def find_service_file():
    if SA_FILE_ENV:
        if os.path.isfile(SA_FILE_ENV):
            return SA_FILE_ENV
        else:
            log(f"⚠️ ملف JSON المحدد في NOON_SA_FILE غير موجود: {SA_FILE_ENV}")

    for f in os.listdir("."):
        if f.lower().endswith(".json"):
            return os.path.abspath(f)

    return None

# ------------- Google Sheets -------------
def connect_sheet(sa_file, spreadsheet_id, sheet_name):
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(sa_file, scopes=scopes)
    client = gspread.authorize(creds)

    ws = client.open_by_key(spreadsheet_id).worksheet(sheet_name)

    try:
        ws_hist = client.open_by_key(spreadsheet_id).worksheet("history")
    except:
        ws_hist = client.open_by_key(spreadsheet_id).add_worksheet("history", rows=20000, cols=10)
        ws_hist.append_row(["SKU", "Old Price", "New Price", "Change", "DateTime"])

    return ws, ws_hist

def safe_update(ws, r, c, val, retries=3):
    for _ in range(retries):
        try:
            ws.update_cell(r, c, val)
            return True
        except Exception as e:
            log(f"⚠️ خطأ أثناء التحديث في الخلية ({r},{c}): {e} — محاولة ثانية بعد 1s")
            time.sleep(1)

    log(f"❌ فشل التحديث في الخلية ({r},{c}) بعد {retries} محاولات.")
    return False

def save_history(ws_hist, sku, old_price, new_price):
    try:
        diff = new_price - (old_price if old_price else 0)
    except:
        diff = ""

    dt = now_str()

    try:
        ws_hist.append_row([sku, old_price, new_price, diff, dt])
    except Exception as e:
        log(f"⚠️ خطأ في حفظ التاريخ للـ SKU {sku}: {e}")

def parse_old_price(cell_value):
    if not cell_value:
        return None

    try:
        return float(re.sub(r"[^\d.]", "", str(cell_value)))
    except:
        return None

# ------------- Scraping (Playwright) -------------
def fetch_price_and_nudge_playwright(page, sku, timeout_ms=30000):

    url = f"https://www.noon.com/saudi-en/{sku}/p/"

    try:
        # FIXED: HTTP2 error → switched to domcontentloaded
        page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

    except Exception as e:
        log(f"⚠️ خطأ أثناء فتح الصفحة للـ SKU {sku}: {e}")
        return None, "-"

    price = None

    selectors = [
        'span[data-qa="priceNow"]',
        'span.PriceOfferV2-module-scss-module__dHtRPW__priceNowText',
        'div.price-now',
        'span.price'
    ]

    for sel in selectors:
        try:
            locator = page.locator(sel)
            if locator.count() > 0:
                txt = locator.first.text_content().strip()
                digits = re.sub(r"[^\d.]", "", txt)
                if digits:
                    try:
                        price = float(digits)
                        break
                    except:
                        continue
        except:
            continue

    nudges_list = []

    try:
        nudges_locator = page.locator('div.Nudges-module-scss-module__dNOKTG__nudgeText')
        count = nudges_locator.count()
        for i in range(count):
            try:
                t = nudges_locator.nth(i).text_content().strip()
                if t:
                    nudges_list.append(t)
            except:
                pass
    except:
        pass

    try:
        sold_locator = page.locator(
            'div.Nudges-module-scss-module__dNOKTG__nudgeText.Nudges-module-scss-module__dNOKTG__isPdp'
        )
        for i in range(sold_locator.count()):
            t = sold_locator.nth(i).text_content().strip()
            if t and t not in nudges_list:
                nudges_list.append(t)
    except:
        pass

    try:
        sold_recent = page.locator("text=sold recently")
        for i in range(sold_recent.count()):
            t = sold_recent.nth(i).text_content().strip()
            if t and t not in nudges_list:
                nudges_list.append(t)
    except:
        pass

    nudges = " | ".join(nudges_list) if nudges_list else "-"

    return price, nudges

# ------------- Main monitor loop -------------
def monitor_loop(sa_file, spreadsheet_id, sheet_name, interval_min):

    log("🔔 بدء المراقبة (Playwright) — اضغط Ctrl+C للإيقاف.")

    with sync_playwright() as p:

        browser = None
        context = None
        page = None

        def ensure_browser():
            nonlocal browser, context, page

            if browser:
                try:
                    _ = browser.contexts
                    return
                except:
                    try:
                        browser.close()
                    except:
                        pass
                    browser, context, page = None, None, None

            try:
                # FIXED: HTTP2 protection bypass
                browser = p.chromium.launch(
                    headless=False,
                    args=[
                        "--disable-http2",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-features=IsolateOrigins,site-per-process",
                        "--start-maximized"
                    ]
                )

                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                    java_script_enabled=True,
                    ignore_https_errors=True
                )

                page = context.new_page()

                log("✅ متصفح Playwright جاهز.")

            except Exception as e:
                log(f"❌ فشل تشغيل المتصفح: {e}")
                browser, context, page = None, None, None

        while not STOP:

            log("🔄 بدأ فحص جديد...")

            try:
                ws, ws_hist = connect_sheet(sa_file, spreadsheet_id, sheet_name)
            except Exception as e:
                log(f"❌ خطأ الاتصال بالشيت: {e}")
                log(traceback.format_exc())
                time.sleep(60)
                continue

            ensure_browser()

            if page is None:
                log("⚠️ المتصفح غير متاح — المحاولة بعد 15 ثانية.")
                time.sleep(15)
                continue

            try:
                all_values = ws.get_all_values()
            except Exception as e:
                log(f"⚠️ فشل قراءة الشيت: {e}")
                time.sleep(30)
                continue

            if len(all_values) < 2:
                log("⚠️ الشيت فارغ.")
                time.sleep(60)
                continue

            for r in range(2, len(all_values) + 1):

                if STOP:
                    break

                row_vals = all_values[r - 1]

                while len(row_vals) < LAST_UPDATE_COL:
                    row_vals.append("")

                updated_any_price = False

                for i in range(6):

                    sku = row_vals[SKU_COLS[i] - 1].strip() if len(row_vals) >= SKU_COLS[i] else ""

                    if not sku:
                        continue

                    sku = re.sub(r"[^A-Za-z0-9\-]", "", sku)

                    if sku == "":
                        continue

                    log(f"📌 جاري فحص SKU: {sku}")

                    price_col = PRICE_COLS[i]
                    nudge_col = NUDGE_COLS[i]

                    old_price = parse_old_price(row_vals[price_col - 1])

                    try:
                        price, nudges = fetch_price_and_nudge_playwright(page, sku)
                    except Exception as e:
                        log(f"⚠️ استثناء أثناء جلب SKU {sku}: {e}")
                        price, nudges = None, "-"

                    if price is not None:
                        if old_price not in [None, 0] and price != old_price:
                            save_history(ws_hist, sku, old_price, price)

                        safe_update(ws, r, price_col, price)
                        safe_update(ws, r, nudge_col, nudges)

                        updated_any_price = True

                if updated_any_price:
                    now = now_str()
                    safe_update(ws, r, LAST_UPDATE_COL, now)
                    log(f"✔️ تحديث الصف رقم {r}")

            log(f"⏳ سيتم بدء الفحص التالي بعد {interval_min} دقيقة...")
            slept = 0
            total_sleep = int(interval_min * 60)

            while slept < total_sleep and not STOP:
                time.sleep(1)
                slept += 1

        try:
            if page: page.close()
            if context: context.close()
            if browser: browser.close()
        except:
            pass

    log("✅ تم الإيقاف.")

# ------------- Entry ------------- 
if __name__ == "__main__":

    sa_file = find_service_file()

    if not sa_file:
        log("❌ لم يتم العثور على ملف JSON!")
        sys.exit(1)

    log(f"استخدام ملف Service JSON: {sa_file}")
    log(f"Spreadsheet ID: {SPREADSHEET_ID} | Sheet: {SHEET_NAME} | Interval: {INTERVAL_MIN} min")

    try:
        monitor_loop(sa_file, SPREADSHEET_ID, SHEET_NAME, INTERVAL_MIN)
    except Exception as e:
        log(f"❌ خطأ غير متوقع: {e}")
        log(traceback.format_exc())
        sys.exit(1)
