Noon Price Monitor (Playwright Version)

سكربت احترافي لمراقبة أسعار منتجات Noon بشكل تلقائي.
يجلب السعر الحالي، والـ Nudges، و"Sold recently"، ثم يقوم بتحديثها داخل Google Sheets،
مع تسجيل جميع التغييرات في ورقة history بشكل تلقائي.

تم اعتماد Playwright بدل Selenium لأداء أسرع وثبات أعلى وبدون متصفح ظاهر (Headless).

🚀 المميزات

قراءة SKUs مباشرة من Google Sheet

جلب السعر الحالي من Noon

قراءة جميع الـ Nudges و sold recently

تحديث الأسعار والـ nudges داخل الأعمدة المخصّصة

حفظ تغييرات الأسعار داخل ورقة history

يعمل تلقائيًا كل X دقيقة (قابل للتعديل)

يعمل بالكامل بدون واجهة (Terminal فقط)

يدعم التشغيل كخدمة Windows / Linux / Docker

📦 التثبيت
1️⃣ تثبيت المتطلبات الأساسية
pip install -r requirements.txt

2️⃣ تثبيت متصفح Playwright
playwright install chromium

3️⃣ التأكد من إصدار Python و pip
python --version
pip --version

4️⃣ (اختياري) استخدام بيئة افتراضية Virtual Environment

إنشاء البيئة:

python -m venv venv


تفعيل على Windows:

venv\Scripts\activate


تفعيل على Linux / macOS:

source venv/bin/activate


ثم تثبيت المتطلبات داخل البيئة:

pip install -r requirements.txt
playwright install chromium

5️⃣ حل مشكلات Playwright (إن لزم)
pip install playwright==1.45.0
playwright install chromium

🔧 إعداد Google Sheets
1) ملف الخدمة (Service Account)

أنشئ مشروع Google Cloud

فعّل Google Sheets API

أنشئ Service Account

نزل ملف JSON

ضعه بجانب السكربت

2) مشاركة الشيت

شارك Google Sheet مع الإيميل الموجود داخل ملف JSON
ثم اعطه صلاحية Editor

3) الأعمدة المطلوبة داخل الشيت
1–6    SKUs  
7–12   Prices  
13–18  Nudges  
19     Last Updated  


ورقة history سيتم إنشاؤها تلقائيًا إذا لم تكن موجودة.

▶️ التشغيل

لتشغيل البرنامج:

python noon_scraper_playwright.py

⚙️ متغيرات البيئة (اختيارية)

يمكن تخصيص الإعدادات بدون تعديل الكود.

Windows:

set NOON_SA_FILE=service.json
set NOON_INTERVAL_MIN=5
set NOON_SHEET_NAME=noon
set NOON_SPREADSHEET_ID=xxxxxxx


Linux/macOS:

export NOON_SA_FILE=service.json
export NOON_INTERVAL_MIN=5
export NOON_SHEET_NAME=noon
export NOON_SPREADSHEET_ID=xxxxxxx

🗂️ هيكل المشروع
/project-folder
│
├── noon_scraper_playwright.py
├── requirements.txt
├── README.md
└── service.json   ← لا ترفعه على GitHub

📁 .gitignore المقترح
*.json
__pycache__/
*.pyc
playwright/

📜 الترخيص

MIT License

❤️ المساهمة

مرحب بأي تحسين أو إضافة
ويسعدني دعم وتطوير المشروع باستمرار.
