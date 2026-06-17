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
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import TELEGRAM_BOT_TOKEN, LANGUAGES, VISA_TYPES, OUTPUT_DIR
from visa_checklists import get_checklist
from ai_generator import generate_cv_sections, generate_motivation_letter
from document_generator import build_cv_docx, build_motivation_letter_docx

logging.basicConfig(level=logging.INFO)
router = Router()

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

    generating = State()


# ---------------------------------------------------------------------------
# Yordamchi: tilga mos matnlar
# ---------------------------------------------------------------------------
TEXTS = {
    "choose_language": {
        "uz": "Tilni tanlang:",
        "ru": "Выберите язык:",
        "en": "Choose your language:",
    },
    "main_menu": {
        "uz": "Nima qilishni xohlaysiz?",
        "ru": "Что вы хотите сделать?",
        "en": "What would you like to do?",
    },
    "menu_cv": {
        "uz": "📄 CV + Motivatsion xat tayyorlash",
        "ru": "📄 Подготовить CV + мотивационное письмо",
        "en": "📄 Prepare CV + Motivation Letter",
    },
    "menu_checklist": {
        "uz": "✅ Hujjatlar checklisti",
        "ru": "✅ Чек-лист документов",
        "en": "✅ Document checklist",
    },
    "choose_visa": {
        "uz": "Viza turini tanlang:",
        "ru": "Выберите тип визы:",
        "en": "Choose visa type:",
    },
    "ask_full_name": {
        "uz": "Ism va familiyangizni to'liq kiriting:",
        "ru": "Введите ваше полное имя и фамилию:",
        "en": "Enter your full name:",
    },
    "ask_birth_date": {
        "uz": "Tug'ilgan sanangizni kiriting (KK.OO.YYYY):",
        "ru": "Введите дату рождения (ДД.ММ.ГГГГ):",
        "en": "Enter your date of birth (DD.MM.YYYY):",
    },
    "ask_nationality": {
        "uz": "Fuqaroligingizni kiriting:",
        "ru": "Введите ваше гражданство:",
        "en": "Enter your nationality:",
    },
    "ask_address": {
        "uz": "Manzilingizni kiriting (shahar, mamlakat):",
        "ru": "Введите ваш адрес (город, страна):",
        "en": "Enter your address (city, country):",
    },
    "ask_phone": {
        "uz": "Telefon raqamingizni kiriting:",
        "ru": "Введите номер телефона:",
        "en": "Enter your phone number:",
    },
    "ask_email": {
        "uz": "Email manzilingizni kiriting:",
        "ru": "Введите ваш email:",
        "en": "Enter your email address:",
    },
    "ask_photo": {
        "uz": "📷 Endi CV uchun fotosuratingizni yuboring (oddiy rasm sifatida, fayl emas — pasport/biometrik fotosurat tavsiya etiladi, oq fon, rasmiy ko'rinish):",
        "ru": "📷 Теперь отправьте ваше фото для CV (как обычное фото, не файл — рекомендуется паспортное/биометрическое фото на белом фоне):",
        "en": "📷 Now send your photo for the CV (as a regular photo, not a file — a passport-style/biometric photo with a white background is recommended):",
    },
    "photo_error": {
        "uz": "⚠️ Iltimos, rasm yuboring (skrepka -> Galereya/Camera orqali oddiy fotosurat sifatida, fayl/dokument sifatida emas).",
        "ru": "⚠️ Пожалуйста, отправьте фото (через скрепку -> Галерея/Камера как обычное фото, не как файл/документ).",
        "en": "⚠️ Please send a photo (via the attachment icon -> Gallery/Camera as a regular photo, not as a file/document).",
    },
    "ask_education": {
        "uz": "Ta'lim haqida yozing (daraja, muassasa, yillar, masalan: 'Bakalavr, Informatika, TATU, 2019-2023'):",
        "ru": "Напишите об образовании (степень, учебное заведение, годы, напр.: 'Бакалавр, Информатика, ТУИТ, 2019-2023'):",
        "en": "Write about your education (degree, institution, years, e.g. 'Bachelor, Computer Science, TUIT, 2019-2023'):",
    },
    "ask_education_more": {
        "uz": "Yana ta'lim ma'lumoti qo'shmoqchimisiz?",
        "ru": "Хотите добавить ещё одно образование?",
        "en": "Add another education entry?",
    },
    "ask_experience": {
        "uz": "Ish tajribangiz haqida yozing (lavozim, kompaniya, yillar, asosiy vazifalar):",
        "ru": "Напишите о вашем опыте работы (должность, компания, годы, основные обязанности):",
        "en": "Write about your work experience (position, company, years, key responsibilities):",
    },
    "ask_experience_more": {
        "uz": "Yana ish tajribasi qo'shmoqchimisiz?",
        "ru": "Хотите добавить ещё один опыт работы?",
        "en": "Add another work experience entry?",
    },
    "ask_languages_skill": {
        "uz": "Bilgan tillaringizni va darajangizni yozing (masalan: O'zbek - ona tili, Ingliz - B2, Nemis - A2):",
        "ru": "Напишите ваши языки и уровень (напр.: Узбекский - родной, Английский - B2, Немецкий - A2):",
        "en": "List your languages and levels (e.g. Uzbek - native, English - B2, German - A2):",
    },
    "ask_it_skills": {
        "uz": "IT/texnik ko'nikmalaringizni yozing (yo'q bo'lsa, '-' yozing):",
        "ru": "Напишите ваши IT/технические навыки (если нет, напишите '-'):",
        "en": "List your IT/technical skills (write '-' if none):",
    },
    "ask_soft_skills": {
        "uz": "Shaxsiy/soft skill larni yozing (masalan: jamoada ishlash, vaqtni boshqarish):",
        "ru": "Напишите ваши личные качества/soft skills (напр.: командная работа, тайм-менеджмент):",
        "en": "List your soft skills (e.g. teamwork, time management):",
    },
    "ask_target_program": {
        "uz": "Qaysi dastur/lavozimga ariza topshirmoqdasiz? (masalan: 'Informatika magistraturasi' yoki 'Software Developer lavozimi')",
        "ru": "На какую программу/должность вы подаёте заявку? (напр.: 'Магистратура по информатике' или 'должность Software Developer')",
        "en": "Which program/position are you applying for? (e.g. 'Master's in Computer Science' or 'Software Developer position')",
    },
    "ask_target_institution": {
        "uz": "Universitet/kompaniya nomini kiriting:",
        "ru": "Введите название университета/компании:",
        "en": "Enter the university/company name:",
    },
    "ask_target_institution_address": {
        "uz": "Universitet/kompaniya manzilini kiriting (agar bilmasangiz, '-' yozing):",
        "ru": "Введите адрес университета/компании (если не знаете, напишите '-'):",
        "en": "Enter the university/company address (write '-' if unknown):",
    },
    "ask_motivation_reason": {
        "uz": "Nima uchun aynan shu dastur/kompaniya va Germaniyani tanladingiz? Qisqacha yozing — bu motivatsion xat uchun muhim:",
        "ru": "Почему вы выбрали именно эту программу/компанию и Германию? Напишите кратко — это важно для мотивационного письма:",
        "en": "Why did you choose this program/company and Germany specifically? Write briefly — this is important for the motivation letter:",
    },
    "generating": {
        "uz": "⏳ Hujjatlaringiz tayyorlanmoqda, biroz kuting...",
        "ru": "⏳ Готовим ваши документы, подождите немного...",
        "en": "⏳ Preparing your documents, please wait...",
    },
    "done": {
        "uz": "✅ Tayyor! Hujjatlaringiz (nemis tilida) quyida.\n\n⚠️ Eslatma: bu hujjatlar AI yordamida tayyorlangan qoralama. Topshirishdan oldin ularni o'zingiz va imkon bo'lsa mutaxassis bilan tekshirib chiqing.",
        "ru": "✅ Готово! Ваши документы (на немецком языке) ниже.\n\n⚠️ Примечание: это черновик, подготовленный с помощью AI. Перед подачей проверьте документы самостоятельно и, если возможно, со специалистом.",
        "en": "✅ Done! Your documents (in German) are below.\n\n⚠️ Note: these documents are an AI-generated draft. Please review them yourself, and ideally with a professional, before submission.",
    },
    "yes": {"uz": "Ha", "ru": "Да", "en": "Yes"},
    "no": {"uz": "Yo'q", "ru": "Нет", "en": "No"},
    "checklist_title": {
        "uz": "📋 {visa} uchun kerakli hujjatlar ro'yxati:\n\n",
        "ru": "📋 Список документов для визы «{visa}»:\n\n",
        "en": "📋 Document checklist for {visa}:\n\n",
    },
    "checklist_footer": {
        "uz": "\n\n⚠️ Diqqat: talablar elchixonaga va vaqtga qarab o'zgarishi mumkin. Har doim rasmiy elchixona saytidan tekshirib chiqing.",
        "ru": "\n\n⚠️ Внимание: требования могут отличаться в зависимости от посольства и времени. Всегда проверяйте на официальном сайте посольства.",
        "en": "\n\n⚠️ Note: requirements may vary by embassy and over time. Always verify on the official embassy website.",
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


# ---------------------------------------------------------------------------
# Boshlanish va til tanlash
# ---------------------------------------------------------------------------
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
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

    kb = InlineKeyboardBuilder()
    kb.button(text=t("menu_cv", lang), callback_data="menu:cv")
    kb.button(text=t("menu_checklist", lang), callback_data="menu:checklist")
    kb.adjust(1)

    await callback.message.edit_text(t("main_menu", lang), reply_markup=kb.as_markup())
    await state.set_state(Flow.main_menu)
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
    await callback.message.edit_text(t("ask_full_name", lang))
    await state.set_state(Flow.full_name)
    await callback.answer()


@router.message(Flow.full_name)
async def get_full_name(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(full_name=message.text.strip())
    await message.answer(t("ask_birth_date", lang))
    await state.set_state(Flow.birth_date)


@router.message(Flow.birth_date)
async def get_birth_date(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(birth_date=message.text.strip())
    await message.answer(t("ask_nationality", lang))
    await state.set_state(Flow.nationality)


@router.message(Flow.nationality)
async def get_nationality(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(nationality=message.text.strip())
    await message.answer(t("ask_address", lang))
    await state.set_state(Flow.address)


@router.message(Flow.address)
async def get_address(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(address=message.text.strip())
    await message.answer(t("ask_phone", lang))
    await state.set_state(Flow.phone)


@router.message(Flow.phone)
async def get_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(phone=message.text.strip())
    await message.answer(t("ask_email", lang))
    await state.set_state(Flow.email)


@router.message(Flow.email)
async def get_email(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(email=message.text.strip())
    await message.answer(t("ask_photo", lang))
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
    await message.answer(t("ask_education", lang))
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
        await callback.message.edit_text(t("ask_education", lang))
        await state.set_state(Flow.education_entry)
    else:
        await callback.message.edit_text(t("ask_experience", lang))
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
        await callback.message.edit_text(t("ask_experience", lang))
        await state.set_state(Flow.experience_entry)
    else:
        await callback.message.edit_text(t("ask_languages_skill", lang))
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
    await message.answer(t("ask_it_skills", lang))
    await state.set_state(Flow.it_skills)


@router.message(Flow.it_skills)
async def get_it_skills(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(it_skills=message.text.strip())
    await message.answer(t("ask_soft_skills", lang))
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
    await message.answer(t("ask_target_institution", lang))
    await state.set_state(Flow.target_institution)


@router.message(Flow.target_institution)
async def get_target_institution(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(target_institution=message.text.strip())
    await message.answer(t("ask_target_institution_address", lang))
    await state.set_state(Flow.target_institution_address)


@router.message(Flow.target_institution_address)
async def get_target_institution_address(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(target_institution_address=message.text.strip())
    await message.answer(t("ask_motivation_reason", lang))
    await state.set_state(Flow.motivation_reason)


@router.message(Flow.motivation_reason)
async def get_motivation_reason_and_generate(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    await state.update_data(motivation_reason=message.text.strip())
    data = await state.get_data()  # yangilangan to'liq ma'lumot

    await message.answer(t("generating", lang))
    await state.set_state(Flow.generating)

    try:
        await generate_and_send_documents(message, data)
    except Exception as e:
        logging.exception("Hujjat generatsiyasida xatolik")
        await message.answer(f"❌ Xatolik yuz berdi: {e}")

    # Asosiy menyuga qaytarish
    kb = InlineKeyboardBuilder()
    kb.button(text=t("menu_cv", lang), callback_data="menu:cv")
    kb.button(text=t("menu_checklist", lang), callback_data="menu:checklist")
    kb.adjust(1)
    await message.answer(t("main_menu", lang), reply_markup=kb.as_markup())
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
    build_cv_docx(personal, cv_sections, cv_path)

    # 2) Motivatsion xatni generatsiya qilish (hujjat har doim nemis tilida)
    letter_text = generate_motivation_letter(ai_input, DOCUMENT_LANG)

    recipient = {
        "name": "",
        "institution": data.get("target_institution", ""),
        "address": data.get("target_institution_address", ""),
    }
    letter_path = os.path.join(user_dir, "Motivationsschreiben.docx")
    build_motivation_letter_docx(personal, recipient, letter_text, letter_path)

    # 3) Foydalanuvchiga yuborish
    await message.answer(t("done", lang))
    await message.answer_document(FSInputFile(cv_path))
    await message.answer_document(FSInputFile(letter_path))

    # 4) Tegishli viza checklisti ham qo'shib yuboriladi
    visa_code = data.get("target_visa_type", "")
    if visa_code:
        visa_name = VISA_TYPES[visa_code][lang]
        items = get_checklist(visa_code, lang)
        text = t("checklist_title", lang).format(visa=visa_name)
        text += "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))
        text += t("checklist_footer", lang)
        await message.answer(text)


# ---------------------------------------------------------------------------
# Ishga tushirish
# ---------------------------------------------------------------------------
async def main():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
