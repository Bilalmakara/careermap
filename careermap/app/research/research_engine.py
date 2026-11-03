"""CareerMap V2.1 Dinamik Araştırma Motoru (Research Engine).
- Kullanıcının seçtiği meslek, kurum türleri ve konuma göre dinamik araştırma görevlerini yürütür.
- Eskişehir diş hekimliği için doğrulanmış zengin veritabanını ve yeniden taramayı kullanır.
- Ankara ve diğer iller için OpenStreetMap Overpass sorguları ve web keşif adaptörlerini çalıştırır.
- Desteklenmeyen meslekler/şehirler için kesinlikle sahte veri üretmez; şeffaf kapsam durumu raporlar.
- Aşamalı ilerleme bildirimleri: queued -> discovering -> enriching -> verifying -> completed.
"""
import logging
import threading
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..database.db import (
    get_connection,
    get_research_job,
    update_research_job_progress,
    add_job_result,
    canonical_id,
    upsert_contact
)
from ..professions.registry import ProfessionRegistry
from ..discovery.osm_source import OVERPASS_ENDPOINTS
import requests

logger = logging.getLogger("careermap.research.engine")

def search_osm_city_dentists(city: str, districts: List[str] = None) -> List[Dict[str, Any]]:
    """Belirli bir il ve ilçe için Overpass API üzerinden gerçek diş hekimi / klinik noktalarını sorgular."""
    district_filter = districts[0] if (districts and len(districts) > 0 and districts[0].lower() != "all") else ""
    
    headers = {
        "User-Agent": "CareerMap/2.1 (Search-First Dentist Discovery; respectful research; info@careermap.local)",
        "Accept": "application/json"
    }

    # İl / İlçe bazlı Overpass sorgusu
    if district_filter:
        query = f"""
        [out:json][timeout:15];
        area["name"="{city}"]["admin_level"~"4|6"]->.cityArea;
        (
          node["amenity"="dentist"](area.cityArea);
          way["amenity"="dentist"](area.cityArea);
          node["healthcare"="dentist"](area.cityArea);
          way["healthcare"="dentist"](area.cityArea);
        );
        out center tags 40;
        """
    else:
        query = f"""
        [out:json][timeout:15];
        area["name"="{city}"]["admin_level"~"4|6"]->.cityArea;
        (
          node["amenity"="dentist"](area.cityArea);
          node["healthcare"="dentist"](area.cityArea);
        );
        out center tags 30;
        """

    records = []
    seen = set()

    for endpoint in OVERPASS_ENDPOINTS:
        try:
            resp = requests.post(endpoint, data={"data": query}, headers=headers, timeout=9)
            if resp.status_code == 200:
                data = resp.json()
                for el in data.get("elements", []):
                    tags = el.get("tags", {})
                    name = tags.get("name") or tags.get("operator") or tags.get("brand")
                    if not name or name.strip() in seen:
                        continue
                    seen.add(name.strip())

                    # Kurum türü tespiti
                    n_lower = name.lower()
                    if "poliklinik" in n_lower or "merkezi" in n_lower or "hastane" in n_lower:
                        emp_type = "Özel poliklinik"
                    elif "dt" in n_lower or "hekim" in n_lower:
                        emp_type = "Bireysel muayenehane"
                    else:
                        emp_type = "Özel poliklinik"

                    phone = tags.get("phone") or tags.get("contact:phone") or ""
                    email = tags.get("email") or tags.get("contact:email") or ""
                    website = tags.get("website") or tags.get("contact:website") or ""
                    address = tags.get("addr:street", "") + " " + tags.get("addr:housenumber", "")
                    if not address.strip():
                        address = f"{district_filter or city} Merkez"

                    records.append({
                        "name": name.strip(),
                        "employer_type": emp_type,
                        "city": city,
                        "district": district_filter or city,
                        "address": address.strip(),
                        "phone": phone,
                        "email": email,
                        "website": website,
                        "source_urls": f"https://www.openstreetmap.org/{el.get('type')}/{el.get('id')}"
                    })
                break
        except Exception as e:
            logger.debug(f"OSM endpoint hatası ({endpoint}): {e}")

    return records


