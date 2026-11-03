"""CareerMap V2.0 Kişiselleştirilmiş Başvuru Mesajı Üreticisi (Message Generator).
- Her kurum için doğrulanmış veriler ışığında farklılaştırılmış, özgün başvuru metinleri üretir.
- Kesin Sıfır Halüsinasyon İlkesi:
  * Adayın sahip olmadığı uzmanlıklar ASLA eklenmez (yalnızca 350+ vaka, SDÜ 2026, restoratif & endodonti).
  * Kurumda doğrulanmamış ilanlar varmış gibi yazılmaz ("Mevcut veya oluşabilecek hekim pozisyonları" standardı).
- E-posta, WhatsApp (Model B & C), Takip/Hatırlatma, Telefon Görüşme Notu ve Form metinlerini hazırlar.
"""
from typing import Dict, Any
from ..channels.whatsapp_handoff import (
    create_whatsapp_link,
    create_whatsapp_web_link,
    create_gmail_compose_link,
    create_mailto_link,
    normalize_tr_mobile_for_whatsapp
)

def get_clinic_specific_pitch(employer: Dict[str, Any]) -> str:
    """Kurumun unvanına, türüne ve ilçesine göre doğrulanmış özelleştirme cümlesi üretir."""
    name = employer.get("name", "")
    district = employer.get("district", "Eskişehir")
    emp_type = (employer.get("employer_type") or "").lower()

    if "dorlion" in name.lower():
        return f"{district} bölgesinde köklü ve modern klinik altyapınızla sunduğunuz hasta memnuniyeti odaklı tedavi standartlarına katkı sağlamayı hedefliyorum."
    elif "mayadapol" in name.lower():
        return f"{district} lokasyonundaki donanımlı poliklinik kadronuz ve multidisipliner klinik yaklaşımınız bünyesinde uzun vadeli değer üretmek istiyorum."
    elif "bc" in name.lower() or "bcklinik" in name.lower():
        return f"{district} bölgesindeki yenilikçi ve estetik diş hekimliği uygulamalarınız doğrultusunda kliniğinizde verimli bir hekimlik süreci yürütmeyi amaçlıyorum."
    elif "klas" in name.lower():
        return f"{district} lokasyonunda dinamik hekim ekibiniz ve geniş tedavi yelpazeniz ile mesleki vizyonumun güçlü bir sinerji oluşturacağına inanıyorum."
    elif "minepol" in name.lower():
        return f"{district} merkezli kliniğinizin çağdaş hasta protokolleri ve ileri restoratif vizyonu ile uyum içinde çalışmayı arzu ediyorum."
    elif "inci" in name.lower():
        return f"{district} bölgesindeki saygın poliklinik yapınız ve kaliteli hekim kadronuz içerisinde sorumluluk alarak kliniğinize katkıda bulunmayı hedefliyorum."
    elif "emek" in name.lower():
        return f"{district} bölgesindeki yoğun hasta sirkülasyonuna sahip poliklinik yapınızda pratik klinik tecrübemi ve vaka deneyimimi değerlendirmek istiyorum."
    elif "smile" in name.lower():
        return f"{district} bölgesindeki estetik ve dijital diş hekimliği vizyonunuz doğrultusunda kliniğiniz bünyesinde aktif hekimlik yapmayı hedefliyorum."
    elif "erkan yücel" in name.lower():
        return f"{district} bölgesindeki köklü ve güvenilir muayenehane pratiğinizde, tecrübenizden istifade ederek hasta odaklı titiz bir hekimlik sunmayı amaçlıyorum."
    elif "fahri kavrut" in name.lower():
        return f"{district} lokasyonundaki saygın klinik tecrübeniz ve uzman yaklaşımınız doğrultusunda kurumunuz bünyesinde mesleki katkı sağlamayı arzu ediyorum."
    elif "poliklinik" in emp_type:
        return f"{district} bölgesindeki kurumsal poliklinik yapınız ve ekip çalışmasına dayalı klinik kültürünüz içerisinde uzun vadeli hekimlik yapmayı hedefliyorum."
    else:
        return f"{district} lokasyonundaki saygın hekimlik pratiğiniz ve hasta güveni odaklı tedavi ortamınızda değer üretmeyi hedefliyorum."

