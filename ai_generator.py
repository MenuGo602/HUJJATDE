# ai_generator.py
"""
Bu modul foydalanuvchi kiritgan ma'lumotlar asosida OpenAI API (GPT) yordamida
Germaniya standartiga (Europass / DIN 5008) mos Lebenslauf bo'limlari
va motivatsion xat matnini generatsiya qiladi.
"""

import json
from openai import OpenAI
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

# Narx/sifat nisbati yaxshi model. Agar sifatni oshirish kerak bo'lsa "gpt-4o"
# ga, arzonlashtirish kerak bo'lsa "gpt-4o-mini" ga almashtiring.
MODEL = "gpt-4o-mini"


def _call_openai(system_prompt: str, user_prompt: str, max_tokens: int = 2000, json_mode: bool = False) -> str:
    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        **kwargs,
    )
    return response.choices[0].message.content


def generate_cv_sections(user_data: dict, lang: str = "German") -> dict:
    """
    user_data: foydalanuvchi forma orqali kiritgan ma'lumotlar (ism, ta'lim,
    ish tajribasi, ko'nikmalar, tillar va h.k.) — bu ma'lumotlar foydalanuvchi
    tomonidan istalgan tilda (uz/ru/en) kiritilgan bo'lishi mumkin.

    `lang` — bu hujjat tili, ya'ni CV matni qaysi tilda yozilishi kerak.
    Germaniya elchixonasi/universitet/ish beruvchi uchun bu har doim
    nemis tili (standart qiymat "German"), interfeys tilidan mustaqil.

    Qaytaradi: lug'at, har bir Europass CV bo'limi uchun tayyor matn bilan:
    {
        "profile_summary": "...",
        "work_experience": [...],
        "education": [...],
        "skills": {...}
    }
    """
    system_prompt = (
        "You are an expert career consultant specializing in CVs for the German job and "
        "study market, following the Europass and DIN 5008 standards. "
        "The user's raw input data may be written in any language (Uzbek, Russian, or "
        "English) — translate and adapt the meaning, do not just copy the source wording. "
        "Given raw user data, produce polished, professional CV section content. "
        "Be concise, use strong action verbs, quantify achievements where possible, "
        "and avoid generic filler phrases. Use standard German CV terminology "
        "(e.g. section content should read naturally to a German HR reader). "
        "Respond ONLY with valid JSON, no markdown formatting, no commentary. "
        f"Write ALL text content in this language: {lang}, regardless of what language "
        "the input data is in."
    )

    user_prompt = f"""
Here is the user's raw information:

{json.dumps(user_data, ensure_ascii=False, indent=2)}

Return a JSON object with this exact structure:
{{
  "profile_summary": "2-3 sentence professional profile summary",
  "work_experience": [
    {{
      "position": "...",
      "company": "...",
      "period": "...",
      "bullets": ["achievement 1", "achievement 2", "achievement 3"]
    }}
  ],
  "education": [
    {{
      "degree": "...",
      "institution": "...",
      "period": "...",
      "details": "optional one-line detail"
    }}
  ],
  "skills": {{
    "languages": ["..."],
    "it_skills": ["..."],
    "soft_skills": ["..."]
  }}
}}
"""
    raw = _call_openai(system_prompt, user_prompt, max_tokens=2000, json_mode=True)
    return json.loads(raw)


def generate_motivation_letter(user_data: dict, lang: str = "German") -> str:
    """
    user_data: foydalanuvchi ma'lumotlari + maqsad (universitet/dastur/lavozim nomi) —
    bu ma'lumotlar foydalanuvchi tomonidan istalgan tilda (uz/ru/en) kiritilgan
    bo'lishi mumkin.

    `lang` — bu hujjat tili. Standart qiymat "German": Motivationsschreiben
    har doim nemis tilida yoziladi, chunki Germaniya elchixonasi/universitet/
    ish beruvchi buni kutadi, interfeys tilidan qat'i nazar.

    Qaytaradi: to'liq motivatsion xat matni (Anrede dan Grußformel gacha),
    Germaniya standartiga mos formatda.
    """
    system_prompt = (
        "You are an expert at writing motivation letters (Motivationsschreiben) for "
        "German university applications, Ausbildung, or job applications, following "
        "standard German formal letter conventions. "
        "The user's raw input data may be written in any language (Uzbek, Russian, or "
        "English) — translate and adapt the meaning into natural, formal German; do not "
        "machine-translate literally. "
        "Write a complete, well-structured motivation letter (around 350-450 words) "
        "with: a formal greeting (use 'Sehr geehrte Damen und Herren' if no specific "
        "recipient name is known), an engaging introduction explaining the applicant's "
        "goal, 2-3 body paragraphs connecting the applicant's background to the "
        "program/position and to Germany specifically, and a formal closing "
        "(e.g. 'Mit freundlichen Grüßen'). "
        "Avoid clichés and generic statements; make it specific and personal based on "
        "the provided data. "
        f"Write the entire letter in this language: {lang}, regardless of what language "
        "the input data is in. "
        "Respond with the letter text only, no extra commentary."
    )

    user_prompt = f"""
Applicant information:

{json.dumps(user_data, ensure_ascii=False, indent=2)}

Write the motivation letter now.
"""
    return _call_openai(system_prompt, user_prompt, max_tokens=1500)
