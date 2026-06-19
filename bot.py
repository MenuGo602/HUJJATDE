# bot.py
"""
Germaniya elchixonasi uchun hujjatlar tayyorlovchi Telegram bot.

Oqim:
1. Til tanlash
2. Asosiy menyu: (a) CV + Motivatsion xat, (b) Faqat hujjatlar checklisti
3. Checklist uchun: viza turini tanlash -> ro'yxat yuborish
4. CV/Motivatsion xat uchun: shaxsiy ma'lumotlar, ta'lim, ish tajribasi,
   ko'nikmalar, maqsad (universitet/dastur/lavozim) -> AI generatsiya -> docx yuborish
"""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import (
    TELEGRAM_BOT_TOKEN,
    LANGUAGES,
    VISA_TYPES,
    OUTPUT_DIR,
    ADMIN_IDS,
    PRICE_CV,
    PRICE_LETTER,
    PAYMENT_CARD_NUMBER,
    PAYMENT_CARD_OWNER,
    PAYMENT_VISA_CARD_NUMBER,
    PAYMENT_VISA_CARD_OWNER,
    BOT_USERNAME,
    REFERRALS_FOR_FREE_CREDIT,
)
from visa_checklists import get_checklist
from ai_generator import generate_cv_sections, generate_motivation_letter
from document_generator import build_cv_docx, build_motivation_letter_docx, convert_to_pdf
import database as db

logging.basicConfig(level=logging.INFO)
router = Router()

# Global FSM storage - admin to'lov tasdiqlovi kabi "tashqi" hodisalardan
# foydalanuvchining holatini to'g'ridan-to'g'ri o'zgartirish uchun ishlatiladi.
storage = MemoryStorage()

# Hujjatlarning (CV va motivatsion xat) chiqish tili. Interfeys tili (uz/ru/en)
# foydalanuvchi bilan muloqot uchun, bu esa hujjatning o'zi uchun — Germaniya
# elchixonasi/universitet/ish beruvchi har doim nemis tilini kutadi.
DOCUMENT_LANG = "German"


# ---------------------------------------------------------------------------
# FSM holatlari
# ---------------------------------------------------------------------------
class Flow(StatesGroup):
    choosing_language = State()
    main_menu = State()
    choosing_visa_for_checklist = State()
    confirming_saved_profile = State()

    # Shaxsiy ma'lumotlar
    full_name = State()
    birth_date = State()
    nationality = State()
    address = State()
    phone = State()
    email = State()
    photo = State()

    # Ta'lim
    education_entry = State()
    education_more = State()

    # Ish tajribasi
    experience_entry = State()
    experience_more = State()

    # Ko'nikmalar
    languages_skill = State()
    it_skills = State()
    soft_skills = State()

    # Maqsad (CV uchun viza turi + Motivatsion xat uchun)
    target_visa_type = State()
    target_program = State()
    target_institution = State()
    target_institution_address = State()
    motivation_reason = State()
    previewing = State()
    choosing_template = State()
    awaiting_payment_screenshot = State()
    awaiting_broadcast_message = State()

    generating = State()


