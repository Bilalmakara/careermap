"""Diş Hekimi mesleği için veri kaynakları ve kurallar."""
from typing import List, Dict, Any
import re
import unicodedata
from bs4 import BeautifulSoup
from .base import BaseProfession

class DentistProfession(BaseProfession):
    id = "dentist"
    name = "Diş Hekimi"
    description = "Ağız ve diş sağlığı poliklinikleri, klinikler ve bireysel muayenehaneler"
    icon = "bi-heart-pulse"
    
    supported_cities = {
        "Eskişehir": [
            "Tepebaşı", "Odunpazarı", "Sivrihisar", "Çifteler",
            "Alpu", "Mahmudiye", "İnönü", "Seyitgazi",
            "Mihalıççık", "Sarıcakaya", "Mihalgazi", "Beylikova",
            "Günyüzü", "Han"
        ],
        "Ankara": [
            "Çankaya", "Yenimahalle", "Keçiören", "Mamak",
            "Etimesgut", "Sincan", "Altındağ", "Gölbaşı",
            "Pursaklar", "Polatlı"
        ],
        "İstanbul": [
            "Kadıköy", "Beşiktaş", "Şişli", "Üsküdar",
            "Bakırköy", "Maltepe", "Ataşehir", "Fatih",
            "Beyoğlu", "Sarıyer", "Pendik", "Ümraniye", "Kartal"
        ],
        "İzmir": [
            "Konak", "Karşıyaka", "Bornova", "Çiğli",
            "Buca", "Bayraklı", "Alsancak", "Gaziemir", "Balçova"
        ],
        "Bursa": [
            "Nilüfer", "Osmangazi", "Yıldırım", "İnegöl", "Gemlik"
        ],
        "Antalya": [
            "Muratpaşa", "Konyaaltı", "Kepez", "Alanya", "Manavgat"
        ],
        "Adana": [
            "Seyhan", "Çukurova", "Yüreğir", "Sarıçam", "Ceyhan"
        ],
        "Konya": [
            "Selçuklu", "Meram", "Karatay", "Ereğli", "Akşehir"
        ],
        "Gaziantep": [
            "Şahinbey", "Şehitkamil", "Nizip"
        ],
        "Kocaeli": [
            "İzmit", "Gebze", "Gölcük", "Körfez", "Darıca", "Kartepe"
        ],
        "Mersin": [
            "Yenişehir", "Mezitli", "Akdeniz", "Toroslar", "Tarsus"
        ],
        "Diyarbakır": [
            "Kayapınar", "Bağlar", "Yenişehir", "Sur"
        ],
        "Samsun": [
            "İlkadım", "Atakum", "Canik", "Bafra"
        ],
        "Trabzon": [
            "Ortahisar", "Akçaabat", "Yomra"
        ],
        "Kayseri": [
            "Melikgazi", "Kocasinan", "Talas"
        ],
        "Muğla": [
            "Bodrum", "Fethiye", "Menteşe", "Marmaris"
        ],
        "Balıkesir": [
            "Altıeylül", "Karesi", "Bandırma", "Edremit"
        ],
        "Denizli": [
            "Pamukkale", "Merkezefendi"
        ],
        "Sakarya": [
            "Adapazarı", "Serdivan", "Erenler", "Hendek"
        ],
        "Tekirdağ": [
            "Süleymanpaşa", "Çorlu", "Çerkezköy"
        ],
        "Manisa": [
            "Şehzadeler", "Yunusemre", "Akhisar", "Turgutlu"
        ],
        "Aydın": [
            "Efeler", "Kuşadası", "Didim", "Nazilli"
        ],
        "Bilecik": [
            "Merkez", "Bozüyük", "Osmaneli"
        ],
        "Kütahya": [
            "Merkez", "Tavşanlı", "Simav"
        ],
        "Afyonkarahisar": [
            "Merkez", "Sandıklı", "Dinar"
        ],
        "Bolu": [
            "Merkez", "Gerede", "Mengen"
        ],
        "Isparta": [
            "Merkez", "Yalvaç", "Eğirdir"
        ]
    }
    
    employer_types = [
        {"id": "all", "label": "Tüm Diş Klinikleri ve Muayenehaneler"},
        {"id": "clinic", "label": "Özel Ağız ve Diş Sağlığı Poliklinikleri"},
        {"id": "office", "label": "Bireysel Diş Hekimi Muayenehaneleri"}
    ]
    
    osm_tags = [
        {"key": "amenity", "value": "dentist"},
        {"key": "healthcare", "value": "dentist"}
    ]

    def get_official_sources(self, city: str) -> List[Dict[str, Any]]:
        if city == "Eskişehir":
            return [
                {
                    "type": "clinic",
                    "label": "Özel Poliklinikler",
                    "url": "https://eskisehirism.saglik.gov.tr/TR-39645/ozel-agiz-ve-dis-sagligi-poliklinikleri.html"
                },
                {
                    "type": "office",
                    "label": "Bireysel Muayenehaneler",
                    "url": "https://eskisehirism.saglik.gov.tr/TR-39637/dis-hekimi-muayenehaneleri.html"
                }
            ]
        return []

    def normalize_for_comparison(self, s: str) -> str:
        s = self.clean_text(s).lower()
        s = s.translate(str.maketrans("çğıöşü", "cgiosu"))
        s = unicodedata.normalize("NFKD", s)
        s = re.sub(r"\b(ozel|agiz|ve|dis|sagligi|poliklinigi|poliklinik|klinigi|klinik|muayenehanesi|muayenehane|dt|dr|dishekimi|hekimligi)\b", " ", s)
        s = re.sub(r"[^a-z0-9]", "", s)
        return s

    def parse_official_records(self, soup_dict: Dict[str, Any], city: str) -> List[Dict[str, Any]]:
        """İl Sağlık Müdürlüğü sayfalarındaki HTML tablolarını parse eder."""
        results = []
        seen = set()

        for source_key, data in soup_dict.items():
            soup: BeautifulSoup = data.get("soup")
            source_url = data.get("url", "")
            emp_type = "Özel poliklinik" if ("clinic" in source_key.lower() or "poliklinik" in source_key.lower()) else "Bireysel muayenehane"

            if not soup:
                continue

            tables = soup.select("table")
            for table in tables:
                rows = table.select("tr")
                if len(rows) < 2:
                    continue

                for tr in rows[1:]:
                    cells = [self.clean_text(c.get_text(" ", strip=True)) for c in tr.find_all(["td", "th"], recursive=False)]
                    if len(cells) < 2 or not cells[0]:
                        continue

                    # Genelde ilk hücre Kurum / Hekim adı, son hücre açık adrestir
                    name = cells[0]
                    if len(name) < 4:
                        continue
                        
                    canon = self.normalize_for_comparison(name)
                    if canon in seen and len(canon) > 3:
                        continue
                    seen.add(canon)

                    address = cells[-1] if len(cells) >= 2 else ""
                    phone = ""
                    # Eğer telefon içeren bir hücre varsa tespit et
                    for c in cells[1:-1]:
                        if any(char.isdigit() for char in c) and len(c) >= 7:
                            phone = c
                            break

                    district = self.detect_district(address, city)
                    if not district and len(cells) >= 3:
                        district = self.detect_district(cells[2], city)
                        
                    formatted_address = address
                    if district and (not formatted_address or formatted_address.upper() in [district.upper(), "ESKİŞEHİR", "ESKISEHIR"]):
                        formatted_address = f"{district} / {city}"
                    
                    record = {
                        "name": name,
                        "employer_type": emp_type,
                        "district": district or "Eskişehir",
                        "address": formatted_address,
                        "phone": phone,
                        "email": "",
                        "website": "",
                        "career_url": "",
                        "email_source_url": "",
                        "source_urls": source_url,
                        "source_type": "Eskişehir İl Sağlık Müdürlüğü"
                    }
                    results.append(record)
                    
        return results

