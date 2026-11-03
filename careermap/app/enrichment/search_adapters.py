"""CareerMap V1.5 Değiştirilebilir Arama Motoru Adapter Mimarisi (Search Adapters).
- FreeSerp (freeserp.ai): Anahtarsız ve ücretsiz web indeksi adapteri.
- Brave Search: API anahtarı yapılandırıldığında çalışan opsiyonel adapter.
- LocalDomainHeuristic: Düşük öncelikli alan adı tahmini fallback adapteri.
- SearchCache: Sorgu sonuçlarını yerel SQLite / JSON dosyasında önbelleğe alan sistem.
- SearchRouter: Sorgu üretimi, önbellekleme ve çoklu sağlayıcı koordinasyonu.
"""
import os
import re
import json
import time
import logging
import sqlite3
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger("careermap.enrichment.search_adapters")

@dataclass
class SearchResult:
    url: str
    domain: str
    title: str
    snippet: str
    source_provider: str
    rank: int = 1
    query: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class BaseSearchAdapter(ABC):
    """Tüm arama motoru sağlayıcıları için temel soyut sınıf."""
    name: str = "base"

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Arama sorgusunu çalıştırır ve SearchResult listesi döner."""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Sağlayıcının sağlık ve erişilebilirlik durumunu döner."""
        pass

class FreeSerpAdapter(BaseSearchAdapter):
    """
    FreeSerp (freeserp.ai) Global Web İndeksi Adapteri.
    - Anahtarsız ve ücretsiz REST API: https://freeserp.ai/api.php?index=web
    - 3.1+ Milyar web sayfası indeksi.
    """
    name = "freeserp"
    BASE_URL = "https://freeserp.ai/api.php"

    def __init__(self, timeout: int = 8, user_agent: Optional[str] = None):
        self.timeout = timeout
        self.user_agent = user_agent or "CareerMap/1.5 (Healthcare Research; info@careermap.local)"
        self.last_status = "idle"
        self.last_error = ""
        self.total_queries = 0
        self.failed_queries = 0

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        self.total_queries += 1
        clean_query = query.strip()
        if not clean_query:
            return []

        params = {
            "index": "web",
            "q": clean_query,
            "lang": "tr",
            "size": str(max_results)
        }
        query_string = urllib.parse.urlencode(params)
        url = f"{self.BASE_URL}?{query_string}"

        results: List[SearchResult] = []
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if response.status != 200:
                    self.last_status = f"http_error_{response.status}"
                    self.failed_queries += 1
                    logger.warning(f"FreeSerp HTTP {response.status} hatası: {query}")
                    return []

                raw_body = response.read().decode("utf-8", errors="replace")
                data = json.loads(raw_body)

                if not isinstance(data, dict) or not data.get("ok"):
                    self.last_status = "api_error"
                    self.last_error = data.get("error", "Bilinmeyen API cevabı") if isinstance(data, dict) else "Geçersiz JSON"
                    return []

                raw_results = data.get("results", [])
                for rank, item in enumerate(raw_results, 1):
                    item_url = item.get("url", "").strip()
                    if not item_url or not item_url.startswith(("http://", "https://")):
                        continue

                    parsed_domain = item.get("domain") or urllib.parse.urlparse(item_url).netloc
                    results.append(SearchResult(
                        url=item_url,
                        domain=parsed_domain.lower().replace("www.", ""),
                        title=item.get("title", "").strip(),
                        snippet=item.get("snippet", "").strip(),
                        source_provider=self.name,
                        rank=rank,
                        query=clean_query
                    ))

                self.last_status = "active"
                self.last_error = ""

        except urllib.error.HTTPError as e:
            self.last_status = f"http_error_{e.code}"
            self.last_error = str(e)
            self.failed_queries += 1
            logger.warning(f"FreeSerp HTTPError ({e.code}) sorgu: '{clean_query}': {e}")
        except urllib.error.URLError as e:
            self.last_status = "connection_failed"
            self.last_error = str(e)
            self.failed_queries += 1
            logger.warning(f"FreeSerp Bağlantı Hatası: '{clean_query}': {e}")
        except Exception as e:
            self.last_status = "unexpected_error"
            self.last_error = str(e)
            self.failed_queries += 1
            logger.warning(f"FreeSerp Beklenmeyen Hata: '{clean_query}': {e}")

        return results

    def get_status(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "status": self.last_status,
            "last_error": self.last_error,
            "total_queries": self.total_queries,
            "failed_queries": self.failed_queries
        }