# ---------------------------------------------------------------------------
# Yordamchi: tilga mos matnlar
# ---------------------------------------------------------------------------
TEXTS = {
    "choose_language": {
        "uz": "Tilni tanlang:",
        "ru": "Выберите язык:",
        "en": "Choose your language:",
        "tr": "Dilinizi seçin:",
        "es": "Elige tu idioma:",
        "hi": "अपनी भाषा चुनें:",
        "uk": "Виберіть мову:",
    },
    "main_menu": {
        "uz": "Nima qilishni xohlaysiz?",
        "ru": "Что вы хотите сделать?",
        "en": "What would you like to do?",
        "tr": "Ne yapmak istersiniz?",
        "es": "¿Qué te gustaría hacer?",
        "hi": "आप क्या करना चाहेंगे?",
        "uk": "Що ви хочете зробити?",
    },
    "menu_cv": {
        "uz": "📄 CV + Motivatsion xat tayyorlash",
        "ru": "📄 Подготовить CV + мотивационное письмо",
        "en": "📄 Prepare CV + Motivation Letter",
        "tr": "📄 CV + Motivasyon Mektubu hazırla",
        "es": "📄 Preparar CV + Carta de Motivación",
        "hi": "📄 CV + प्रेरणा पत्र तैयार करें",
        "uk": "📄 Підготувати CV + мотиваційний лист",
    },
    "menu_checklist": {
        "uz": "✅ Hujjatlar checklisti",
        "ru": "✅ Чек-лист документов",
        "en": "✅ Document checklist",
        "tr": "✅ Belge kontrol listesi",
        "es": "✅ Lista de documentos",
        "hi": "✅ दस्तावेज़ चेकलिस्ट",
        "uk": "✅ Чек-лист документів",
    },
    "choose_visa": {
        "uz": "Viza turini tanlang:",
        "ru": "Выберите тип визы:",
        "en": "Choose visa type:",
        "tr": "Vize türünü seçin:",
        "es": "Elige el tipo de visa:",
        "hi": "वीज़ा प्रकार चुनें:",
        "uk": "Виберіть тип візи:",
    },
    "ask_full_name": {
        "uz": "Ism va familiyangizni to'liq kiriting:",
        "ru": "Введите ваше полное имя и фамилию:",
        "en": "Enter your full name:",
        "tr": "Tam adınızı girin:",
        "es": "Introduce tu nombre completo:",
        "hi": "अपना पूरा नाम दर्ज करें:",
        "uk": "Введіть ваше повне ім'я:",
    },
    "ask_birth_date": {
        "uz": "Tug'ilgan sanangizni kiriting (KK.OO.YYYY):",
        "ru": "Введите дату рождения (ДД.ММ.ГГГГ):",
        "en": "Enter your date of birth (DD.MM.YYYY):",
        "tr": "Doğum tarihinizi girin (GG.AA.YYYY):",
        "es": "Introduce tu fecha de nacimiento (DD.MM.AAAA):",
        "hi": "अपनी जन्मतिथि दर्ज करें (DD.MM.YYYY):",
        "uk": "Введіть дату народження (ДД.ММ.РРРР):",
    },
    "ask_nationality": {
        "uz": "Fuqaroligingizni kiriting:",
        "ru": "Введите ваше гражданство:",
        "en": "Enter your nationality:",
        "tr": "Vatandaşlığınızı girin:",
        "es": "Introduce tu nacionalidad:",
        "hi": "अपनी राष्ट्रीयता दर्ज करें:",
        "uk": "Введіть ваше громадянство:",
    },
    "ask_address": {
        "uz": "Manzilingizni kiriting (shahar, mamlakat):",
        "ru": "Введите ваш адрес (город, страна):",
        "en": "Enter your address (city, country):",
        "tr": "Adresinizi girin (şehir, ülke):",
        "es": "Introduce tu dirección (ciudad, país):",
        "hi": "अपना पता दर्ज करें (शहर, देश):",
        "uk": "Введіть вашу адресу (місто, країна):",
    },
    "ask_phone": {
        "uz": "Telefon raqamingizni kiriting:",
        "ru": "Введите номер телефона:",
        "en": "Enter your phone number:",
        "tr": "Telefon numaranızı girin:",
        "es": "Introduce tu número de teléfono:",
        "hi": "अपना फ़ोन नंबर दर्ज करें:",
        "uk": "Введіть номер телефону:",
    },
    "ask_email": {
        "uz": "Email manzilingizni kiriting:",
        "ru": "Введите ваш email:",
        "en": "Enter your email address:",
        "tr": "E-posta adresinizi girin:",
        "es": "Introduce tu correo electrónico:",
        "hi": "अपना ईमेल पता दर्ज करें:",
        "uk": "Введіть вашу електронну адресу:",
    },
    "ask_photo": {
        "uz": "📷 Endi CV uchun fotosuratingizni yuboring (oddiy rasm sifatida, fayl emas — pasport/biometrik fotosurat tavsiya etiladi, oq fon, rasmiy ko'rinish):",
        "ru": "📷 Теперь отправьте ваше фото для CV (как обычное фото, не файл — рекомендуется паспортное/биометрическое фото на белом фоне):",
        "en": "📷 Now send your photo for the CV (as a regular photo, not a file — a passport-style/biometric photo with a white background is recommended):",
        "tr": "📷 Şimdi CV için fotoğrafınızı gönderin (dosya olarak değil, normal fotoğraf olarak — beyaz arka planlı pasaport/biyometrik fotoğraf önerilir):",
        "es": "📷 Ahora envía tu foto para el CV (como foto normal, no como archivo — se recomienda una foto tipo pasaporte con fondo blanco):",
        "hi": "📷 अब CV के लिए अपनी फ़ोटो भेजें (फ़ाइल के रूप में नहीं, सामान्य फ़ोटो के रूप में — सफ़ेद बैकग्राउंड वाली पासपोर्ट/बायोमेट्रिक फ़ोटो की सलाह दी जाती है):",
        "uk": "📷 Тепер надішліть своє фото для CV (як звичайне фото, не як файл — рекомендується паспортне/біометричне фото на білому фоні):",
    },
    "photo_error": {
        "uz": "⚠️ Iltimos, rasm yuboring (skrepka -> Galereya/Camera orqali oddiy fotosurat sifatida, fayl/dokument sifatida emas).",
        "ru": "⚠️ Пожалуйста, отправьте фото (через скрепку -> Галерея/Камера как обычное фото, не как файл/документ).",
        "en": "⚠️ Please send a photo (via the attachment icon -> Gallery/Camera as a regular photo, not as a file/document).",
        "tr": "⚠️ Lütfen bir fotoğraf gönderin (ataç simgesi -> Galeri/Kamera üzerinden normal fotoğraf olarak, dosya/belge olarak değil).",
        "es": "⚠️ Por favor, envía una foto (a través del icono de adjuntar -> Galería/Cámara como foto normal, no como archivo/documento).",
        "hi": "⚠️ कृपया एक फ़ोटो भेजें (अटैचमेंट आइकन -> गैलरी/कैमरा के माध्यम से सामान्य फ़ोटो के रूप में, फ़ाइल/दस्तावेज़ के रूप में नहीं)।",
        "uk": "⚠️ Будь ласка, надішліть фото (через іконку скріпки -> Галерея/Камера як звичайне фото, не як файл/документ).",
    },
    "ask_education": {
        "uz": "Ta'lim haqida yozing (daraja, muassasa, yillar, masalan: 'Bakalavr, Informatika, TATU, 2019-2023'):",
        "ru": "Напишите об образовании (степень, учебное заведение, годы, напр.: 'Бакалавр, Информатика, ТУИТ, 2019-2023'):",
        "en": "Write about your education (degree, institution, years, e.g. 'Bachelor, Computer Science, TUIT, 2019-2023'):",
        "tr": "Eğitiminiz hakkında yazın (derece, kurum, yıllar, örn: 'Lisans, Bilgisayar Bilimi, TUIT, 2019-2023'):",
        "es": "Escribe sobre tu educación (título, institución, años, ej.: 'Licenciatura, Informática, TUIT, 2019-2023'):",
        "hi": "अपनी शिक्षा के बारे में लिखें (डिग्री, संस्थान, वर्ष, जैसे: 'स्नातक, कंप्यूटर साइंस, TUIT, 2019-2023'):",
        "uk": "Напишіть про освіту (ступінь, заклад, роки, напр.: 'Бакалавр, Інформатика, TUIT, 2019-2023'):",
    },
    "ask_education_more": {
        "uz": "Yana ta'lim ma'lumoti qo'shmoqchimisiz?",
        "ru": "Хотите добавить ещё одно образование?",
        "en": "Add another education entry?",
        "tr": "Başka bir eğitim bilgisi eklemek ister misiniz?",
        "es": "¿Quieres añadir otra entrada de educación?",
        "hi": "क्या आप एक और शिक्षा प्रविष्टि जोड़ना चाहते हैं?",
        "uk": "Бажаєте додати ще одну освіту?",
    },
    "ask_experience": {
        "uz": "Ish tajribangiz haqida yozing (lavozim, kompaniya, yillar, asosiy vazifalar):",
        "ru": "Напишите о вашем опыте работы (должность, компания, годы, основные обязанности):",
        "en": "Write about your work experience (position, company, years, key responsibilities):",
        "tr": "İş deneyiminiz hakkında yazın (pozisyon, şirket, yıllar, temel sorumluluklar):",
        "es": "Escribe sobre tu experiencia laboral (puesto, empresa, años, responsabilidades principales):",
        "hi": "अपने कार्य अनुभव के बारे में लिखें (पद, कंपनी, वर्ष, मुख्य ज़िम्मेदारियाँ):",
        "uk": "Напишіть про досвід роботи (посада, компанія, роки, основні обов'язки):",
    },
    "ask_experience_more": {
        "uz": "Yana ish tajribasi qo'shmoqchimisiz?",
        "ru": "Хотите добавить ещё один опыт работы?",
        "en": "Add another work experience entry?",
        "tr": "Başka bir iş deneyimi eklemek ister misiniz?",
        "es": "¿Quieres añadir otra experiencia laboral?",
        "hi": "क्या आप एक और कार्य अनुभव जोड़ना चाहते हैं?",
        "uk": "Бажаєте додати ще один досвід роботи?",
    },
    "ask_languages_skill": {
        "uz": "Bilgan tillaringizni va darajangizni yozing (masalan: O'zbek - ona tili, Ingliz - B2, Nemis - A2):",
        "ru": "Напишите ваши языки и уровень (напр.: Узбекский - родной, Английский - B2, Немецкий - A2):",
        "en": "List your languages and levels (e.g. Uzbek - native, English - B2, German - A2):",
        "tr": "Bildiğiniz dilleri ve seviyelerini yazın (örn: Özbekçe - anadil, İngilizce - B2, Almanca - A2):",
        "es": "Indica tus idiomas y niveles (ej.: Uzbeko - nativo, Inglés - B2, Alemán - A2):",
        "hi": "अपनी भाषाएँ और स्तर लिखें (जैसे: उज़्बेक - मातृभाषा, अंग्रेज़ी - B2, जर्मन - A2):",
        "uk": "Напишіть свої мови та рівні (напр.: Узбецька - рідна, Англійська - B2, Німецька - A2):",
    },
    "ask_it_skills": {
        "uz": "IT/texnik ko'nikmalaringizni yozing (yo'q bo'lsa, '-' yozing):",
        "ru": "Напишите ваши IT/технические навыки (если нет, напишите '-'):",
        "en": "List your IT/technical skills (write '-' if none):",
        "tr": "IT/teknik becerilerinizi yazın (yoksa '-' yazın):",
        "es": "Indica tus habilidades técnicas/informáticas (escribe '-' si no tienes):",
        "hi": "अपने IT/तकनीकी कौशल लिखें (न हो तो '-' लिखें):",
        "uk": "Напишіть свої IT/технічні навички (якщо немає, напишіть '-'):",
    },
    "ask_soft_skills": {
        "uz": "Shaxsiy/soft skill larni yozing (masalan: jamoada ishlash, vaqtni boshqarish):",
        "ru": "Напишите ваши личные качества/soft skills (напр.: командная работа, тайм-менеджмент):",
        "en": "List your soft skills (e.g. teamwork, time management):",
        "tr": "Kişisel/soft becerilerinizi yazın (örn: takım çalışması, zaman yönetimi):",
        "es": "Indica tus habilidades blandas (ej.: trabajo en equipo, gestión del tiempo):",
        "hi": "अपने सॉफ्ट स्किल्स लिखें (जैसे: टीम वर्क, समय प्रबंधन):",
        "uk": "Напишіть свої soft skills (напр.: командна робота, тайм-менеджмент):",
    },
    "ask_target_program": {
        "uz": "Qaysi dastur/lavozimga ariza topshirmoqdasiz? (masalan: 'Informatika magistraturasi' yoki 'Software Developer lavozimi')",
        "ru": "На какую программу/должность вы подаёте заявку? (напр.: 'Магистратура по информатике' или 'должность Software Developer')",
        "en": "Which program/position are you applying for? (e.g. 'Master's in Computer Science' or 'Software Developer position')",
        "tr": "Hangi programa/pozisyona başvuruyorsunuz? (örn: 'Bilgisayar Bilimi Yüksek Lisansı' veya 'Software Developer pozisyonu')",
        "es": "¿A qué programa/puesto te postulas? (ej.: 'Máster en Informática' o 'puesto de Software Developer')",
        "hi": "आप किस कार्यक्रम/पद के लिए आवेदन कर रहे हैं? (जैसे: 'कंप्यूटर साइंस में मास्टर्स' या 'Software Developer पद')",
        "uk": "На яку програму/посаду ви подаєте заявку? (напр.: 'Магістратура з інформатики' або 'посада Software Developer')",
    },
    "ask_target_institution": {
        "uz": "Universitet/kompaniya nomini kiriting:",
        "ru": "Введите название университета/компании:",
        "en": "Enter the university/company name:",
        "tr": "Üniversite/şirket adını girin:",
        "es": "Introduce el nombre de la universidad/empresa:",
        "hi": "विश्वविद्यालय/कंपनी का नाम दर्ज करें:",
        "uk": "Введіть назву університету/компанії:",
    },
    "ask_target_institution_address": {
        "uz": "Universitet/kompaniya manzilini kiriting (agar bilmasangiz, '-' yozing):",
        "ru": "Введите адрес университета/компании (если не знаете, напишите '-'):",
        "en": "Enter the university/company address (write '-' if unknown):",
        "tr": "Üniversite/şirket adresini girin (bilmiyorsanız '-' yazın):",
        "es": "Introduce la dirección de la universidad/empresa (escribe '-' si no la sabes):",
        "hi": "विश्वविद्यालय/कंपनी का पता दर्ज करें (न जानते हों तो '-' लिखें):",
        "uk": "Введіть адресу університету/компанії (якщо не знаєте, напишіть '-'):",
    },
    "ask_motivation_reason": {
        "uz": "Nima uchun aynan shu dastur/kompaniya va Germaniyani tanladingiz? Qisqacha yozing — bu motivatsion xat uchun muhim:",
        "ru": "Почему вы выбрали именно эту программу/компанию и Германию? Напишите кратко — это важно для мотивационного письма:",
        "en": "Why did you choose this program/company and Germany specifically? Write briefly — this is important for the motivation letter:",
        "tr": "Neden özellikle bu programı/şirketi ve Almanya'yı seçtiniz? Kısaca yazın — bu motivasyon mektubu için önemlidir:",
        "es": "¿Por qué elegiste precisamente este programa/empresa y Alemania? Escribe brevemente — esto es importante para la carta de motivación:",
        "hi": "आपने विशेष रूप से यह कार्यक्रम/कंपनी और जर्मनी क्यों चुना? संक्षेप में लिखें — यह प्रेरणा पत्र के लिए महत्वपूर्ण है:",
        "uk": "Чому ви обрали саме цю програму/компанію та Німеччину? Напишіть коротко — це важливо для мотиваційного листа:",
    },
    "generating": {
        "uz": "⏳ Hujjatlaringiz tayyorlanmoqda, biroz kuting...",
        "ru": "⏳ Готовим ваши документы, подождите немного...",
        "en": "⏳ Preparing your documents, please wait...",
        "tr": "⏳ Belgeleriniz hazırlanıyor, lütfen biraz bekleyin...",
        "es": "⏳ Preparando tus documentos, espera un momento...",
        "hi": "⏳ आपके दस्तावेज़ तैयार किए जा रहे हैं, कृपया प्रतीक्षा करें...",
        "uk": "⏳ Готуємо ваші документи, зачекайте трохи...",
    },
    "choose_template": {
        "uz": "🎨 CV uchun dizayn shablonini tanlang:",
        "ru": "🎨 Выберите шаблон дизайна для CV:",
        "en": "🎨 Choose a design template for your CV:",
        "tr": "🎨 CV'niz için bir tasarım şablonu seçin:",
        "es": "🎨 Elige una plantilla de diseño para tu CV:",
        "hi": "🎨 अपने CV के लिए एक डिज़ाइन टेम्पलेट चुनें:",
        "uk": "🎨 Виберіть шаблон дизайну для CV:",
    },
    "preview_title": {
        "uz": "📋 Ma'lumotlaringizni tekshiring:\n\n",
        "ru": "📋 Проверьте ваши данные:\n\n",
        "en": "📋 Please review your information:\n\n",
        "tr": "📋 Bilgilerinizi kontrol edin:\n\n",
        "es": "📋 Por favor revisa tu información:\n\n",
        "hi": "📋 कृपया अपनी जानकारी जांचें:\n\n",
        "uk": "📋 Перевірте вашу інформацію:\n\n",
    },
    "preview_confirm": {
        "uz": "✅ Hammasi to'g'ri, davom et",
        "ru": "✅ Всё верно, продолжить",
        "en": "✅ Everything is correct, continue",
        "tr": "✅ Her şey doğru, devam et",
        "es": "✅ Todo es correcto, continuar",
        "hi": "✅ सब कुछ सही है, जारी रखें",
        "uk": "✅ Все правильно, продовжити",
    },
    "preview_restart": {
        "uz": "🔄 Boshidan qaytadan to'ldirish",
        "ru": "🔄 Заполнить всё заново",
        "en": "🔄 Start over from the beginning",
        "tr": "🔄 Baştan yeniden doldur",
        "es": "🔄 Empezar de nuevo desde el principio",
        "hi": "🔄 शुरुआत से फिर से भरें",
        "uk": "🔄 Заповнити все знову",
    },
    "free_credits_status": {
        "uz": "🎁 Sizda {count} ta bepul CV+xat huquqi mavjud.",
        "ru": "🎁 У вас {count} бесплатных прав на CV+письмо.",
        "en": "🎁 You have {count} free CV+letter credit(s).",
        "tr": "🎁 {count} ücretsiz CV+mektup hakkınız var.",
        "es": "🎁 Tienes {count} crédito(s) gratuito(s) de CV+carta.",
        "hi": "🎁 आपके पास {count} मुफ़्त CV+पत्र क्रेडिट हैं।",
        "uk": "🎁 У вас {count} безкоштовних прав на CV+лист.",
    },
    "no_free_credits_intro": {
        "uz": "Bepul huquqingiz tugagan. Hujjatlarni davom ettirish uchun to'lov qiling, yoki do'stlarni taklif qilib bepul huquq oling.",
        "ru": "Ваше бесплатное право закончилось. Чтобы продолжить, оплатите, или пригласите друзей и получите бесплатное право.",
        "en": "Your free credit has run out. To continue, please pay, or invite friends to earn a free credit.",
        "tr": "Ücretsiz hakkınız bitti. Devam etmek için ödeme yapın veya arkadaşlarınızı davet ederek ücretsiz hak kazanın.",
        "es": "Tu crédito gratuito se ha agotado. Para continuar, paga, o invita a amigos para obtener un crédito gratuito.",
        "hi": "आपका मुफ़्त क्रेडिट समाप्त हो गया है। जारी रखने के लिए भुगतान करें, या मुफ़्त क्रेडिट पाने के लिए मित्रों को आमंत्रित करें।",
        "uk": "Ваше безкоштовне право закінчилося. Щоб продовжити, оплатіть, або запросіть друзів і отримайте безкоштовне право.",
    },
    "payment_info": {
        "uz": "💳 To'lov ma'lumotlari:\n\nCV (Lebenslauf): {price_cv} so'm\nMotivatsion xat: {price_letter} so'm\nJami: {total} so'm\n\n🏦 1-karta (Uzcard/Humo):\n{card_number}\n{card_owner}{visa_section}\n\nTo'lovni amalga oshirgandan keyin, to'lov skrinshotini shu yerga yuboring.",
        "ru": "💳 Информация об оплате:\n\nCV (Lebenslauf): {price_cv} сум\nМотивационное письмо: {price_letter} сум\nИтого: {total} сум\n\n🏦 Карта 1 (Uzcard/Humo):\n{card_number}\n{card_owner}{visa_section}\n\nПосле оплаты отправьте скриншот оплаты сюда.",
        "en": "💳 Payment information:\n\nCV (Lebenslauf): {price_cv} UZS\nMotivation letter: {price_letter} UZS\nTotal: {total} UZS\n\n🏦 Card 1 (Uzcard/Humo):\n{card_number}\n{card_owner}{visa_section}\n\nAfter paying, please send a screenshot of the payment here.",
        "tr": "💳 Ödeme bilgileri:\n\nCV (Lebenslauf): {price_cv} UZS\nMotivasyon mektubu: {price_letter} UZS\nToplam: {total} UZS\n\n🏦 Kart 1 (Uzcard/Humo):\n{card_number}\n{card_owner}{visa_section}\n\nÖdemeden sonra, ödeme ekran görüntüsünü buraya gönderin.",
        "es": "💳 Información de pago:\n\nCV (Lebenslauf): {price_cv} UZS\nCarta de motivación: {price_letter} UZS\nTotal: {total} UZS\n\n🏦 Tarjeta 1 (Uzcard/Humo):\n{card_number}\n{card_owner}{visa_section}\n\nDespués de pagar, envía una captura de pantalla del pago aquí.",
        "hi": "💳 भुगतान जानकारी:\n\nCV (Lebenslauf): {price_cv} UZS\nप्रेरणा पत्र: {price_letter} UZS\nकुल: {total} UZS\n\n🏦 कार्ड 1 (Uzcard/Humo):\n{card_number}\n{card_owner}{visa_section}\n\nभुगतान करने के बाद, यहाँ भुगतान का स्क्रीनशॉट भेजें।",
        "uk": "💳 Інформація про оплату:\n\nCV (Lebenslauf): {price_cv} сум\nМотиваційний лист: {price_letter} сум\nРазом: {total} сум\n\n🏦 Картка 1 (Uzcard/Humo):\n{card_number}\n{card_owner}{visa_section}\n\nПісля оплати надішліть скріншот оплати сюди.",
    },
    "referral_offer": {
        "uz": "👥 Yoki: 2 ta do'stingizni shu havola orqali taklif qiling — ular botdan foydalansa, sizga 1 ta bepul huquq beriladi!\n\n🔗 {referral_link}\n\nHozirgi taklif qilganlar soni: {referral_count}/{needed}",
        "ru": "👥 Или: пригласите 2 друзей по этой ссылке — когда они воспользуются ботом, вы получите 1 бесплатное право!\n\n🔗 {referral_link}\n\nТекущее количество приглашённых: {referral_count}/{needed}",
        "en": "👥 Or: invite 2 friends using this link — once they use the bot, you'll get 1 free credit!\n\n🔗 {referral_link}\n\nCurrent referrals: {referral_count}/{needed}",
        "tr": "👥 Veya: bu bağlantıyla 2 arkadaşınızı davet edin — botu kullandıklarında size 1 ücretsiz hak verilecek!\n\n🔗 {referral_link}\n\nMevcut davet sayısı: {referral_count}/{needed}",
        "es": "👥 O: invita a 2 amigos con este enlace — cuando usen el bot, ¡recibirás 1 crédito gratuito!\n\n🔗 {referral_link}\n\nReferidos actuales: {referral_count}/{needed}",
        "hi": "👥 या: इस लिंक से 2 मित्रों को आमंत्रित करें — जब वे बॉट का उपयोग करेंगे, आपको 1 मुफ़्त क्रेडिट मिलेगा!\n\n🔗 {referral_link}\n\nवर्तमान रेफ़रल: {referral_count}/{needed}",
        "uk": "👥 Або: запросіть 2 друзів за цим посиланням — коли вони скористаються ботом, ви отримаєте 1 безкоштовне право!\n\n🔗 {referral_link}\n\nПоточна кількість запрошених: {referral_count}/{needed}",
    },
    "send_screenshot_button": {
        "uz": "📤 To'lov skrinshotini yuborish",
        "ru": "📤 Отправить скриншот оплаты",
        "en": "📤 Send payment screenshot",
        "tr": "📤 Ödeme ekran görüntüsü gönder",
        "es": "📤 Enviar captura de pago",
        "hi": "📤 भुगतान स्क्रीनशॉट भेजें",
        "uk": "📤 Надіслати скріншот оплати",
    },
    "ask_payment_screenshot": {
        "uz": "📤 To'lov skrinshotini (rasm sifatida) yuboring:",
        "ru": "📤 Отправьте скриншот оплаты (как фото):",
        "en": "📤 Please send the payment screenshot (as a photo):",
        "tr": "📤 Lütfen ödeme ekran görüntüsünü gönderin (fotoğraf olarak):",
        "es": "📤 Por favor envía la captura de pantalla del pago (como foto):",
        "hi": "📤 कृपया भुगतान का स्क्रीनशॉट भेजें (फ़ोटो के रूप में):",
        "uk": "📤 Будь ласка, надішліть скріншот оплати (як фото):",
    },
    "payment_submitted": {
        "uz": "✅ Skrinshot qabul qilindi! To'lovingiz admin tomonidan tekshirilmoqda, biroz vaqt olishi mumkin. Tasdiqlangandan keyin hujjatlaringiz avtomatik yuboriladi.",
        "ru": "✅ Скриншот получен! Ваш платёж проверяется администратором, это может занять некоторое время. После подтверждения документы будут отправлены автоматически.",
        "en": "✅ Screenshot received! Your payment is being reviewed by the admin, this may take a little time. Once approved, your documents will be sent automatically.",
        "tr": "✅ Ekran görüntüsü alındı! Ödemeniz yönetici tarafından inceleniyor, bu biraz zaman alabilir. Onaylandıktan sonra belgeleriniz otomatik olarak gönderilecek.",
        "es": "✅ ¡Captura recibida! Tu pago está siendo revisado por el administrador, esto puede tardar un poco. Una vez aprobado, tus documentos se enviarán automáticamente.",
        "hi": "✅ स्क्रीनशॉट प्राप्त हुआ! आपके भुगतान की समीक्षा एडमिन द्वारा की जा रही है, इसमें कुछ समय लग सकता है। स्वीकृत होने के बाद, आपके दस्तावेज़ स्वचालित रूप से भेजे जाएंगे।",
        "uk": "✅ Скріншот отримано! Ваш платіж перевіряється адміністратором, це може зайняти деякий час. Після підтвердження ваші документи будуть надіслані автоматично.",
    },
    "payment_approved_user": {
        "uz": "✅ To'lovingiz tasdiqlandi! Hujjatlaringiz tayyorlanmoqda...",
        "ru": "✅ Ваш платёж подтверждён! Готовим ваши документы...",
        "en": "✅ Your payment has been approved! Preparing your documents...",
        "tr": "✅ Ödemeniz onaylandı! Belgeleriniz hazırlanıyor...",
        "es": "✅ ¡Tu pago ha sido aprobado! Preparando tus documentos...",
        "hi": "✅ आपका भुगतान स्वीकृत हो गया है! आपके दस्तावेज़ तैयार किए जा रहे हैं...",
        "uk": "✅ Ваш платіж підтверджено! Готуємо ваші документи...",
    },
    "payment_rejected_user": {
        "uz": "❌ To'lovingiz tasdiqlanmadi. Iltimos, to'lov ma'lumotlarini tekshirib qaytadan urinib ko'ring, yoki admin bilan bog'laning.",
        "ru": "❌ Ваш платёж не подтверждён. Пожалуйста, проверьте данные оплаты и попробуйте снова, или свяжитесь с администратором.",
        "en": "❌ Your payment was not approved. Please double-check the payment details and try again, or contact the admin.",
        "tr": "❌ Ödemeniz onaylanmadı. Lütfen ödeme bilgilerini kontrol edip yeniden deneyin veya yönetici ile iletişime geçin.",
        "es": "❌ Tu pago no fue aprobado. Por favor verifica los datos de pago e intenta de nuevo, o contacta al administrador.",
        "hi": "❌ आपका भुगतान स्वीकृत नहीं हुआ। कृपया भुगतान विवरण जांचें और पुनः प्रयास करें, या एडमिन से संपर्क करें।",
        "uk": "❌ Ваш платіж не підтверджено. Будь ласка, перевірте дані оплати і спробуйте знову, або зв'яжіться з адміністратором.",
    },
    "ask_use_saved_profile": {
        "uz": "📁 Sizda avval to'ldirilgan ma'lumotlar mavjud. Ulardan foydalanib davom etamizmi, yoki hammasini qaytadan to'ldiramizmi?\n\n👤 {full_name}\n🎓 Ta'lim: {education_count} ta yozuv\n💼 Tajriba: {experience_count} ta yozuv",
        "ru": "📁 У вас есть ранее заполненные данные. Продолжим с ними, или заполним всё заново?\n\n👤 {full_name}\n🎓 Образование: {education_count} запис(ей)\n💼 Опыт: {experience_count} запис(ей)",
        "en": "📁 You have previously saved data. Continue with it, or fill everything in again?\n\n👤 {full_name}\n🎓 Education: {education_count} entries\n💼 Experience: {experience_count} entries",
        "tr": "📁 Daha önce kaydedilmiş bilgileriniz var. Bunlarla devam edelim mi, yoksa her şeyi yeniden mi dolduralım?\n\n👤 {full_name}\n🎓 Eğitim: {education_count} kayıt\n💼 Deneyim: {experience_count} kayıt",
        "es": "📁 Tienes datos guardados anteriormente. ¿Continuamos con ellos, o lo rellenamos todo de nuevo?\n\n👤 {full_name}\n🎓 Educación: {education_count} entradas\n💼 Experiencia: {experience_count} entradas",
        "hi": "📁 आपके पास पहले से सहेजा गया डेटा है। क्या इसके साथ जारी रखें, या सब कुछ फिर से भरें?\n\n👤 {full_name}\n🎓 शिक्षा: {education_count} प्रविष्टियाँ\n💼 अनुभव: {experience_count} प्रविष्टियाँ",
        "uk": "📁 У вас є раніше збережені дані. Продовжимо з ними, чи заповнимо все знову?\n\n👤 {full_name}\n🎓 Освіта: {education_count} запис(ів)\n💼 Досвід: {experience_count} запис(ів)",
    },
    "use_saved_profile_yes": {
        "uz": "✅ Hammasi to'g'ri, davom et",
        "ru": "✅ Всё верно, продолжить",
        "en": "✅ All correct, continue",
        "tr": "✅ Hepsi doğru, devam et",
        "es": "✅ Todo correcto, continuar",
        "hi": "✅ सब सही है, जारी रखें",
        "uk": "✅ Все правильно, продовжити",
    },
    "use_saved_profile_no": {
        "uz": "🔄 Qaytadan to'ldirish",
        "ru": "🔄 Заполнить заново",
        "en": "🔄 Fill in again",
        "tr": "🔄 Yeniden doldur",
        "es": "🔄 Rellenar de nuevo",
        "hi": "🔄 फिर से भरें",
        "uk": "🔄 Заповнити знову",
    },
    "template_yellow": {
        "uz": "🟡 Sariq (sidebar)",
        "ru": "🟡 Жёлтый (sidebar)",
        "en": "🟡 Yellow (sidebar)",
        "tr": "🟡 Sarı (sidebar)",
        "es": "🟡 Amarillo (sidebar)",
        "hi": "🟡 पीला (sidebar)",
        "uk": "🟡 Жовтий (sidebar)",
    },
    "template_blue": {
        "uz": "🔵 Ko'k (sidebar)",
        "ru": "🔵 Синий (sidebar)",
        "en": "🔵 Blue (sidebar)",
        "tr": "🔵 Mavi (sidebar)",
        "es": "🔵 Azul (sidebar)",
        "hi": "🔵 नीला (sidebar)",
        "uk": "🔵 Синій (sidebar)",
    },
    "template_green": {
        "uz": "🟢 Yashil (sidebar)",
        "ru": "🟢 Зелёный (sidebar)",
        "en": "🟢 Green (sidebar)",
        "tr": "🟢 Yeşil (sidebar)",
        "es": "🟢 Verde (sidebar)",
        "hi": "🟢 हरा (sidebar)",
        "uk": "🟢 Зелений (sidebar)",
    },
    "done": {
        "uz": "✅ Tayyor! Hujjatlaringiz (nemis tilida) quyida.\n\n⚠️ Eslatma: bu hujjatlar AI yordamida tayyorlangan qoralama. Topshirishdan oldin ularni o'zingiz va imkon bo'lsa mutaxassis bilan tekshirib chiqing.",
        "ru": "✅ Готово! Ваши документы (на немецком языке) ниже.\n\n⚠️ Примечание: это черновик, подготовленный с помощью AI. Перед подачей проверьте документы самостоятельно и, если возможно, со специалистом.",
        "en": "✅ Done! Your documents (in German) are below.\n\n⚠️ Note: these documents are an AI-generated draft. Please review them yourself, and ideally with a professional, before submission.",
        "tr": "✅ Hazır! Belgeleriniz (Almanca) aşağıda.\n\n⚠️ Not: bu belgeler AI ile hazırlanmış bir taslaktır. Göndermeden önce kendiniz ve mümkünse bir uzmanla kontrol edin.",
        "es": "✅ ¡Listo! Tus documentos (en alemán) están abajo.\n\n⚠️ Nota: estos documentos son un borrador generado por IA. Revísalos tú mismo, e idealmente con un profesional, antes de presentarlos.",
        "hi": "✅ तैयार! आपके दस्तावेज़ (जर्मन में) नीचे हैं।\n\n⚠️ ध्यान दें: ये दस्तावेज़ AI द्वारा तैयार किया गया एक ड्राफ्ट है। जमा करने से पहले इन्हें स्वयं और संभव हो तो किसी विशेषज्ञ से जांच लें।",
        "uk": "✅ Готово! Ваші документи (німецькою) нижче.\n\n⚠️ Примітка: це чернетка, підготовлена за допомогою AI. Перед поданням перевірте документи самостійно і, якщо можливо, з фахівцем.",
    },
    "yes": {"uz": "Ha", "ru": "Да", "en": "Yes", "tr": "Evet", "es": "Sí", "hi": "हाँ", "uk": "Так"},
    "no": {"uz": "Yo'q", "ru": "Нет", "en": "No", "tr": "Hayır", "es": "No", "hi": "नहीं", "uk": "Ні"},
    "back_button": {
        "uz": "⬅️ Orqaga",
        "ru": "⬅️ Назад",
        "en": "⬅️ Back",
        "tr": "⬅️ Geri",
        "es": "⬅️ Atrás",
        "hi": "⬅️ वापस",
        "uk": "⬅️ Назад",
    },
    "cancelled": {
        "uz": "❌ Bekor qilindi. Qaytadan boshlash uchun /start buyrug'ini yuboring.",
        "ru": "❌ Отменено. Чтобы начать снова, отправьте /start.",
        "en": "❌ Cancelled. Send /start to begin again.",
        "tr": "❌ İptal edildi. Yeniden başlamak için /start gönderin.",
        "es": "❌ Cancelado. Envía /start para empezar de nuevo.",
        "hi": "❌ रद्द कर दिया गया। फिर से शुरू करने के लिए /start भेजें।",
        "uk": "❌ Скасовано. Щоб почати знову, надішліть /start.",
    },
    "nothing_to_cancel": {
        "uz": "Hozir bekor qiladigan jarayon yo'q. /start bilan boshlashingiz mumkin.",
        "ru": "Сейчас нет процесса для отмены. Вы можете начать с /start.",
        "en": "There's nothing to cancel right now. You can begin with /start.",
        "tr": "Şu anda iptal edilecek bir işlem yok. /start ile başlayabilirsiniz.",
        "es": "Ahora no hay ningún proceso que cancelar. Puedes comenzar con /start.",
        "hi": "अभी रद्द करने के लिए कोई प्रक्रिया नहीं है। आप /start से शुरू कर सकते हैं।",
        "uk": "Зараз немає процесу для скасування. Можете почати з /start.",
    },
    "checklist_title": {
        "uz": "📋 {visa} uchun kerakli hujjatlar ro'yxati:\n\n",
        "ru": "📋 Список документов для визы «{visa}»:\n\n",
        "en": "📋 Document checklist for {visa}:\n\n",
        "tr": "📋 {visa} için gerekli belgeler listesi:\n\n",
        "es": "📋 Lista de documentos para {visa}:\n\n",
        "hi": "📋 {visa} के लिए आवश्यक दस्तावेज़ों की सूची:\n\n",
        "uk": "📋 Список документів для {visa}:\n\n",
    },
    "checklist_footer": {
        "uz": "\n\n⚠️ Diqqat: talablar elchixonaga va vaqtga qarab o'zgarishi mumkin. Har doim rasmiy elchixona saytidan tekshirib chiqing.",
        "ru": "\n\n⚠️ Внимание: требования могут отличаться в зависимости от посольства и времени. Всегда проверяйте на официальном сайте посольства.",
        "en": "\n\n⚠️ Note: requirements may vary by embassy and over time. Always verify on the official embassy website.",
        "tr": "\n\n⚠️ Not: gereksinimler büyükelçiliğe ve zamana göre değişebilir. Her zaman resmi büyükelçilik web sitesinden kontrol edin.",
        "es": "\n\n⚠️ Nota: los requisitos pueden variar según la embajada y el tiempo. Verifica siempre en el sitio web oficial de la embajada.",
        "hi": "\n\n⚠️ ध्यान दें: आवश्यकताएँ दूतावास और समय के अनुसार भिन्न हो सकती हैं। हमेशा आधिकारिक दूतावास वेबसाइट पर जांचें।",
        "uk": "\n\n⚠️ Увага: вимоги можуть відрізнятися залежно від посольства та часу. Завжди перевіряйте на офіційному сайті посольства.",
    },
}


