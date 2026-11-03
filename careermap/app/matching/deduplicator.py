"""CareerMap V1.1 Akıllı Tekilleştirme ve Çelişki Tespit Motoru."""
import re
import logging
from typing import List, Dict, Any
from difflib import SequenceMatcher

try:
    from rapidfuzz import fuzz
    USE_RAPIDFUZZ = True
except ImportError:
    USE_RAPIDFUZZ = False

from ..professions.base import BaseProfession

logger = logging.getLogger("careermap.matching.deduplicator")

def similarity_ratio(s1: str, s2: str) -> float:
    if not s1 or not s2:
        return 0.0
    if USE_RAPIDFUZZ:
        return fuzz.ratio(s1, s2) / 100.0
    return SequenceMatcher(None, s1, s2).ratio()

def is_same_employer(a: Dict[str, Any], b: Dict[str, Any], profession: BaseProfession) -> bool:
    """İki kaydın aynı işletme olup olmadığını test eder; şubeleri ve aynı soyadlı hekimleri korur."""
    name_a_raw = a.get("name", "")
    name_b_raw = b.get("name", "")

    # 1. Bireysel hekimlerde aynı soyadı taşıyan farklı hekimler ASLA birleştirilmez!
    is_doc_a = name_a_raw.strip().lower().startswith("dt") or "muayenehane" in a.get("employer_type", "").lower()
    is_doc_b = name_b_raw.strip().lower().startswith("dt") or "muayenehane" in b.get("employer_type", "").lower()
    if is_doc_a and is_doc_b:
        # İsimlerin temizlenmiş hali birebir aynı değilse birleştirme!
        ca = profession.normalize_for_comparison(name_a_raw)
        cb = profession.normalize_for_comparison(name_b_raw)
        if ca != cb:
            return False

    # 2. Şube kontrolü: Eğer isimde şube belirteci varsa (Çamlıca, Emek, Doktorlar, Sakarya) ve uyuşmuyorsa birleştirme!
    branch_keywords = ["şube", "sube", "çamlıca", "camlica", "emek", "sakarya", "doktorlar", "batı", "bati"]
    for kw in branch_keywords:
        in_a = kw in name_a_raw.lower()
        in_b = kw in name_b_raw.lower()
        if in_a != in_b:
            return False

    # 3. İlçe kontrolü: Farklı ilçelerdeyseler ASLA birleştirilmez!
    dist_a = (a.get("district") or "").strip().lower()
    dist_b = (b.get("district") or "").strip().lower()
    if dist_a and dist_b and dist_a != dist_b:
        return False

    name_a = profession.normalize_for_comparison(name_a_raw)
    name_b = profession.normalize_for_comparison(name_b_raw)
    if not name_a or not name_b:
        return False

    name_sim = similarity_ratio(name_a, name_b)

    # 4. Telefon uyuşması varsa
    phone_a = re.sub(r"\D", "", a.get("phone", ""))
    phone_b = re.sub(r"\D", "", b.get("phone", ""))
    if phone_a and phone_b and len(phone_a) >= 7 and phone_a[-7:] == phone_b[-7:] and name_sim > 0.75:
        return True

    # 5. İsim benzerliği ve adres kontrolü
    addr_a = profession.normalize_for_comparison(a.get("address", ""))
    addr_b = profession.normalize_for_comparison(b.get("address", ""))

    if name_sim >= 0.95:
        if addr_a and addr_b and len(addr_a) > 10 and len(addr_b) > 10:
            addr_sim = similarity_ratio(addr_a, addr_b)
            if addr_sim < 0.35:
                return False
        return True

    return False

def merge_two_records(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """İki kaydı birleştirirken çelişkili telefonları tespit eder."""
    merged = dict(base)

    # Çelişkili telefon kontrolü
    base_phone = re.sub(r"\D", "", merged.get("phone", ""))
    inc_phone = re.sub(r"\D", "", incoming.get("phone", ""))
    if base_phone and inc_phone and len(base_phone) >= 7 and len(inc_phone) >= 7:
        if base_phone[-7:] != inc_phone[-7:]:
            merged["verification_status"] = "conflict"
            logger.warning(f"Telefon çelişkisi tespit edildi: {merged.get('name')} ({merged.get('phone')} vs {incoming.get('phone')})")

    # Eksik alanları tamamla
    for field in ["phone", "phone_source_url", "website", "website_source_url", "email", "email_source_url", "address", "district", "career_url"]:
        if not merged.get(field) and incoming.get(field):
            merged[field] = incoming[field]

    # Kaynak URL'lerini birleştir
    src_urls = set()
    for s in [base.get("source_urls", ""), incoming.get("source_urls", "")]:
        for url in s.split(" | "):
            if url.strip():
                src_urls.add(url.strip())
    merged["source_urls"] = " | ".join(sorted(src_urls))

    # Kaynak türlerini birleştir
    types = set()
    for t in [base.get("source_type", ""), incoming.get("source_type", "")]:
        for part in t.split(" + "):
            if part.strip() and part.strip() != "Bilinmiyor":
                types.add(part.strip())
    merged["source_type"] = " + ".join(sorted(types)) if types else "Genel Kaynak"

    return merged

def deduplicate_records(records: List[Dict[str, Any]], profession: BaseProfession) -> List[Dict[str, Any]]:
    combined: List[Dict[str, Any]] = []

    for item in records:
        matched_idx = -1
        for idx, existing in enumerate(combined):
            if is_same_employer(existing, item, profession):
                matched_idx = idx
                break

        if matched_idx >= 0:
            combined[matched_idx] = merge_two_records(combined[matched_idx], item)
        else:
            combined.append(dict(item))

    logger.info(f"Tekilleştirme tamamlandı: {len(records)} ham kayıt -> {len(combined)} tekil kayıt.")
    return combined