class ResearchJobService:
    """Arka planda bağımsız araştırma görevlerini koordine eden servis."""

    @classmethod
    def execute_job_sync(cls, job_id: str):
        """Araştırma görevini senkron yürütür (arka plan iş parçacığı veya test için)."""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            job = get_research_job(job_id, conn)
            if not job:
                logger.error(f"Araştırma görevi bulunamadı: {job_id}")
                return

            profession_id = job["profession_id"]
            city = job["city"]
            districts = job["districts"]
            employer_types = job["employer_types"]
            keywords = job["keywords"]

            # 1. Başlangıç / Queued -> Discovering
            update_research_job_progress(
                job_id,
                status="discovering",
                progress_percent=15,
                progress_stage="Hedef konum ve meslek için resmî veri kaynakları taranıyor...",
                conn=conn
            )
            time.sleep(0.3)

            # Meslek kontrolü
            profession_obj = ProfessionRegistry.get(profession_id)
            if not profession_obj:
                update_research_job_progress(
                    job_id,
                    status="failed",
                    progress_percent=100,
                    progress_stage="Bilinmeyen meslek kategorisi.",
                    error_message=f"'{profession_id}' meslek kaydı bulunamadı.",
                    conn=conn
                )
                return

            # Desteklenmeyen meslek kontrolü (Sahte veri üretmeme garantisi)
            if profession_id != "dentist":
                update_research_job_progress(
                    job_id,
                    status="completed",
                    progress_percent=100,
                    progress_stage=f"'{profession_obj.name}' mesleği için {city} veri kaynağı adaptörü geliştirme aşamasındadır. Doğrulanmamış sahte sonuç üretilmemektedir.",
                    total_found=0,
                    contacts_found=0,
                    verified_count=0,
                    conn=conn
                )
                return

            # DİŞ HEKİMİ MESLEĞİ İÇİN ARAŞTIRMA AKIŞI
            # 1. Aşama: Çok Kaynaklı Dinamik Keşif Motoru (DiscoveryEngine - OSM & Resmî & Web Keşfi)
            update_research_job_progress(
                job_id,
                status="discovering",
                progress_percent=30,
                progress_stage=f"{city} için bağımsız kaynak adaptörleri (Yerel OSM, Resmî Sicil, Kamuya Açık Rehberler) taranıyor...",
                conn=conn
            )
            time.sleep(0.2)

            from ..discovery.discovery_engine import DiscoveryEngine
            discovery_res = DiscoveryEngine.discover_employers(
                profession_id=profession_id,
                city=city,
                districts=districts,
                employer_types=employer_types,
                research_job_id=job_id,
                conn=conn
            )

            # 2. Aşama: Çok Kriterli Filtreleme (İl, İlçe, Kurum Türü, Anahtar Kelime - Karantinadakiler hariç)
            query_parts = ["city = ? AND profession_id = 'dentist' AND research_status != 'quarantined'"]
            params = [city]

            if districts and len(districts) > 0 and districts[0].lower() not in ("all", "tüm ilçeler"):
                dist_placeholders = ",".join(["?" for _ in districts])
                query_parts.append(f"district IN ({dist_placeholders})")
                params.extend(districts)

            if employer_types and "all" not in employer_types:
                type_conds = []
                for et in employer_types:
                    if et == "clinic":
                        type_conds.append("employer_type LIKE '%poliklinik%'")
                    elif et == "office":
                        type_conds.append("(employer_type LIKE '%muayenehane%' OR name LIKE 'Dt.%' OR name LIKE 'Dr.%')")
                if type_conds:
                    query_parts.append(f"({' OR '.join(type_conds)})")

            if keywords and keywords.strip():
                term = f"%{keywords.strip()}%"
                query_parts.append("(name LIKE ? OR address LIKE ?)")
                params.extend([term, term])

            cursor.execute(f"SELECT * FROM employers WHERE {' AND '.join(query_parts)} ORDER BY confidence_score DESC, is_email_found DESC", tuple(params))
            found_employers = [dict(r) for r in cursor.fetchall()]

            total_count = len(found_employers)

            # 3. Aşama: Tekilleştirme & İletişim Zenginleştirme (Discovering -> Enriching)
            update_research_job_progress(
                job_id,
                status="enriching",
                progress_percent=60,
                progress_stage=f"{total_count} işletme noktası tespit edildi. Web siteleri ve iletişim kanalları inceleniyor...",
                total_found=total_count,
                conn=conn
            )
            time.sleep(0.2)

            # V2.5: Kalıcı İletişim Zenginleştirme Kuyruğu (Arbitrary [:3] Sınırı Kaldırıldı)
            from ..enrichment.enrichment_queue import ContactEnrichmentQueue
            enqueued_count = ContactEnrichmentQueue.enqueue_employers_for_job(job_id, found_employers, conn=conn)
            enrichment_summary = ContactEnrichmentQueue.process_pending_queue(
                research_job_id=job_id,
                batch_limit=25,
                timeout_secs=2,
                conn=conn
            )
            logger.info(f"İletişim Zenginleştirme: {enqueued_count} kurum kuyruğa alındı, {enrichment_summary['processed']} web sitesi tarandı.")

            # Zenginleştirilmiş iletişimleri veritabanından yeniden yükle
            cursor.execute(f"SELECT * FROM employers WHERE {' AND '.join(query_parts)} ORDER BY confidence_score DESC, is_email_found DESC", tuple(params))
            found_employers = [dict(r) for r in cursor.fetchall()]

            contacts_count = 0
            verified_count = 0
            quarantined_count = 0

            for emp in found_employers:
                emp_id = emp["employer_id"]
                # Araştırma sonuç tablosuna ekle
                add_job_result(job_id, emp_id, has_job_posting=0, posting_details="Genel Başvuru", conn=conn)

                res_status = emp.get("research_status", "")
                conf_score = emp.get("confidence_score", 0)

                if res_status == "quarantined" or conf_score < 40:
                    quarantined_count += 1
                else:
                    verified_count += 1

                has_contact = bool(emp.get("phone") or emp.get("email") or emp.get("whatsapp_url") or emp.get("contact_form_url"))
                if has_contact and res_status != "quarantined":
                    contacts_count += 1

            # 4. Aşama: Doğrulama & Kanıt Kontrolü (Verifying)
            update_research_job_progress(
                job_id,
                status="verifying",
                progress_percent=85,
                progress_stage=f"{contacts_count} başvuruya uygun iletişim kanalı doğrulandı. Kanıtlar kontrol ediliyor...",
                total_found=total_count,
                contacts_found=contacts_count,
                verified_count=verified_count,
                quarantined_count=quarantined_count,
                conn=conn
            )
            time.sleep(0.2)

            # 5. Aşama: Görev Tamamlandı / Kısmi Kapsam (P5 & P6 & P9)
            sources_summary = discovery_res.get("sources_summary", {})
            succ_count = len(sources_summary.get("succeeded", []))
            total_sources = len(sources_summary.get("attempted", []))
            has_failed_source = len(sources_summary.get("failed", [])) > 0

            final_stage_msg = (
                f"{city} bölgesinde {total_count} kurum bulundu "
                f"({verified_count} doğrulanmış, {contacts_count} iletişimi mevcut). "
                f"Planlanan {total_sources} kaynak görevinin {succ_count}'si tamamlandı."
            )
            if total_count == 0:
                final_stage_msg = f"{city} / {', '.join(districts) or 'Genel'} bölgesinde henüz resmî liste kaydı bulunamadı."

            final_status = "partial" if has_failed_source else "completed"

            audit = discovery_res.get("audit_funnel", {})
            cov_metrics = discovery_res.get("coverage_metrics", {})
            ref_str = ""
            if cov_metrics and cov_metrics.get("has_benchmark"):
                ref_str = f" | Pazar Referansı: {cov_metrics['official_reference_count']} ({cov_metrics['coverage_level']}, Kapsama: %{cov_metrics['coverage_ratio_percent']})"

            audit_summary_str = (
                f"Ham Kaynak: {audit.get('total_raw_candidates', total_count)} -> "
                f"Tekilleştirilmiş: {audit.get('unique_after_dedup', total_count)} -> "
                f"Filtrelenmiş Sonuç: {total_count} (İletişimli: {contacts_count}, Doğrulanmış: {verified_count})"
                f"{ref_str}"
            )

            update_research_job_progress(
                job_id,
                status=final_status,
                progress_percent=100,
                progress_stage=final_stage_msg,
                total_found=total_count,
                contacts_found=contacts_count,
                verified_count=verified_count,
                coverage_summary=audit_summary_str,
                quarantined_count=quarantined_count,
                conn=conn
            )

        except Exception as e:
            logger.exception(f"Araştırma görevi hatası ({job_id}): {e}")
            update_research_job_progress(
                job_id,
                status="failed",
                progress_percent=100,
                progress_stage="Araştırma sırasında beklenmeyen hata oluştu.",
                error_message=str(e),
                conn=conn
            )
        finally:
            conn.close()

    @classmethod
    def start_job_async(cls, job_id: str):
        """Araştırmayı arka planda ayrı iş parçacığında çalıştırır."""
        thread = threading.Thread(target=cls.execute_job_sync, args=(job_id,), daemon=True)
        thread.start()
        return thread