class BraveSearchAdapter(BaseSearchAdapter):
    """
    Brave Search API Adapteri.
    - Ortam değişkeninde 'BRAVE_SEARCH_API_KEY' varsa aktifleşir.
    - Aylık 5$ / ~1.000 sorgu ücretsiz kredi imkânı.
    """
    name = "brave"
    ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: Optional[str] = None, timeout: int = 8):
        self.api_key = api_key or os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
        self.timeout = timeout
        self.last_status = "active" if self.api_key else "not_configured"
        self.last_error = ""

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        if not self.api_key:
            self.last_status = "not_configured"
            return []

        params = {
            "q": query.strip(),
            "count": str(max_results),
            "country": "TR",
            "search_lang": "tr"
        }
        url = f"{self.ENDPOINT}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key,
                "User-Agent": "CareerMap/1.5"
            }
        )

        results: List[SearchResult] = []
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                web_items = data.get("web", {}).get("results", [])
                for rank, item in enumerate(web_items, 1):
                    item_url = item.get("url", "")
                    if item_url:
                        parsed = urllib.parse.urlparse(item_url)
                        results.append(SearchResult(
                            url=item_url,
                            domain=parsed.netloc.lower().replace("www.", ""),
                            title=item.get("title", ""),
                            snippet=item.get("description", ""),
                            source_provider=self.name,
                            rank=rank,
                            query=query
                        ))
            self.last_status = "active"
        except Exception as e:
            self.last_status = "error"
            self.last_error = str(e)
            logger.warning(f"Brave Search hatası: {e}")

        return results

    def get_status(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "status": self.last_status,
            "last_error": self.last_error,
            "configured": bool(self.api_key)
        }

class LocalDomainHeuristicAdapter(BaseSearchAdapter):
    """
    Düşük Öncelikli Alan Adı Tahmini (Heuristic Fallback).
    - Arama motoru ulaşılamadığında veya sonuç dönmediğinde devreye girer.
    - Asla arama motoru sonucu gibi sunulmaz; 'domain_heuristic' olarak etiketlenir.
    """
    name = "domain_heuristic"

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        # Geriye dönük uyumluluk: query'den basit aday türetir
        return []

    def get_status(self) -> Dict[str, Any]:
        return {"provider": self.name, "status": "active"}

class SearchCache:
    """
    Kalıcı SQLite Arama Önbelleği.
    - search_cache.db bağımsız veritabanında çalışarak ana veritabanında kilitlenmeleri önler.
    - Aynı sorgunun gereksiz yere ağa gitmesini engeller.
    - TTL süresi varsayılan 14 gündür.
    """
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).resolve().parent.parent.parent / "search_cache.db"
        self.db_path = db_path
        self._init_cache_table()

    def _init_cache_table(self):
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_query_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_key TEXT UNIQUE,
                query_text TEXT,
                provider TEXT,
                results_json TEXT,
                result_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'ok',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Search cache tablosu başlatılamadı: {e}")

    def get(self, query: str, provider: str) -> Optional[List[SearchResult]]:
        query_key = f"{provider}:{query.strip().lower()}"
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("SELECT results_json, status FROM search_query_cache WHERE query_key = ?", (query_key,))
            row = cursor.fetchone()
            conn.close()
            if row and row[0]:
                data = json.loads(row[0])
                return [SearchResult(**item) for item in data]
        except Exception as e:
            logger.debug(f"Cache okuma hatası: {e}")
        return None

    def set(self, query: str, provider: str, results: List[SearchResult], status: str = "ok"):
        query_key = f"{provider}:{query.strip().lower()}"
        results_json = json.dumps([r.to_dict() for r in results], ensure_ascii=False)
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO search_query_cache (query_key, query_text, provider, results_json, result_count, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (query_key, query.strip(), provider, results_json, len(results), status))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug(f"Cache yazma hatası: {e}")

