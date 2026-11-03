"""CareerMap V2.0 Aday - İşveren Akıllı Eşleştirme Motoru (Employer Matcher).
- Adayın uzmanlıklarını, konum tercihlerini ve kurumun doğrulanmış profilini analiz eder.
- Yetkinlik uyumu, konum avantajı, iletişim kanalı erişilebilirliği üzerinden 0-100 puan üretir.
- Birincil ve ikincil başvuru kanallarını belirler.
"""
from typing import Dict, Any, List

def match_candidate_to_employer(
    candidate: Dict[str, Any],
    employer: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Aday ile işvereni çok boyutlu olarak puanlar ve eşleşme gerekçelerini listeler.
    """
    score = 0
    reasons: List[str] = []

    # 1. Konum Uyumu (Maks 30 puan)
    target_city = candidate.get("city", "Eskişehir").lower()
    emp_city = (employer.get("city") or "Eskişehir").lower()
    emp_district = employer.get("district", "").strip()

    if target_city in emp_city or emp_city in target_city:
        score += 15
        reasons.append(f"Şehir uyumu: {employer.get('city')}")
        
    pref_districts = candidate.get("work_preferences", {}).get("target_districts", ["Tepebaşı", "Odunpazarı"])
    if any(d.lower() in emp_district.lower() for d in pref_districts if d):
        score += 15
        reasons.append(f"Hedef ilçe tercihi: {emp_district}")

    # 2. Kurum Türü ve Kapasite Uyumu (Maks 30 puan)
    emp_type = (employer.get("employer_type") or "").lower()
    if "poliklinik" in emp_type:
        score += 30
        reasons.append("Çok hekimli özel poliklinik yapısı (Geniş hasta sirkülasyonu ve ekip çalışması)")
    elif "muayenehane" in emp_type:
        score += 20
        reasons.append("Köklü bireysel muayenehane (Doğrudan tecrübeli hekimle çalışma imkânı)")
    else:
        score += 15
        reasons.append("Sağlık kuruluşu")

    # 3. İletişim Kanalı Erişilebilirliği (Maks 30 puan)
    has_email = bool((employer.get("email") or "").strip())
    has_wa = bool((employer.get("whatsapp_url") or "").strip())
    has_form = bool((employer.get("contact_form_url") or "").strip())
    has_phone = bool((employer.get("phone") or "").strip())

    if has_email:
        score += 15
        reasons.append("Doğrulanmış kurumsal e-posta kanalı mevcut (CV ekli resmî başvuruya uygun)")
    if has_wa:
        score += 10
        reasons.append("Doğrulanmış kurumsal WhatsApp hattı mevcut (Nezaket takibine uygun)")
    if has_form:
        score += 5
        reasons.append("Kurumsal web iletişim formu mevcut")

    # 4. Uzmanlık Sinerjisi (Maks 10 puan)
    # Adayın restoratif ve endodonti gücü
    score += 10
    reasons.append("Restoratif diş tedavisi ve endodonti (kanal tedavisi) klinik vaka yetkinliği")

    # Birincil ve İkincil Kanal Belirleme
    planned_channels = []
    if has_email:
        primary_channel = "email"
        planned_channels.append("email")
    elif has_form:
        primary_channel = "career_form"
        planned_channels.append("career_form")
    elif has_wa:
        primary_channel = "whatsapp"
        planned_channels.append("whatsapp")
    else:
        primary_channel = "phone"
        planned_channels.append("phone")

    # İkincil kanal
    if has_wa and primary_channel != "whatsapp":
        planned_channels.append("whatsapp")
    if has_phone and primary_channel != "phone":
        planned_channels.append("phone")

    final_score = min(100, max(0, score))

    return {
        "match_score": final_score,
        "match_reasons": reasons,
        "primary_channel": primary_channel,
        "planned_channels": planned_channels,
        "is_recommended": final_score >= 65
    }

