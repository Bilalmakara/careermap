"""CareerMap V2.5 İki Aşamalı Kalıcı İletişim Zenginleştirme Kuyruğu (Two-Stage Contact Enrichment Queue).
- 1. Aşama (website_discovery): Web sitesi olmayan işletmeler için arama motoru üzerinden resmî siteyi keşfeder.
- 2. Aşama (contact_extraction): Bulunan veya mevcut web sitesinden e-posta, telefon ve iletişim formunu tarar.
- E-postası olan ancak telefonu eksik olan kurumları da kuyruğa dahil eder.
- Sürekli işlenebilir worker mantığı; bir çalıştırmada 25 limit dolsa bile kalan işler pending kalır ve unutulmaz.
- Telefon bulunması otomatik WhatsApp sayılmaz; alan bazlı kanıt (evidence_json) tutulur.
"""
import uuid
import time
import json
import logging
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional

from .contact_page_crawler import crawl_business_website
from .search_adapters import FreeSerpAdapter
from .web_search_discovery import DIRECTORY_DOMAINS, is_third_party_directory
from .website_identity_matcher import normalize_tr_text
from ..database.db import get_connection, upsert_contact

logger = logging.getLogger("careermap.enrichment.queue")


class ContactEnrichmentQueue:
    """İki aşamalı kalıcı iletişim zenginleştirme kuyruk yöneticisi."""

    @classmethod
    def enqueue_employers_for_job(
        cls,
        research_job_id: str,
        employers: List[Dict[str, Any]],
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict[str, int]:
        """
        Araştırma görevindeki kurumları durumlarına göre website_discovery veya contact_extraction görevine alır.
        """
        should_close = False
        if conn is None:
            conn = get_connection()
            should_close = True

        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        web_disc_count = 0
        contact_ext_count = 0

        for emp in employers:
            emp_id = emp.get("employer_id")
            website = (emp.get("website") or "").strip()
            email = (emp.get("email") or "").strip()
            phone = (emp.get("phone") or "").strip()

            # 1. Görev Türü: Web sitesi hiç yoksa -> website_discovery
            if not website:
                qid = f"queue-web-{uuid.uuid4().hex[:10]}"
                try:
                    cursor.execute("""
                    INSERT OR IGNORE INTO contact_enrichment_queue (
                        queue_id, employer_id, research_job_id, task_type, website_url,
                        status, attempts, created_at, updated_at
                    ) VALUES (?, ?, ?, 'website_discovery', '', 'pending', 0, ?, ?)
                    """, (qid, emp_id, research_job_id, now_str, now_str))
                    web_disc_count += 1
                except Exception as e:
                    logger.debug(f"Kuyruk ekleme hatası (web): {e}")

            # 2. Görev Türü: Web sitesi var ama e-posta veya telefon eksikse -> contact_extraction
            elif not email or not phone:
                qid = f"queue-ext-{uuid.uuid4().hex[:10]}"
                try:
                    cursor.execute("""
                    INSERT OR IGNORE INTO contact_enrichment_queue (
                        queue_id, employer_id, research_job_id, task_type, website_url,
                        status, attempts, created_at, updated_at
                    ) VALUES (?, ?, ?, 'contact_extraction', ?, 'pending', 0, ?, ?)
                    """, (qid, emp_id, research_job_id, website, now_str, now_str))
                    contact_ext_count += 1
                except Exception as e:
                    logger.debug(f"Kuyruk ekleme hatası (contact): {e}")

        conn.commit()
        if should_close:
            conn.close()

        logger.info(
            f"İş Kuyruğu: Görev '{research_job_id}' için "
            f"{web_disc_count} web sitesi keşfi, {contact_ext_count} iletişim çıkarma görevi eklendi."
        )
        return {
            "website_discovery_enqueued": web_disc_count,
            "contact_extraction_enqueued": contact_ext_count,
            "total_enqueued": web_disc_count + contact_ext_count
        }

    @classmethod
    def process_pending_queue(
        cls,
        research_job_id: Optional[str] = None,
        batch_limit: int = 50,
        timeout_secs: int = 2,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict[str, Any]:
        """
        Kuyruktaki bekleyen işleri alır; iki aşamalı olarak işler.
        """
        should_close = False
        if conn is None:
            conn = get_connection()
            should_close = True

        cursor = conn.cursor()
        query = """
        SELECT q.queue_id, q.employer_id, q.task_type, q.website_url, q.attempts,
               e.name, e.city, e.district
        FROM contact_enrichment_queue q
        JOIN employers e ON q.employer_id = e.employer_id
        WHERE q.status = 'pending'
        """
        params = []
        if research_job_id:
            query += " AND q.research_job_id = ?"
            params.append(research_job_id)
        query += " ORDER BY q.created_at ASC LIMIT ?"
        params.append(batch_limit)

        cursor.execute(query, tuple(params))
        items = cursor.fetchall()

        processed = 0
        websites_found = 0
        emails_found = 0
        phones_found = 0
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        search_adapter = FreeSerpAdapter(timeout=2)
        start_time = time.time()

        for item in items:
            if time.time() - start_time > 4.0:
                logger.info("Kuyruk senkron süresi tamamlandı; kalan kayıtlar arka plan kuyruğunda bekletiliyor.")
                break
            qid = item[0]
            emp_id = item[1]
            task_type = item[2]
            web_url = item[3]
            attempts = item[4] + 1
            emp_name = item[5]
            emp_city = item[6]
            emp_dist = item[7]

            cursor.execute("UPDATE contact_enrichment_queue SET status = 'processing', attempts = ?, updated_at = ? WHERE queue_id = ?", (attempts, now_str, qid))
            conn.commit()

            try:
                # --- 1. AŞAMA: Web Sitesi Keşfi (website_discovery) ---
                if task_type == "website_discovery":
                    q_term = f"{emp_name} {emp_dist or emp_city} diş"
                    res = search_adapter.search(q_term, max_results=5)
                    found_site = ""
                    norm_emp = normalize_tr_text(emp_name).replace("ozel", "").replace("agiz ve dis sagligi", "").replace("poliklinigi", "").replace("merkezi", "").strip()
                    tokens = [t for t in norm_emp.split() if len(t) > 2 and t not in ("dis", "dent", "klinik")]

                    for r in res:
                        if is_third_party_directory(r.url):
                            continue
                        dom = r.domain.lower().replace("www.", "")
                        # Domain veya başlık işletme adıyla en azından bir anahtar kelime eşleşmeli
                        if tokens and not any(tok in dom for tok in tokens) and not any(tok in normalize_tr_text(r.title) for tok in tokens):
                            continue

                        # Kök etki alanını esas al (derin makale/forum url'lerini değil)
                        from urllib.parse import urlparse
                        p_parsed = urlparse(r.url)
                        base_site = f"{p_parsed.scheme}://{p_parsed.netloc}"
                        found_site = base_site
                        break

                    if found_site:
                        websites_found += 1
                        cursor.execute("""
                        UPDATE employers
                        SET website = ?, website_source_url = ?, website_verification_status = 'observed_on_search', updated_at = ?
                        WHERE employer_id = ?
                        """, (found_site, found_site, now_str, emp_id))

                        cursor.execute("""
                        UPDATE contact_enrichment_queue
                        SET status = 'completed', website_url = ?, updated_at = ?
                        WHERE queue_id = ?
                        """, (found_site, now_str, qid))

                        # İkinci aşama için otomatik iletişim çıkarma görevi aç
                        next_qid = f"queue-ext-{uuid.uuid4().hex[:10]}"
                        cursor.execute("""
                        INSERT OR IGNORE INTO contact_enrichment_queue (
                            queue_id, employer_id, research_job_id, task_type, website_url,
                            status, attempts, created_at, updated_at
                        ) VALUES (?, ?, ?, 'contact_extraction', ?, 'pending', 0, ?, ?)
                        """, (next_qid, emp_id, research_job_id or "", found_site, now_str, now_str))
                    else:
                        cursor.execute("""
                        UPDATE contact_enrichment_queue
                        SET status = 'no_website_found', updated_at = ?
                        WHERE queue_id = ?
                        """, (now_str, qid))

                # --- 2. AŞAMA: İletişim Çıkarma (contact_extraction) ---
                else:
                    if not web_url:
                        cursor.execute("UPDATE contact_enrichment_queue SET status = 'failed', error_message = 'Web URL eksik', updated_at = ? WHERE queue_id = ?", (now_str, qid))
                        continue

                    crawl_res = crawl_business_website(web_url, max_pages=3)
                    discovered_email = crawl_res.get("primary_email", "")
                    discovered_phone = crawl_res.get("primary_phone", "")
                    discovered_form = crawl_res.get("contact_form_url", "")
                    evidence = crawl_res.get("evidence", {})

                    update_fields = []
                    update_params = []

                    if discovered_email:
                        update_fields.append("email = ?")
                        update_params.append(discovered_email)
                        update_fields.append("email_source_url = ?")
                        update_params.append(web_url)
                        update_fields.append("email_verification_status = 'observed_on_website'")
                        update_fields.append("is_email_found = 1")
                        emails_found += 1
                        upsert_contact(cursor, emp_id, "email", discovered_email, "corporate", web_url, "website_crawler", "enrichment_queue", verification_status="observed_on_website")

                    if discovered_phone:
                        update_fields.append("phone = CASE WHEN phone = '' OR phone IS NULL THEN ? ELSE phone END")
                        update_params.append(discovered_phone)
                        update_fields.append("phone_source_url = CASE WHEN phone_source_url = '' OR phone_source_url IS NULL THEN ? ELSE phone_source_url END")
                        update_params.append(web_url)
                        update_fields.append("phone_verification_status = CASE WHEN phone_verification_status = 'unverified' THEN 'observed_on_website' ELSE phone_verification_status END")
                        phones_found += 1
                        upsert_contact(cursor, emp_id, "phone", discovered_phone, "corporate", web_url, "website_crawler", "enrichment_queue", verification_status="observed_on_website")

                    if discovered_form:
                        update_fields.append("contact_form_url = ?")
                        update_params.append(discovered_form)

                    if update_fields:
                        update_fields.append("updated_at = ?")
                        update_params.append(now_str)
                        update_params.append(emp_id)
                        cursor.execute(f"UPDATE employers SET {', '.join(update_fields)} WHERE employer_id = ?", tuple(update_params))

                    cursor.execute("""
                    UPDATE contact_enrichment_queue
                    SET status = 'completed',
                        discovered_email = ?,
                        discovered_phone = ?,
                        discovered_contact_form = ?,
                        evidence_json = ?,
                        updated_at = ?
                    WHERE queue_id = ?
                    """, (discovered_email, discovered_phone, discovered_form, json.dumps(evidence, ensure_ascii=False), now_str, qid))

                processed += 1

            except Exception as e:
                logger.warning(f"Kuyruk işleme hatası ({qid}): {e}")
                cursor.execute("""
                UPDATE contact_enrichment_queue
                SET status = CASE WHEN attempts >= 3 THEN 'failed' ELSE 'pending' END,
                    error_message = ?,
                    updated_at = ?
                WHERE queue_id = ?
                """, (str(e), now_str, qid))

            conn.commit()

        # Kalan kuyruk derinliğini say
        cursor.execute("SELECT count(1) FROM contact_enrichment_queue WHERE status = 'pending'")
        remaining_pending = cursor.fetchone()[0]

        if should_close:
            conn.close()

        logger.info(
            f"Kuyruk İşleme: {processed} iş tamamlandı. "
            f"Bulunanlar: {websites_found} site, {emails_found} mail, {phones_found} tel. "
            f"Kalan Bekleyen İş: {remaining_pending}."
        )
        return {
            "processed": processed,
            "websites_found": websites_found,
            "emails_found": emails_found,
            "phones_found": phones_found,
            "remaining_pending": remaining_pending
        }
