"""CareerMap V2.2 Veri Bütünlüğü ve Karantina Yönetim Modülü (Quarantine Manager).
- P0: Bağımsız kaynak kanıtı (resmî sicil URL, OSM nesne kimliği, teyitli web sitesi) bulunmayan kayıtları tespit eder.
- Sabit katalog ve sentetik üretim kökenli kayıtları 'quarantined' statüsüne alır.
- Bu kayıtların iletişim kanallarını otomatik başvuru gönderimine kapatır.
- Eskişehir'in 220 adet doğrulanmış ve resmî kayıtlarını korur.
"""
import logging
import sqlite3
from typing import Dict, Any, List, Tuple
from datetime import datetime

logger = logging.getLogger("careermap.discovery.quarantine")


def execute_v2_2_quarantine(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Veritabanındaki bağımsız kaynak kanıtı bulunmayan katalog ve sentetik kayıtları karantinaya alır.
    Eskişehir il sağlık ve TDB sicil kayıtları kesinlikle korunur.
    """
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Karantinaya alınacak kayıtları tespit et
    # Kriter: Eskişehir dışındaki illerde olup kaynak tipi 'Resmî Rehber' veya genel 'https://saglik.gov.tr' olanlar
    cursor.execute("""
    SELECT employer_id, city, district, name, source_type, source_urls, phone, email, whatsapp_url
    FROM employers
    WHERE city != 'Eskişehir'
      AND (
          source_type = 'Resmî Rehber'
          OR source_urls = 'https://saglik.gov.tr'
          OR source_urls LIKE '%saglik.gov.tr%' AND (source_urls NOT LIKE '%/%/%' OR source_urls = 'https://saglik.gov.tr')
          OR research_status = 'verified' AND source_type NOT IN ('OpenStreetMap', 'TDB Resmî Sicil', 'İl Sağlık Müdürlüğü')
      )
    """)
    candidates = cursor.fetchall()

    quarantined_by_city: Dict[str, int] = {}
    quarantined_ids = []

    for row in candidates:
        emp_id = row[0]
        city = row[1]
        quarantined_ids.append(emp_id)
        quarantined_by_city[city] = quarantined_by_city.get(city, 0) + 1

    if quarantined_ids:
        # Employers tablosunu güncelle: quarantined statüsü, düşük güven skoru
        placeholders = ",".join(["?" for _ in quarantined_ids])
        cursor.execute(f"""
        UPDATE employers
        SET research_status = 'quarantined',
            confidence_score = 30,
            confidence_level = 'Düşük',
            phone_verification_status = 'unverified',
            email_verification_status = 'unverified',
            website_verification_status = 'unverified',
            research_notes = 'Kaynak kanıtı bağımsız olarak doğrulanmadığı için karantinaya alındı (V2.2 integrity policy). Başvuru gönderimine kapalıdır.',
            updated_at = ?
        WHERE employer_id IN ({placeholders})
        """, [now_str] + quarantined_ids)

        # employer_contacts tablosunu güncelle: unverified ve quarantined
        cursor.execute(f"""
        UPDATE employer_contacts
        SET verification_status = 'unverified',
            confidence_category = 'quarantined'
        WHERE employer_id IN ({placeholders})
        """, quarantined_ids)

    conn.commit()

    logger.warning(
        f"CareerMap V2.2 Karantina Politikası: Toplam {len(quarantined_ids)} kurum karantinaya alındı. "
        f"Şehirler: {quarantined_by_city}"
    )

    return {
        "status": "success",
        "total_quarantined": len(quarantined_ids),
        "quarantined_by_city": quarantined_by_city,
        "executed_at": now_str,
        "policy": "V2.2-A Nationwide Data Integrity"
    }


def is_employer_allowed_for_application(employer: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Bir işverene başvuru dosyası hazırlanıp hazırlanamayacağını ve
    mesaj gönderilip gönderilemeyeceğini denetler.
    Karantinaya alınmış veya güven skoru düşük kurumlara başvuru kesinlikle engellenir.
    """
    status = employer.get("research_status", "")
    conf_score = employer.get("confidence_score", 50)
    source_type = employer.get("source_type", "")

    if status == "quarantined":
        return False, "Bu kurumun bağımsız kaynak kanıtı doğrulanmadığı için karantinaya alınmıştır. Güvenli başvuru gönderimine kapalıdır."

    if status == "needs_review":
        return False, "Bu kurum insan denetimi (needs_review) beklemektedir. Otomatik başvuru hazırlanamaz."

    if conf_score < 40:
        return False, f"Kurumun güven skoru ({conf_score}/100) başvuru için yetersizdir. En az 40 puan gereklidir."

    if source_type in ("synthetic", "unverified_catalog"):
        return False, "Sentetik veya doğrulanmamış katalog kayıtlarına başvuru gönderilemez."

    return True, "Onaylandı"

