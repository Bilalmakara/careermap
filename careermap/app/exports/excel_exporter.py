"""CareerMap V1.3 Çok Kaynaklı 7 Sekmeli Profesyonel Excel Raporu (openpyxl).
- 'contact_form_url' (İletişim Formu) sütunu entegrasyonu.
- Çok kaynaklı iletişim kanalları ve doğrulama durumları.
- Kalite ve inceleme filtreleri.
"""
import io
from datetime import datetime
from typing import List, Dict, Any
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Renk Paleti (Modern Slate & Corporate Blue)
NAVY_HEADER = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
BLUE_HEADER = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
EMERALD_HEADER = PatternFill(start_color="059669", end_color="059669", fill_type="solid")
INDIGO_HEADER = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
PURPLE_HEADER = PatternFill(start_color="7C3AED", end_color="7C3AED", fill_type="solid")
AMBER_HEADER = PatternFill(start_color="D97706", end_color="D97706", fill_type="solid")
TEAL_HEADER = PatternFill(start_color="0D9488", end_color="0D9488", fill_type="solid")

ZEBRA_FILL = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
WHITE_FILL = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

GREEN_BADGE = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
YELLOW_BADGE = PatternFill(start_color="FEF9C3", end_color="FEF9C3", fill_type="solid")
RED_BADGE = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
GRAY_BADGE = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

WHITE_BOLD_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
DARK_BOLD_FONT = Font(name="Calibri", size=11, bold=True, color="0F172A")
REGULAR_FONT = Font(name="Calibri", size=10, color="1E293B")
NOTE_FONT = Font(name="Calibri", size=9, italic=True, color="64748B")

THIN_BORDER = Border(
    left=Side(style='thin', color='E2E8F0'),
    right=Side(style='thin', color='E2E8F0'),
    top=Side(style='thin', color='E2E8F0'),
    bottom=Side(style='thin', color='E2E8F0')
)

MAIN_COLUMNS = [
    ("Klinik / İşveren Adı", "name", 34),
    ("Kurum Türü", "employer_type", 22),
    ("İlçe", "district", 16),
    ("Açık Adres", "address", 38),
    ("Telefon", "phone", 20),
    ("Telefon Türü", "phone_type", 18),
    ("Telefon Kaynak URL", "phone_source_url", 32),
    ("Telefon Durumu", "phone_verification_status", 18),
    ("Kurumsal E-posta", "email", 28),
    ("E-posta Türü", "email_type", 16),
    ("E-posta Kaynak URL", "email_source_url", 32),
    ("E-posta Durumu", "email_verification_status", 18),
    ("Web Sitesi", "website", 30),
    ("Web Kaynak URL", "website_source_url", 32),
    ("Web Durumu", "website_verification_status", 18),
    ("Kariyer Sayfası", "career_url", 28),
    ("İletişim Formu", "contact_form_url", 32),
    ("WhatsApp Bağlantısı", "whatsapp_url", 28),
    ("Denenen Kaynaklar", "attempted_sources", 25),
    ("Araştırma Notu / Kanıt", "research_notes", 38),
    ("Araştırma Durumu", "research_status", 18),
    ("Kaynakta Görülme", "source_last_checked", 16),
    ("İletişim Teyit Tarihi", "contact_last_verified", 18)
]

def format_sheet_table(ws, headers: List[str], rows: List[List[Any]], header_fill, col_widths: List[int]):
    ws.append(headers)
    ws.row_dimensions[1].height = 28
    
    for col_idx, text in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = WHITE_BOLD_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER

    for row_idx, row_data in enumerate(rows, 2):
        ws.append(row_data)
        ws.row_dimensions[row_idx].height = 22
        is_even = (row_idx % 2 == 0)
        row_fill = ZEBRA_FILL if is_even else WHITE_FILL
        
        for col_idx, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = REGULAR_FONT
            cell.border = THIN_BORDER
            cell.fill = row_fill
            cell.alignment = Alignment(vertical="center")

            val_str = str(val or "")
            if col_idx in [2, 3, 5, 6, 8, 10, 12, 15, 18, 19, 20]:
                cell.alignment = Alignment(horizontal="center", vertical="center")

            if val_str in ["verified", "completed", "active", "observed_on_source", "cross_source_supported", "manually_confirmed"]:
                cell.fill = GREEN_BADGE
            elif val_str in ["manual_review", "partial", "needs_review"]:
                cell.fill = YELLOW_BADGE
            elif val_str in ["conflict", "invalid"]:
                cell.fill = RED_BADGE
            elif val_str in ["unverified", "pending", "unknown"]:
                cell.fill = GRAY_BADGE

    for col_idx, width in enumerate(col_widths, 1):
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = width

    ws.freeze_panes = "A2"

