"""CareerMap V2.0 WhatsApp Kullanıcı Kontrollü İletişim Modülü (WhatsApp Handoff).
- WhatsApp Business API yerine, adayın kendi WhatsApp hesabıyla kuruma kontrollü mesaj göndermesini sağlar.
- Model B: Önceden doldurulmuş mesaj + Güvenli süreli CV bağlantısı.
- Model C: Önceden doldurulmuş mesaj + Kullanıcının PDF'yi kendisi eklemesi için yönlendirme.
- wa.me resmî bağlantı standartlarına tam uyumludur.
"""
import re
from urllib.parse import quote, urlparse, parse_qs
from typing import Optional, Dict, Any

def normalize_tr_mobile_for_whatsapp(phone_str: str) -> Optional[str]:
    """
    Telefon numarasını WhatsApp uluslararası formatına (905XXXXXXXXX) dönüştürür.
    Sabit hat (0222) veya çağrı merkezleri (0850) mobil WhatsApp için uygun değildir.
    """
    if not phone_str:
        return None

    # URL içerisinden telefon ayıklama (wa.me, api.whatsapp.com)
    m = re.search(r'(?:phone=|\/)(?:\+?90|0+)?(5\d{9})', phone_str)
    if m:
        return "90" + m.group(1)

    # Metin içi 5XX XXX XX XX kalıbı
    m2 = re.search(r'(?:^|[^\d])(?:\+?90|0+)?(5\d{9})(?:[^\d]|$)', phone_str)
    if m2:
        return "90" + m2.group(1)

    digits = re.sub(r"\D", "", phone_str)

    # 05XX XXX XX XX -> 905XXXXXXXXX
    if len(digits) == 11 and digits.startswith("05"):
        return "9" + digits
    # 5XX XXX XX XX -> 905XXXXXXXXX
    elif len(digits) == 10 and digits.startswith("5"):
        return "90" + digits
    # 905XX XXX XX XX -> 905XXXXXXXXX
    elif len(digits) == 12 and digits.startswith("905"):
        return digits

    return None

def create_whatsapp_link(phone: str, message: str) -> str:
    """
    Doğrulanmış cep numarası ve kuruma özel mesaj için resmî wa.me bağlantısı üretir.
    """
    clean_phone = normalize_tr_mobile_for_whatsapp(phone)
    if not clean_phone:
        clean_phone = "".join(c for c in phone if c.isdigit())
        if clean_phone.startswith("0"):
            clean_phone = "9" + clean_phone
        elif not clean_phone.startswith("90"):
            clean_phone = "90" + clean_phone

    quoted_message = quote(message.strip())
    return f"https://wa.me/{clean_phone}?text={quoted_message}"

def create_whatsapp_web_link(phone: str, message: str) -> str:
    """
    Doğrudan masaüstü / tarayıcı WhatsApp Web (web.whatsapp.com) sohbet bağlantısı üretir.
    """
    clean_phone = normalize_tr_mobile_for_whatsapp(phone)
    if not clean_phone:
        clean_phone = "".join(c for c in phone if c.isdigit())
        if clean_phone.startswith("0"):
            clean_phone = "9" + clean_phone
        elif not clean_phone.startswith("90"):
            clean_phone = "90" + clean_phone

    quoted_message = quote(message.strip())
    return f"https://web.whatsapp.com/send?phone={clean_phone}&text={quoted_message}"

def create_gmail_compose_link(to_email: str, subject: str, body: str) -> str:
    """
    Gmail Web Composer penceresini önceden doldurulmuş alıcı, konu ve metin ile açan bağlantı üretir.
    """
    if not to_email:
        return ""
    q_to = quote(to_email.strip())
    q_su = quote(subject.strip())
    q_body = quote(body.strip())
    return f"https://mail.google.com/mail/?view=cm&fs=1&to={q_to}&su={q_su}&body={q_body}"

def create_mailto_link(to_email: str, subject: str, body: str) -> str:
    """
    Varsayılan e-posta istemcisi (Outlook, Apple Mail vb.) için mailto bağlantısı üretir.
    """
    if not to_email:
        return ""
    q_su = quote(subject.strip())
    q_body = quote(body.strip())
    return f"mailto:{to_email.strip()}?subject={q_su}&body={q_body}"

def build_whatsapp_application_package(
    employer: Dict[str, Any],
    candidate: Dict[str, Any],
    message_model_b: str,
    message_model_c: str,
    followup_message: str
) -> Dict[str, Any]:
    """
    İşveren için Model B (Güvenli Bağlantı) ve Model C (Doğrudan PDF Ekli) WhatsApp paketini hazırlar.
    """
    raw_phone = employer.get("whatsapp_url") or employer.get("phone") or ""
    clean_mobile = normalize_tr_mobile_for_whatsapp(raw_phone)

    is_eligible = clean_mobile is not None
    link_model_b = create_whatsapp_link(clean_mobile, message_model_b) if is_eligible else ""
    link_web_b = create_whatsapp_web_link(clean_mobile, message_model_b) if is_eligible else ""
    link_model_c = create_whatsapp_link(clean_mobile, message_model_c) if is_eligible else ""
    link_followup = create_whatsapp_link(clean_mobile, followup_message) if is_eligible else ""

    return {
        "is_eligible": is_eligible,
        "clean_mobile_phone": clean_mobile or "",
        "whatsapp_account_verification": "observed_mobile_pattern_unverified_account",
        "whatsapp_account_notice": "05xx biçimindeki cep telefonu tespit edilmiştir. WhatsApp resmi şartları uyarınca numaranın aktif WhatsApp hesabı taşıdığı sohbet başlatılarak teyit edilir; sistem teyitsiz numarayı kesin hesap ilan etmez.",
        "model_b": {
            "name": "Model B — Mesaj + Güvenli CV Bağlantısı (Önerilen)",
            "description": "WhatsApp açılır, kuruma özel mesaj ve süreli CV bağlantısı yazılmış olur. Tek tıkla gönderilir.",
            "message_text": message_model_b,
            "action_url": link_model_b,
            "whatsapp_web_url": link_web_b
        },
        "model_c": {
            "name": "Model C — Mesaj + Gerçek PDF Dosya Eki",
            "description": "WhatsApp açılır, hazır mesaj iletilir; aday cihazındaki PDF CV dosyasını sohbete ekleyerek gönderir.",
            "message_text": message_model_c,
            "action_url": link_model_c
        },
        "followup": {
            "name": "Nezaket Hatırlatması (4-5 İş Günü Sonrası)",
            "description": "Daha önce e-posta ile başvuru yapılmış ve yanıt alınamamışsa gönderilecek nazik durum sorgusu.",
            "message_text": followup_message,
            "action_url": link_followup
        },
        "user_guidelines": [
            "1. Düğmeye tıkladığınızda WhatsApp sohbet penceresi önceden doldurulmuş metinle açılacaktır.",
            "2. Mesaj henüz kliniğe iletilmemiştir; son kontrolü yapıp 'Gönder' tuşuna basmanız gerekmektedir.",
            "3. Gönderimi tamamladıktan sonra CareerMap paneline dönüp 'Gönderdim' olarak işaretleyiniz."
        ]
    }