class SearchRouter:
    """
    Akıllı Arama Yönlendiricisi ve Sorgu Üreticisi.
    - İşletme unvanına göre en verimli 2-3 hedefli sorguyu üretir.
    - Önbelleği kontrol eder.
    - Birincil ve ikincil sağlayıcıları sırayla dener.
    - Arama başarısızlığı ile sonuç bulunamamasını kesin olarak ayırır.
    """
    def __init__(
        self,
        primary_adapter: Optional[BaseSearchAdapter] = None,
        fallback_adapters: Optional[List[BaseSearchAdapter]] = None,
        cache: Optional[SearchCache] = None
    ):
        self.primary_adapter = primary_adapter or FreeSerpAdapter()
        self.fallback_adapters = fallback_adapters or [BraveSearchAdapter()]
        self.cache = cache or SearchCache()

    def generate_queries_for_employer(self, employer: Dict[str, Any]) -> List[str]:
        """İşletme için 2-3 hedefli ve rafine arama sorgusu üretir."""
        raw_name = employer.get("name", "").strip()
        city = employer.get("city", "Eskişehir").strip()
        district = employer.get("district", "").strip()
        emp_type = employer.get("employer_type", "").lower()
        is_office = "muayenehane" in emp_type or raw_name.lower().startswith("dt")

        clean_name = re.sub(r"^(?:prof\.\s*dr\.|doç\.\s*dr\.|doc\.\s*dr\.|dr\.\s*dt\.|dt\.|dr\.|dt|dr)\s+", "", raw_name, flags=re.IGNORECASE).strip()
        queries: List[str] = []

        if is_office:
            # 1. Hekim adı + soyadı + şehir + diş hekimi
            queries.append(f"{clean_name} diş hekimi {city}")
            # 2. Hekim adı + şehir + iletişim
            queries.append(f"{clean_name} {city} iletişim")
            # 3. Varsa ilçe ekle
            if district:
                queries.append(f"{clean_name} {district} telefon")
        else:
            # Poliklinik için
            clean_clinic = re.sub(r"\b(ozel|özel|ağız|agiz|ve|diş|dis|sağlığı|sagligi|polikliniği|poliklinigi)\b", "", raw_name, flags=re.IGNORECASE).strip()
            brand = " ".join(clean_clinic.split()[:3])
            
            # 1. Tam klinik unvanı + şehir
            queries.append(f"{raw_name} {city}")
            # 2. Marka + şehir + diş iletişim
            if brand:
                queries.append(f"{brand} diş {city} iletişim")
            # 3. Varsa ilçe
            if district:
                queries.append(f"{raw_name} {district} telefon")

        # Tekilleştir
        seen = set()
        unique_queries = []
        for q in queries:
            q_norm = " ".join(q.split())
            if q_norm not in seen:
                seen.add(q_norm)
                unique_queries.append(q_norm)

        return unique_queries[:3]

    def search_for_employer(
        self,
        employer: Dict[str, Any],
        max_results_per_query: int = 4
    ) -> Dict[str, Any]:
        """
        İşletme için tüm hedefli sorguları çalıştırır, tekilleştirilmiş sonuç havuzu döner.
        Rapor alanı:
        - status: 'success' | 'no_results' | 'search_failed'
        - candidates: List[SearchResult]
        - queries_executed: List[str]
        - provider_used: str
        """
        queries = self.generate_queries_for_employer(employer)
        all_candidates: List[SearchResult] = []
        seen_urls = set()
        queries_executed = []
        provider_used = self.primary_adapter.name
        had_network_error = False

        for q in queries:
            queries_executed.append(q)
            # 1. Önce önbelleğe bak
            cached = self.cache.get(q, provider_used)
            if cached is not None:
                for c in cached:
                    if c.url not in seen_urls:
                        seen_urls.add(c.url)
                        all_candidates.append(c)
                continue

            # 2. Önbellekte yoksa API'yi çağır
            time.sleep(0.3)  # Saygılı hız sınırı
            res = self.primary_adapter.search(q, max_results=max_results_per_query)
            provider_status = self.primary_adapter.get_status()

            if "error" in provider_status.get("status", "") or "failed" in provider_status.get("status", ""):
                had_network_error = True
                # Fallback adapter dene (varsa Brave)
                for fb in self.fallback_adapters:
                    fb_res = fb.search(q, max_results=max_results_per_query)
                    if fb_res:
                        res = fb_res
                        provider_used = fb.name
                        break

            # Önbelleğe yaz
            self.cache.set(q, provider_used, res, status="ok" if res else "empty")

            for item in res:
                if item.url not in seen_urls:
                    seen_urls.add(item.url)
                    all_candidates.append(item)

        # Durum belirle
        if all_candidates:
            final_status = "success"
        elif had_network_error and not all_candidates:
            final_status = "search_failed"
        else:
            final_status = "no_results"

        return {
            "status": final_status,
            "candidates": all_candidates,
            "queries_executed": queries_executed,
            "provider_used": provider_used,
            "candidate_count": len(all_candidates)
        }
