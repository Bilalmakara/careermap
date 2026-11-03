"""CareerMap V2.0 Web İletişim Formu Başvuru Modülü (Career Form Handoff).
- Kliniğin resmî web sitesindeki başvuru/iletişim formuna doğrudan bağlantı sağlar.
- Formun 'Mesajınız' alanına kopyalanıp yapıştırılacak kurumsal metni hazır eder.
"""
from typing import Dict, Any

def generate_career_form_handoff(
    employer: Dict[str, Any],
    candidate: Dict[str, Any],
    form_message_text: str
) -> Dict[str, Any]:
    form_url = (employer.get("contact_form_url") or employer.get("website") or "").strip()

    return {
        "employer_name": employer.get("name", ""),
        "form_url": form_url,
        "is_available": bool(form_url),
        "message_to_paste": form_message_text,
        "candidate_info": {
            "name": candidate.get("full_name", ""),
            "email": candidate.get("email", ""),
            "phone": candidate.get("phone", ""),
            "subject": f"Diş Hekimi İş Başvurusu — {candidate.get('full_name', '')}"
        },
        "instructions": [
            "1. 'Form Sayfasını Aç' düğmesine tıklayarak kliniğin resmî sayfasına gidin.",
            "2. Ad, e-posta ve telefon bilgilerinizi doldurun.",
            "3. 'Mesajınız' alanına hazırlanan başvuru metnini yapıştırıp formu gönderin.",
            "4. CareerMap paneline dönüp başvuruyu 'Gönderildi' olarak onaylayın."
        ]
    }

