"""CareerMap V2.0 Excel İçe ve Dışa Aktarma Servisi (Excel Service).
- Mevcut 7 sekmeli CareerMap Excel yapısını (test_output.xlsx) ilişkisel veri tabanına aktarır.
- İşveren kimliklerini (canonical employer_id) korur ve mükerrer kayıt oluşmasını engeller.
- Çoklu telefon, e-posta, WhatsApp, web sitesi ve form kanallarını employer_contacts tablosuna kanıtlarıyla yazar.
- Doğrulama durumlarını (observed_on_source, directory_observed, needs_review) korur.
- Excel dışa aktarımında 7 sekmeli profesyonel raporu üretir.
"""
import io
import re
import sqlite3
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
import openpyxl

from ..database.db import get_connection, canonical_id, upsert_contact
from ..exports.excel_exporter import generate_careermap_excel

logger = logging.getLogger("careermap.services.excel")

def import_employers_from_excel(
    excel_source: Any,
    conn: Optional[sqlite3.Connection] = None,
    city: str = "Eskişehir",
    profession_id: str = "dentist"
) -> Dict[str, Any]:
    """
    Excel dosyasından 220 işveren kaydını ve iletişim kanallarını veritabanına aktarır.
    excel_source: str, Path veya BytesIO olabilir.
    """
    if conn is None:
        conn = get_connection()

    if isinstance(excel_source, (str, Path)):
        wb = openpyxl.load_workbook(str(excel_source), data_only=True)
    else:
        wb = openpyxl.load_workbook(excel_source, data_only=True)

    sheet_names = wb.sheetnames
    if "Tüm İşverenler" in sheet_names:
        ws = wb["Tüm İşverenler"]
    else:
        ws = wb.active

    # Başlık satırını oku
    headers = [str(ws.cell(row=1, column=col).value or "").strip() for col in range(1, ws.max_column + 1)]
    header_map = {name.lower(): idx + 1 for idx, name in enumerate(headers)}

    def get_val(row_idx: int, col_name: str) -> str:
        for k, col_num in header_map.items():
            if col_name.lower() in k:
                val = ws.cell(row=row_idx, column=col_num).value
                return str(val).strip() if val is not None else ""
        return ""

    cursor = conn.cursor()
    imported_count = 0
    updated_count = 0
    contacts_count = 0
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_str = datetime.now().strftime("%Y-%m-%d")

    for r_idx in range(2, ws.max_row + 1):
        name = get_val(r_idx, "klinik") or get_val(r_idx, "işveren") or get_val(r_idx, "ad")
        if not name:
            continue

        emp_type = get_val(r_idx, "tür") or "Özel poliklinik"
        district = get_val(r_idx, "ilçe") or "Tepebaşı"
        address = get_val(r_idx, "adres")
        
        phone = get_val(r_idx, "telefon")
        phone_type = get_val(r_idx, "telefon türü") or "corporate"
        phone_src = get_val(r_idx, "telefon kaynak")
        phone_status = get_val(r_idx, "telefon durumu") or "observed_on_source"

        email = get_val(r_idx, "e-posta")
        email_type = get_val(r_idx, "e-posta türü") or "general"
        email_src = get_val(r_idx, "e-posta kaynak")
        email_status = get_val(r_idx, "e-posta durumu") or "observed_on_source"

        website = get_val(r_idx, "web sitesi")
        web_src = get_val(r_idx, "web kaynak")
        web_status = get_val(r_idx, "web durumu") or "observed_on_source"

        career_url = get_val(r_idx, "kariyer")
        form_url = get_val(r_idx, "iletişim formu") or get_val(r_idx, "form")
        whatsapp_url = get_val(r_idx, "whatsapp")
        attempted_sources = get_val(r_idx, "denenen")
        research_notes = get_val(r_idx, "araştırma notu") or get_val(r_idx, "not")
        research_status = get_val(r_idx, "araştırma durumu") or "completed"

        # Tutarlı Canonical Employer ID
        emp_id = canonical_id(name, district, emp_type)

        # Mevcut kayıt kontrolü
        cursor.execute("SELECT id FROM employers WHERE employer_id = ?", (emp_id,))
        existing = cursor.fetchone()

        cursor.execute("""
        INSERT INTO employers (
            employer_id, profession_id, city, district, name, employer_type,
            address, phone, phone_type, phone_source_url, phone_verification_status,
            email, email_type, email_source_url, email_verification_status,
            website, website_source_url, website_verification_status,
            career_url, contact_form_url, whatsapp_url,
            business_status, research_status, attempted_sources, research_notes,
            confidence_score, confidence_level, is_email_found,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, 70, 'Yüksek', ?, ?, ?)
        ON CONFLICT(employer_id) DO UPDATE SET
            district = excluded.district,
            name = excluded.name,
            employer_type = excluded.employer_type,
            address = COALESCE(NULLIF(excluded.address, ''), employers.address),
            phone = COALESCE(NULLIF(excluded.phone, ''), employers.phone),
            phone_type = excluded.phone_type,
            phone_source_url = COALESCE(NULLIF(excluded.phone_source_url, ''), employers.phone_source_url),
            phone_verification_status = excluded.phone_verification_status,
            email = COALESCE(NULLIF(excluded.email, ''), employers.email),
            email_type = excluded.email_type,
            email_source_url = COALESCE(NULLIF(excluded.email_source_url, ''), employers.email_source_url),
            email_verification_status = excluded.email_verification_status,
            website = COALESCE(NULLIF(excluded.website, ''), employers.website),
            website_source_url = COALESCE(NULLIF(excluded.website_source_url, ''), employers.website_source_url),
            website_verification_status = excluded.website_verification_status,
            career_url = COALESCE(NULLIF(excluded.career_url, ''), employers.career_url),
            contact_form_url = COALESCE(NULLIF(excluded.contact_form_url, ''), employers.contact_form_url),
            whatsapp_url = COALESCE(NULLIF(excluded.whatsapp_url, ''), employers.whatsapp_url),
            attempted_sources = COALESCE(NULLIF(excluded.attempted_sources, ''), employers.attempted_sources),
            research_notes = COALESCE(NULLIF(excluded.research_notes, ''), employers.research_notes),
            is_email_found = excluded.is_email_found,
            updated_at = excluded.updated_at
        """, (
            emp_id, profession_id, city, district, name, emp_type,
            address, phone, phone_type, phone_src, phone_status,
            email, email_type, email_src, email_status,
            website, web_src, web_status,
            career_url, form_url, whatsapp_url,
            research_status, attempted_sources, research_notes,
            1 if email else 0,
            now_str, now_str
        ))

        if existing:
            updated_count += 1
        else:
            imported_count += 1

        # employer_contacts tablosuna kanalları normalize ekle
        if phone:
            upsert_contact(cursor, emp_id, "phone", phone, phone_type, phone_src, "excel_import",
                           discovery_method="official_registry", evidence_text="Excel İçe Aktarım",
                           confidence_category="kaynakli", verification_status=phone_status, today_str=today_str)
            contacts_count += 1
        if email:
            upsert_contact(cursor, emp_id, "email", email, email_type, email_src, "excel_import",
                           discovery_method="web_crawl", evidence_text="Excel İçe Aktarım",
                           confidence_category="kaynakli", verification_status=email_status, today_str=today_str)
            contacts_count += 1
        if website:
            upsert_contact(cursor, emp_id, "website", website, "corporate", web_src, "excel_import",
                           discovery_method="domain_verification", evidence_text="Excel İçe Aktarım",
                           confidence_category="kaynakli", verification_status=web_status, today_str=today_str)
            contacts_count += 1
        if whatsapp_url:
            upsert_contact(cursor, emp_id, "whatsapp", whatsapp_url, "messaging", whatsapp_url, "excel_import",
                           discovery_method="whatsapp_link", evidence_text="WhatsApp İletişim Kanalı",
                           confidence_category="kaynakli", verification_status="observed_on_source", today_str=today_str)
            contacts_count += 1
        if form_url:
            upsert_contact(cursor, emp_id, "contact_form", form_url, "contact_form", form_url, "excel_import",
                           discovery_method="form_action", evidence_text="İletişim Formu",
                           confidence_category="kaynakli", verification_status="observed_on_source", today_str=today_str)
            contacts_count += 1

    conn.commit()

    return {
        "status": "success",
        "imported_new": imported_count,
        "updated_existing": updated_count,
        "total_processed": imported_count + updated_count,
        "contacts_stored": contacts_count
    }

def export_employers_to_excel_stream(
    conn: Optional[sqlite3.Connection] = None,
    city: str = "Eskişehir",
    profession_id: str = "dentist"
) -> io.BytesIO:
    """Veritabanındaki tüm işverenleri 7 sekmeli profesyonel Excel akışı olarak üretir."""
    if conn is None:
        conn = get_connection()

    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM employers 
    WHERE city = ? AND profession_id = ?
    ORDER BY employer_type DESC, name ASC
    """, (city, profession_id))
    rows = [dict(r) for r in cursor.fetchall()]

    return generate_careermap_excel(
        records=rows,
        profession_name="Diş Hekimi",
        city=city
    )

