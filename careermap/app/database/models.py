"""CareerMap V1.4 Alan Bazlı Doğrulama, Kanıt Tabanlı İletişim İstihbaratı ve Tip Tanımlamaları."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class EmployerContactRecord(BaseModel):
    contact_id: Optional[int] = None
    employer_id: str
    contact_type: str  # phone, email, website, contact_form, career_page, appointment_form
    contact_value: str
    contact_category: str = "unknown"  # corporate, personal_registry, career, general, randevu, contact_form, other, unknown
    source_url: str = ""
    source_type: str = "unknown"  # official_health, tdb, osm, website_scrape, open_directory
    discovery_method: str = "unknown"  # tel_link, mailto, json_ld, microdata, text_regex, form_action, tdb_registry, osm_tag
    evidence_text: str = ""  # Kanıt metni / snippet / HTML context
    confidence_category: str = "kaynakli"  # kaynakli, capraz_destekli, supheli, manuel_dogrulanmis
    discovered_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    last_checked_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    verification_status: str = "unverified"  # verified, unverified, manual_review, conflict

class EmployerRecord(BaseModel):
    id: Optional[int] = None
    employer_id: str  # Kalıcı, deterministik kimlik
    profession_id: str = "dentist"
    city: str = "Eskişehir"
    district: str = ""
    name: str
    employer_type: str = "Genel İşveren"
    address: str = ""
    
    # Birincil / Ana İletişim Bilgileri (Hızlı erişim)
    phone: str = ""
    phone_type: str = "unknown"  # corporate, personal_registry, unknown
    phone_source_url: str = ""
    phone_verification_status: str = "unverified"  # verified, unverified, conflict, manual_review
    
    email: str = ""
    email_type: str = "unknown"  # career, general, other, unknown
    email_source_url: str = ""
    email_verification_status: str = "unverified"  # verified, unverified, manual_review
    
    website: str = ""
    website_source_url: str = ""
    website_verification_status: str = "unverified"  # verified, unverified, manual_review
    career_url: str = ""
    contact_form_url: str = ""
    
    # Çoklu İletişim Listesi (Kanıtlı)
    contacts: List[EmployerContactRecord] = Field(default_factory=list)
    
    # Kaynak, Faaliyet ve Araştırma Durumları
    source_urls: str = ""
    source_type: str = "Bilinmiyor"
    business_status: str = "unknown"  # active, unknown, closed_or_moved
    research_status: str = "pending"  # pending, running, completed, partial, failed, manual_review
    attempted_sources: str = ""  # Örn: "OSM, TDB, Web"
    research_notes: str = ""  # Neden bulunamadığı veya araştırma özeti
    
    # Puanlama ve Tarihler
    confidence_score: int = 50
    confidence_level: str = "Orta"  # Yüksek, Orta, Düşük
    is_email_found: bool = False
    source_last_checked: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    contact_last_verified: Optional[str] = None
    observed_at: Optional[str] = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class SearchQuery(BaseModel):
    profession: str = "dentist"
    city: str = "Eskişehir"
    districts: List[str] = []
    employer_type: str = "all"
    phone_status: Optional[str] = None
    email_status: Optional[str] = None
    research_status: Optional[str] = None
    force_refresh: bool = False

class SearchSummary(BaseModel):
    profession_id: str
    profession_name: str
    city: str
    total_employers: int
    with_phone: int
    with_email: int
    with_website: int
    with_contact_form: int = 0
    verified_phones: int
    verified_emails: int
    verified_websites: int
    manual_review_count: int
    last_scanned: Optional[str] = None
