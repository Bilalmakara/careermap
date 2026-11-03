"""CareerMap V2.0 Telefon Görüşme ve Arama Hazırlık Modülü (Phone Handoff).
- İş arayan hekim için klinikle yapılacak 30-45 saniyelik profesyonel görüşme notunu hazırlar.
- Tıklanabilir tel: bağlantısı ve sekreterya/mesul müdür konuşma rehberi sunar.
"""
from typing import Dict, Any

def generate_phone_handoff(
    employer: Dict[str, Any],
    candidate: Dict[str, Any],
    call_script: str
) -> Dict[str, Any]:
    raw_phone = (employer.get("phone") or "").strip()
    clean_digits = "".join(c for c in raw_phone if c.isdigit())
    tel_link = f"tel:{clean_digits}" if clean_digits else ""

    return {
        "employer_name": employer.get("name", ""),
        "phone_formatted": raw_phone,
        "tel_link": tel_link,
        "call_script": call_script,
        "instructions": [
            "1. Kurumu aramadan önce görüşme notunu gözden geçirin.",
            "2. Klinik mesul müdürü veya insan kaynakları yetkilisi ile görüşmek istediğinizi belirtin.",
            "3. Görüşme sonrasında aldığınız cevabı (Görüşme planlandı, İleride değerlendirilecek vb.) panele kaydedin."
        ]
    }