def t(key: str, lang: str) -> str:
    return TEXTS[key].get(lang, TEXTS[key]["en"])


def yes_no_kb(lang: str) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(text=t("yes", lang), callback_data="yes")
    kb.button(text=t("no", lang), callback_data="no")
    kb.adjust(2)
    return kb


def back_kb(lang: str, target_state: str) -> InlineKeyboardBuilder:
    """Bitta '⬅️ Orqaga' tugmasi bilan klaviatura. target_state - qaytiladigan
    FSM holatining nomi (masalan 'full_name')."""
    kb = InlineKeyboardBuilder()
    kb.button(text=t("back_button", lang), callback_data=f"back:{target_state}")
    return kb


# CV/Motivatsion xat oqimidagi matnli-javob qadamlarining ketma-ketligi.
# Har bir holat uchun: (oldingi_holat, oldingi_holatga_qaytganda_ko'rsatiladigan_savol_kaliti)
# Bu xarita "⬅️ Orqaga" tugmasi bosilganda foydalanuvchini to'g'ri qadamga va
# to'g'ri savol matniga qaytarish uchun ishlatiladi.
STEP_BACK_MAP = {
    "birth_date": ("full_name", "ask_full_name"),
    "nationality": ("birth_date", "ask_birth_date"),
    "address": ("nationality", "ask_nationality"),
    "phone": ("address", "ask_address"),
    "email": ("phone", "ask_phone"),
    "photo": ("email", "ask_email"),
    "education_entry": ("photo", "ask_photo"),
    "experience_entry": ("education_entry", "ask_education"),
    "languages_skill": ("experience_entry", "ask_experience"),
    "it_skills": ("languages_skill", "ask_languages_skill"),
    "soft_skills": ("it_skills", "ask_it_skills"),
    "target_program": ("soft_skills", "ask_soft_skills"),
    "target_institution": ("target_program", "ask_target_program"),
    "target_institution_address": ("target_institution", "ask_target_institution"),
    "motivation_reason": ("target_institution_address", "ask_target_institution_address"),
}

