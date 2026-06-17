# Germaniya elchixonasi uchun hujjatlar tayyorlovchi Telegram bot

CV (Lebenslauf), motivatsion xat (Motivationsschreiben) va viza turi bo'yicha
kerakli hujjatlar checklistini avtomatik tayyorlaydigan Telegram bot.

## Qanday ishlaydi

1. Foydalanuvchi botga /start yozadi, **interfeys tilini** tanlaydi (uz/ru/en) —
   bot savollarni shu tilda beradi
2. Ikki yo'ldan birini tanlaydi:
   - **CV + Motivatsion xat tayyorlash** — bot bosqichma-bosqich savol beradi
     (ism, ta'lim, ish tajribasi, ko'nikmalar, maqsad dastur/lavozim, sabab)
   - **Hujjatlar checklisti** — faqat viza turini tanlab, kerakli hujjatlar
     ro'yxatini darrov oladi
3. CV/xat so'ralganda, javoblar OpenAI API'ga (GPT) yuboriladi. **Hujjatning o'zi
   (CV va motivatsion xat) har doim nemis tilida chiqariladi** — interfeys
   tilidan qat'i nazar, chunki Germaniya elchixonasi/universitet/ish beruvchi
   buni talab qiladi. Foydalanuvchi ma'lumotlarni o'zbek/rus/ingliz tilida
   kiritsa ham, GPT ularni tarjima qilib, Europass/DIN 5008 standartiga
   mos nemis tilidagi professional matn yaratadi.
4. Matnlar Word (.docx) hujjatlariga joylanadi va foydalanuvchiga yuboriladi

> **Interfeys tili** (`lang`) va **hujjat tili** (`DOCUMENT_LANG`, `bot.py`da
> qattiq belgilangan `"German"`) ataylab ajratilgan — bu ikkisini bot.py
> ichida alohida o'zgaruvchi sifatida ko'rasiz. Agar kelajakda foydalanuvchiga
> hujjat tilini (masalan nemis/ingliz) tanlash imkonini bermoqchi bo'lsangiz,
> shu joyga viza-turi tanlovidan keyin yana bitta tanlov qadami qo'shiladi.

## O'rnatish

```bash
# 1. Virtual environment yaratish (tavsiya etiladi)
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Kutubxonalarni o'rnatish
pip install -r requirements.txt

# 3. Maxfiy kalitlarni sozlash
cp .env.example .env
# .env faylini ochib, haqiqiy tokenlarni kiriting:
#   TELEGRAM_BOT_TOKEN -> @BotFather orqali olinadi
#   OPENAI_API_KEY     -> https://platform.openai.com/api-keys dan olinadi

# 4. Botni ishga tushirish
python bot.py
```

## Fayllar tuzilishi

| Fayl | Vazifasi |
|---|---|
| `bot.py` | Asosiy bot logikasi — FSM holatlari, savol-javob oqimi |
| `config.py` | Tokenlar, tillar, viza turlari ro'yxati |
| `visa_checklists.py` | Har bir viza turi uchun statik hujjatlar ro'yxati (uz/ru/en) |
| `ai_generator.py` | OpenAI API chaqiruvlari — CV bo'limlari va motivatsion xat matnini yaratish |
| `document_generator.py` | python-docx orqali Word fayllarini yaratish |
| `requirements.txt` | Python kutubxonalari ro'yxati |

## Keyingi qadamlar (kengaytirish uchun)

- **Saqlash**: hozir foydalanuvchi ma'lumotlari faqat xotirada (MemoryStorage)
  saqlanadi — bot qayta ishga tushganda yo'qoladi. Productionga chiqarishdan
  oldin SQLite/PostgreSQL + FSM storage (masalan RedisStorage) qo'shish kerak.
- **PDF eksport**: hozir faqat .docx chiqadi. Agar PDF kerak bo'lsa, LibreOffice
  headless rejimda (`soffice --headless --convert-to pdf`) yoki `docx2pdf`
  kutubxonasidan foydalanish mumkin (serverda LibreOffice o'rnatilgan bo'lishi kerak).
- **To'lov tizimi**: agar bot pullik xizmat bo'lsa, Telegram Payments API yoki
  Click/Payme integratsiyasini qo'shish kerak.
- **Veb-sayt versiyasi**: shu logikaning katta qismi (ai_generator.py,
  document_generator.py, visa_checklists.py) o'zgarishsiz qayta ishlatiladi —
  faqat frontend (forma) va backend endpoint (Flask/FastAPI) qo'shiladi.
- **Validatsiya**: hozir input validatsiyasi minimal (masalan sana formatini
  tekshirish yo'q). Productionga chiqarishdan oldin qo'shish tavsiya etiladi.

## Muhim eslatma

Bot tomonidan yaratilgan hujjatlar AI yordamida tuzilgan qoralama hisoblanadi.
Elchixonaga topshirishdan oldin foydalanuvchi ularni albatta o'zi tekshirib,
imkon bo'lsa mutaxassis (viza konsultanti) bilan ko'rib chiqishi kerak — bu
haqida bot foydalanuvchiga avtomatik eslatma yuboradi.
