# noon_scraper_playwright.py
# Playwright version with HTTP2 disabled + real user-agent (fix Noon ERR_HTTP2_PROTOCOL_ERROR)

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

DEFAULT_SPREADSHEET_ID = "1EIgmqX2Ku_0_tfULUc8IfvNELFj96WGz_aLoIekfluk"
DEFAULT_SHEET_NAME = "noon"
DEFAULT_INTERVAL_MIN = 5.0

SA_FILE_ENV = os.environ.get("NOON_SA_FILE", "").strip()
SPREADSHEET_ID = os.environ.get("NOON_SPREADSHEET_ID", DEFAULT_SPREADSHEET_ID).strip()
SHEET_NAME = os.environ.get("NOON_SHEET_NAME", DEFAULT_SHEET_NAME).strip()
INTERVAL_MIN = float(os.environ.get("NOON_INTERVAL_MIN", DEFAULT_INTERVAL_MIN))

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


def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    print(f"[{now_str()}] {msg}")


def find_service_file():
    if SA_FILE_ENV and os.path.isfile(SA_FILE_ENV):
        return SA_FILE_ENV
    for f in os.listdir("."):
        if f.lower().endswith(".json"):
            return os.path.abspath(f)
    return None


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


def safe_update(ws, r, c, val):
    for _ in range(3):
        try:
            ws.update_cell(r, c, val)
            return True
        except:
            time.sleep(1)
    return False


def save_history(ws_hist, sku, old_price, new_price):
    diff = ""
    try:
        diff = new_price - (old_price if old_price else 0)
    except:
        diff = ""
    ws_hist.append_row([sku, old_price, new_price, diff, now_str()])


def parse_old_price(txt):
    if not txt:
        return None
    try:
        return float(re.sub(r"[^\d.]", "", txt))
    except:
        return None


# ==========================================
# 🔥 FIX: Playwright anti-block + disable HTTP2
# ==========================================

def create_stealth_browser(p):
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--disable-http2",             # ← حل Noon ERR_HTTP2_PROTOCOL_ERROR
            "--disable-web-security",
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-site-isolation-trials",
        ]
    )

    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/119.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        java_script_enabled=True,
        bypass_csp=True,
        ignore_https_errors=True,
    )

    page = context.new_page()

    # Remove navigator.webdriver
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)

    return browser, context, page


# ==========================================

def fetch_price_and_nudge(page, sku):
    url = f"https://www.noon.com/saudi-en/{sku}/p/"

    try:
        page.goto(url, timeout=40000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
    except Exception as e:
        log(f"⚠️ خطأ أثناء فتح الصفحة للـ SKU {sku}: {e}")
        return None, "-"

    # ---- Price ----
    price = None
    selectors = [
        'span[data-qa="priceNow"]',
        'span.PriceOfferV2-module-scss-module__dHtRPW__priceNowText',
        'div.price-now',
        'span.price'
    ]

    for sel in selectors:
        try:
            el = page.locator(sel)
            if el.count() > 0:
                txt = el.first.text_content().strip()
                digits = re.sub(r"[^\d.]", "", txt)
                if digits:
                    price = float(digits)
                    break
        except:
            pass

    # ---- Nudges ----
    nudges_list = []
    try:
        all_nudges = page.locator("div[class*='nudge']")
        for i in range(all_nudges.count()):
            txt = all_nudges.nth(i).text_content().strip()
            if txt:
                nudges_list.append(txt)
    except:
        pass

    nudges = " | ".join(nudges_list) if nudges_list else "-"
    return price, nudges


def monitor_loop(sa_file, spreadsheet_id, sheet_name, interval_min):
    log("🔔 بدء المراقبة — اضغط Ctrl+C للإيقاف.")

    with sync_playwright() as p:
        browser, context, page = create_stealth_browser(p)
        log("✅ متصفح Playwright تم تشغيله بدون HTTP2.")

        while not STOP:
            log("🔄 بدأ فحص جديد...")

            try:
                ws, ws_hist = connect_sheet(sa_file, spreadsheet_id, sheet_name)
            except Exception as e:
                log(f"❌ خطأ الاتصال بالشيت: {e}")
                time.sleep(30)
                continue

            rows = ws.get_all_values()
            if len(rows) < 2:
                time.sleep(60)
                continue

            for r in range(2, len(rows) + 1):
                row = rows[r - 1]
                row += [""] * (LAST_UPDATE_COL - len(row))

                changed = False

                for i in range(6):
                    sku = row[SKU_COLS[i] - 1].strip()
                    if not sku:
                        continue

                    sku = re.sub(r"[^A-Za-z0-9\-]", "", sku)

                    log(f"📌 فحص SKU: {sku}")
                    old_price = parse_old_price(row[PRICE_COLS[i] - 1])

                    price, nudges = fetch_price_and_nudge(page, sku)

                    if price is not None:
                        if old_price not in [None, 0] and price != old_price:
                            save_history(ws_hist, sku, old_price, price)

                        safe_update(ws, r, PRICE_COLS[i], price)
                        safe_update(ws, r, NUDGE_COLS[i], nudges)

                        changed = True

                if changed:
                    safe_update(ws, r, LAST_UPDATE_COL, now_str())
                    log(f"✔️ تم تحديث الصف {r}")

            log(f"⏳ التالي بعد {interval_min} دقيقة...")
            for _ in range(int(interval_min * 60)):
                if STOP:
                    break
                time.sleep(1)

        browser.close()
        log("🛑 تم الإيقاف بنجاح.")


if __name__ == "__main__":
    sa_file = find_service_file()
    if not sa_file:
        log("❌ JSON غير موجود.")
        sys.exit(1)

    log(f"استخدام JSON: {sa_file}")
    log(f"Spreadsheet: {SPREADSHEET_ID} | Sheet: {SHEET_NAME}")

    monitor_loop(sa_file, SPREADSHEET_ID, SHEET_NAME, INTERVAL_MIN)
