"""CareerMap V2.0 Başvuru CRM ve İletişim Takip Motoru (Application CRM).
- 1 İşveren = 1 Başvuru Kaydı, çoklu kanal hareketleri (`channel_attempts`).
- Durum geçişleri: draft -> pending_approval -> approved -> attempted -> waiting_reply -> interview / rejected.
- Aday kontrol paneli için özet metrikler ve kurum başvuru kartları üretir.
"""
import uuid
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import sqlite3

from ..database.db import get_connection

logger = logging.getLogger("careermap.tracking.crm")

class ApplicationCRM:
    """Başvuru CRM'i ve yaşam döngüsü yöneticisi."""

    def __init__(self, db_conn: Optional[sqlite3.Connection] = None):
        self.conn = db_conn or get_connection()

    def create_application_record(
        self,
        candidate_id: str,
        employer_id: str,
        position_title: str = "Diş Hekimi",
        match_data: Optional[Dict[str, Any]] = None,
        workflow_plan: Optional[Dict[str, Any]] = None,
        messages_package: Optional[Dict[str, Any]] = None,
        status: str = "draft"
    ) -> str:
        """İşveren için tekil başvuru kaydını ve ilgili mesaj taslaklarını oluşturur."""
        app_id = f"app-{candidate_id[-6:]}-{employer_id[-12:]}"
        cursor = self.conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        match_score = match_data.get("match_score", 70) if match_data else 70
        match_reasons = json.dumps(match_data.get("match_reasons", []) if match_data else [], ensure_ascii=False)
        planned_channels = json.dumps(workflow_plan.get("steps", []) if workflow_plan else [], ensure_ascii=False)
        primary_channel = workflow_plan.get("primary_channel", "email") if workflow_plan else "email"

        cursor.execute("""
        INSERT INTO applications (
            application_id, candidate_id, employer_id, position_title,
            status, orchestration_step, planned_channels_json,
            match_score, match_reasons_json, primary_channel,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(candidate_id, employer_id, position_title) DO UPDATE SET
            status = excluded.status,
            match_score = excluded.match_score,
            match_reasons_json = excluded.match_reasons_json,
            planned_channels_json = excluded.planned_channels_json,
            primary_channel = excluded.primary_channel,
            updated_at = excluded.updated_at
        """, (
            app_id,
            candidate_id,
            employer_id,
            position_title,
            status,
            planned_channels,
            match_score,
            match_reasons,
            primary_channel,
            now_str,
            now_str
        ))

        # Mesaj taslaklarını kaydet
        if messages_package:
            # E-posta
            if "email" in messages_package:
                em = messages_package["email"]
                cursor.execute("""
                INSERT OR REPLACE INTO application_messages (
                    message_id, application_id, channel, message_type,
                    subject, body_text, recipient_contact, secure_cv_url, action_url,
                    is_approved, created_at
                ) VALUES (?, ?, 'email', 'initial', ?, ?, ?, ?, '', 0, ?)
                """, (
                    f"msg-email-{app_id}",
                    app_id,
                    em.get("subject", ""),
                    em.get("body", ""),
                    em.get("recipient", ""),
                    em.get("attachment_name", ""),
                    now_str
                ))

            # WhatsApp Model B
            if "whatsapp_model_b" in messages_package:
                wb = messages_package["whatsapp_model_b"]
                wa_action_url = messages_package.get("whatsapp_handoff_link_b", "")
                cursor.execute("""
                INSERT OR REPLACE INTO application_messages (
                    message_id, application_id, channel, message_type,
                    subject, body_text, recipient_contact, secure_cv_url, action_url,
                    is_approved, created_at
                ) VALUES (?, ?, 'whatsapp', 'model_b', 'WhatsApp Başvuru (Model B)', ?, ?, ?, ?, 0, ?)
                """, (
                    f"msg-wa-b-{app_id}",
                    app_id,
                    wb.get("body", ""),
                    messages_package.get("whatsapp_phone", ""),
                    wb.get("secure_url", ""),
                    wa_action_url,
                    now_str
                ))

            # Telefon Görüşme Notu
            if "phone_script" in messages_package:
                ps = messages_package["phone_script"]
                cursor.execute("""
                INSERT OR REPLACE INTO application_messages (
                    message_id, application_id, channel, message_type,
                    subject, body_text, recipient_contact, action_url,
                    is_approved, created_at
                ) VALUES (?, ?, 'phone_script', 'call_brief', 'Telefonla Ön Görüşme Notu', ?, ?, '', 0, ?)
                """, (
                    f"msg-phone-{app_id}",
                    app_id,
                    ps.get("body", ""),
                    ps.get("target_phone", ""),
                    now_str
                ))

        # Başlangıç Olay Kaydı
        cursor.execute("""
        INSERT INTO application_events (
            event_id, application_id, event_type, old_status, new_status, details_text, created_at
        ) VALUES (?, ?, 'application_created', '', ?, 'Başvuru dosyası ve kişiselleştirilmiş taslaklar hazırlandı.', ?)
        """, (
            f"evt-{uuid.uuid4().hex[:10]}",
            app_id,
            status,
            now_str
        ))

        self.conn.commit()
        return app_id

    def approve_application(self, application_id: str) -> bool:
        """Kullanıcının başvuruyu ve mesaj taslaklarını onaylaması."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = self.conn.cursor()
        cursor.execute("UPDATE applications SET status = 'pending_approval', updated_at = ? WHERE application_id = ?", (now_str, application_id))
        cursor.execute("UPDATE application_messages SET is_approved = 1, approved_at = ? WHERE application_id = ?", (now_str, application_id))
        cursor.execute("""
        INSERT INTO application_events (
            event_id, application_id, event_type, old_status, new_status, details_text, created_at
        ) VALUES (?, ?, 'application_approved', 'draft', 'pending_approval', 'Aday taslakları ve gönderimi onayladı.', ?)
        """, (f"evt-{uuid.uuid4().hex[:10]}", application_id, now_str))
        self.conn.commit()
        return True

    def record_channel_action(
        self,
        application_id: str,
        channel: str,
        contact_value: str,
        action_status: str = "confirmed_by_user",
        notes: str = ""
    ) -> str:
        """Kullanıcının kanaldan gönderim yaptığını veya durumu güncellediğini kaydeder."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        att_id = f"att-{uuid.uuid4().hex[:10]}"
        cursor = self.conn.cursor()

        cursor.execute("""
        INSERT INTO channel_attempts (
            attempt_id, application_id, channel, contact_value,
            attempt_type, status, notes, attempted_at
        ) VALUES (?, ?, ?, ?, 'initial_application', ?, ?, ?)
        """, (att_id, application_id, channel, contact_value, action_status, notes, now_str))

        cursor.execute("UPDATE applications SET status = 'waiting_reply', orchestration_step = 2, updated_at = ? WHERE application_id = ?", (now_str, application_id))

        cursor.execute("""
        INSERT INTO application_events (
            event_id, application_id, event_type, old_status, new_status, details_text, created_at
        ) VALUES (?, ?, 'channel_attempt_logged', 'pending_approval', 'waiting_reply', ?, ?)
        """, (f"evt-{uuid.uuid4().hex[:10]}", application_id, f"{channel.upper()} kanalı üzerinden gönderim kaydedildi: {notes}", now_str))

        self.conn.commit()
        return att_id

    def update_application_status(self, application_id: str, new_status: str, notes: str = "") -> bool:
        """Başvuru durumunu (waiting_reply, interview, rejected vb.) günceller."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = self.conn.cursor()
        cursor.execute("SELECT status FROM applications WHERE application_id = ?", (application_id,))
        row = cursor.fetchone()
        old_status = row[0] if row else "unknown"

        cursor.execute("UPDATE applications SET status = ?, updated_at = ? WHERE application_id = ?", (new_status, now_str, application_id))
        cursor.execute("""
        INSERT INTO application_events (
            event_id, application_id, event_type, old_status, new_status, details_text, created_at
        ) VALUES (?, ?, 'status_changed', ?, ?, ?, ?)
        """, (f"evt-{uuid.uuid4().hex[:10]}", application_id, old_status, new_status, notes, now_str))

        self.conn.commit()
        return True

    def get_candidate_crm_dashboard(self, candidate_id: str) -> Dict[str, Any]:
        """Aday kontrol paneli için özet metrikler ve başvuru kartları döner."""
        cursor = self.conn.cursor()

        cursor.execute("""
        SELECT 
            COUNT(*) as total_apps,
            SUM(CASE WHEN status IN ('attempted', 'waiting_reply', 'sent') THEN 1 ELSE 0 END) as sent_count,
            SUM(CASE WHEN status IN ('waiting_reply', 'interview') THEN 1 ELSE 0 END) as replies_count,
            SUM(CASE WHEN status = 'interview' THEN 1 ELSE 0 END) as interview_count,
            SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) as draft_count,
            SUM(CASE WHEN status = 'pending_approval' THEN 1 ELSE 0 END) as pending_approval_count
        FROM applications WHERE candidate_id = ?
        """, (candidate_id,))
        stats = cursor.fetchone()

        # Detaylı başvuru kartları
        cursor.execute("""
        SELECT 
            a.application_id, a.employer_id, a.position_title, a.status,
            a.match_score, a.match_reasons_json, a.primary_channel,
            a.orchestration_step, a.created_at, a.updated_at,
            e.name as employer_name, e.employer_type, e.district,
            e.email, e.phone, e.whatsapp_url, e.website, e.contact_form_url
        FROM applications a
        JOIN employers e ON a.employer_id = e.employer_id
        WHERE a.candidate_id = ?
        ORDER BY a.match_score DESC, a.created_at DESC
        """, (candidate_id,))
        app_rows = [dict(r) for r in cursor.fetchall()]

        application_cards = []
        for ar in app_rows:
            ar["match_reasons"] = json.loads(ar.get("match_reasons_json") or "[]")
            
            # Mesajları çek
            cursor.execute("SELECT channel, message_type, subject, body_text, secure_cv_url, action_url, is_approved FROM application_messages WHERE application_id = ?", (ar["application_id"],))
            msgs = [dict(m) for m in cursor.fetchall()]
            ar["messages"] = msgs

            # Kanal denemelerini çek
            cursor.execute("SELECT channel, contact_value, status, attempted_at, notes FROM channel_attempts WHERE application_id = ? ORDER BY attempted_at DESC", (ar["application_id"],))
            attempts = [dict(att) for att in cursor.fetchall()]
            ar["channel_attempts"] = attempts

            # Olay geçmişini çek
            cursor.execute("SELECT event_type, old_status, new_status, details_text, created_at FROM application_events WHERE application_id = ? ORDER BY created_at DESC", (ar["application_id"],))
            events = [dict(ev) for ev in cursor.fetchall()]
            ar["events"] = events

            application_cards.append(ar)

        return {
            "candidate_id": candidate_id,
            "metrics": {
                "target_employers": stats[0] if stats else 0,
                "applications_sent": stats[1] if stats else 0,
                "replies_or_active": stats[2] if stats else 0,
                "interviews": stats[3] if stats else 0,
                "drafts": stats[4] if stats else 0,
                "pending_approval": stats[5] if stats else 0
            },
            "applications": application_cards
        }

