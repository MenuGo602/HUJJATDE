# document_generator.py
"""
Bu modul AI tomonidan generatsiya qilingan matnlarni Germaniya standartiga
mos Word (.docx) hujjatlariga joylaydi:
  - Lebenslauf (Europass uslubidagi jadval-based CV)
  - Motivationsschreiben (rasmiy xat formati)
"""

import os
from datetime import date
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

ACCENT_COLOR = RGBColor(0x1F, 0x3A, 0x5F)  # to'q ko'k - rasmiy ko'rinish


def _set_cell_text(cell, text, bold=False, size=10, color=None):
    cell.text = ""
    p = cell.paragraphs[0]
    run = p.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)
    if color:
        run.font.color.rgb = color


def build_cv_docx(personal: dict, cv_sections: dict, output_path: str):
    """
    personal: {"full_name", "address", "phone", "email", "birth_date", "nationality", "photo_path" (optional)}
    cv_sections: ai_generator.generate_cv_sections() natijasi
    """
    doc = Document()

    # Sahifa marginlari
    for section in doc.sections:
        section.top_margin = Cm(1.5)
        section.bottom_margin = Cm(1.5)
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)

    # --- Sarlavha: ism va aloqa ma'lumotlari ---
    title = doc.add_heading(personal.get("full_name", ""), level=0)
    title.runs[0].font.color.rgb = ACCENT_COLOR

    contact_line = f"{personal.get('address', '')} | {personal.get('phone', '')} | {personal.get('email', '')}"
    p = doc.add_paragraph(contact_line)
    p.runs[0].font.size = Pt(10)

    if personal.get("birth_date") or personal.get("nationality"):
        meta_line = f"Geburtsdatum: {personal.get('birth_date', '')}    |    Staatsangehörigkeit: {personal.get('nationality', '')}"
        mp = doc.add_paragraph(meta_line)
        mp.runs[0].font.size = Pt(10)
        mp.runs[0].italic = True

    doc.add_paragraph()  # bo'sh qator

    # --- Profil / Über mich ---
    h = doc.add_heading("Profil", level=1)
    h.runs[0].font.color.rgb = ACCENT_COLOR
    doc.add_paragraph(cv_sections.get("profile_summary", ""))

    # --- Berufserfahrung ---
    h = doc.add_heading("Berufserfahrung", level=1)
    h.runs[0].font.color.rgb = ACCENT_COLOR
    for job in cv_sections.get("work_experience", []):
        table = doc.add_table(rows=1, cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.LEFT
        table.columns[0].width = Cm(3.5)
        row = table.rows[0]
        _set_cell_text(row.cells[0], job.get("period", ""), bold=True, size=10)
        _set_cell_text(row.cells[1], f"{job.get('position', '')} — {job.get('company', '')}", bold=True, size=11)

        for bullet in job.get("bullets", []):
            bp = doc.add_paragraph(bullet, style="List Bullet")
            bp.paragraph_format.left_indent = Cm(3.5)
        doc.add_paragraph()

    # --- Ausbildung ---
    h = doc.add_heading("Ausbildung", level=1)
    h.runs[0].font.color.rgb = ACCENT_COLOR
    for edu in cv_sections.get("education", []):
        table = doc.add_table(rows=1, cols=2)
        table.columns[0].width = Cm(3.5)
        row = table.rows[0]
        _set_cell_text(row.cells[0], edu.get("period", ""), bold=True, size=10)
        title_text = f"{edu.get('degree', '')} — {edu.get('institution', '')}"
        _set_cell_text(row.cells[1], title_text, bold=True, size=11)
        if edu.get("details"):
            dp = doc.add_paragraph(edu["details"])
            dp.paragraph_format.left_indent = Cm(3.5)
            dp.runs[0].font.size = Pt(10)
        doc.add_paragraph()

    # --- Kompetenzen ---
    h = doc.add_heading("Kompetenzen", level=1)
    h.runs[0].font.color.rgb = ACCENT_COLOR
    skills = cv_sections.get("skills", {})

    if skills.get("languages"):
        p = doc.add_paragraph()
        run = p.add_run("Sprachen: ")
        run.bold = True
        p.add_run(", ".join(skills["languages"]))

    if skills.get("it_skills"):
        p = doc.add_paragraph()
        run = p.add_run("IT-Kenntnisse: ")
        run.bold = True
        p.add_run(", ".join(skills["it_skills"]))

    if skills.get("soft_skills"):
        p = doc.add_paragraph()
        run = p.add_run("Soft Skills: ")
        run.bold = True
        p.add_run(", ".join(skills["soft_skills"]))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    return output_path


def build_motivation_letter_docx(personal: dict, recipient: dict, letter_text: str, output_path: str):
    """
    personal: {"full_name", "address", "phone", "email"}
    recipient: {"name", "institution", "address"} - kimga yo'llanayotgani (universitet/kompaniya)
    letter_text: ai_generator.generate_motivation_letter() natijasi
    """
    doc = Document()

    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    # Yuboruvchi ma'lumotlari (yuqori o'ng burchak - DIN 5008 uslubi)
    sender_p = doc.add_paragraph()
    sender_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    sender_p.add_run(
        f"{personal.get('full_name', '')}\n"
        f"{personal.get('address', '')}\n"
        f"{personal.get('phone', '')}\n"
        f"{personal.get('email', '')}"
    )

    doc.add_paragraph()

    # Qabul qiluvchi ma'lumotlari
    recipient_p = doc.add_paragraph()
    recipient_p.add_run(
        f"{recipient.get('name', '')}\n"
        f"{recipient.get('institution', '')}\n"
        f"{recipient.get('address', '')}"
    )

    doc.add_paragraph()

    # Sana
    date_p = doc.add_paragraph()
    date_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    date_p.add_run(date.today().strftime("%d.%m.%Y"))

    doc.add_paragraph()

    # Xat matni - paragraflarga bo'lib qo'shamiz
    for para in letter_text.strip().split("\n\n"):
        para = para.strip()
        if para:
            doc.add_paragraph(para)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    return output_path
