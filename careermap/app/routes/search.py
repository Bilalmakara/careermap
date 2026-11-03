"""Arama, tarama ve filtreleme API uç noktaları."""
from fastapi import APIRouter, Query, BackgroundTasks, HTTPException
from typing import List, Optional
from ..professions.registry import ProfessionRegistry
from ..database.db import query_employers, get_cache_info
from ..services.scanner import run_pipeline

router = APIRouter(prefix="/api", tags=["search"])

@router.get("/professions")
def get_professions():
    """Desteklenen tüm meslekleri ve yapılandırmalarını listeler."""
    return ProfessionRegistry.list_all()

@router.get("/search")
def search_employers(
    profession: str = Query("dentist", description="Meslek kimliği"),
    city: str = Query("Eskişehir", description="Şehir adı"),
    districts: Optional[str] = Query(None, description="Virgülle ayrılmış ilçeler"),
    employer_type: Optional[str] = Query("all", description="İşveren türü"),
    verification_status: Optional[str] = Query(None, description="Doğrulama durumu: verified, unverified, manual_review, conflict"),
    q: Optional[str] = Query(None, description="Metin arama"),
    only_with_email: bool = Query(False, description="Sadece e-postası olanlar")
):
    """Filtrelere göre veritabanındaki kayıtları sorgular."""
    district_list = [d.strip() for d in districts.split(",")] if districts else None
    
    cache_info = get_cache_info(profession, city)
    if not cache_info or cache_info.get("total_count", 0) == 0:
        run_pipeline(profession, city, force_refresh=False)
        cache_info = get_cache_info(profession, city)

    records = query_employers(
        profession_id=profession,
        city=city,
        districts=district_list,
        employer_type=employer_type,
        verification_status=verification_status,
        search_text=q,
        only_with_email=only_with_email
    )

    return {
        "status": "success",
        "cache_info": cache_info,
        "count": len(records),
        "records": records
    }

@router.post("/scan")
def trigger_scan(
    profession: str = Query("dentist"),
    city: str = Query("Eskişehir"),
    enrich_emails: bool = Query(True)
):
    """Yeni bir tarama başlatır ve önbelleği tazeler."""
    try:
        records = run_pipeline(profession, city, force_refresh=True, enrich_emails=enrich_emails)
        cache_info = get_cache_info(profession, city)
        return {
            "status": "success",
            "message": "Tarama tamamlandı ve önbellek güncellendi.",
            "total_count": len(records),
            "cache_info": cache_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