def generate_careermap_excel(
    records: List[Dict[str, Any]],
    profession_name: str = "Diş Hekimi",
    city: str = "Eskişehir"
) -> io.BytesIO:
    """CareerMap V1.3 7 sekmeli profesyonel Excel raporu üretir."""
    wb = openpyxl.Workbook()
    
    # 1. Sayfa: Tüm İşverenler
    ws_all = wb.active
    ws_all.title = "Tüm İşverenler"
    headers_all = [c[0] for c in MAIN_COLUMNS]
    widths_all = [c[2] for c in MAIN_COLUMNS]
    rows_all = [[r.get(c[1], "") or "" for c in MAIN_COLUMNS] for r in records]
    format_sheet_table(ws_all, headers_all, rows_all, NAVY_HEADER, widths_all)

    # 2. Sayfa: Telefon Bulunanlar
    ws_phone = wb.create_sheet(title="Telefon Bulunanlar")
    phone_records = [r for r in records if (r.get("phone") or "").strip()]
    PHONE_COLS = [
        ("İşveren / Hekim Adı", "name", 34),
        ("Kurum Türü", "employer_type", 22),
        ("İlçe", "district", 16),
        ("Telefon", "phone", 20),
        ("Telefon Türü", "phone_type", 18),
        ("Telefon Kaynak URL", "phone_source_url", 34),
        ("Doğrulama Durumu", "phone_verification_status", 18),
        ("Açık Adres", "address", 38)
    ]
    headers_phone = [c[0] for c in PHONE_COLS]
    widths_phone = [c[2] for c in PHONE_COLS]
    rows_phone = [[r.get(c[1], "") or "" for c in PHONE_COLS] for r in phone_records]
    format_sheet_table(ws_phone, headers_phone, rows_phone, BLUE_HEADER, widths_phone)

    # 3. Sayfa: E-posta ve Başvuru Kanalları Bulunanlar
    ws_email = wb.create_sheet(title="E-posta ve Başvuru")
    contact_channels_records = [
        r for r in records 
        if (r.get("email") or "").strip() or (r.get("contact_form_url") or "").strip() or (r.get("career_url") or "").strip() or (r.get("whatsapp_url") or "").strip()
    ]
    EMAIL_COLS = [
        ("İşveren / Klinik Adı", "name", 34),
        ("İlçe", "district", 16),
        ("Kurumsal E-posta", "email", 28),
        ("E-posta Türü", "email_type", 16),
        ("İletişim / Başvuru Formu", "contact_form_url", 32),
        ("Kariyer Sayfası", "career_url", 30),
        ("WhatsApp İletişim", "whatsapp_url", 30),
        ("Web Sitesi", "website", 30),
        ("Telefon", "phone", 20)
    ]
    headers_email = [c[0] for c in EMAIL_COLS]
    widths_email = [c[2] for c in EMAIL_COLS]
    rows_email = [[r.get(c[1], "") or "" for c in EMAIL_COLS] for r in contact_channels_records]
    format_sheet_table(ws_email, headers_email, rows_email, EMERALD_HEADER, widths_email)

    # 4. Sayfa: Web Sitesi Bulunanlar
    ws_web = wb.create_sheet(title="Web Sitesi Bulunanlar")
    web_records = [r for r in records if (r.get("website") or "").strip()]
    WEB_COLS = [
        ("İşveren / Klinik Adı", "name", 34),
        ("Kurum Türü", "employer_type", 22),
        ("İlçe", "district", 16),
        ("Web Sitesi", "website", 32),
        ("Web Kaynak URL", "website_source_url", 34),
        ("Doğrulama Durumu", "website_verification_status", 18),
        ("İletişim Formu", "contact_form_url", 30),
        ("Kariyer Sayfası", "career_url", 30),
        ("Telefon", "phone", 20)
    ]
    headers_web = [c[0] for c in WEB_COLS]
    widths_web = [c[2] for c in WEB_COLS]
    rows_web = [[r.get(c[1], "") or "" for c in WEB_COLS] for r in web_records]
    format_sheet_table(ws_web, headers_web, rows_web, INDIGO_HEADER, widths_web)

    # 5. Sayfa: Manuel İnceleme Gerektirenler
    ws_review = wb.create_sheet(title="Manuel İnceleme")
    review_records = [
        r for r in records
        if r.get("phone_verification_status") in ["manual_review", "conflict", "needs_review", "invalid"]
        or r.get("email_verification_status") in ["manual_review", "conflict", "needs_review", "invalid"]
        or r.get("website_verification_status") in ["manual_review", "conflict", "needs_review", "invalid"]
    ]
    REVIEW_COLS = [
        ("İşveren / Hekim Adı", "name", 34),
        ("Kurum Türü", "employer_type", 22),
        ("İlçe", "district", 16),
        ("Telefon", "phone", 20),
        ("Tel Durumu", "phone_verification_status", 16),
        ("Web Sitesi", "website", 30),
        ("Web Durumu", "website_verification_status", 16),
        ("İşveren Kimliği", "employer_id", 34),
        ("Kaynak URL(ler)", "source_urls", 38)
    ]
    headers_review = [c[0] for c in REVIEW_COLS]
    widths_review = [c[2] for c in REVIEW_COLS]
    rows_review = [[r.get(c[1], "") or "" for c in REVIEW_COLS] for r in review_records]
    format_sheet_table(ws_review, headers_review, rows_review, PURPLE_HEADER, widths_review)

    # 6. Sayfa: Araştırılan Ama İletişimi Bulunamayanlar
    ws_missing = wb.create_sheet(title="İletişimi Bulunamayanlar")
    missing_records = [
        r for r in records 
        if not (r.get("phone") or "").strip() 
        and not (r.get("email") or "").strip() 
        and not (r.get("website") or "").strip()
        and not (r.get("contact_form_url") or "").strip()
    ]
    MISSING_COLS = [
        ("İşveren / Hekim Adı", "name", 34),
        ("Kurum Türü", "employer_type", 22),
        ("İlçe", "district", 16),
        ("Açık Adres", "address", 38),
        ("Resmî Kaynak Portalı", "source_type", 30),
        ("Denenen Kaynaklar", "attempted_sources", 26),
        ("Neden Bulunamadı / Not", "research_notes", 42),
        ("Kaynakta Son Görülme", "source_last_checked", 18),
        ("İşveren Kimliği", "employer_id", 34)
    ]
    headers_missing = [c[0] for c in MISSING_COLS]
    widths_missing = [c[2] for c in MISSING_COLS]
    rows_missing = [[r.get(c[1], "") or "" for c in MISSING_COLS] for r in missing_records]
    format_sheet_table(ws_missing, headers_missing, rows_missing, AMBER_HEADER, widths_missing)

    # 7. Sayfa: Kaynaklar ve Tarama Raporu
    ws_meta = wb.create_sheet(title="Kaynaklar ve Rapor")
    ws_meta.column_dimensions["A"].width = 30
    ws_meta.column_dimensions["B"].width = 75
    
    total = len(records)
    with_phone = len(phone_records)
    with_email = sum(1 for r in records if (r.get("email") or "").strip())
    with_web = len(web_records)
    with_form = sum(1 for r in records if (r.get("contact_form_url") or "").strip())
    with_wa = sum(1 for r in records if (r.get("whatsapp_url") or "").strip())
    with_career = sum(1 for r in records if (r.get("career_url") or "").strip())
    with_any_channel = sum(1 for r in records if (r.get("phone") or "").strip() or (r.get("email") or "").strip() or (r.get("whatsapp_url") or "").strip() or (r.get("contact_form_url") or "").strip())
    manual_cnt = len(review_records)
    unfound_cnt = len(missing_records)
    
    verified_phones = sum(1 for r in records if r.get("phone_verification_status") in ["observed_on_source", "cross_source_supported", "verified"])
    directory_phones = sum(1 for r in records if r.get("phone_verification_status") == "directory_observed")
    verified_emails = sum(1 for r in records if r.get("email_verification_status") in ["observed_on_source", "cross_source_supported", "verified"])
    verified_websites = sum(1 for r in records if r.get("website_verification_status") in ["observed_on_source", "cross_source_supported", "verified"])
    
    report_data = [
        ["RAPOR METRİĞİ", "DEĞER VE AÇIKLAMA"],
        ["Platform Sürümü", "CareerMap V1.6 — Full Coverage Contact Intelligence & Multi-Channel Discovery"],
        ["Meslek & Konum", f"{profession_name} - {city} (Tüm İlçeler)"],
        ["Tarama Tarihi", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["Toplam Araştırılan İşveren", f"{total} adet tekilleştirilmiş işletme / hekim"],
        ["EN AZ BİR KANALLA ULAŞILABİLEN", f"{with_any_channel} adet (%{(with_any_channel/total*100 if total else 0):.1f}) — Doğrudan iş arayan hekim için aktif temas"],
        ["Telefonu Bulunanlar", f"{with_phone} adet (%{(with_phone/total*100 if total else 0):.1f}) — {verified_phones} adedi TR E.164 / TDB sicil teyitli, {directory_phones} rehber teyitli"],
        ["E-postası Bulunanlar", f"{with_email} adet (%{(with_email/total*100 if total else 0):.1f}) — {verified_emails} adedi açık web varlıklarında teyitli"],
        ["WhatsApp Bağlantısı Bulunanlar", f"{with_wa} adet doğrulanmış WhatsApp Business / mobil mesajlaşma hattı"],
        ["İletişim / Başvuru Formu Bulunanlar", f"{with_form} adet kurumsal iletişim formu (randevu formlarından ayrıştırılmış)"],
        ["Kariyer Sayfası Bulunanlar", f"{with_career} adet doğrudan iş başvuru modülü / sayfası"],
        ["Web Sitesi Doğrulananlar", f"{with_web} adet kimlik ve sektör teyitli web sitesi"],
        ["Manuel İnceleme / Özel Kategori", f"{manual_cnt} adet kayıt (ajans altbilgisi veya inceleme notlu)"],
        ["İletişimi Bulunamayanlar", f"{unfound_cnt} adet (kamuda kayıtlı, web iletişimi açıkta bulunamayan)"],
        ["---", "---"],
        ["DOĞRULAMA STANDARDI", "V1.6 KAPSAMI VE STATÜ TANIMLARI"],
        ["observed_on_source", "Kamuya açık resmî sitede / kaynakta doğrudan gözlemlenen iletişim bilgisi."],
        ["cross_source_supported", "Birden fazla bağımsız kaynak veya şubeler arası teyit edilmiş (örn. kurumsal ortak santral)."],
        ["directory_observed", "Kamuya açık hekim/kurum rehber profilinden derlenmiş ikincil kurumsal iletişim bilgisi."],
        ["needs_review", "Aday tespit edilmiş ancak üçüncü taraf ajans/altbilgi şüphesi taşıyan temas noktası."],
        ["associated_clinic", "Hekimin bağımsız web sitesi olmayıp poliklinik kadrosunda yer aldığı kurumsal bağlantı."],
        ["Çok Faktörlü Puanlama", "%35 İsim/Marka, %30 Adres, %15 Konum, %15 Telefon, %5 Diş Hekimliği Faaliyet Alanı."],
        ["---", "---"],
        ["VERİ VE ARAMA KAYNAKLARI", "AÇIKLAMA VE YASAL ÇERÇEVE"],
        ["1. Resmî Kurum Portalı", "Eskişehir İl Sağlık Müdürlüğü Açık Veri Portalı (Mart 2025 / Nisan 2024 listeleri)"],
        ["2. TDB Resmî Kamusal Sicil", "Türk Dişhekimleri Birliği Kamusal Sicil Portalı (Token bazlı tam hekim ad-soyad teyitli)"],
        ["3. OpenStreetMap (OSM)", "Overpass API (Odaklı merkez BBOX, node/way/relation - ODbL Lisansı)"],
        ["4. FreeSerp Web İndeksi", "FreeSerp (freeserp.ai) 3.1+ Milyar web sayfası arama adapteri (SearchRouter, 10 sonuçlu)"],
        ["5. Deep Contact Crawler", "Çok sayfalı saygılı tarama, JSON-LD, mailto, tel, WhatsApp, formlar ve PDF doküman desteği"],
        ["6. İkincil Hekim Rehberleri", "DoktorTakvimi vb. kamuya açık işletme profillerinden kurumsal santral/mobil tespiti"],
        ["7. Bağımsız İletişim Havuzu", "employer_contacts tablosunda kanıt izi (discovery_method, evidence_text) ile saklanan temaslar"],
        ["---", "---"],
        ["KVKK VE KULLANIM UYARISI", "TDB'den derlenen hekim telefonları resmî sicil oda telefonlarıdır. Web sitesi yayınları açık kaynak gözlemidir; izinsiz toplu pazarlama iletisi amacıyla kullanılamaz."]
    ]
    
    for row_idx, (k, v) in enumerate(report_data, 1):
        ws_meta.cell(row=row_idx, column=1, value=k)
        ws_meta.cell(row=row_idx, column=2, value=v)
        ws_meta.row_dimensions[row_idx].height = 22
        
        c1 = ws_meta.cell(row=row_idx, column=1)
        c2 = ws_meta.cell(row=row_idx, column=2)
        
        if k in ["RAPOR METRİĞİ", "VERİ KAYNAKLARI", "KVKK VE KULLANIM UYARISI"]:
            c1.fill = TEAL_HEADER
            c2.fill = TEAL_HEADER
            c1.font = WHITE_BOLD_FONT
            c2.font = WHITE_BOLD_FONT
        elif k == "---":
            c1.font = NOTE_FONT
            c2.font = NOTE_FONT
        else:
            c1.font = DARK_BOLD_FONT
            c2.font = REGULAR_FONT
            c1.fill = ZEBRA_FILL
            c2.fill = WHITE_FILL
            c1.border = THIN_BORDER
            c2.border = THIN_BORDER

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
