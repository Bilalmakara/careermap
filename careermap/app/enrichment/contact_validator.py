"""CareerMap V1.5 Merkezi İletişim Doğrulama ve Kalite Motoru (Contact Validator).
- Bütün iletişim verilerinin (e-posta, telefon, web sitesi, form) tekil kalite ve doğrulama noktasıdır.
- Geçersiz, semver, kütüphane veya ajans e-postalarını eler.
- Telefonları Google phonenumbers ile TR E.164 formatına ve standart 0(222)/0(5XX) görünümüne dönüştürür.
- Yabancı ülke veya şüpheli numaraları incelemeye sevk eder.
- Kişisel hekim telefonu ile kurumsal klinik santrali ayrımını korur.
- 'observed_on_source' (kaynakta gözlemlendi) standardını uygular.
"""
import re
import logging
from typing import Dict, Any, List, Optional
import phonenumbers
from phonenumbers import PhoneNumberType, PhoneNumberFormat

from .email_extractor import clean_email, classify_email, is_agency_email, SOFTWARE_PACKAGES, STRICT_EMAIL_RE
from .phone_extractor import inspect_phone_number, format_e164

logger = logging.getLogger("careermap.enrichment.validator")

# Bilinen kurumsal ortak santraller (Örn: Modapol, İpek Diş)
KNOWN_SHARED_SWITCHBOARDS = {
    "0(222) 220 50 50": "Özel Modapol Polikliniği Çok Şubeli Merkezi Santral",
    "0(222) 231 15 15": "Özel İpek Polikliniği Çok Şubeli Ortak Santral"
}

def validate_email_contact(
    raw_email: str,
    employer: Dict[str, Any],
    source_url: str = ""
) -> Dict[str, Any]:
    """
    E-postayı sıkı kalite ve işletme uyum denetiminden geçirir.
    """
    res = {
        "is_valid": False,
        "cleaned_email": "",
        "email_type": "unknown",
        "verification_status": "invalid",
        "reasons": [],
        "evidence_snippet": ""
    }

    cleaned = clean_email(raw_email)
    if not cleaned:
        res["reasons"].append("Geçersiz e-posta formatı veya reddedilen uzantı/paket adı.")
        return res

    res["cleaned_email"] = cleaned
    category = classify_email(cleaned)
    res["email_type"] = category

    # Ajans kontrolü
    if is_agency_email(cleaned):
        res["is_valid"] = True
        res["verification_status"] = "needs_review"
        res["email_type"] = "agency"
        res["reasons"].append("Web tasarım / yazılım ajansı altbilgi e-postası (birincil hekim e-postası olamaz).")
        return res

    domain = cleaned.split("@")[1].lower()
    emp_name = employer.get("name", "").lower()

    # Geliştirici, dizin veya şablon engeli
    directory_portal_domains = {
        "sitem.com", "example.com", "dentisarea.com", "dishek.org", "isigmeclisi.org",
        "firmaportal.com", "hekimhane.com.tr", "istebudoktor.com.tr", "dishekimleri.net",
        "ilandan.com", "doktortakvimi.com", "doktorsitesi.com", "bulurum.com", "yellowpages.com.tr"
    }
    if "sentry" in domain or "wixpress" in domain or domain in directory_portal_domains:
        res["reasons"].append(f"Geliştirici, dizin veya şablon e-postası engellendi: @{domain}")
        return res
    
    # Genel ücretsiz sağlayıcılar (gmail, hotmail vb.) veya kurumsal özel domain
    free_providers = ["gmail.com", "hotmail.com", "yahoo.com", "outlook.com", "yandex.com"]
    if domain in free_providers:
        res["is_valid"] = True
        res["verification_status"] = "observed_on_source"
        res["reasons"].append(f"Resmi sitede listelenen genel sağlayıcı e-postası ({domain}).")
    else:
        res["is_valid"] = True
        res["verification_status"] = "observed_on_source"
        res["reasons"].append(f"Kurumsal alan adı e-postası (@{domain}).")

    return res

def validate_phone_contact(
    raw_phone: str,
    employer: Dict[str, Any],
    source_url: str = ""
) -> Dict[str, Any]:
    """
    Telefonu TR numaralandırma planına ve E.164 standardına göre doğrular ve biçimlendirir.
    """
    res = {
        "is_valid": False,
        "formatted_phone": "",
        "e164": "",
        "phone_type": "unknown",
        "verification_status": "invalid",
        "reasons": []
    }

    if not raw_phone or not raw_phone.strip():
        res["reasons"].append("Telefon numarası boş.")
        return res

    # 7 haneli yerel Eskişehir numarası normalizasyonu (Örn: 2214603 -> 0(222) 221 46 03)
    digits_only = re.sub(r"[^0-9]", "", raw_phone)
    if len(digits_only) == 7 and digits_only[0] in ["2", "3"]:
        raw_phone = f"0222{digits_only}"

    phone_info = inspect_phone_number(raw_phone)
    if not phone_info or not phone_info.get("is_valid") or phone_info.get("is_foreign"):
        res["reasons"].append(f"Geçersiz Türkiye numarası veya yabancı ülke kodu: '{raw_phone}'")
        return res

    formatted = phone_info.get("formatted", "")
    e164_val = phone_info.get("e164", "")
    p_type = phone_info.get("line_type", "unknown")

    res["is_valid"] = True
    res["formatted_phone"] = formatted
    res["e164"] = e164_val

    # Kurumsal ortak santral denetimi
    if formatted in KNOWN_SHARED_SWITCHBOARDS:
        res["phone_type"] = "corporate_shared_switchboard"
        res["verification_status"] = "cross_source_supported"
        res["reasons"].append(KNOWN_SHARED_SWITCHBOARDS[formatted])
        return res

    emp_type = employer.get("employer_type", "").lower()
    is_office = "muayenehane" in emp_type or employer.get("name", "").strip().lower().startswith("dt")

    if is_office:
        # Bireysel hekimde mobil numara tescilli sicil veya kurumsal cep olabilir
        if p_type == "mobile":
            res["phone_type"] = "personal_mobile"
        else:
            res["phone_type"] = "office_landline"
    else:
        res["phone_type"] = "corporate"

    res["verification_status"] = "observed_on_source"
    res["reasons"].append("TR E.164 standardı doğrulandı.")
    return res

def validate_associated_clinic(
    clinic_name: str,
    clinic_url: str,
    dentist_employer: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Bireysel bir hekimin bir poliklinik veya klinikte çalıştığı tespit edildiğinde,
    hekimle klinik arasındaki bağlantıyı ayrı bir tüzel ilişki olarak modeller.
    """
    return {
        "is_valid": True,
        "relation_type": "associated_clinic",
        "dentist_id": dentist_employer.get("employer_id", ""),
        "dentist_name": dentist_employer.get("name", ""),
        "clinic_name": clinic_name.strip(),
        "clinic_url": clinic_url.rstrip("/"),
        "verification_status": "observed_on_source",
        "evidence_text": f"Hekim '{dentist_employer.get('name')}', '{clinic_name}' poliklinik hekim kadrosunda tespit edildi."
    }
