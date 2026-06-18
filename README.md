# Germaniya elchixonasi uchun hujjatlar tayyorlovchi Telegram bot

CV (Lebenslauf), motivatsion xat (Motivationsschreiben) va viza turi bo'yicha
kerakli hujjatlar checklistini avtomatik tayyorlaydigan Telegram bot.

## Qanday ishlaydi

1. Foydalanuvchi botga /start yozadi, **interfeys tilini** tanlaydi (uz/ru/en/
   tr/es/hi/uk — 7 til) — bot savollarni shu tilda beradi
2. Ikki yo'ldan birini tanlaydi:
   - **CV + Motivatsion xat tayyorlash** — bot bosqichma-bosqich savol beradi
     (ism, **fotosurat (majburiy)**, ta'lim, ish tajribasi, ko'nikmalar, maqsad
     dastur/lavozim, sabab, **CV dizayn shabloni**) — fotosurat CV sarlavhasiga
     avtomatik joylanadi
   - **Hujjatlar checklisti** — faqat viza turini tanlab, kerakli hujjatlar
     ro'yxatini darrov oladi
3. CV/xat so'ralganda, javoblar OpenAI API'ga (GPT) yuboriladi. **Hujjatning o'zi
   (CV va motivatsion xat) har doim nemis tilida chiqariladi** — interfeys
   tilidan qat'i nazar, chunki Germaniya elchixonasi/universitet/ish beruvchi
   buni talab qiladi. Foydalanuvchi ma'lumotlarni o'zbek/rus/ingliz tilida
   kiritsa ham, GPT ularni tarjima qilib, Europass/DIN 5008 standartiga
   mos nemis tilidagi professional matn yaratadi.
4. Barcha ma'lumotlar yig'ilgandan keyin, bot **umumiy ko'rinishni (preview)**
   ko'rsatadi — foydalanuvchi hammasini tekshirib, "Hammasi to'g'ri, davom et"
   yoki "Boshidan qaytadan to'ldirish" tugmalaridan birini tanlaydi
5. Tasdiqlangandan keyin, CV dizayn shabloni tanlanadi, so'ngra matnlar Word
   (.docx) hujjatlariga joylanadi, foydalanuvchi tanlagan dizayn shabloniga
   (klassik/zamonaviy/rangli) mos rang va uslubda. Shu bilan birga, agar server
   LibreOffice'ga ega bo'lsa, har bir hujjat avtomatik .pdf formatiga ham
   konvertatsiya qilinadi — foydalanuvchiga ikkala format (.docx va .pdf)
   ham yuboriladi

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

- **Saqlash**: `database.py` orqali SQLite ulandi — foydalanuvchi profili
  (shaxsiy ma'lumotlar, ta'lim, tajriba, ko'nikmalar) bot qayta ishga tushgandan
  keyin ham saqlanib qoladi, va keyingi CV so'rovida "eski ma'lumotdan
  foydalanish" sifatida taklif qilinadi. Lekin **diqqat**: foydalanuvchi
  yuborgan fotosurat fayli (`photo_path`) serverning vaqtinchalik disk
  joyida (`generated_files/`) saqlanadi — agar Railway konteyneri qayta
  qurilsa (re-deploy) va persistent volume ulanmagan bo'lsa, bu fayl
  yo'qolishi mumkin, profil esa rasm yo'lini eslab qoladi-yu, fayl mavjud
  bo'lmaydi. To'liq ishonchli saqlash uchun rasmni bulutga (S3 va h.k.)
  yuklash kerak bo'ladi — hozircha bu soddalashtirilgan versiya.
  FSM holati (suhbat davomidagi vaqtinchalik javoblar) hali ham xotirada
  (MemoryStorage) saqlanadi — bot qayta ishga tushganda **joriy** to'ldirish
  jarayoni yo'qoladi, lekin **yakunlangan** profillar SQLite'da saqlanib qoladi.
- **PDF eksport**: qo'shildi — `document_generator.py`dagi `convert_to_pdf()`
  funksiyasi LibreOffice'ni headless rejimda chaqirib (`soffice --headless
  --convert-to pdf`) .docx hujjatlarni .pdf'ga aylantiradi. Buning ishlashi
  uchun serverda LibreOffice o'rnatilgan bo'lishi kerak — Railway uchun bu
  `nixpacks.toml` faylida `libreoffice-fresh` paketi orqali ta'minlangan.
  Agar LibreOffice topilmasa, funksiya `None` qaytaradi va bot xatosiz davom
  etib, faqat .docx faylni yuboradi.
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
