"""CareerMap V1.2 Alan Bazlı Doğrulama ve Kalite Değerlendirme Motoru."""
from datetime import datetime
from typing import List, Dict, Any
from ..professions.base import BaseProfession

def assess_records_quality(records: List[Dict[str, Any]], profession: BaseProfession) -> List[Dict[str, Any]]:
    """
    Her kayıt için ALAN BAZLI doğrulama durumlarını ve genel veri doluluk puanını hesaplar.
    İşletmenin kendisi ile telefon, e-posta ve web sitesi durumları birbirinden bağımsızdır!
    """
    today_str = datetime.now().strftime("%Y-%m-%d")

    for r in records:
        phone = (r.get("phone") or "").strip()
        phone_src = (r.get("phone_source_url") or "").strip()
        email = (r.get("email") or "").strip()
        email_src = (r.get("email_source_url") or "").strip()
        web = (r.get("website") or "").strip()
        web_src = (r.get("website_source_url") or "").strip()
        
        # 1. Telefon Alanı Doğrulaması
        current_p_status = r.get("phone_verification_status", "unverified")
        if current_p_status == "conflict":
            p_status = "conflict"
        elif phone and phone_src:
            p_status = "verified"
        elif phone:
            p_status = "manual_review"
        else:
            p_status = "unverified"
        r["phone_verification_status"] = p_status

        # 2. E-posta Alanı Doğrulaması
        if email and email_src:
            e_status = "verified"
        elif email:
            e_status = "manual_review"
        else:
            e_status = "unverified"
        r["email_verification_status"] = e_status

        # 3. Web Sitesi Alanı Doğrulaması
        current_w_status = r.get("website_verification_status", "unverified")
        if current_w_status == "manual_review":
            w_status = "manual_review"
        elif web and web_src:
            w_status = "verified"
        elif web:
            w_status = "manual_review"
        else:
            w_status = "unverified"
        r["website_verification_status"] = w_status

        # 4. Araştırma ve İşletme Durumu
        form = (r.get("contact_form_url") or "").strip()
        r["business_status"] = r.get("business_status") or "active"
        if phone and (email or form) and web:
            r["research_status"] = "completed"
        elif phone or email or web or form:
            r["research_status"] = "partial"
        else:
            r["research_status"] = "pending"

        # Geriye dönük genel doğrulama durumu
        if p_status == "verified" or e_status == "verified":
            r["verification_status"] = "verified"
        elif p_status in ["manual_review", "conflict"] or e_status == "manual_review":
            r["verification_status"] = "manual_review"
        else:
            r["verification_status"] = "unverified"

        # 5. Güven Puanı (Veri Zenginliği & Çoklu Kaynak)
        score = 25
        if "İl Sağlık" in r.get("source_type", ""):
            score += 25
        if "TDB" in r.get("source_type", "") or "tdb.org.tr" in phone_src:
            score += 25
        if "OpenStreetMap" in r.get("source_type", ""):
            score += 15
        if "+" in r.get("source_type", ""):
            score += 15
            
        if phone: score += 5
        if email: score += 5
        if web: score += 5
        if r.get("address") and len(r["address"]) > 12: score += 5

        score = min(score, 100)
        r["confidence_score"] = score
        r["confidence_level"] = "Yüksek" if score >= 75 else ("Orta" if score >= 50 else "Düşük")
        
        r["is_email_found"] = bool(email)
        if not r.get("source_last_checked"):
            r["source_last_checked"] = today_str
        if not r.get("observed_at"):
            r["observed_at"] = today_str
            
        if p_status == "verified" or e_status == "verified":
            r["contact_last_verified"] = today_str

    # Sıralama
    records.sort(key=lambda x: (
        x.get("phone_verification_status") != "verified",
        not x.get("is_email_found"),
        -x.get("confidence_score", 0),
        x.get("district", ""),
        x.get("name", "")
    ))
    return records
