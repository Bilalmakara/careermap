"""CareerMap V1.4 SQLite Veritabanı ve Kalıcı Kayıt Yöneticisi.
- Alan Bazlı Doğrulama & Audit Log.
- Yeni `employer_contacts` tablosu ile kanıt tabanlı çoklu iletişim desteği (discovery_method, evidence_text, confidence_category).
- Başarısız/eksik araştırmaların nedenleri (`attempted_sources`, `research_notes`).
- Kalıcı deterministik `employer_id` (canonical_id).
"""
import sqlite3
import re
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent.parent.parent / "careermap.db"

def get_connection(db_path: Optional[Any] = None) -> sqlite3.Connection:
    target = str(db_path) if db_path else str(DB_PATH)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    return conn

def canonical_id(name: str, district: str, employer_type: str, city: str = "Eskişehir", profession: str = "dentist") -> str:
    """İşletme veya hekim için deterministik, çakışmayan kararlı kimlik üretir."""
    s = name.replace("I", "ı").replace("İ", "i").lower()
    s = s.translate(str.maketrans("çğıöşü", "cgiosu"))
    s = unicodedata.normalize("NFKD", s)
    
    branch = ""
    for b in ["camlica", "emek", "sakarya", "doktorlar", "bati", "subesi", "kizilay", "cankaya", "tunali", "tunali-hilmi", "bahcelievler"]:
        if b in s:
            branch = f"-{b}"
            break
            
    is_office = "muayenehane" in employer_type.lower() or s.startswith("dt") or "büro" in employer_type.lower()
    prefix = "office" if is_office else "clinic"
    
    clean_name = re.sub(r"\b(ozel|agiz|ve|dis|sagligi|poliklinigi|poliklinik|klinigi|klinik|muayenehanesi|muayenehane|dt|dr)\b", " ", s)
    clean_name = re.sub(r"[^a-z0-9]", "", clean_name)
    
    dist_slug = ""
    if district:
        d = district.replace("I", "ı").replace("İ", "i").lower()
        d = d.translate(str.maketrans("çğıöşü", "cgiosu"))
        d = re.sub(r"[^a-z0-9]", "", d)
        if d:
            dist_slug = f"-{d}"

    city_slug = city.replace("I", "ı").replace("İ", "i").lower()
    city_slug = city_slug.translate(str.maketrans("çğıöşü", "cgiosu"))
    city_slug = re.sub(r"[^a-z0-9]", "", city_slug) or "eskisehir"

    prof_slug = profession.lower().replace("_", "-")
            
    return f"{prof_slug}-{city_slug}-{prefix}{dist_slug}-{clean_name[:40]}{branch}"