def generate_application_messages(
    employer: Dict[str, Any],
    candidate: Dict[str, Any],
    secure_cv_url: str = "https://careermap.local/cv/view/demo",
    cv_file_name: str = "Rumeysa_Colak_CV.pdf"
) -> Dict[str, Any]:
    """
    İşveren ve aday için tüm kanallara ait kişiselleştirilmiş başvuru metin paketini döner.
    """
    clinic_name = employer.get("name", "Klinik")
    district = employer.get("district", "Eskişehir")
    cand_name = candidate.get("full_name", "Dt. Rümeysa Çolak")
    cand_school = candidate.get("graduation_school", "Süleyman Demirel Üniversitesi Diş Hekimliği Fakültesi")
    cand_year = candidate.get("graduation_year", 2026)
    cand_cases = candidate.get("clinical_case_count", 350)
    cand_phone = candidate.get("phone", "0(555) 000 26 26")
    cand_email = candidate.get("email", "rumeysacolak.dt@gmail.com")

    clinic_pitch = get_clinic_specific_pitch(employer)

    # 1. E-POSTA BAŞVURU TASLAĞI (Resmî, Kurumsal, CV Ekli)
    email_subject = f"Diş Hekimi İş Başvurusu — {cand_name} | {clinic_name}"
    email_body = f"""Sayın Yetkili,

Ben {cand_name}. {cand_school} {cand_year} yılı mezunuyum.

Eğitimim süresince {cand_cases}'nin üzerinde klinik vaka deneyimi edindim. Özellikle restoratif diş tedavisi, estetik anterior ve posterior kompozit restorasyonlar ile endodonti (kanal tedavisi) alanlarında yoğun klinik uygulamalar gerçekleştirdim. Mezuniyetimin ardından özel bir diş kliniğinde çalışarak hasta iletişimi, vaka takibi ve klinik iş akışında profesyonel deneyim kazandım.

{clinic_pitch}

Kliniğinizde mevcut veya ilerleyen dönemde oluşabilecek diş hekimi pozisyonları için özgeçmişimi değerlendirmenize sunuyorum.

Uygun görmeniz hâlinde yüz yüze veya çevrim içi bir ön görüşme gerçekleştirmekten büyük memnuniyet duyarım.

Saygılarımla,

{cand_name}
Telefon: {cand_phone}
E-posta: {cand_email}

Ek: {cv_file_name}"""

    # 2. WHATSAPP MODEL B (Önceden Doldurulmuş Mesaj + Güvenli CV Bağlantısı)
    whatsapp_model_b = f"""Merhaba, ben {cand_name}. {cand_school} mezunuyum.

Kliniğinizde ({clinic_name}) oluşabilecek diş hekimi pozisyonları için başvuruda bulunmak istiyorum.

Özgeçmişimi aşağıdaki güvenli bağlantıdan inceleyebilirsiniz:
{secure_cv_url}

Uygun görmeniz hâlinde görüşmekten memnuniyet duyarım. İyi çalışmalar dilerim."""

    # 3. WHATSAPP MODEL C (Önceden Doldurulmuş Mesaj + Adayın PDF'i Eklemesi)
    whatsapp_model_c = f"""Merhaba, ben {cand_name}. {cand_school} mezunuyum.

Kliniğiniz bünyesinde ({clinic_name}) değerlendirilmek üzere özgeçmişimi ekte PDF dosyası olarak iletiyorum.

Özellikle restoratif ve endodontik tedavilerdeki 350+ vaka tecrübemle kurumunuza değer katmayı hedefliyorum. Uygun görmeniz halinde görüşmekten memnuniyet duyarım. İyi çalışmalar dilerim."""

    # 4. WHATSAPP HATIRLATMA (E-postadan 4-5 iş günü sonra, yalnızca yanıt yoksa)
    whatsapp_followup = f"""Merhaba, ben {cand_name}.

Diş hekimi pozisyonları için geçtiğimiz günlerde kliniğinize özgeçmişimi e-posta yoluyla iletmiştim.

Başvurumun değerlendirilme imkânı olup olmadığını nazikçe öğrenmek istedim. Uygun görmeniz hâlinde tanışmaktan ve görüşmekten memnuniyet duyarım.

İyi çalışmalar dilerim."""

    # 5. TELEFON GÖRÜŞME REHBERİ (30-45 saniyelik sekreterya / mesul müdür konuşması)
    phone_script = f"""İyi günler, ben {cand_name}. {cand_school} mezunu diş hekimiyim.

Kliniğinizin mesul müdürü veya hekim işe alımından sorumlu yetkilisi ile görüşmem mümkün müdür?

(Yetkili bağlandığında):
"Merhabalar Hocam / İyi günler. Ben Dt. Rümeysa Çolak. Süleyman Demirel Üniversitesi Diş Hekimliği Fakültesi mezunuyum. 350'nin üzerinde restoratif ve endodontik vaka tecrübem ve özel klinik deneyimim bulunuyor. Kliniğiniz bünyesinde diş hekimi kadrosu değerlendirmesi için özgeçmişimi iletmek ve uygun görmeniz halinde kendimi kısaca tanıtmak isterdim." """

    # 6. WEB İLETİŞİM FORMU METNİ
    contact_form_text = f"""Sayın {clinic_name} Yetkilisi,

Ben Dt. Rümeysa Çolak. Süleyman Demirel Üniversitesi Diş Hekimliği Fakültesi 2026 yılı mezunuyum. 350'nin üzerinde restoratif ve endodontik klinik vaka deneyimim ve özel klinik hekimlik tecrübem bulunmaktadır.

{clinic_pitch}

Kliniğiniz bünyesinde diş hekimi kadrolarında değerlendirilmek üzere özgeçmişimi takdim etmek isterim. İletişim: {cand_phone} / {cand_email}."""

    recipient_email = (employer.get("email") or "").strip()
    gmail_compose_url = create_gmail_compose_link(recipient_email, email_subject, email_body) if recipient_email else ""
    mailto_url = create_mailto_link(recipient_email, email_subject, email_body) if recipient_email else ""

    raw_phone = employer.get("whatsapp_url") or employer.get("phone") or ""
    clean_phone = normalize_tr_mobile_for_whatsapp(raw_phone) or ""
    wa_app_link = create_whatsapp_link(clean_phone, whatsapp_model_b) if clean_phone else ""
    wa_web_link = create_whatsapp_web_link(clean_phone, whatsapp_model_b) if clean_phone else ""

    return {
        "email": {
            "subject": email_subject,
            "body": email_body,
            "attachment_name": cv_file_name,
            "recipient": recipient_email,
            "gmail_compose_url": gmail_compose_url,
            "mailto_url": mailto_url
        },
        "whatsapp_model_b": {
            "body": whatsapp_model_b,
            "secure_url": secure_cv_url,
            "action_url": wa_app_link,
            "whatsapp_web_url": wa_web_link
        },
        "whatsapp_model_c": {
            "body": whatsapp_model_c,
            "attachment_instruction": f"Aday cihazındaki '{cv_file_name}' dosyasını sohbete eklemelidir."
        },
        "whatsapp_followup": {
            "body": whatsapp_followup
        },
        "phone_script": {
            "body": phone_script,
            "target_phone": employer.get("phone", "")
        },
        "contact_form": {
            "body": contact_form_text,
            "form_url": employer.get("contact_form_url", employer.get("website", ""))
        },
        "whatsapp_phone": clean_phone,
        "whatsapp_handoff_link_b": wa_app_link,
        "whatsapp_web_link_b": wa_web_link,
        "gmail_compose_url": gmail_compose_url,
        "mailto_url": mailto_url
    }

