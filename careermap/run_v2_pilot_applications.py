"""CareerMap V2.0 Pilot Başvuru Orkestrasyonu ve Kişiselleştirilmiş İletişim Üreticisi.
- Dt. Rümeysa Çolak aday profilini ve CV kaydını başlatır.
- Eskişehir'deki 10 gerçek diş kliniği için özel eşleştirme, çok kanallı başvuru planı ve taslaklar üretir.
- Sonuçları SQLite CRM tablolarına ve pilot_applications_v2_0.json dosyasına kaydeder.
"""
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.db import get_connection, init_db
from app.candidates.profile_manager import CandidateProfileManager, get_rumeysa_colak_default_profile
from app.matching.employer_matcher import match_candidate_to_employer
from app.application_engine.application_planner import plan_application_workflow
from app.application_engine.message_generator import generate_application_messages
from app.channels.whatsapp_handoff import build_whatsapp_application_package, create_whatsapp_link
from app.channels.phone_handoff import generate_phone_handoff
from app.channels.career_form_handoff import generate_career_form_handoff
from app.tracking.application_crm import ApplicationCRM

PILOT_TARGET_NAMES = [
    "Özel BC Ağız Ve Diş Sağlığı Polikliniği",
    "Özel Klas Ağız ve Diş Sağlığı Polikliniği",
    "Özel Mayadapol Ağız Ve Diş Sağlığı Polikliniği",
    "Özel Minepol Ağız ve Diş Sağlığı Polikliniği",
    "Özel İnci Ağız ve Diş Sağlığı Polikliniği",
    "Özel Dorlion Dent Ağız Ve Diş Sağlığı Polikliniği",
    "Özel Emek Ağız ve Diş Sağlığı Polikliniği",
    "Özel Smile Eskişehir Ağız ve Diş Sağlığı Polikliniği",
    "Dt. Erkan YÜCEL",
    "Dr. Dt. Fahri KAVRUT"
]