def init_db(conn: Optional[sqlite3.Connection] = None):
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    cursor = conn.cursor()
    
    # 1. employers tablosu
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employer_id TEXT UNIQUE NOT NULL,
        profession_id TEXT NOT NULL,
        city TEXT NOT NULL,
        district TEXT,
        name TEXT NOT NULL,
        employer_type TEXT,
        address TEXT,
        phone TEXT,
        phone_type TEXT DEFAULT 'unknown',
        phone_source_url TEXT,
        phone_verification_status TEXT DEFAULT 'unverified',
        email TEXT,
        email_type TEXT DEFAULT 'unknown',
        email_source_url TEXT,
        email_verification_status TEXT DEFAULT 'unverified',
        website TEXT,
        website_source_url TEXT,
        website_verification_status TEXT DEFAULT 'unverified',
        career_url TEXT,
        contact_form_url TEXT DEFAULT '',
        whatsapp_url TEXT DEFAULT '',
        source_urls TEXT,
        source_type TEXT,
        business_status TEXT DEFAULT 'active',
        research_status TEXT DEFAULT 'pending',
        attempted_sources TEXT DEFAULT '',
        research_notes TEXT DEFAULT '',
        confidence_score INTEGER DEFAULT 50,
        confidence_level TEXT DEFAULT 'Orta',
        is_email_found INTEGER DEFAULT 0,
        source_last_checked TEXT,
        contact_last_verified TEXT,
        observed_at TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    # employers kolon kontrolleri
    cursor.execute("PRAGMA table_info(employers)")
    cols = [col["name"] for col in cursor.fetchall()]
    if "contact_form_url" not in cols:
        cursor.execute("ALTER TABLE employers ADD COLUMN contact_form_url TEXT DEFAULT ''")
    if "whatsapp_url" not in cols:
        cursor.execute("ALTER TABLE employers ADD COLUMN whatsapp_url TEXT DEFAULT ''")
    if "attempted_sources" not in cols:
        cursor.execute("ALTER TABLE employers ADD COLUMN attempted_sources TEXT DEFAULT ''")
    if "research_notes" not in cols:
        cursor.execute("ALTER TABLE employers ADD COLUMN research_notes TEXT DEFAULT ''")
    
    # 2. employer_contacts tablosu (Kanıtlı çoklu iletişim ve kanallar)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employer_contacts (
        contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
        employer_id TEXT NOT NULL,
        contact_type TEXT NOT NULL,
        contact_value TEXT NOT NULL,
        contact_category TEXT DEFAULT 'unknown',
        source_url TEXT DEFAULT '',
        source_type TEXT DEFAULT 'unknown',
        discovery_method TEXT DEFAULT 'unknown',
        evidence_text TEXT DEFAULT '',
        confidence_category TEXT DEFAULT 'kaynakli',
        discovered_at TEXT,
        last_checked_at TEXT,
        verification_status TEXT DEFAULT 'unverified',
        FOREIGN KEY(employer_id) REFERENCES employers(employer_id) ON DELETE CASCADE,
        UNIQUE(employer_id, contact_type, contact_value)
    )
    """)

    # employer_contacts kolon kontrolleri
    cursor.execute("PRAGMA table_info(employer_contacts)")
    c_cols = [col["name"] for col in cursor.fetchall()]
    if "discovery_method" not in c_cols:
        cursor.execute("ALTER TABLE employer_contacts ADD COLUMN discovery_method TEXT DEFAULT 'unknown'")
    if "evidence_text" not in c_cols:
        cursor.execute("ALTER TABLE employer_contacts ADD COLUMN evidence_text TEXT DEFAULT ''")
    if "confidence_category" not in c_cols:
        cursor.execute("ALTER TABLE employer_contacts ADD COLUMN confidence_category TEXT DEFAULT 'kaynakli'")
    
    # 3. employer_audit_log tablosu
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employer_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employer_id TEXT NOT NULL,
        field_name TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        source TEXT,
        changed_at TEXT NOT NULL
    )
    """)
    
    # 4. search_cache tablosu
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS search_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profession_id TEXT NOT NULL,
        city TEXT NOT NULL,
        last_scanned_at TEXT,
        total_count INTEGER DEFAULT 0,
        email_count INTEGER DEFAULT 0,
        phone_count INTEGER DEFAULT 0,
        contact_form_count INTEGER DEFAULT 0,
        osm_status TEXT DEFAULT 'unknown',
        official_status TEXT DEFAULT 'unknown',
        status TEXT DEFAULT 'ready',
        error_log TEXT,
        UNIQUE(profession_id, city)
    )
    """)

    # 5. V2.0 Aday Yönetimi ve Başvuru CRM Tabloları
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS candidates (
        candidate_id TEXT PRIMARY KEY,
        user_id TEXT DEFAULT '',
        full_name TEXT NOT NULL,
        title TEXT DEFAULT 'Diş Hekimi',
        email TEXT,
        phone TEXT,
        city TEXT DEFAULT 'Eskişehir',
        graduation_school TEXT,
        graduation_year INTEGER,
        clinical_case_count INTEGER DEFAULT 0,
        specialties_json TEXT DEFAULT '[]',
        experience_summary TEXT DEFAULT '',
        work_preferences_json TEXT DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("PRAGMA table_info(candidates)")
    cand_cols = [col["name"] for col in cursor.fetchall()]
    if "user_id" not in cand_cols:
        cursor.execute("ALTER TABLE candidates ADD COLUMN user_id TEXT DEFAULT ''")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS candidate_documents (
        document_id TEXT PRIMARY KEY,
        candidate_id TEXT NOT NULL,
        document_type TEXT DEFAULT 'cv_pdf',
        file_name TEXT NOT NULL,
        file_path TEXT DEFAULT '',
        secure_token TEXT UNIQUE NOT NULL,
        expires_at TEXT,
        view_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        application_id TEXT PRIMARY KEY,
        candidate_id TEXT NOT NULL,
        employer_id TEXT NOT NULL,
        position_title TEXT DEFAULT 'Diş Hekimi',
        status TEXT DEFAULT 'draft',
        orchestration_step INTEGER DEFAULT 1,
        planned_channels_json TEXT DEFAULT '[]',
        match_score INTEGER DEFAULT 0,
        match_reasons_json TEXT DEFAULT '[]',
        primary_channel TEXT DEFAULT 'email',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE,
        FOREIGN KEY(employer_id) REFERENCES employers(employer_id) ON DELETE CASCADE,
        UNIQUE(candidate_id, employer_id, position_title)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS application_messages (
        message_id TEXT PRIMARY KEY,
        application_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        message_type TEXT DEFAULT 'initial',
        subject TEXT DEFAULT '',
        body_text TEXT NOT NULL,
        recipient_contact TEXT DEFAULT '',
        secure_cv_url TEXT DEFAULT '',
        action_url TEXT DEFAULT '',
        is_approved INTEGER DEFAULT 0,
        approved_at TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(application_id) REFERENCES applications(application_id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS channel_attempts (
        attempt_id TEXT PRIMARY KEY,
        application_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        contact_value TEXT NOT NULL,
        attempt_type TEXT DEFAULT 'initial_application',
        status TEXT DEFAULT 'prepared',
        notes TEXT DEFAULT '',
        attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(application_id) REFERENCES applications(application_id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS application_events (
        event_id TEXT PRIMARY KEY,
        application_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        old_status TEXT DEFAULT '',
        new_status TEXT DEFAULT '',
        details_text TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(application_id) REFERENCES applications(application_id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS communication_preferences (
        preference_id TEXT PRIMARY KEY,
        candidate_id TEXT NOT NULL,
        allow_email_applications INTEGER DEFAULT 1,
        allow_whatsapp_handoff INTEGER DEFAULT 1,
        whatsapp_model TEXT DEFAULT 'model_b_secure_link',
        min_followup_days INTEGER DEFAULT 4,
        max_reminders_per_employer INTEGER DEFAULT 1,
        FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE
    )
    """)

    # İndeksler
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_emp_uid ON employers(employer_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_emp_prof_city ON employers(profession_id, city)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_emp_district ON employers(district)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_emp_phone_verif ON employers(phone_verification_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_emp_email_verif ON employers(email_verification_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_empid ON employer_audit_log(employer_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contact_empid ON employer_contacts(employer_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contact_type ON employer_contacts(contact_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contact_verif ON employer_contacts(verification_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_candidate ON applications(candidate_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_employer ON applications(employer_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_status ON applications(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_msg ON application_messages(application_id)")
    
    # 6. V2.1 Dinamik Araştırma Görevleri (Research Jobs)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS research_jobs (
        research_job_id TEXT PRIMARY KEY,
        user_id TEXT DEFAULT '',
        profession_id TEXT NOT NULL,
        profession_name TEXT NOT NULL,
        employer_types_json TEXT DEFAULT '[]',
        country TEXT DEFAULT 'Türkiye',
        city TEXT NOT NULL,
        districts_json TEXT DEFAULT '[]',
        keywords TEXT DEFAULT '',
        status TEXT DEFAULT 'queued',
        total_found INTEGER DEFAULT 0,
        contacts_found INTEGER DEFAULT 0,
        verified_count INTEGER DEFAULT 0,
        progress_percent INTEGER DEFAULT 0,
        progress_stage TEXT DEFAULT '',
        error_message TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        started_at TEXT,
        completed_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS research_job_results (
        job_result_id TEXT PRIMARY KEY,
        research_job_id TEXT NOT NULL,
        employer_id TEXT NOT NULL,
        is_selected_for_application INTEGER DEFAULT 0,
        has_job_posting INTEGER DEFAULT 0,
        posting_details TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(research_job_id) REFERENCES research_jobs(research_job_id) ON DELETE CASCADE,
        FOREIGN KEY(employer_id) REFERENCES employers(employer_id) ON DELETE CASCADE,
        UNIQUE(research_job_id, employer_id)
    )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_res_jobs_user ON research_jobs(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_res_jobs_status ON research_jobs(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_res_results_job ON research_job_results(research_job_id)")
    
    # 7. Kullanıcılar tablosunu başlat ve varsayılan hesapları oluştur
    from ..auth.auth_service import init_users_table
    init_users_table(conn)

    # 8. V2.2 Şehir Bazlı Keşif ve Veri Bütünlüğü Tabloları (Discovery Sources, Runs, Source Records, Links)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS discovery_sources (
        source_id TEXT PRIMARY KEY,
        source_name TEXT NOT NULL,
        source_type TEXT NOT NULL,
        city TEXT DEFAULT '',
        base_url TEXT DEFAULT '',
        reliability_tier TEXT DEFAULT 'secondary_directory',
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS discovery_runs (
        run_id TEXT PRIMARY KEY,
        research_job_id TEXT DEFAULT '',
        source_id TEXT NOT NULL,
        city TEXT NOT NULL,
        district TEXT DEFAULT '',
        status TEXT DEFAULT 'running',
        items_found INTEGER DEFAULT 0,
        items_new INTEGER DEFAULT 0,
        items_updated INTEGER DEFAULT 0,
        error_message TEXT DEFAULT '',
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT,
        FOREIGN KEY(source_id) REFERENCES discovery_sources(source_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employer_source_records (
        record_id INTEGER PRIMARY KEY AUTOINCREMENT,
        employer_id TEXT NOT NULL,
        source_id TEXT NOT NULL,
        source_object_id TEXT DEFAULT '',
        source_url TEXT DEFAULT '',
        raw_name TEXT DEFAULT '',
        raw_address TEXT DEFAULT '',
        raw_phone TEXT DEFAULT '',
        raw_email TEXT DEFAULT '',
        raw_website TEXT DEFAULT '',
        coordinates TEXT DEFAULT '',
        observed_at TEXT DEFAULT '',
        confidence_score INTEGER DEFAULT 50,
        metadata_json TEXT DEFAULT '{}',
        FOREIGN KEY(employer_id) REFERENCES employers(employer_id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employer_identity_links (
        link_id INTEGER PRIMARY KEY AUTOINCREMENT,
        primary_employer_id TEXT NOT NULL,
        linked_employer_id TEXT NOT NULL,
        link_type TEXT NOT NULL,
        confidence REAL DEFAULT 1.0,
        reason TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(primary_employer_id) REFERENCES employers(employer_id) ON DELETE CASCADE
    )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_disc_runs_job ON discovery_runs(research_job_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_disc_runs_src ON discovery_runs(source_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_src_rec_emp ON employer_source_records(employer_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_src_rec_src ON employer_source_records(source_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ident_link_pri ON employer_identity_links(primary_employer_id)")

    # 9. V2.5 Kalıcı İletişim Zenginleştirme Kuyruğu (Contact Enrichment Queue)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contact_enrichment_queue (
        queue_id TEXT PRIMARY KEY,
        employer_id TEXT NOT NULL,
        research_job_id TEXT DEFAULT '',
        website_url TEXT DEFAULT '',
        status TEXT DEFAULT 'pending',
        attempts INTEGER DEFAULT 0,
        max_attempts INTEGER DEFAULT 3,
        discovered_email TEXT DEFAULT '',
        discovered_phone TEXT DEFAULT '',
        discovered_contact_form TEXT DEFAULT '',
        evidence_json TEXT DEFAULT '{}',
        error_message TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(employer_id) REFERENCES employers(employer_id) ON DELETE CASCADE
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ceq_status ON contact_enrichment_queue(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ceq_empid ON contact_enrichment_queue(employer_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ceq_jobid ON contact_enrichment_queue(research_job_id)")


    # research_jobs kolon kontrolleri (V2.2 metrikleri)
    cursor.execute("PRAGMA table_info(research_jobs)")
    res_cols = [col["name"] for col in cursor.fetchall()]
    if "quarantined_count" not in res_cols:
        cursor.execute("ALTER TABLE research_jobs ADD COLUMN quarantined_count INTEGER DEFAULT 0")
    if "sources_attempted_json" not in res_cols:
        cursor.execute("ALTER TABLE research_jobs ADD COLUMN sources_attempted_json TEXT DEFAULT '[]'")
    if "sources_succeeded_json" not in res_cols:
        cursor.execute("ALTER TABLE research_jobs ADD COLUMN sources_succeeded_json TEXT DEFAULT '[]'")
    if "sources_failed_json" not in res_cols:
        cursor.execute("ALTER TABLE research_jobs ADD COLUMN sources_failed_json TEXT DEFAULT '[]'")
    if "coverage_summary" not in res_cols:
        cursor.execute("ALTER TABLE research_jobs ADD COLUMN coverage_summary TEXT DEFAULT ''")

    # Temel keşif kaynaklarını kaydet
    default_sources = [
        ("osm_turkey_local", "OpenStreetMap Türkiye Diş Hekimliği İndeksi", "osm", "", "https://www.openstreetmap.org", "geographical_osm", 1),
        ("eskisehir_ism_official", "Eskişehir İl Sağlık Müdürlüğü Özel Sağlık Kuruluşları", "official", "Eskişehir", "https://eskisehirism.saglik.gov.tr", "primary_official", 1),
        ("tdb_registry", "Türk Dişhekimleri Birliği Resmî Sicil & Odalar", "chamber", "", "https://www.tdb.org.tr", "primary_official", 1),
        ("web_search_freeserp", "SearchRouter Dinamik Web Keşfi", "web_search", "", "https://freeserp.local", "fallback_search", 1),
        ("permitted_directories", "Kamuya Açık Sağlık Rehberleri", "directory", "", "https://doktortakvimi.com", "secondary_directory", 1)
    ]
    for s_id, s_name, s_type, s_city, s_url, s_tier, s_active in default_sources:
        cursor.execute("""
        INSERT OR IGNORE INTO discovery_sources (source_id, source_name, source_type, city, base_url, reliability_tier, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (s_id, s_name, s_type, s_city, s_url, s_tier, s_active))

    conn.commit()
    if should_close:
        conn.close()

def upsert_contact(
    cursor: sqlite3.Cursor,
    employer_id: str,
    contact_type: Any,
    contact_value: Any = "",
    contact_category: str = "unknown",
    source_url: str = "",
    source_type: str = "unknown",
    discovery_method: str = "unknown",
    evidence_text: str = "",
    confidence_category: str = "kaynakli",
    verification_status: str = "unverified",
    today_str: Optional[str] = None
) -> None:
    """Tekil bir iletişim bilgisini employer_contacts tablosuna kanıtlarıyla güvenle ekler veya günceller."""
    if isinstance(contact_type, dict):
        c_dict = contact_type
        if isinstance(contact_value, str) and contact_value.startswith("20"):
            today_str = contact_value
        contact_type = c_dict.get("contact_type", "")
        contact_value = c_dict.get("contact_value", "")
        contact_category = c_dict.get("contact_category", "unknown")
        source_url = c_dict.get("source_url", "")
        source_type = c_dict.get("source_type", "unknown")
        discovery_method = c_dict.get("discovery_method", "unknown")
        evidence_text = c_dict.get("evidence_text", "")
        confidence_category = c_dict.get("confidence_category", "kaynakli")
        verification_status = c_dict.get("verification_status", "observed_on_source")

    val = (contact_value or "").strip()
    if not val or not employer_id:
        return
    
    if today_str is None:
        today_str = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
    INSERT INTO employer_contacts (
        employer_id, contact_type, contact_value, contact_category, source_url, source_type,
        discovery_method, evidence_text, confidence_category, discovered_at, last_checked_at, verification_status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(employer_id, contact_type, contact_value) DO UPDATE SET
        contact_category = CASE WHEN excluded.contact_category != 'unknown' THEN excluded.contact_category ELSE employer_contacts.contact_category END,
        source_url = CASE WHEN excluded.source_url != '' THEN excluded.source_url ELSE employer_contacts.source_url END,
        source_type = CASE WHEN excluded.source_type != 'unknown' THEN excluded.source_type ELSE employer_contacts.source_type END,
        discovery_method = CASE WHEN excluded.discovery_method != 'unknown' THEN excluded.discovery_method ELSE employer_contacts.discovery_method END,
        evidence_text = CASE WHEN excluded.evidence_text != '' THEN excluded.evidence_text ELSE employer_contacts.evidence_text END,
        confidence_category = excluded.confidence_category,
        last_checked_at = excluded.last_checked_at,
        verification_status = CASE 
            WHEN excluded.verification_status = 'verified' THEN 'verified'
            WHEN employer_contacts.verification_status = 'verified' THEN 'verified'
            ELSE excluded.verification_status
        END
    """, (
        employer_id, contact_type, val, contact_category, source_url, source_type,
        discovery_method, evidence_text, confidence_category, today_str, today_str, verification_status
    ))

def get_employer_contacts(employer_id: str, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """İşverene ait tüm doğrulanmış ve aday iletişim kayıtlarını kanıtlarıyla getirir."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    cursor = conn.cursor()
    cursor.execute("""
    SELECT contact_id, employer_id, contact_type, contact_value, contact_category,
           source_url, source_type, discovery_method, evidence_text, confidence_category,
           discovered_at, last_checked_at, verification_status
    FROM employer_contacts
    WHERE employer_id = ?
    ORDER BY contact_type ASC, 
             CASE verification_status 
                 WHEN 'observed_on_source' THEN 1 
                 WHEN 'verified' THEN 1 
                 WHEN 'cross_source_supported' THEN 2 
                 WHEN 'needs_review' THEN 3 
                 ELSE 4 
             END ASC
    """, (employer_id,))
    rows = cursor.fetchall()
    if should_close:
        conn.close()
    return [dict(r) for r in rows]
    return [dict(r) for r in rows]

def upsert_employer(cursor: sqlite3.Cursor, r: Dict[str, Any], profession_id: str, city: str, today_str: str, now_str: str):
    name = r.get("name", "").strip()
    district = r.get("district", "").strip()
    emp_type = r.get("employer_type", "Genel İşveren")
    emp_id = r.get("employer_id") or canonical_id(name, district, emp_type)
    
    cursor.execute("SELECT * FROM employers WHERE employer_id = ?", (emp_id,))
    existing = cursor.fetchone()
    
    inc_phone = (r.get("phone") or "").strip()
    inc_phone_src = (r.get("phone_source_url") or "").strip()
    inc_phone_type = r.get("phone_type", "unknown")
    inc_phone_status = r.get("phone_verification_status", "unverified")
    
    inc_email = (r.get("email") or "").strip()
    inc_email_src = (r.get("email_source_url") or "").strip()
    inc_email_type = r.get("email_type", "unknown")
    inc_email_status = r.get("email_verification_status", "unverified")
    inc_whatsapp = (r.get("whatsapp_url") or "").strip()
    
    inc_web = (r.get("website") or "").strip()
    inc_web_src = (r.get("website_source_url") or "").strip()
    inc_web_status = r.get("website_verification_status", "unverified")
    
    inc_career = (r.get("career_url") or "").strip()
    inc_form = (r.get("contact_form_url") or "").strip()
    
    inc_attempted = (r.get("attempted_sources") or "").strip()
    inc_notes = (r.get("research_notes") or "").strip()
    
    inc_score = r.get("confidence_score", 50)
    inc_level = r.get("confidence_level", "Orta")
    inc_business = r.get("business_status", "active")
    inc_research = r.get("research_status", "completed" if (inc_phone or inc_email or inc_web or inc_form) else "pending")
    
    if existing:
        ex = dict(existing)
        
        # Telefon çelişkisi kontrolü
        final_phone = ex["phone"]
        final_phone_src = ex["phone_source_url"]
        final_phone_type = ex["phone_type"]
        final_phone_status = ex["phone_verification_status"]
        
        if inc_phone:
            if ex["phone"] and ex["phone"] != inc_phone:
                final_phone_status = "conflict"
            else:
                final_phone = inc_phone
                final_phone_src = inc_phone_src or ex["phone_source_url"]
                final_phone_type = inc_phone_type if inc_phone_type != "unknown" else ex["phone_type"]
                final_phone_status = inc_phone_status
                
        final_email = inc_email or ex["email"]
        final_email_src = inc_email_src or ex["email_source_url"]
        final_email_type = inc_email_type if inc_email_type != "unknown" else ex["email_type"]
        final_email_status = inc_email_status if inc_email else ex["email_verification_status"]
        
        final_web = inc_web or ex["website"]
        final_web_src = inc_web_src or ex["website_source_url"]
        final_web_status = inc_web_status if inc_web else ex["website_verification_status"]
        
        final_career = inc_career or ex.get("career_url", "")
        final_form = inc_form or ex.get("contact_form_url", "")
        final_whatsapp = inc_whatsapp or ex.get("whatsapp_url", "")
        
        final_attempted = inc_attempted or ex.get("attempted_sources", "")
        final_notes = inc_notes or ex.get("research_notes", "")
        
        final_verified_at = ex["contact_last_verified"]
        if (final_phone_status == "verified" or final_email_status == "verified"):
            final_verified_at = today_str

        # Audit Log
        for field, old_val, new_val in [
            ("phone", ex["phone"], final_phone),
            ("email", ex["email"], final_email),
            ("website", ex["website"], final_web),
            ("contact_form_url", ex.get("contact_form_url", ""), final_form),
            ("phone_verification_status", ex["phone_verification_status"], final_phone_status)
        ]:
            if old_val != new_val and new_val:
                cursor.execute("""
                INSERT INTO employer_audit_log (employer_id, field_name, old_value, new_value, source, changed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (emp_id, field, old_val, new_val, r.get("source_type", "scan"), now_str))

        cursor.execute("""
        UPDATE employers SET
            district = ?,
            name = ?,
            employer_type = ?,
            address = ?,
            phone = ?,
            phone_type = ?,
            phone_source_url = ?,
            phone_verification_status = ?,
            email = ?,
            email_type = ?,
            email_source_url = ?,
            email_verification_status = ?,
            website = ?,
            website_source_url = ?,
            website_verification_status = ?,
            career_url = ?,
            contact_form_url = ?,
            whatsapp_url = ?,
            source_urls = ?,
            source_type = ?,
            business_status = ?,
            research_status = ?,
            attempted_sources = ?,
            research_notes = ?,
            confidence_score = ?,
            confidence_level = ?,
            is_email_found = ?,
            source_last_checked = ?,
            contact_last_verified = ?,
            observed_at = ?,
            updated_at = ?
        WHERE employer_id = ?
        """, (
            district or ex["district"],
            name,
            emp_type or ex["employer_type"],
            r.get("address") or ex["address"],
            final_phone,
            final_phone_type,
            final_phone_src,
            final_phone_status,
            final_email,
            final_email_type,
            final_email_src,
            final_email_status,
            final_web,
            final_web_src,
            final_web_status,
            final_career,
            final_form,
            final_whatsapp,
            r.get("source_urls") or ex["source_urls"],
            r.get("source_type") or ex["source_type"],
            inc_business,
            "completed" if (final_phone or final_email or final_web or final_form or final_whatsapp) else "pending",
            final_attempted,
            final_notes,
            inc_score,
            inc_level,
            1 if final_email else 0,
            today_str,
            final_verified_at,
            today_str,
            now_str,
            emp_id
        ))
    else:
        final_verified_at = today_str if (inc_phone_status == "verified" or inc_email_status == "verified") else None
        cursor.execute("""
        INSERT INTO employers (
            employer_id, profession_id, city, district, name, employer_type,
            address, phone, phone_type, phone_source_url, phone_verification_status,
            email, email_type, email_source_url, email_verification_status,
            website, website_source_url, website_verification_status, career_url,
            contact_form_url, whatsapp_url, source_urls, source_type, business_status, research_status,
            attempted_sources, research_notes,
            confidence_score, confidence_level, is_email_found,
            source_last_checked, contact_last_verified, observed_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            emp_id, profession_id, city, district, name, emp_type,
            r.get("address", ""),
            inc_phone, inc_phone_type, inc_phone_src, inc_phone_status,
            inc_email, inc_email_type, inc_email_src, inc_email_status,
            inc_web, inc_web_src, inc_web_status,
            inc_career, inc_form, inc_whatsapp,
            r.get("source_urls", ""),
            r.get("source_type", "Bilinmiyor"),
            inc_business, inc_research,
            inc_attempted, inc_notes,
            inc_score, inc_level,
            1 if inc_email else 0,
            today_str, final_verified_at, today_str,
            now_str, now_str
        ))

    # Çoklu İletişim Kayıtlarını employer_contacts tablosuna da kaydet
    src_type = r.get("source_type", "Bilinmiyor")
    if inc_phone:
        upsert_contact(cursor, emp_id, "phone", inc_phone, inc_phone_type, inc_phone_src, src_type,
                       discovery_method="scan", evidence_text="Birincil telefon", confidence_category="kaynakli",
                       verification_status=inc_phone_status, today_str=today_str)
    if inc_email:
        upsert_contact(cursor, emp_id, "email", inc_email, inc_email_type, inc_email_src, src_type,
                       discovery_method="scan", evidence_text="Birincil e-posta", confidence_category="kaynakli",
                       verification_status=inc_email_status, today_str=today_str)
    if inc_web:
        upsert_contact(cursor, emp_id, "website", inc_web, "corporate", inc_web_src or inc_web, src_type,
                       discovery_method="scan", evidence_text="Birincil web sitesi", confidence_category="kaynakli",
                       verification_status=inc_web_status, today_str=today_str)
    if inc_career:
        upsert_contact(cursor, emp_id, "career_page", inc_career, "career", inc_career, src_type,
                       discovery_method="scan", evidence_text="Kariyer sayfası", confidence_category="kaynakli",
                       verification_status="verified", today_str=today_str)
    if inc_form:
        upsert_contact(cursor, emp_id, "contact_form", inc_form, "contact_form", inc_form, src_type,
                       discovery_method="scan", evidence_text="İletişim formu", confidence_category="kaynakli",
                       verification_status="verified", today_str=today_str)
    if final_whatsapp:
        upsert_contact(cursor, emp_id, "whatsapp", final_whatsapp, "messaging", final_whatsapp, src_type,
                       discovery_method="scan", evidence_text="WhatsApp iletişim kanalı", confidence_category="kaynakli",
                       verification_status="observed_on_source", today_str=today_str)

    # Detaylı kontaklar listesi verilmişse (kanıtlarıyla birlikte)
    for c in r.get("contacts", []):
        upsert_contact(
            cursor, emp_id,
            contact_type=c.get("contact_type", "unknown"),
            contact_value=c.get("contact_value", ""),
            contact_category=c.get("contact_category", "unknown"),
            source_url=c.get("source_url", ""),
            source_type=c.get("source_type", src_type),
            discovery_method=c.get("discovery_method", "unknown"),
            evidence_text=c.get("evidence_text", ""),
            confidence_category=c.get("confidence_category", "kaynakli"),
            verification_status=c.get("verification_status", "unverified"),
            today_str=today_str
        )

def save_employers(
    profession_id: str,
    city: str,
    records: List[Dict[str, Any]],
    osm_status: str = "success",
    official_status: str = "success",
    error_log: Optional[str] = None
):
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_str = datetime.now().strftime("%Y-%m-%d")

    for r in records:
        upsert_employer(cursor, r, profession_id, city, today_str, now_str)
        
    cursor.execute("""
    SELECT 
        COUNT(*) as cnt,
        SUM(CASE WHEN email != '' THEN 1 ELSE 0 END) as email_cnt,
        SUM(CASE WHEN phone != '' THEN 1 ELSE 0 END) as phone_cnt,
        SUM(CASE WHEN contact_form_url != '' THEN 1 ELSE 0 END) as form_cnt
    FROM employers WHERE profession_id = ? AND city = ?
    """, (profession_id, city))
    stats = cursor.fetchone()
    total_count = stats["cnt"] or 0
    email_count = stats["email_cnt"] or 0
    phone_count = stats["phone_cnt"] or 0
    form_count = stats["form_cnt"] or 0

    cursor.execute("""
    INSERT INTO search_cache (profession_id, city, last_scanned_at, total_count, email_count, phone_count, contact_form_count, osm_status, official_status, status, error_log)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?)
    ON CONFLICT(profession_id, city) DO UPDATE SET
        last_scanned_at = excluded.last_scanned_at,
        total_count = excluded.total_count,
        email_count = excluded.email_count,
        phone_count = excluded.phone_count,
        contact_form_count = excluded.contact_form_count,
        osm_status = excluded.osm_status,
        official_status = excluded.official_status,
        status = 'ready',
        error_log = excluded.error_log
    """, (profession_id, city, now_str, total_count, email_count, phone_count, form_count, osm_status, official_status, error_log))

    conn.commit()
    if should_close:
        conn.close()

def get_cache_info(profession_id: str, city: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT profession_id, city, last_scanned_at, total_count, email_count, phone_count, contact_form_count, osm_status, official_status, status, error_log
    FROM search_cache
    WHERE profession_id = ? AND city = ?
    """, (profession_id, city))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def query_employers(
    profession_id: str = "dentist",
    city: str = "Eskişehir",
    districts: Optional[List[str]] = None,
    employer_type: Optional[str] = None,
    phone_status: Optional[str] = None,
    email_status: Optional[str] = None,
    research_status: Optional[str] = None,
    search_text: Optional[str] = None,
    only_with_email: bool = False,
    include_contacts: bool = False,
    verification_status: Optional[str] = None
) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM employers WHERE profession_id = ? AND city = ?"
    params: List[Any] = [profession_id, city]
    
    if districts:
        valid_districts = [d for d in districts if d and d.lower() != "tümü" and d.lower() != "all"]
        if valid_districts:
            placeholders = ",".join("?" for _ in valid_districts)
            query += f" AND district IN ({placeholders})"
            params.extend(valid_districts)
            
    if employer_type and employer_type != "all" and employer_type != "Tüm uygun işverenler":
        query += " AND employer_type LIKE ?"
        params.append(f"%{employer_type}%")

    if phone_status and phone_status != "all":
        query += " AND phone_verification_status = ?"
        params.append(phone_status)

    if email_status and email_status != "all":
        query += " AND email_verification_status = ?"
        params.append(email_status)

    if verification_status and verification_status != "all":
        query += " AND (phone_verification_status = ? OR email_verification_status = ? OR website_verification_status = ?)"
        params.extend([verification_status, verification_status, verification_status])

    if research_status and research_status != "all":
        query += " AND research_status = ?"
        params.append(research_status)
        
    if only_with_email:
        query += " AND email != ''"
        
    if search_text:
        query += " AND (name LIKE ? OR address LIKE ? OR district LIKE ? OR phone LIKE ?)"
        term = f"%{search_text}%"
        params.extend([term, term, term, term])
        
    query += " ORDER BY confidence_score DESC, district ASC, name ASC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    results = [dict(r) for r in rows]
    
    if include_contacts and results:
        for r in results:
            emp_id = r["employer_id"]
            cursor.execute("""
            SELECT * FROM employer_contacts 
            WHERE employer_id = ? 
            ORDER BY contact_type, 
                     CASE verification_status WHEN 'verified' THEN 1 WHEN 'manual_review' THEN 2 ELSE 3 END ASC
            """, (emp_id,))
            r["contacts"] = [dict(c) for c in cursor.fetchall()]
            
    conn.close()
    return results

# ==========================================
# V2.1 Dinamik Araştırma Görevleri Yardımcıları
# ==========================================

import json
import uuid

def create_research_job(
    profession_id: str,
    profession_name: str,
    city: str,
    employer_types: Optional[List[str]] = None,
    districts: Optional[List[str]] = None,
    keywords: str = "",
    user_id: str = "user-candidate-rumeysa",
    country: str = "Türkiye",
    conn: Optional[sqlite3.Connection] = None
) -> str:
    """Yeni bir araştırma görevi kaydeder ve job_id döner."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    cursor = conn.cursor()
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    emp_types_json = json.dumps(employer_types or ["all"], ensure_ascii=False)
    districts_json = json.dumps(districts or [], ensure_ascii=False)

    cursor.execute("""
    INSERT INTO research_jobs (
        research_job_id, user_id, profession_id, profession_name,
        employer_types_json, country, city, districts_json, keywords,
        status, total_found, contacts_found, verified_count, progress_percent,
        progress_stage, created_at, started_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', 0, 0, 0, 5, 'Araştırma sıraya alındı...', ?, ?)
    """, (
        job_id, user_id, profession_id, profession_name,
        emp_types_json, country, city, districts_json, keywords.strip(),
        now_str, now_str
    ))
    conn.commit()
    if should_close:
        conn.close()
    return job_id

def get_research_job(job_id: str, conn: Optional[sqlite3.Connection] = None) -> Optional[Dict[str, Any]]:
    """Araştırma görevinin durumunu ve ilerlemesini döner."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM research_jobs WHERE research_job_id = ?", (job_id,))
    row = cursor.fetchone()
    if not row:
        if should_close:
            conn.close()
        return None
    d = dict(row)
    d["employer_types"] = json.loads(d.get("employer_types_json") or "[]")
    d["districts"] = json.loads(d.get("districts_json") or "[]")
    if should_close:
        conn.close()
    return d

def list_research_jobs(user_id: Optional[str] = None, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """Kullanıcının kayıtlı araştırmalarını listeler."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    cursor = conn.cursor()
    if user_id:
        cursor.execute("SELECT * FROM research_jobs WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    else:
        cursor.execute("SELECT * FROM research_jobs ORDER BY created_at DESC")
    rows = cursor.fetchall()
    jobs = []
    for r in rows:
        d = dict(r)
        d["employer_types"] = json.loads(d.get("employer_types_json") or "[]")
        d["districts"] = json.loads(d.get("districts_json") or "[]")
        jobs.append(d)
    if should_close:
        conn.close()
    return jobs

def update_research_job_progress(
    job_id: str,
    status: str,
    progress_percent: int,
    progress_stage: str,
    total_found: Optional[int] = None,
    contacts_found: Optional[int] = None,
    verified_count: Optional[int] = None,
    error_message: Optional[str] = None,
    coverage_summary: Optional[str] = None,
    quarantined_count: Optional[int] = None,
    conn: Optional[sqlite3.Connection] = None
):
    """Araştırma görevinin anlık durumunu ve ilerleme sayacını günceller."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    updates = ["status = ?", "progress_percent = ?", "progress_stage = ?"]
    params = [status, progress_percent, progress_stage]

    if total_found is not None:
        updates.append("total_found = ?")
        params.append(total_found)
    if contacts_found is not None:
        updates.append("contacts_found = ?")
        params.append(contacts_found)
    if verified_count is not None:
        updates.append("verified_count = ?")
        params.append(verified_count)
    if error_message is not None:
        updates.append("error_message = ?")
        params.append(error_message)
    if coverage_summary is not None:
        updates.append("coverage_summary = ?")
        params.append(coverage_summary)
    if quarantined_count is not None:
        updates.append("quarantined_count = ?")
        params.append(quarantined_count)
    if status in ("completed", "failed", "partial"):
        updates.append("completed_at = ?")
        params.append(now_str)

    params.append(job_id)
    cursor.execute(f"UPDATE research_jobs SET {', '.join(updates)} WHERE research_job_id = ?", tuple(params))
    conn.commit()
    if should_close:
        conn.close()

def add_job_result(
    job_id: str,
    employer_id: str,
    has_job_posting: int = 0,
    posting_details: str = "",
    conn: Optional[sqlite3.Connection] = None
) -> str:
    """İşvereni belirli bir araştırma görevinin sonuç kümesine ekler."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    cursor = conn.cursor()
    res_id = f"res-{uuid.uuid4().hex[:12]}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    INSERT INTO research_job_results (
        job_result_id, research_job_id, employer_id, is_selected_for_application,
        has_job_posting, posting_details, created_at
    ) VALUES (?, ?, ?, 0, ?, ?, ?)
    ON CONFLICT(research_job_id, employer_id) DO UPDATE SET
        has_job_posting = excluded.has_job_posting,
        posting_details = excluded.posting_details
    """, (res_id, job_id, employer_id, has_job_posting, posting_details, now_str))
    conn.commit()
    if should_close:
        conn.close()
    return res_id

def get_job_results(
    job_id: str,
    filter_reachable: bool = False,
    filter_email: bool = False,
    filter_whatsapp: bool = False,
    filter_unapplied: bool = False,
    candidate_id: str = "candidate-dt-rumeysa-colak",
    conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """Araştırma görevi ile keşfedilen işverenlerin zengin kart verilerini döner."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    cursor = conn.cursor()
    cursor.execute("""
    SELECT 
        r.job_result_id, r.research_job_id, r.employer_id, r.is_selected_for_application,
        r.has_job_posting, r.posting_details,
        e.name, e.employer_type, e.city, e.district, e.address,
        e.phone, e.phone_verification_status,
        e.email, e.email_verification_status,
        e.website, e.website_verification_status,
        e.whatsapp_url, e.contact_form_url, e.career_url,
        e.source_urls, e.confidence_score, e.confidence_level, e.source_last_checked
    FROM research_job_results r
    JOIN employers e ON r.employer_id = e.employer_id
    WHERE r.research_job_id = ?
    ORDER BY 
        r.has_job_posting DESC,
        (CASE WHEN e.email != '' AND e.whatsapp_url != '' THEN 3 WHEN e.email != '' THEN 2 WHEN e.phone != '' THEN 1 ELSE 0 END) DESC,
        e.name ASC
    """, (job_id,))

    rows = cursor.fetchall()
    
    # Aday başvurusu var mı kontrolü
    cursor.execute("SELECT employer_id, status FROM applications WHERE candidate_id = ?", (candidate_id,))
    app_map = {r[0]: r[1] for r in cursor.fetchall()}

    results = []
    for row in rows:
        d = dict(row)
        channels = []
        if d.get("email"): channels.append("email")
        if d.get("whatsapp_url"): channels.append("whatsapp")
        if d.get("phone"): channels.append("phone")
        if d.get("website"): channels.append("website")
        if d.get("contact_form_url"): channels.append("contact_form")

        is_reachable = bool(d.get("email") or d.get("whatsapp_url") or d.get("phone") or d.get("contact_form_url"))
        app_status = app_map.get(d["employer_id"])

        if filter_reachable and not is_reachable:
            continue
        if filter_email and not d.get("email"):
            continue
        if filter_whatsapp and not d.get("whatsapp_url"):
            continue
        if filter_unapplied and app_status:
            continue

        d["available_channels"] = channels
        d["is_reachable"] = is_reachable
        d["application_status"] = app_status
        d["posting_type_label"] = "Açık İlan Tespit Edildi" if d.get("has_job_posting") else "Genel Başvuru"

        # V2.3 Multi-tenant Güvenliği: Oturum açan adayın gerçek profili ve doğrulanmış CV'si dinamik kullanılır
        from ..candidates.profile_manager import CandidateProfileManager
        from urllib.parse import quote
        from ..channels.whatsapp_handoff import normalize_tr_mobile_for_whatsapp

        mgr = CandidateProfileManager(conn)
        cand_profile = mgr.get_candidate(candidate_id) if candidate_id else None
        if not cand_profile and candidate_id:
            cand_profile = mgr.get_candidate_by_user_id(candidate_id)

        if cand_profile:
            cand_name = cand_profile.get("full_name") or f"{cand_profile.get('first_name', '')} {cand_profile.get('last_name', '')}".strip() or "Diş Hekimi Adayı"
            cand_uni = cand_profile.get("graduation_school") or cand_profile.get("university", "Diş Hekimliği Fakültesi")
            cand_phone = cand_profile.get("phone", "")
            cand_cv_url = cand_profile.get("secure_cv_url") or f"https://careermap.local/cv/view/{cand_profile.get('candidate_id', '')}"
        else:
            cand_name = "Diş Hekimi Adayı"
            cand_uni = "Diş Hekimliği Fakültesi"
            cand_phone = ""
            cand_cv_url = "https://careermap.local/cv"

        emp_email = (d.get("email") or "").strip()
        clinic_name = d.get("name") or "Klinik"
        email_subj = f"Diş Hekimi İş Başvurusu – {cand_name} | {clinic_name}"
        email_body_text = f"""Sayın Yetkili ({clinic_name}),

Ben {cand_name}. {cand_uni} mezunuyum.

Kliniğiniz bünyesinde diş hekimi kadrosunda değerlendirilmek üzere doğrulanmış özgeçmişimi bilgilerinize sunuyorum:
{cand_cv_url}

Saygılarımla,
{cand_name}
{cand_phone}"""

        # V2.2 Karantina ve Güvenilirlik Kontrolü
        status = d.get("research_status", "")
        conf = d.get("confidence_score", 50)
        is_quar = (status == "quarantined") or (conf < 40)
        d["is_quarantined"] = is_quar
        d["can_apply"] = not is_quar

        if emp_email and not is_quar:
            d["gmail_compose_url"] = f"https://mail.google.com/mail/?view=cm&fs=1&to={quote(emp_email)}&su={quote(email_subj)}&body={quote(email_body_text)}"
            d["mailto_url"] = f"mailto:{emp_email}?subject={quote(email_subj)}&body={quote(email_body_text)}"
        else:
            d["gmail_compose_url"] = ""
            d["mailto_url"] = ""

        # WhatsApp doğrudan yönlendirme bağlantıları (P4: Telefon bulunması otomatik WhatsApp sayılmaz)
        raw_wa = d.get("whatsapp_url") or ""
        clean_wa = normalize_tr_mobile_for_whatsapp(raw_wa) if (raw_wa and not is_quar) else ""
        if clean_wa:
            wa_text = f"Merhaba Sayın Yetkili ({clinic_name}), ben {cand_name} ({cand_uni}). Kliniğinizde değerlendirilmek üzere özgeçmişimi paylaşmak isterim: {cand_cv_url} . İyi çalışmalar dilerim."
            d["whatsapp_web_url"] = f"https://web.whatsapp.com/send?phone={clean_wa}&text={quote(wa_text)}"
            d["whatsapp_app_url"] = f"https://api.whatsapp.com/send?phone={clean_wa}&text={quote(wa_text)}"
        else:
            d["whatsapp_web_url"] = ""
            d["whatsapp_app_url"] = ""
        results.append(d)

    if should_close:
        conn.close()
    return results

def set_job_result_selection(job_id: str, employer_id: str, is_selected: bool, conn: Optional[sqlite3.Connection] = None):
    """Kullanıcının başvuru hazırlamak için seçtiği kurumları işaretler."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    cursor = conn.cursor()
    val = 1 if is_selected else 0
    cursor.execute("""
    UPDATE research_job_results SET is_selected_for_application = ?
    WHERE research_job_id = ? AND employer_id = ?
    """, (val, job_id, employer_id))
    conn.commit()
    if should_close:
        conn.close()

# --- V2.2 Şehir Keşif Motoru ve Kayıt Helper Fonksiyonları ---

def record_discovery_run(
    source_id: str,
    city: str,
    district: str = "",
    research_job_id: str = "",
    conn: Optional[sqlite3.Connection] = None
) -> str:
    """Yeni bir kaynak keşif koşusu kaydeder."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    cursor = conn.cursor()
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    INSERT INTO discovery_runs (run_id, research_job_id, source_id, city, district, status, started_at)
    VALUES (?, ?, ?, ?, ?, 'running', ?)
    """, (run_id, research_job_id, source_id, city, district, now_str))

    conn.commit()
    if should_close:
        conn.close()
    return run_id

def update_discovery_run(
    run_id: str,
    status: str,
    items_found: int = 0,
    items_new: int = 0,
    items_updated: int = 0,
    error_message: str = "",
    conn: Optional[sqlite3.Connection] = None
):
    """Keşif koşusunun sonuçlarını ve tamamlanma durumunu günceller."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    UPDATE discovery_runs
    SET status = ?, items_found = ?, items_new = ?, items_updated = ?, error_message = ?, completed_at = ?
    WHERE run_id = ?
    """, (status, items_found, items_new, items_updated, error_message, now_str, run_id))

    conn.commit()
    if should_close:
        conn.close()

def add_employer_source_record(
    employer_id: str,
    source_id: str,
    source_object_id: str = "",
    source_url: str = "",
    raw_name: str = "",
    raw_address: str = "",
    raw_phone: str = "",
    raw_email: str = "",
    raw_website: str = "",
    coordinates: str = "",
    confidence_score: int = 50,
    metadata: Optional[Dict[str, Any]] = None,
    conn: Optional[sqlite3.Connection] = None
):
    """Bir işverenin belirli bir kaynaktan elde edilen ham kanıt kaydını ekler."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)

    cursor.execute("""
    INSERT INTO employer_source_records (
        employer_id, source_id, source_object_id, source_url,
        raw_name, raw_address, raw_phone, raw_email, raw_website,
        coordinates, observed_at, confidence_score, metadata_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        employer_id, source_id, source_object_id, source_url,
        raw_name, raw_address, raw_phone, raw_email, raw_website,
        coordinates, now_str, confidence_score, meta_json
    ))

    conn.commit()
    if should_close:
        conn.close()

def add_employer_identity_link(
    primary_employer_id: str,
    linked_employer_id: str,
    link_type: str = "branch",
    confidence: float = 1.0,
    reason: str = "",
    conn: Optional[sqlite3.Connection] = None
):
    """İki işveren kaydı arasındaki kimlik/şube ilişkisini kaydeder."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO employer_identity_links (primary_employer_id, linked_employer_id, link_type, confidence, reason)
    VALUES (?, ?, ?, ?, ?)
    """, (primary_employer_id, linked_employer_id, link_type, confidence, reason))

    conn.commit()
    if should_close:
        conn.close()

init_db()
