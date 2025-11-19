# noon_scraper_playwright.py
# Playwright version of the Noon price monitor (console script, no GUI).
# Behavior mirrors original selenium script: reads SKUs from Google Sheet, fetches price/nudges, updates sheet, saves history.

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
    # Priority: env var, then first .json in cwd
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
    except Exception:
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
    except Exception:
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
        page.goto(url, timeout=timeout_ms)
        # allow some time for dynamic content
        page.wait_for_timeout(2500)
    except PlaywrightTimeoutError:
        log(f"⚠️ مهلة تحميل الصفحة للـ SKU {sku}")
        # continue and try to query whatever loaded
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
                # extract digits/decimal
                digits = re.sub(r"[^\d.]", "", txt)
                if digits:
                    try:
                        price = float(digits)
                        break
                    except:
                        continue
        except Exception:
            continue

    # collect nudges
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
                continue
    except Exception:
        pass

    try:
        sold_locator = page.locator('div.Nudges-module-scss-module__dNOKTG__nudgeText.Nudges-module-scss-module__dNOKTG__isPdp')
        for i in range(sold_locator.count()):
            try:
                t = sold_locator.nth(i).text_content().strip()
                if t and t not in nudges_list:
                    nudges_list.append(t)
            except:
                continue
    except Exception:
        pass

    try:
        sold_recent = page.locator("text=sold recently")
        for i in range(sold_recent.count()):
            try:
                t = sold_recent.nth(i).text_content().strip()
                if t and t not in nudges_list:
                    nudges_list.append(t)
            except:
                continue
    except Exception:
        pass

    nudges = " | ".join(nudges_list) if nudges_list else "-"
    return price, nudges

# ------------- Main monitor loop -------------
def monitor_loop(sa_file, spreadsheet_id, sheet_name, interval_min):
    log("🔔 بدء المراقبة (Playwright) — اضغط Ctrl+C للإيقاف.")
    # prepare Playwright and browser
    with sync_playwright() as p:
        browser = None
        context = None
        page = None

        def ensure_browser():
            nonlocal browser, context, page
            if browser:
                try:
                    # a simple call to ensure browser still responsive
                    _ = browser.contexts
                    return
                except Exception:
                    try:
                        browser.close()
                    except:
                        pass
                    browser = None
                    context = None
                    page = None
            try:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                log("✅ متصفح Playwright جاهز.")
            except Exception as e:
                log(f"❌ فشل تشغيل المتصفح: {e}")
                browser = None
                context = None
                page = None

        while not STOP:
            log("🔄 بدأ فحص جديد...")
            # connect to sheet
            try:
                ws, ws_hist = connect_sheet(sa_file, spreadsheet_id, sheet_name)
            except Exception as e:
                log(f"❌ خطأ الاتصال بالشيت: {e}")
                log(traceback.format_exc())
                time.sleep(60)
                if STOP:
                    break
                continue

            ensure_browser()
            if page is None:
                log("⚠️ المتصفح غير متاح الآن — إعادة المحاولة بعد 15 ثانية.")
                time.sleep(15)
                if STOP:
                    break
                continue

            try:
                all_values = ws.get_all_values()
            except Exception as e:
                log(f"⚠️ فشل جلب القيم من الشيت: {e}")
                time.sleep(30)
                if STOP:
                    break
                continue

            if len(all_values) < 2:
                log("⚠️ الشيت لا يحتوي على بيانات كافية (صفوف أقل من 2).")
                time.sleep(60)
                if STOP:
                    break
                continue

            # iterate rows
            for r in range(2, len(all_values) + 1):
                if STOP:
                    break

                row_vals = all_values[r - 1]
                # pad row to expected length
                while len(row_vals) < LAST_UPDATE_COL:
                    row_vals.append("")

                updated_any_price = False

                for i in range(6):
                    sku = ""
                    try:
                        sku = row_vals[SKU_COLS[i] - 1].strip()
                    except Exception:
                        sku = ""
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
                        log(f"⚠️ استثناء أثناء جلب السعر للـ SKU {sku}: {e}")
                        nudges = "-"
                        price = None

                    if price is not None:
                        # save history if changed
                        try:
                            if old_price not in [None, 0] and price != old_price:
                                save_history(ws_hist, sku, old_price, price)
                        except Exception as e:
                            log(f"⚠️ خطأ أثناء حفظ التاريخ: {e}")

                        safe_update(ws, r, price_col, price)
                        safe_update(ws, r, nudge_col, nudges)
                        updated_any_price = True

                if updated_any_price:
                    now = now_str()
                    safe_update(ws, r, LAST_UPDATE_COL, now)
                    log(f"✔️ تم تحديث أسعار الصف رقم {r}")

            # sleep until next run
            log(f"⏳ سيتم بدء الفحص التالي بعد {interval_min} دقيقة...")
            slept = 0
            total_sleep = int(interval_min * 60)
            while slept < total_sleep and not STOP:
                time.sleep(1)
                slept += 1

        # cleanup browser
        try:
            if page:
                page.close()
            if context:
                context.close()
            if browser:
                browser.close()
        except:
            pass
    log("✅ تم الإيقاف. وداعًا!")

# ------------- Entry point -------------
if __name__ == "__main__":
    sa_file = find_service_file()
    if not sa_file:
        log("❌ لم يتم العثور على ملف Service JSON ولا تم تحديد NOON_SA_FILE. ضع ملف JSON في نفس المجلد أو عيّن NOON_SA_FILE.")
        sys.exit(1)
    log(f"استخدام ملف Service JSON: {sa_file}")
    log(f"Spreadsheet ID: {SPREADSHEET_ID} | Sheet: {SHEET_NAME} | Interval: {INTERVAL_MIN} min")
    try:
        monitor_loop(sa_file, SPREADSHEET_ID, SHEET_NAME, INTERVAL_MIN)
    except Exception as e:
        log(f"❌ خطأ غير متوقع في البرنامج: {e}")
        log(traceback.format_exc())
        sys.exit(1)
