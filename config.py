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

# Qo'llab-quvvatlanadigan tillar
LANGUAGES = {
    "uz": "O'zbekcha",
    "ru": "Русский",
    "en": "English",
}

# Viza turlari
VISA_TYPES = {
    "student": {
        "uz": "Talaba (o'qish) vizasi",
        "ru": "Студенческая виза",
        "en": "Student Visa",
    },
    "work": {
        "uz": "Ish vizasi",
        "ru": "Рабочая виза",
        "en": "Work Visa",
    },
    "ausbildung": {
        "uz": "Ausbildung (kasb-hunar ta'limi) vizasi",
        "ru": "Виза для Ausbildung",
        "en": "Ausbildung Visa",
    },
    "family": {
        "uz": "Oila qo'shilishi vizasi",
        "ru": "Виза для соединения семьи",
        "en": "Family Reunion Visa",
    },
    "job_seeker": {
        "uz": "Ish izlash vizasi (Chancenkarte)",
        "ru": "Виза для поиска работы (Chancenkarte)",
        "en": "Job Seeker Visa (Chancenkarte)",
    },
}