# Har bir FSM holati nomini, shu holatga kirilganda ko'rsatiladigan savol
# matnining TEXTS kalitiga bog'laydi. go_back() shu yerdan foydalanib,
# "Orqaga" bosilganda to'g'ri savolni qayta chiqaradi.
STATE_QUESTION_MAP = {
    "full_name": "ask_full_name",
    "birth_date": "ask_birth_date",
    "nationality": "ask_nationality",
    "address": "ask_address",
    "phone": "ask_phone",
    "email": "ask_email",
    "photo": "ask_photo",
    "education_entry": "ask_education",
    "experience_entry": "ask_experience",
    "languages_skill": "ask_languages_skill",
    "it_skills": "ask_it_skills",
    "soft_skills": "ask_soft_skills",
    "target_program": "ask_target_program",
    "target_institution": "ask_target_institution",
    "target_institution_address": "ask_target_institution_address",
    "motivation_reason": "ask_motivation_reason",
}


# ---------------------------------------------------------------------------
# Boshlanish va til tanlash
# ---------------------------------------------------------------------------
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    # Referal kodini aniqlash: /start REF<user_id> ko'rinishida keladi
    referred_by = None
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) > 1 and parts[1].startswith("REF"):
        try:
            candidate_id = int(parts[1][3:])
            if candidate_id != message.from_user.id:
                referred_by = candidate_id
        except ValueError:
            pass

    db.get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        referred_by=referred_by,
    )

    # Agar referal orqali kelgan bo'lsa va taklif qilgan kishi yetarli
    # miqdorda referal to'plagan bo'lsa, unga bepul huquq qo'shamiz
    if referred_by:
        ref_count = db.count_referrals(referred_by)
        if ref_count > 0 and ref_count % REFERRALS_FOR_FREE_CREDIT == 0:
            db.add_free_credit(referred_by, 1)

    kb = InlineKeyboardBuilder()
    for code, name in LANGUAGES.items():
        kb.button(text=name, callback_data=f"lang:{code}")
    kb.adjust(1)
    await message.answer(
        "Salom! / Привет! / Hello!\n\n" + TEXTS["choose_language"]["en"],
        reply_markup=kb.as_markup(),
    )
    await state.set_state(Flow.choosing_language)


