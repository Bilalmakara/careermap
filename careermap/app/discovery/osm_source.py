"""CareerMap V1.3 OpenStreetMap (Overpass API) Keşif Motoru.
- Odaklı coğrafi sorgular ve dinamik ayna sunucu yük devri (failover).
- Düşük ağ gecikmesi için optimize zaman aşımları (8s).
- Kurumsal telefon, e-posta ve web sitesi etiketlerini ayıklar.
"""
import logging
import requests
from typing import List, Dict, Any, Tuple
from ..professions.base import BaseProfession
from ..enrichment.phone_extractor import format_phone

logger = logging.getLogger("careermap.discovery.osm")

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
]

# Eskişehir Merkez (Tepebaşı ve Odunpazarı yoğunluklu) odaklı BBOX (south, west, north, east)
ESKISEHIR_ZONES = [
    # Tepebaşı ve Odunpazarı Şehir Merkezi (En yoğun klinik bölgesi)
    {"name": "Eskişehir Merkez", "bbox": (39.73, 30.45, 39.82, 30.58)},
    # Doğu / Odunpazarı Çevre
    {"name": "Eskişehir Doğu", "bbox": (39.70, 30.55, 39.80, 30.65)},
    # Batı / Tepebaşı Çevre
    {"name": "Eskişehir Batı", "bbox": (39.75, 30.35, 39.85, 30.48)}
]

def build_zone_query(bbox: Tuple[float, float, float, float]) -> str:
    """Belirli bir coğrafi kutu için optimize Overpass sorgusu üretir."""
    bbox_str = f"({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]})"
    return f"""
    [out:json][timeout:15];
    (
      node["amenity"="dentist"]{bbox_str};
      way["amenity"="dentist"]{bbox_str};
      relation["amenity"="dentist"]{bbox_str};
      node["healthcare"="dentist"]{bbox_str};
      way["healthcare"="dentist"]{bbox_str};
      relation["healthcare"="dentist"]{bbox_str};
    );
    out center tags;
    """

def fetch_osm_records(profession: BaseProfession, city: str = "Eskişehir") -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Overpass API üzerinden odaklı sorgulama yapar.
    Hızlı hata devri (8s timeout) ile sunucu yanıt vermediğinde beklemeyi minimize eder.
    """
    headers = {
        "User-Agent": "CareerMap/1.3 (OpenStreetMap Dentist Research; respectful educational; info@careermap.local)",
        "Accept": "application/json"
    }

    all_elements = []
    seen_ids = set()
    status_report = {
        "status": "failed",
        "successful_endpoint": None,
        "failed_attempts": [],
        "total_elements": 0,
        "zones_scanned": []
    }

    working_endpoint = None
    test_query = build_zone_query(ESKISEHIR_ZONES[0]["bbox"])

    for endpoint in OVERPASS_ENDPOINTS:
        try:
            logger.info(f"Overpass sunucusu test ediliyor: {endpoint}")
            resp = requests.post(endpoint, data={"data": test_query}, headers=headers, timeout=8)
            if resp.status_code == 200:
                working_endpoint = endpoint
                status_report["successful_endpoint"] = endpoint
                status_report["status"] = "success"
                data = resp.json()
                for el in data.get("elements", []):
                    uid = f"{el.get('type')}_{el.get('id')}"
                    if uid not in seen_ids:
                        seen_ids.add(uid)
                        all_elements.append(el)
                status_report["zones_scanned"].append(ESKISEHIR_ZONES[0]["name"])
                break
            else:
                status_report["failed_attempts"].append(f"{endpoint}: HTTP {resp.status_code}")
        except Exception as e:
            status_report["failed_attempts"].append(f"{endpoint}: {type(e).__name__}")

    # Çalışan sunucu bulunduysa diğer bölgeleri tara
    if working_endpoint:
        for zone in ESKISEHIR_ZONES[1:]:
            try:
                zone_q = build_zone_query(zone["bbox"])
                resp = requests.post(working_endpoint, data={"data": zone_q}, headers=headers, timeout=8)
                if resp.status_code == 200:
                    data = resp.json()
                    for el in data.get("elements", []):
                        uid = f"{el.get('type')}_{el.get('id')}"
                        if uid not in seen_ids:
                            seen_ids.add(uid)
                            all_elements.append(el)
                    status_report["zones_scanned"].append(zone["name"])
            except Exception as e:
                logger.debug(f"OSM bölge sorgu hatası ({zone['name']}): {e}")

    status_report["total_elements"] = len(all_elements)

    records = []
    for elem in all_elements:
        tags = elem.get("tags", {})
        name = tags.get("name") or tags.get("operator") or tags.get("brand")
        if not name:
            continue

        raw_phone = tags.get("phone") or tags.get("contact:phone") or ""
        phone = format_phone(raw_phone) if raw_phone else ""
        website = tags.get("website") or tags.get("contact:website") or ""
        email = tags.get("email") or tags.get("contact:email") or ""

        street = tags.get("addr:street")
        housenumber = tags.get("addr:housenumber")
        suburb = tags.get("addr:suburb") or tags.get("addr:neighbourhood")
        district = tags.get("addr:district") or tags.get("addr:subdistrict") or ""
        
        addr_parts = []
        if street:
            addr_parts.append(f"{street} No:{housenumber}" if housenumber else street)
        if suburb:
            addr_parts.append(suburb)
            
        full_addr = tags.get("addr:full") or ", ".join(addr_parts)
        if not district:
            district = profession.detect_district(full_addr, city)

        osm_id = elem.get("id")
        osm_type = elem.get("type", "node")
        source_url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}"

        contacts = []
        if phone:
            contacts.append({
                "contact_type": "phone",
                "contact_value": phone,
                "contact_category": "corporate",
                "source_url": source_url,
                "source_type": "osm",
                "verification_status": "verified"
            })
        if email:
            contacts.append({
                "contact_type": "email",
                "contact_value": email,
                "contact_category": "general",
                "source_url": source_url,
                "source_type": "osm",
                "verification_status": "verified"
            })
        if website:
            contacts.append({
                "contact_type": "website",
                "contact_value": website,
                "contact_category": "corporate",
                "source_url": source_url,
                "source_type": "osm",
                "verification_status": "verified"
            })

        records.append({
            "name": name,
            "employer_type": "Klinik / Muayenehane (OSM)",
            "district": district,
            "address": full_addr,
            "phone": phone,
            "phone_source_url": source_url if phone else "",
            "phone_type": "corporate" if phone else "unknown",
            "phone_verification_status": "verified" if phone else "unverified",
            "email": email,
            "email_source_url": source_url if email else "",
            "email_type": "general" if email else "unknown",
            "email_verification_status": "verified" if email else "unverified",
            "website": website,
            "website_source_url": source_url if website else "",
            "website_verification_status": "verified" if website else "unverified",
            "career_url": "",
            "contact_form_url": "",
            "contacts": contacts,
            "source_urls": source_url,
            "source_type": "OpenStreetMap",
            "business_status": "active",
            "research_status": "completed" if (phone or website or email) else "pending"
        })

    return records, status_report
