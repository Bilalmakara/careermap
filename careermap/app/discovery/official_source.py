"""Resmî kurum sayfalarından veri toplama modülü."""
import logging
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, List
from ..professions.base import BaseProfession

logger = logging.getLogger("careermap.discovery.official")

HEADERS = {
    "User-Agent": "CareerMapBot/1.0 (Public Educational & Career Directory Research; respectful rate limits)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr,en-US;q=0.7,en;q=0.3"
}

def fetch_official_sources(profession: BaseProfession, city: str) -> List[Dict[str, Any]]:
    """İlgili mesleğin resmî kaynaklarını çeker ve kayıt listesi üretir."""
    sources = profession.get_official_sources(city)
    if not sources:
        return []

    soup_dict = {}
    session = requests.Session()

    for src in sources:
        url = src.get("url")
        src_type = src.get("type", "general")
        logger.info(f"Resmî kaynak çekiliyor: {src.get('label')} ({url})")
        
        try:
            resp = session.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                soup_dict[src_type] = {
                    "soup": soup,
                    "url": url,
                    "label": src.get("label")
                }
            else:
                logger.warning(f"Resmî kaynak HTTP {resp.status_code}: {url}")
        except Exception as e:
            logger.error(f"Resmî kaynak çekme hatası ({url}): {e}")

    # Mesleğin kendi parser'ı ile dönüştür
    records = profession.parse_official_records(soup_dict, city)
    logger.info(f"Resmî kaynaktan toplam {len(records)} kayıt çıkarıldı.")
    return records