@router.callback_query(Flow.choosing_language, F.data.startswith("lang:"))
async def set_language(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split(":")[1]
    await state.update_data(lang=lang)
    db.set_user_lang(callback.from_user.id, lang)

    kb = InlineKeyboardBuilder()
    kb.button(text=t("menu_cv", lang), callback_data="menu:cv")
    kb.button(text=t("menu_checklist", lang), callback_data="menu:checklist")
    kb.adjust(1)

    await callback.message.edit_text(t("main_menu", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.main_menu)
    await callback.answer()


# ---------------------------------------------------------------------------
# /cancel buyrug'i - istalgan vaqtda jarayonni bekor qilish
# ---------------------------------------------------------------------------
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    data = await state.get_data()
    lang = data.get("lang", "en")

    if current_state is None:
        await message.answer(t("nothing_to_cancel", lang))
        return

    await state.clear()
    await message.answer(t("cancelled", lang))


# ---------------------------------------------------------------------------
# /stats buyrug'i - faqat adminlar uchun, umumiy statistika
# ---------------------------------------------------------------------------
@router.message(Command("stats"))
async def cmd_stats(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return  # adminlardan boshqasiga sukut bilan e'tibor bermaymiz

    stats = db.get_stats()
    approved_sum = f"{stats['approved_payments_sum']:,}".replace(",", " ")

    text = (
        "📊 *Bot statistikasi*\n\n"
        f"👥 Foydalanuvchilar: {stats['total_users']}\n"
        f"📄 Yaratilgan hujjatlar: {stats['total_docs']}\n"
        f"   • CV: {stats['cv_docs']}\n"
        f"   • Motivatsion xat: {stats['letter_docs']}\n\n"
        f"💳 To'lovlar:\n"
        f"   • Kutilayotgan: {stats['pending_payments']}\n"
        f"   • Tasdiqlangan: {stats['approved_payments_count']} ta "
        f"({approved_sum} so'm)\n"
    )
    await message.answer(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /broadcast buyrug'i - faqat adminlar uchun, barcha foydalanuvchilarga
# umumiy xabar yuborish
# ---------------------------------------------------------------------------
@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    await message.answer(
        "📢 Barcha foydalanuvchilarga yuboriladigan xabar matnini kiriting "
        "(yoki /cancel bilan bekor qiling):"
    )
    await state.set_state(Flow.awaiting_broadcast_message)


@router.message(Flow.awaiting_broadcast_message)
async def do_broadcast(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    broadcast_text = message.text or message.caption or ""
    user_ids = db.get_all_user_ids()

    await message.answer(f"⏳ {len(user_ids)} foydalanuvchiga yuborilmoqda...")

    sent = 0
    failed = 0
    bot = message.bot
    for uid in user_ids:
        try:
            await bot.send_message(uid, broadcast_text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # Telegram rate-limit'iga urilmaslik uchun kichik pauza

    await message.answer(f"✅ Yuborildi: {sent} ta\n❌ Xato: {failed} ta")
    await state.clear()


# ---------------------------------------------------------------------------
# Universal "⬅️ Orqaga" tugmasi - matnli-javob qadamlari uchun
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("back:"))
async def go_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "en")
    target_state_name = callback.data.split(":", 1)[1]

    target_state = getattr(Flow, target_state_name)
    # STEP_BACK_MAP'da bu holatga mos savol matni kerak emas - bu yerda biz
    # to'g'ridan-to'g'ri target_state'ga mos savolni qayta ko'rsatamiz.
    # Buning uchun har bir holatning savol kalitini topamiz:
    question_key = STATE_QUESTION_MAP.get(target_state_name)
    await state.set_state(target_state)

    if question_key:
        # Agar bu qadam ham "Orqaga" tugmasiga ega bo'lsa, qayta qo'shamiz
        prev = STEP_BACK_MAP.get(target_state_name)
        if prev:
            kb = back_kb(lang, prev[0])
            await callback.message.edit_text(t(question_key, lang), reply_markup=kb.as_markup())
        else:
            await callback.message.edit_text(t(question_key, lang))
    await callback.answer()


# ---------------------------------------------------------------------------
# Checklist tarmog'i
# ---------------------------------------------------------------------------
@router.callback_query(Flow.main_menu, F.data == "menu:checklist")
async def choose_visa_for_checklist(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]

    kb = InlineKeyboardBuilder()
    for code, names in VISA_TYPES.items():
        kb.button(text=names[lang], callback_data=f"checklist_visa:{code}")
    kb.adjust(1)

    await callback.message.edit_text(t("choose_visa", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.choosing_visa_for_checklist)
    await callback.answer()


@router.callback_query(Flow.choosing_visa_for_checklist, F.data.startswith("checklist_visa:"))
async def send_checklist(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    visa_code = callback.data.split(":")[1]
    visa_name = VISA_TYPES[visa_code][lang]

    items = get_checklist(visa_code, lang)
    text = t("checklist_title", lang).format(visa=visa_name)
    text += "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))
    text += t("checklist_footer", lang)

    await callback.message.answer(text)
    await callback.answer()

    # Asosiy menyuga qaytarish
    kb = InlineKeyboardBuilder()
    kb.button(text=t("menu_cv", lang), callback_data="menu:cv")
    kb.button(text=t("menu_checklist", lang), callback_data="menu:checklist")
    kb.adjust(1)
    await callback.message.answer(t("main_menu", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.main_menu)


# ---------------------------------------------------------------------------
# CV + Motivatsion xat tarmog'i — shaxsiy ma'lumotlar
# ---------------------------------------------------------------------------
@router.callback_query(Flow.main_menu, F.data == "menu:cv")
async def start_cv_flow(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    user_id = callback.from_user.id

    saved_profile = db.load_profile(user_id)
    if saved_profile and saved_profile.get("full_name"):
        text = t("ask_use_saved_profile", lang).format(
            full_name=saved_profile.get("full_name", ""),
            education_count=len(saved_profile.get("education_list", [])),
            experience_count=len(saved_profile.get("experience_list", [])),
        )
        kb = InlineKeyboardBuilder()
        kb.button(text=t("use_saved_profile_yes", lang), callback_data="use_saved:yes")
        kb.button(text=t("use_saved_profile_no", lang), callback_data="use_saved:no")
        kb.adjust(1)
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
        await state.set_state(Flow.confirming_saved_profile)
        await callback.answer()
        return

    await callback.message.edit_text(t("ask_full_name", lang))
    await state.set_state(Flow.full_name)
    await callback.answer()


@router.callback_query(Flow.confirming_saved_profile, F.data.startswith("use_saved:"))
async def handle_saved_profile_choice(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    user_id = callback.from_user.id
    choice = callback.data.split(":")[1]

    if choice == "yes":
        saved_profile = db.load_profile(user_id)
        # Saqlangan shaxsiy ma'lumotlar, ta'lim, tajriba, ko'nikmalarni holatga yuklaymiz.
        # Maqsad (dastur/muassasa/sabab) qismi har safar qayta so'raladi, chunki
        # foydalanuvchi turli dasturlarga ariza topshirishi mumkin.
        await state.update_data(
            full_name=saved_profile.get("full_name", ""),
            birth_date=saved_profile.get("birth_date", ""),
            nationality=saved_profile.get("nationality", ""),
            address=saved_profile.get("address", ""),
            phone=saved_profile.get("phone", ""),
            email=saved_profile.get("email", ""),
            photo_path=saved_profile.get("photo_path", ""),
            education_list=saved_profile.get("education_list", []),
            experience_list=saved_profile.get("experience_list", []),
            languages_skill=saved_profile.get("languages_skill", ""),
            it_skills=saved_profile.get("it_skills", ""),
            soft_skills=saved_profile.get("soft_skills", ""),
        )
        # To'g'ridan-to'g'ri maqsad (viza turi) tanlashga o'tamiz
        kb = InlineKeyboardBuilder()
        for code, names in VISA_TYPES.items():
            kb.button(text=names[lang], callback_data=f"target_visa:{code}")
        kb.adjust(1)
        await callback.message.edit_text(t("choose_visa", lang), reply_markup=kb.as_markup())
        await state.set_state(Flow.target_visa_type)
    else:
        await callback.message.edit_text(t("ask_full_name", lang))
        await state.set_state(Flow.full_name)

    await callback.answer()


@router.message(Flow.full_name)
async def get_full_name(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(full_name=message.text.strip())
    kb = back_kb(lang, STEP_BACK_MAP["birth_date"][0])
    await message.answer(t("ask_birth_date", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.birth_date)


@router.message(Flow.birth_date)
async def get_birth_date(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(birth_date=message.text.strip())
    kb = back_kb(lang, STEP_BACK_MAP["nationality"][0])
    await message.answer(t("ask_nationality", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.nationality)


@router.message(Flow.nationality)
async def get_nationality(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(nationality=message.text.strip())
    kb = back_kb(lang, STEP_BACK_MAP["address"][0])
    await message.answer(t("ask_address", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.address)


@router.message(Flow.address)
async def get_address(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(address=message.text.strip())
    kb = back_kb(lang, STEP_BACK_MAP["phone"][0])
    await message.answer(t("ask_phone", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.phone)


@router.message(Flow.phone)
async def get_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(phone=message.text.strip())
    kb = back_kb(lang, STEP_BACK_MAP["email"][0])
    await message.answer(t("ask_email", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.email)


@router.message(Flow.email)
async def get_email(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(email=message.text.strip())
    kb = back_kb(lang, STEP_BACK_MAP["photo"][0])
    await message.answer(t("ask_photo", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.photo)


@router.message(Flow.photo, F.photo)
async def get_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    user_id = message.from_user.id

    # Eng yuqori sifatli (eng katta) versiyasini olamiz
    photo = message.photo[-1]
    user_dir = os.path.join(OUTPUT_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    photo_path = os.path.join(user_dir, "photo.jpg")

    bot = message.bot
    file = await bot.get_file(photo.file_id)
    await bot.download_file(file.file_path, destination=photo_path)

    await state.update_data(photo_path=photo_path, education_list=[], experience_list=[])
    kb = back_kb(lang, STEP_BACK_MAP["education_entry"][0])
    await message.answer(t("ask_education", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.education_entry)


@router.message(Flow.photo)
async def get_photo_invalid(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await message.answer(t("photo_error", lang))


# ---------------------------------------------------------------------------
# Ta'lim (bir nechta yozuv qo'shish mumkin)
# ---------------------------------------------------------------------------
@router.message(Flow.education_entry)
async def get_education_entry(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    education_list = data.get("education_list", [])
    education_list.append(message.text.strip())
    await state.update_data(education_list=education_list)

    kb = yes_no_kb(lang)
    await message.answer(t("ask_education_more", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.education_more)


@router.callback_query(Flow.education_more, F.data.in_(["yes", "no"]))
async def education_more(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    if callback.data == "yes":
        kb = back_kb(lang, STEP_BACK_MAP["education_entry"][0])
        await callback.message.edit_text(t("ask_education", lang), reply_markup=kb.as_markup())
        await state.set_state(Flow.education_entry)
    else:
        kb = back_kb(lang, STEP_BACK_MAP["experience_entry"][0])
        await callback.message.edit_text(t("ask_experience", lang), reply_markup=kb.as_markup())
        await state.set_state(Flow.experience_entry)
    await callback.answer()


# ---------------------------------------------------------------------------
# Ish tajribasi (bir nechta yozuv qo'shish mumkin)
# ---------------------------------------------------------------------------
@router.message(Flow.experience_entry)
async def get_experience_entry(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    experience_list = data.get("experience_list", [])
    experience_list.append(message.text.strip())
    await state.update_data(experience_list=experience_list)

    kb = yes_no_kb(lang)
    await message.answer(t("ask_experience_more", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.experience_more)


@router.callback_query(Flow.experience_more, F.data.in_(["yes", "no"]))
async def experience_more(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    if callback.data == "yes":
        kb = back_kb(lang, STEP_BACK_MAP["experience_entry"][0])
        await callback.message.edit_text(t("ask_experience", lang), reply_markup=kb.as_markup())
        await state.set_state(Flow.experience_entry)
    else:
        kb = back_kb(lang, STEP_BACK_MAP["languages_skill"][0])
        await callback.message.edit_text(t("ask_languages_skill", lang), reply_markup=kb.as_markup())
        await state.set_state(Flow.languages_skill)
    await callback.answer()


# ---------------------------------------------------------------------------
# Ko'nikmalar
# ---------------------------------------------------------------------------
@router.message(Flow.languages_skill)
async def get_languages_skill(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(languages_skill=message.text.strip())
    kb = back_kb(lang, STEP_BACK_MAP["it_skills"][0])
    await message.answer(t("ask_it_skills", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.it_skills)


@router.message(Flow.it_skills)
async def get_it_skills(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(it_skills=message.text.strip())
    kb = back_kb(lang, STEP_BACK_MAP["soft_skills"][0])
    await message.answer(t("ask_soft_skills", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.soft_skills)


@router.message(Flow.soft_skills)
async def get_soft_skills(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(soft_skills=message.text.strip())

    # Maqsad bosqichi - viza turi
    kb = InlineKeyboardBuilder()
    for code, names in VISA_TYPES.items():
        kb.button(text=names[lang], callback_data=f"target_visa:{code}")
    kb.adjust(1)
    await message.answer(t("choose_visa", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.target_visa_type)


# ---------------------------------------------------------------------------
# Maqsad: viza turi, dastur, muassasa, motivatsiya sababi
# ---------------------------------------------------------------------------
@router.callback_query(Flow.target_visa_type, F.data.startswith("target_visa:"))
async def get_target_visa(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    visa_code = callback.data.split(":")[1]
    await state.update_data(target_visa_type=visa_code)
    await callback.message.edit_text(t("ask_target_program", lang))
    await state.set_state(Flow.target_program)
    await callback.answer()


@router.message(Flow.target_program)
async def get_target_program(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(target_program=message.text.strip())
    kb = back_kb(lang, STEP_BACK_MAP["target_institution"][0])
    await message.answer(t("ask_target_institution", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.target_institution)


@router.message(Flow.target_institution)
async def get_target_institution(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(target_institution=message.text.strip())
    kb = back_kb(lang, STEP_BACK_MAP["target_institution_address"][0])
    await message.answer(t("ask_target_institution_address", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.target_institution_address)


@router.message(Flow.target_institution_address)
async def get_target_institution_address(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(target_institution_address=message.text.strip())
    kb = back_kb(lang, STEP_BACK_MAP["motivation_reason"][0])
    await message.answer(t("ask_motivation_reason", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.motivation_reason)


@router.message(Flow.motivation_reason)
async def get_motivation_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(motivation_reason=message.text.strip())
    data = await state.get_data()  # yangilangan to'liq ma'lumot

    preview = build_preview_text(data, lang)

    kb = InlineKeyboardBuilder()
    kb.button(text=t("preview_confirm", lang), callback_data="preview:confirm")
    kb.button(text=t("preview_restart", lang), callback_data="preview:restart")
    kb.adjust(1)
    await message.answer(preview, reply_markup=kb.as_markup())
    await state.set_state(Flow.previewing)


def build_preview_text(data: dict, lang: str) -> str:
    """To'plangan ma'lumotlar asosida o'qish uchun qulay umumiy ko'rinish tayyorlaydi."""
    education_lines = "\n".join(f"   • {e}" for e in data.get("education_list", [])) or "   —"
    experience_lines = "\n".join(f"   • {e}" for e in data.get("experience_list", [])) or "   —"

    visa_code = data.get("target_visa_type", "")
    visa_name = VISA_TYPES.get(visa_code, {}).get(lang, visa_code)

    text = t("preview_title", lang)
    text += (
        f"👤 {data.get('full_name', '')}\n"
        f"🎂 {data.get('birth_date', '')}    🌍 {data.get('nationality', '')}\n"
        f"📍 {data.get('address', '')}\n"
        f"📞 {data.get('phone', '')}    ✉️ {data.get('email', '')}\n\n"
        f"🎓 Ta'lim / Education:\n{education_lines}\n\n"
        f"💼 Tajriba / Experience:\n{experience_lines}\n\n"
        f"🗣 {data.get('languages_skill', '')}\n"
        f"💻 {data.get('it_skills', '')}\n"
        f"🤝 {data.get('soft_skills', '')}\n\n"
        f"🎯 {visa_name}\n"
        f"📚 {data.get('target_program', '')} — {data.get('target_institution', '')}\n"
    )
    return text


@router.callback_query(Flow.previewing, F.data == "preview:restart")
async def preview_restart(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    # Boshidan qaytadan to'ldirish - oldingi javoblarni tozalaymiz, faqat
    # tilni saqlab qolamiz
    await state.set_data({"lang": lang})
    await callback.message.edit_text(t("ask_full_name", lang))
    await state.set_state(Flow.full_name)
    await callback.answer()


@router.callback_query(Flow.previewing, F.data == "preview:confirm")
async def preview_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    user_id = callback.from_user.id

    # Bepul huquq mavjudligini tekshiramiz
    if db.consume_free_credit(user_id):
        await show_template_choice(callback.message, state, lang, edit=True)
        await callback.answer()
        return

    # Bepul huquq yo'q - to'lov oqimini boshlaymiz
    referral_link = f"https://t.me/{BOT_USERNAME}?start=REF{user_id}" if BOT_USERNAME else "—"
    referral_count = db.count_referrals(user_id)

    # Visa karta qo'shilgan bo'lsa, ikkinchi karta ham ko'rsatiladi
    visa_section = ""
    if PAYMENT_VISA_CARD_NUMBER:
        visa_section = f"\n\n💳 2-karta (Visa/Mastercard):\n{PAYMENT_VISA_CARD_NUMBER}\n{PAYMENT_VISA_CARD_OWNER}"

    text = t("no_free_credits_intro", lang) + "\n\n"
    text += t("payment_info", lang).format(
        price_cv=f"{PRICE_CV:,}".replace(",", " "),
        price_letter=f"{PRICE_LETTER:,}".replace(",", " "),
        total=f"{PRICE_CV + PRICE_LETTER:,}".replace(",", " "),
        card_number=PAYMENT_CARD_NUMBER,
        card_owner=PAYMENT_CARD_OWNER,
        visa_section=visa_section,
    )
    text += "\n\n" + t("referral_offer", lang).format(
        referral_link=referral_link,
        referral_count=referral_count,
        needed=REFERRALS_FOR_FREE_CREDIT,
    )

    kb = InlineKeyboardBuilder()
    kb.button(text=t("send_screenshot_button", lang), callback_data="payment:send_screenshot")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


async def show_template_choice(message: Message, state: FSMContext, lang: str, edit: bool = False):
    kb = InlineKeyboardBuilder()
    kb.button(text=t("template_yellow", lang), callback_data="template:yellow")
    kb.button(text=t("template_blue", lang), callback_data="template:blue")
    kb.button(text=t("template_green", lang), callback_data="template:green")
    kb.adjust(1)
    if edit:
        await message.edit_text(t("choose_template", lang), reply_markup=kb.as_markup())
    else:
        await message.answer(t("choose_template", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.choosing_template)


@router.callback_query(F.data == "payment:send_screenshot")
async def ask_payment_screenshot(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await callback.message.answer(t("ask_payment_screenshot", lang))
    await state.set_state(Flow.awaiting_payment_screenshot)
    await callback.answer()


@router.message(Flow.awaiting_payment_screenshot, F.photo)
async def receive_payment_screenshot(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    user_id = message.from_user.id

    photo_file_id = message.photo[-1].file_id
    total = PRICE_CV + PRICE_LETTER
    payment_id = db.create_payment_request(user_id, "bundle", total, photo_file_id)

    await message.answer(t("payment_submitted", lang))
    await state.set_state(Flow.previewing)  # admin javobini kutish holatiga o'xshash

    # Adminlarga xabar yuboramiz
    bot = message.bot
    username_part = f"@{message.from_user.username}" if message.from_user.username else str(user_id)
    admin_caption = (
        f"💳 Yangi to'lov so'rovi #{payment_id}\n"
        f"Foydalanuvchi: {username_part} (ID: {user_id})\n"
        f"Summa: {total:,} so'm".replace(",", " ")
    )
    admin_kb = InlineKeyboardBuilder()
    admin_kb.button(text="✅ Tasdiqlash", callback_data=f"admin_payment:approve:{payment_id}")
    admin_kb.button(text="❌ Rad etish", callback_data=f"admin_payment:reject:{payment_id}")
    admin_kb.adjust(2)

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                admin_id,
                photo_file_id,
                caption=admin_caption,
                reply_markup=admin_kb.as_markup(),
            )
        except Exception:
            logging.exception("Adminga to'lov xabarini yuborishda xatolik: %s", admin_id)


@router.message(Flow.awaiting_payment_screenshot)
async def payment_screenshot_invalid(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await message.answer(t("photo_error", lang))


@router.callback_query(F.data.startswith("admin_payment:"))
async def handle_admin_payment_decision(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return

    _, action, payment_id_str = callback.data.split(":")
    payment_id = int(payment_id_str)
    payment = db.get_payment(payment_id)

    if not payment:
        await callback.answer("To'lov topilmadi.", show_alert=True)
        return

    approved = action == "approve"
    db.resolve_payment(payment_id, approved)

    user_id = payment["user_id"]
    bot = callback.bot

    if approved:
        db.add_free_credit(user_id, 1)
        db.consume_free_credit(user_id)  # to'lov tasdiqlangan zahoti shu huquqni ishlatamiz

    await callback.message.edit_caption(
        caption=callback.message.caption + f"\n\n{'✅ TASDIQLANDI' if approved else '❌ RAD ETILDI'}"
    )
    await callback.answer()

    # Foydalanuvchiga xabar beramiz
    try:
        user_row = db.get_or_create_user(user_id)
        user_lang = user_row["lang"] if user_row else "en"

        if approved:
            await bot.send_message(user_id, t("payment_approved_user", user_lang))

            kb = InlineKeyboardBuilder()
            kb.button(text=t("template_yellow", user_lang), callback_data="template:yellow")
            kb.button(text=t("template_blue", user_lang), callback_data="template:blue")
            kb.button(text=t("template_green", user_lang), callback_data="template:green")
            kb.adjust(1)
            await bot.send_message(
                user_id,
                t("choose_template", user_lang),
                reply_markup=kb.as_markup(),
            )

            # Foydalanuvchining FSM holatini "choosing_template"ga to'g'ridan-to'g'ri
            # o'rnatamiz, chunki bu hodisa admin tomonidan boshqa context'da
            # ishga tushirilgan (foydalanuvchining o'z xabari emas).
            user_key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
            user_fsm = FSMContext(storage=storage, key=user_key)
            await user_fsm.set_state(Flow.choosing_template)
        else:
            await bot.send_message(user_id, t("payment_rejected_user", user_lang))
    except Exception:
        logging.exception("Foydalanuvchiga to'lov natijasini yuborishda xatolik: %s", user_id)


@router.callback_query(Flow.choosing_template, F.data.startswith("template:"))
async def choose_template_and_generate(callback: CallbackQuery, state: FSMContext):
    template = callback.data.split(":")[1]
    await state.update_data(cv_template=template)
    data = await state.get_data()
    lang = data["lang"]

    await callback.message.edit_text(t("generating", lang))
    await callback.answer()
    await state.set_state(Flow.generating)

    try:
        await generate_and_send_documents(callback.message, data)
    except Exception as e:
        logging.exception("Hujjat generatsiyasida xatolik")
        await callback.message.answer(f"❌ Xatolik yuz berdi: {e}")

    # Asosiy menyuga qaytarish
    kb = InlineKeyboardBuilder()
    kb.button(text=t("menu_cv", lang), callback_data="menu:cv")
    kb.button(text=t("menu_checklist", lang), callback_data="menu:checklist")
    kb.adjust(1)
    await callback.message.answer(t("main_menu", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.main_menu)


# ---------------------------------------------------------------------------
# Hujjatlarni generatsiya qilish va yuborish
# ---------------------------------------------------------------------------
async def generate_and_send_documents(message: Message, data: dict):
    lang = data["lang"]
    user_id = message.from_user.id

    personal = {
        "full_name": data.get("full_name", ""),
        "birth_date": data.get("birth_date", ""),
        "nationality": data.get("nationality", ""),
        "address": data.get("address", ""),
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "photo_path": data.get("photo_path", ""),
    }

    # AI uchun yagona kontekst ma'lumotlar lug'ati
    ai_input = {
        **personal,
        "education": data.get("education_list", []),
        "work_experience": data.get("experience_list", []),
        "languages": data.get("languages_skill", ""),
        "it_skills": data.get("it_skills", ""),
        "soft_skills": data.get("soft_skills", ""),
        "target_program": data.get("target_program", ""),
        "target_institution": data.get("target_institution", ""),
        "target_visa_type": data.get("target_visa_type", ""),
        "motivation_reason": data.get("motivation_reason", ""),
    }

    # 1) CV bo'limlarini generatsiya qilish (hujjat har doim nemis tilida)
    cv_sections = generate_cv_sections(ai_input, DOCUMENT_LANG)

    user_dir = os.path.join(OUTPUT_DIR, str(user_id))
    cv_path = os.path.join(user_dir, "Lebenslauf.docx")
    cv_template = data.get("cv_template", "yellow")
    build_cv_docx(personal, cv_sections, cv_path, template=cv_template)

    # 2) Motivatsion xatni generatsiya qilish (hujjat har doim nemis tilida)
    letter_text = generate_motivation_letter(ai_input, DOCUMENT_LANG)

    recipient = {
        "name": "",
        "institution": data.get("target_institution", ""),
        "address": data.get("target_institution_address", ""),
    }
    letter_path = os.path.join(user_dir, "Motivationsschreiben.docx")
    build_motivation_letter_docx(personal, recipient, letter_text, letter_path)

    # 3) Har bir .docx hujjatni PDF formatiga ham konvertatsiya qilamiz
    #    (LibreOffice mavjud bo'lmasa, convert_to_pdf None qaytaradi va biz
    #    shunchaki .docx faylni yuborish bilan davom etamiz).
    cv_pdf_path = convert_to_pdf(cv_path)
    letter_pdf_path = convert_to_pdf(letter_path)

    # 4) Foydalanuvchiga yuborish
    await message.answer(t("done", lang))

    await message.answer_document(FSInputFile(cv_path))
    if cv_pdf_path:
        await message.answer_document(FSInputFile(cv_pdf_path))

    await message.answer_document(FSInputFile(letter_path))
    if letter_pdf_path:
        await message.answer_document(FSInputFile(letter_pdf_path))

    # 5) Tegishli viza checklisti ham qo'shib yuboriladi
    visa_code = data.get("target_visa_type", "")
    if visa_code:
        visa_name = VISA_TYPES[visa_code][lang]
        items = get_checklist(visa_code, lang)
        text = t("checklist_title", lang).format(visa=visa_name)
        text += "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))
        text += t("checklist_footer", lang)
        await message.answer(text)

    # 6) Profilni keyingi safar uchun saqlaymiz (maqsad/dastur qismidan tashqari -
    #    shaxsiy ma'lumotlar, ta'lim, tajriba, ko'nikmalar saqlanadi)
    db.save_profile(user_id, {
        "full_name": personal["full_name"],
        "birth_date": personal["birth_date"],
        "nationality": personal["nationality"],
        "address": personal["address"],
        "phone": personal["phone"],
        "email": personal["email"],
        "photo_path": personal["photo_path"],
        "education_list": data.get("education_list", []),
        "experience_list": data.get("experience_list", []),
        "languages_skill": data.get("languages_skill", ""),
        "it_skills": data.get("it_skills", ""),
        "soft_skills": data.get("soft_skills", ""),
    })

    # 7) Statistika uchun yaratilgan hujjatlarni qaydga olamiz
    db.log_document_created(user_id, "cv")
    db.log_document_created(user_id, "letter")


# ---------------------------------------------------------------------------
# Ishga tushirish
# ---------------------------------------------------------------------------
async def main():
    db.init_db()
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
