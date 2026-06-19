# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram bot tokenini @BotFather orqali oling
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# OpenAI API kalitini https://platform.openai.com/api-keys dan oling
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Foydalanuvchi fayllari vaqtincha shu papkada saqlanadi
OUTPUT_DIR = "generated_files"

# SQLite ma'lumotlar bazasi fayli (foydalanuvchilar, to'lovlar, statistika)
DB_PATH = os.getenv("DB_PATH", "bot_data.db")

# Admin(lar) Telegram user_id si — to'lovlarni tasdiqlash va /stats buyrug'i uchun.
# Bir nechta admin bo'lsa, vergul bilan ajratib yozing: "123456,789012"
ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
]

# Narxlar (so'mda)
PRICE_CV = 25_000
PRICE_LETTER = 20_000

# To'lov qabul qilinadigan kartalar (foydalanuvchiga ko'rsatiladi).
# 1-karta - asosiy (masalan Uzcard/Humo), 2-karta - Visa (xalqaro to'lovlar uchun,
# masalan boshqa mamlakatdagi foydalanuvchilar uchun qulay).
PAYMENT_CARD_NUMBER = os.getenv("PAYMENT_CARD_NUMBER", "0000 0000 0000 0000")
PAYMENT_CARD_OWNER = os.getenv("PAYMENT_CARD_OWNER", "F.I.Sh.")

PAYMENT_VISA_CARD_NUMBER = os.getenv("PAYMENT_VISA_CARD_NUMBER", "")
PAYMENT_VISA_CARD_OWNER = os.getenv("PAYMENT_VISA_CARD_OWNER", "")

# Bot username (referal havola yaratish uchun, @ belgisisiz, masalan "germany_docs_bot")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")

# Necha nafar referal taklif qilinsa, 1 ta bepul huquq beriladi
REFERRALS_FOR_FREE_CREDIT = 2

# Qo'llab-quvvatlanadigan tillar
LANGUAGES = {
    "uz": "O'zbekcha",
    "ru": "Русский",
    "en": "English",
    "tr": "Türkçe",
    "es": "Español",
    "hi": "हिन्दी",
    "uk": "Українська",
}

# Viza turlari
VISA_TYPES = {
    "student": {
        "uz": "Talaba (o'qish) vizasi",
        "ru": "Студенческая виза",
        "en": "Student Visa",
        "tr": "Öğrenci Vizesi",
        "es": "Visa de Estudiante",
        "hi": "छात्र वीज़ा",
        "uk": "Студентська віза",
    },
    "work": {
        "uz": "Ish vizasi",
        "ru": "Рабочая виза",
        "en": "Work Visa",
        "tr": "Çalışma Vizesi",
        "es": "Visa de Trabajo",
        "hi": "वर्क वीज़ा",
        "uk": "Робоча віза",
    },
    "ausbildung": {
        "uz": "Ausbildung (kasb-hunar ta'limi) vizasi",
        "ru": "Виза для Ausbildung",
        "en": "Ausbildung Visa",
        "tr": "Ausbildung (Mesleki Eğitim) Vizesi",
        "es": "Visa de Ausbildung (Formación Profesional)",
        "hi": "Ausbildung (व्यावसायिक प्रशिक्षण) वीज़ा",
        "uk": "Віза для Ausbildung (професійного навчання)",
    },
    "family": {
        "uz": "Oila qo'shilishi vizasi",
        "ru": "Виза для соединения семьи",
        "en": "Family Reunion Visa",
        "tr": "Aile Birleşimi Vizesi",
        "es": "Visa de Reunificación Familiar",
        "hi": "परिवार पुनर्मिलन वीज़ा",
        "uk": "Віза для об'єднання сім'ї",
    },
    "job_seeker": {
        "uz": "Ish izlash vizasi (Chancenkarte)",
        "ru": "Виза для поиска работы (Chancenkarte)",
        "en": "Job Seeker Visa (Chancenkarte)",
        "tr": "İş Arama Vizesi (Chancenkarte)",
        "es": "Visa de Búsqueda de Empleo (Chancenkarte)",
        "hi": "नौकरी खोज वीज़ा (Chancenkarte)",
        "uk": "Віза для пошуку роботи (Chancenkarte)",
    },
}
