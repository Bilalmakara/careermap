"""CareerMap V2.0 Başvuru Orkestrasyonu ve Süreç Planlayıcı (Application Planner).
- İşverenin doğrulanmış kanallarına göre kişiselleştirilmiş, çok kanallı başvuru takvimi üretir.
- Kanalların aynı anda rastgele kullanılmasını engeller; profesyonel bekleme süreleri koyar.
- Yanıt geldiğinde otomatik olarak diğer takip adımlarını durduracak kuralları tanımlar.
"""
from typing import Dict, Any, List

def plan_application_workflow(
    employer: Dict[str, Any],
    candidate: Dict[str, Any]
) -> Dict[str, Any]:
    """
    İşveren için aşamalı, kanalları koordine eden başvuru planını oluşturur.
    """
    has_email = bool((employer.get("email") or "").strip())
    has_wa = bool((employer.get("whatsapp_url") or "").strip())
    has_form = bool((employer.get("contact_form_url") or "").strip())
    has_phone = bool((employer.get("phone") or "").strip())

    steps: List[Dict[str, Any]] = []

    # 1. Aşama: İlk Başvuru
    if has_email:
        primary_channel = "email"
        steps.append({
            "step_number": 1,
            "day": 1,
            "action_type": "initial_application",
            "channel": "email",
            "title": "CV Ekli E-posta Başvurusu",
            "description": f"Sayın Yetkili hitabıyla hazırlanan kişiselleştirilmiş başvuru metni ve {candidate.get('full_name')} CV PDF eki kurumsal e-posta adresine ({employer.get('email')}) iletilir.",
            "requires_user_approval": True,
            "is_automated_possible": True
        })
    elif has_form:
        primary_channel = "career_form"
        steps.append({
            "step_number": 1,
            "day": 1,
            "action_type": "initial_application",
            "channel": "career_form",
            "title": "Web İletişim / Başvuru Formu Gönderimi",
            "description": f"Kliniğin resmî web sitesindeki forma ({employer.get('contact_form_url')}) hazırlanan başvuru özeti yapıştırılarak iletilir.",
            "requires_user_approval": True,
            "is_automated_possible": False
        })
    elif has_wa:
        primary_channel = "whatsapp"
        steps.append({
            "step_number": 1,
            "day": 1,
            "action_type": "initial_application",
            "channel": "whatsapp",
            "title": "WhatsApp Üzerinden İlk Başvuru (Model B/C)",
            "description": f"Doğrulanmış WhatsApp hattına ({employer.get('whatsapp_url')}) hazır başvuru metni ve güvenli CV bağlantısı yönlendirilir.",
            "requires_user_approval": True,
            "is_automated_possible": False
        })
    else:
        primary_channel = "phone"
        steps.append({
            "step_number": 1,
            "day": 1,
            "action_type": "initial_application",
            "channel": "phone",
            "title": "Telefon ile Ön Görüşme",
            "description": f"Kliniğin sabit santral/mobil numarası ({employer.get('phone')}) aranarak mesul müdür ile hekim pozisyonları hakkında ön görüşme yapılır.",
            "requires_user_approval": True,
            "is_automated_possible": False
        })

    # 2. Aşama: Bekleme ve Durum Kontrolü
    steps.append({
        "step_number": 2,
        "day": 4,
        "action_type": "wait_and_check",
        "channel": "crm_monitor",
        "title": "4-5 İş Günü Yanıt Bekleme Penceresi",
        "description": "Kliniğin e-posta veya telefon dönüşü olup olmadığı CRM üzerinden kontrol edilir. Yanıt geldiyse takip durdurulur.",
        "requires_user_approval": False,
        "is_automated_possible": True
    })

    # 3. Aşama: İkincil Nezaket Hatırlatması (Yalnızca yanıt yoksa)
    if has_wa and primary_channel != "whatsapp":
        steps.append({
            "step_number": 3,
            "day": 5,
            "action_type": "followup_reminder",
            "channel": "whatsapp",
            "title": "WhatsApp Nezaket Hatırlatması (Yalnızca Cevap Gelmediyse)",
            "description": "E-posta başvurusunun ulaşıp ulaşmadığını nazikçe soran kısa WhatsApp durum kontrol mesajı.",
            "requires_user_approval": True,
            "is_automated_possible": False
        })
    elif has_phone and primary_channel != "phone":
        steps.append({
            "step_number": 3,
            "day": 6,
            "action_type": "followup_reminder",
            "channel": "phone",
            "title": "Telefonla Takip Araması (Yalnızca Cevap Gelmediyse)",
            "description": "Klinik sekreteryası aranarak gönderilen CV'nin ilgili mesul müdürün değerlendirmesine sunulup sunulmadığı teyit edilir.",
            "requires_user_approval": True,
            "is_automated_possible": False
        })

    # 4. Aşama: Süreç Sonuçlandırma
    steps.append({
        "step_number": len(steps) + 1,
        "day": 10,
        "action_type": "finalize_or_archive",
        "channel": "crm_monitor",
        "title": "Başvuru Durumunu Netleştirme",
        "description": "Görüşme daveti, olumsuz geri bildirim veya ileri tarihte değerlendirilmek üzere arşivleme kararı CRM'e işlenir.",
        "requires_user_approval": True,
        "is_automated_possible": False
    })

    return {
        "employer_id": employer.get("employer_id", ""),
        "employer_name": employer.get("name", ""),
        "primary_channel": primary_channel,
        "has_multi_channel_support": (has_email and has_wa),
        "total_steps": len(steps),
        "steps": steps,
        "coordination_rules": [
            "Aynı kliniğe birden fazla kanaldan aynı anda mesaj ASLA gönderilmez.",
            "Kurumdan ret veya görüşme daveti geldiğinde takip otomatik sonlandırılır.",
            "Hasta acil veya randevu hatlarına doğrudan iş ilanı spamı yapılmaz."
        ]
    }