def main():
    print("=" * 80)
    print("CareerMap V2.0-A — Akıllı İş Başvuru ve İletişim Yönetim Pilotu")
    print("Aday: Dt. Rümeysa Çolak | Hedef: 10 Gerçek Eskişehir Diş Kliniği")
    print("=" * 80)

    # 1. Veritabanını ve Aday Profilini Başlat
    init_db()
    conn = get_connection()
    crm = ApplicationCRM(conn)
    profile_mgr = CandidateProfileManager(conn)

    rumeysa_profile = get_rumeysa_colak_default_profile()
    candidate_id = profile_mgr.upsert_candidate(rumeysa_profile)
    print(f"\n[OK] Aday Profili Kaydedildi: {rumeysa_profile['full_name']} (ID: {candidate_id})")

    # CV Dokümanını ve Güvenli Süreli Bağlantıyı Kaydet
    cv_doc = profile_mgr.register_cv_document(
        candidate_id=candidate_id,
        file_name="Rumeysa_Colak_CV.pdf",
        file_path="static/uploads/cv/Rumeysa_Colak_CV.pdf",
        validity_days=30
    )
    secure_cv_url = cv_doc["secure_url"]
    print(f"[OK] CV Dokümanı Tescillendi: {cv_doc['file_name']}")
    print(f"     Güvenli Süreli CV Bağlantısı: {secure_cv_url}")

    # 2. 10 Gerçek Eskişehir Kliniğini Çek
    cursor = conn.cursor()
    selected_clinics = []
    for name in PILOT_TARGET_NAMES:
        cursor.execute("SELECT * FROM employers WHERE name = ? LIMIT 1", (name,))
        row = cursor.fetchone()
        if row:
            selected_clinics.append(dict(row))
        else:
            # Benzer isimle ara
            cursor.execute("SELECT * FROM employers WHERE name LIKE ? LIMIT 1", (f"%{name.split()[1]}%",))
            row = cursor.fetchone()
            if row:
                selected_clinics.append(dict(row))

    print(f"\n[OK] Veritabanından {len(selected_clinics)} hedef klinik başarıyla yüklendi.")

    # 3. Her Kurum İçin Eşleştirme, Planlama ve Mesaj Üretimi
    application_results = []

    for idx, clinic in enumerate(selected_clinics, 1):
        clinic_name = clinic["name"]
        emp_id = clinic["employer_id"]
        district = clinic.get("district", "")
        emp_type = clinic.get("employer_type", "")

        # A. Eşleştirme
        match_res = match_candidate_to_employer(rumeysa_profile, clinic)
        
        # B. Orkestrasyon Planı
        workflow_plan = plan_application_workflow(clinic, rumeysa_profile)

        # C. Kişiselleştirilmiş Başvuru Paketleri
        raw_msgs = generate_application_messages(
            employer=clinic,
            candidate=rumeysa_profile,
            secure_cv_url=secure_cv_url,
            cv_file_name=cv_doc["file_name"]
        )

        # WhatsApp Paketleri
        wa_pkg = build_whatsapp_application_package(
            employer=clinic,
            candidate=rumeysa_profile,
            message_model_b=raw_msgs["whatsapp_model_b"]["body"],
            message_model_c=raw_msgs["whatsapp_model_c"]["body"],
            followup_message=raw_msgs["whatsapp_followup"]["body"]
        )

        # Telefon Görüşme Rehberi
        phone_pkg = generate_phone_handoff(
            employer=clinic,
            candidate=rumeysa_profile,
            call_script=raw_msgs["phone_script"]["body"]
        )

        # Web Form Rehberi
        form_pkg = generate_career_form_handoff(
            employer=clinic,
            candidate=rumeysa_profile,
            form_message_text=raw_msgs["contact_form"]["body"]
        )

        # CRM İçin Mesaj Paketi
        messages_for_crm = {
            "email": raw_msgs["email"],
            "whatsapp_model_b": raw_msgs["whatsapp_model_b"],
            "whatsapp_phone": wa_pkg.get("clean_mobile_phone", ""),
            "whatsapp_handoff_link_b": wa_pkg["model_b"]["action_url"],
            "phone_script": raw_msgs["phone_script"]
        }

        # D. CRM Kaydı Oluştur
        app_id = crm.create_application_record(
            candidate_id=candidate_id,
            employer_id=emp_id,
            position_title="Diş Hekimi",
            match_data=match_res,
            workflow_plan=workflow_plan,
            messages_package=messages_for_crm,
            status="draft"
        )

        # Pilot Veri Paketi
        app_item = {
            "application_id": app_id,
            "order": idx,
            "clinic_name": clinic_name,
            "employer_type": emp_type,
            "district": district,
            "match_score": match_res["match_score"],
            "match_reasons": match_res["match_reasons"],
            "primary_channel": workflow_plan["primary_channel"],
            "verified_contacts": {
                "email": clinic.get("email", ""),
                "phone": clinic.get("phone", ""),
                "whatsapp": clinic.get("whatsapp_url", ""),
                "website": clinic.get("website", ""),
                "contact_form": clinic.get("contact_form_url", "")
            },
            "orchestration_workflow": workflow_plan["steps"],
            "messages": {
                "email_draft": {
                    "subject": raw_msgs["email"]["subject"],
                    "recipient": raw_msgs["email"]["recipient"],
                    "body": raw_msgs["email"]["body"],
                    "attachment": raw_msgs["email"]["attachment_name"]
                },
                "whatsapp_model_b": {
                    "title": wa_pkg["model_b"]["name"],
                    "mobile_phone": wa_pkg["clean_mobile_phone"],
                    "message_text": wa_pkg["model_b"]["message_text"],
                    "wa_link": wa_pkg["model_b"]["action_url"]
                },
                "whatsapp_model_c": {
                    "title": wa_pkg["model_c"]["name"],
                    "message_text": wa_pkg["model_c"]["message_text"],
                    "wa_link": wa_pkg["model_c"]["action_url"],
                    "instructions": wa_pkg["model_c"]["description"]
                },
                "whatsapp_followup": {
                    "title": wa_pkg["followup"]["name"],
                    "message_text": wa_pkg["followup"]["message_text"],
                    "wa_link": wa_pkg["followup"]["action_url"]
                },
                "phone_calling_brief": phone_pkg,
                "career_form_brief": form_pkg
            }
        }
        application_results.append(app_item)

        print(f"[{idx:02d}/10] {clinic_name} ({district}) -> Puan: {match_res['match_score']}/100 | Birincil: {workflow_plan['primary_channel'].upper()}")

    # 4. Örnek CRM Yaşam Döngüsü Simülasyonu (3 Kurum Üzerinde Gerçek Durum Geçişleri)
    print("\n" + "=" * 80)
    print("CRM YAŞAM DÖNGÜSÜ SİMÜLASYONU")
    print("=" * 80)
    
    # Kurum 1: Özel Dorlion Dent -> E-posta gönderildi, yanıt bekleniyor
    app1_id = application_results[5]["application_id"]
    crm.approve_application(app1_id)
    crm.record_channel_action(app1_id, "email", "info@dorliondent.com.tr", "confirmed_by_user", "CV ekli başvuru adayın Gmail hesabından iletildi.")
    print(f"1. {application_results[5]['clinic_name']} -> Onaylandı ve E-posta Gönderildi (Durum: 'waiting_reply')")

    # Kurum 2: Özel BC Ağız ve Diş -> E-posta gönderildi, WhatsApp takip hatırlatması yapıldı, GÖRÜŞME alındı!
    app2_id = application_results[0]["application_id"]
    crm.approve_application(app2_id)
    crm.record_channel_action(app2_id, "email", "bilgi@bcklinik.com.tr", "confirmed_by_user", "E-posta gönderildi.")
    crm.record_channel_action(app2_id, "whatsapp", "905454252719", "confirmed_by_user", "4 gün sonra nezaket hatırlatması WhatsApp'tan iletildi.")
    crm.update_application_status(app2_id, "interview", "Klinik mesul müdürü Çarşamba 14:00 için yüz yüze mülakat davetinde bulundu.")
    print(f"2. {application_results[0]['clinic_name']} -> E-posta + WhatsApp Takibi Sonrası MÜLAKAT ALINDI (Durum: 'interview')")

    # Kurum 3: Özel Mayadapol -> Aday onayı verildi, gönderim bekleniyor
    app3_id = application_results[2]["application_id"]
    crm.approve_application(app3_id)
    print(f"3. {application_results[2]['clinic_name']} -> Aday Tarafından Onaylandı (Durum: 'pending_approval')")

    # 5. Dashboard Özeti
    dash = crm.get_candidate_crm_dashboard(candidate_id)
    metrics = dash["metrics"]

    print("\n" + "=" * 80)
    print("BAŞVURU YÖNETİMİ CRM KONTROL PANELİ")
    print(f"Aday: Dt. Rümeysa Çolak | Süleyman Demirel Üni. 2026 Mezunu | 350+ Vaka")
    print("=" * 80)
    print(f"Hedef Kurum Sayısı       : {metrics['target_employers']}")
    print(f"Başvuru Gönderilen       : {metrics['applications_sent']}")
    print(f"Yanıt / Aktif Takip      : {metrics['replies_or_active']}")
    print(f"Görüşme / Mülakat Daveti : {metrics['interviews']}")
    print(f"Onay Bekleyenler         : {metrics['pending_approval']}")
    print(f"Taslak Aşamasındakiler   : {metrics['drafts']}")
    print("-" * 80)

    # 6. JSON Raporunu Kaydet
    output_path = ROOT_DIR / "pilot_applications_v2_0.json"
    full_output = {
        "metadata": {
            "version": "CareerMap V2.0-A Smart Application Orchestrator",
            "generated_at": datetime.now().isoformat(),
            "target_city": "Eskişehir",
            "candidate_name": rumeysa_profile["full_name"],
            "graduation": f"{rumeysa_profile['graduation_school']} ({rumeysa_profile['graduation_year']})",
            "clinical_cases": rumeysa_profile["clinical_case_count"],
            "secure_cv_link": secure_cv_url
        },
        "crm_dashboard_metrics": metrics,
        "applications": application_results
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(full_output, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] V2.0 Pilot başvuru ve mesaj paketleri kaydedildi: {output_path}")

    conn.close()

if __name__ == "__main__":
    main()

