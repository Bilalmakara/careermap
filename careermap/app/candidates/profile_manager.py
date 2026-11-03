"""CareerMap V2.0 Aday Profili ve CV Doküman Yönetimi (Profile Manager).
- Adayın doğrulanmış mesleki profilini, klinik vaka sayılarını ve tercihlerini yönetir.
- CV PDF dosyalarının güvenli süreli erişim belirteçlerini (secure token) üretir.
- Dt. Rümeysa Çolak için referans kanonik profili sağlar.
"""
import uuid
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import sqlite3

from ..database.db import get_connection

logger = logging.getLogger("careermap.candidates.profile")

def get_rumeysa_colak_default_profile() -> Dict[str, Any]:
    """Dt. Rümeysa Çolak için doğrulanmış kanonik aday profilini döner."""
    return {
        "candidate_id": "candidate-dt-rumeysa-colak",
        "full_name": "Dt. Rümeysa Çolak",
        "title": "Diş Hekimi",
        "email": "rumeysacolak.dt@gmail.com",
        "phone": "0(555) 000 26 26",
        "city": "Eskişehir",
        "graduation_school": "Süleyman Demirel Üniversitesi Diş Hekimliği Fakültesi",
        "graduation_year": 2026,
        "clinical_case_count": 350,
        "specialties": [
            "Restoratif Diş Tedavisi",
            "Endodonti (Kanal Tedavisi)",
            "Estetik Kompozit Dolgular",
            "Protetik Diş Tedavisi",
            "Periodontoloji (Diş Eti Tedavisi)",
            "Cerrahi Diş Çekimi"
        ],
        "experience_summary": (
            "Süleyman Demirel Üniversitesi Diş Hekimliği Fakültesi'nde 5 yıllık eğitim ve staj sürecinde "
            "350'nin üzerinde klinik vaka deneyimi. Özellikle restoratif diş tedavisi, estetik anterior/posterior kompozitler "
            "ve endodontik tedavilerde yoğun klinik uygulama yetkinliği. Mezuniyetin ardından özel bir diş kliniğinde "
            "aktif hekimlik yaparak hasta iletişimi ve klinik iş akışında profesyonel deneyim kazanmıştır."
        ),
        "work_preferences": {
            "target_city": "Eskişehir",
            "target_districts": ["Tepebaşı", "Odunpazarı"],
            "employment_type": "Tam Zamanlı / Yarı Zamanlı",
            "preferred_clinic_types": ["Özel poliklinik", "Bireysel muayenehane"],
            "career_objective": "Mesleki gelişimimi sürdürebileceğim, hasta memnuniyetini ve multidisipliner klinik yaklaşımı önceleyen dinamik bir klinikte uzun vadeli değer üretmek."
        }
    }

class CandidateProfileManager:
    """Aday profili, CV belgeleri ve tercihleri için veritabanı servis sınıfı."""

    def __init__(self, db_conn: Optional[sqlite3.Connection] = None):
        self.conn = db_conn or get_connection()

    def upsert_candidate(self, candidate_data: Dict[str, Any]) -> str:
        """Adayı veritabanına kaydeder veya günceller."""
        cid = candidate_data.get("candidate_id") or f"cand-{uuid.uuid4().hex[:10]}"
        cursor = self.conn.cursor()

        specs_json = json.dumps(candidate_data.get("specialties", []), ensure_ascii=False)
        pref_json = json.dumps(candidate_data.get("work_preferences", {}), ensure_ascii=False)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        user_id = candidate_data.get("user_id", "user-candidate-rumeysa")
        cursor.execute("""
        INSERT INTO candidates (
            candidate_id, user_id, full_name, title, email, phone, city,
            graduation_school, graduation_year, clinical_case_count,
            specialties_json, experience_summary, work_preferences_json,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(candidate_id) DO UPDATE SET
            user_id = COALESCE(NULLIF(excluded.user_id, ''), candidates.user_id),
            full_name = excluded.full_name,
            title = excluded.title,
            email = excluded.email,
            phone = excluded.phone,
            city = excluded.city,
            graduation_school = excluded.graduation_school,
            graduation_year = excluded.graduation_year,
            clinical_case_count = excluded.clinical_case_count,
            specialties_json = excluded.specialties_json,
            experience_summary = excluded.experience_summary,
            work_preferences_json = excluded.work_preferences_json,
            updated_at = excluded.updated_at
        """, (
            cid,
            user_id,
            candidate_data.get("full_name", ""),
            candidate_data.get("title", "Diş Hekimi"),
            candidate_data.get("email", ""),
            candidate_data.get("phone", ""),
            candidate_data.get("city", "Eskişehir"),
            candidate_data.get("graduation_school", ""),
            candidate_data.get("graduation_year", 2026),
            candidate_data.get("clinical_case_count", 0),
            specs_json,
            candidate_data.get("experience_summary", ""),
            pref_json,
            now_str,
            now_str
        ))

        # İletişim tercihlerini başlat
        cursor.execute("""
        INSERT OR IGNORE INTO communication_preferences (
            preference_id, candidate_id, allow_email_applications,
            allow_whatsapp_handoff, whatsapp_model, min_followup_days, max_reminders_per_employer
        ) VALUES (?, ?, 1, 1, 'model_b_secure_link', 4, 1)
        """, (f"pref-{cid}", cid))

        self.conn.commit()
        return cid

    def get_candidate(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        """Aday profilini döner."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM candidates WHERE candidate_id = ?", (candidate_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["specialties"] = json.loads(d.get("specialties_json") or "[]")
        d["work_preferences"] = json.loads(d.get("work_preferences_json") or "{}")
        return d

    def get_candidate_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Kullanıcı kimliğine (user_id) bağlı aday profilini döner."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM candidates WHERE user_id = ? OR email IN (SELECT email FROM users WHERE user_id = ?) LIMIT 1", (user_id, user_id))
        row = cursor.fetchone()
        if not row:
            return self.get_candidate("candidate-dt-rumeysa-colak")
        d = dict(row)
        d["specialties"] = json.loads(d.get("specialties_json") or "[]")
        d["work_preferences"] = json.loads(d.get("work_preferences_json") or "{}")
        return d

    def register_cv_document(
        self,
        candidate_id: str,
        file_name: str = "Rumeysa_Colak_CV.pdf",
        file_path: str = "static/uploads/cv/Rumeysa_Colak_CV.pdf",
        validity_days: int = 30
    ) -> Dict[str, Any]:
        """Aday için güvenli süreli erişim belirteçli CV kaydı oluşturur."""
        doc_id = f"doc-{uuid.uuid4().hex[:12]}"
        secure_token = uuid.uuid4().hex[:16]
        now = datetime.now()
        expires = (now + timedelta(days=validity_days)).strftime("%Y-%m-%d %H:%M:%S")

        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO candidate_documents (
            document_id, candidate_id, document_type, file_name,
            file_path, secure_token, expires_at, view_count, created_at
        ) VALUES (?, ?, 'cv_pdf', ?, ?, ?, ?, 0, ?)
        """, (
            doc_id,
            candidate_id,
            file_name,
            file_path,
            secure_token,
            expires,
            now.strftime("%Y-%m-%d %H:%M:%S")
        ))
        self.conn.commit()

        return {
            "document_id": doc_id,
            "candidate_id": candidate_id,
            "file_name": file_name,
            "file_path": file_path,
            "secure_token": secure_token,
            "expires_at": expires,
            "secure_url": f"https://careermap.local/cv/view/{secure_token}"
        }

    def get_active_cv_document(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        """Adayın en güncel aktif CV belgesini döner."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT document_id, candidate_id, document_type, file_name,
                   file_path, secure_token, expires_at, view_count, created_at
            FROM candidate_documents
            WHERE candidate_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (candidate_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        token = d.get("secure_token", "demo")
        d["secure_url"] = f"https://careermap-dnlb.onrender.com/api/v2/cv/view/{token}"
        return d

