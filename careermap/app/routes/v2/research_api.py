"""CareerMap V2.1 Dinamik Araştırma ve Keşif API Uç Noktaları (Research API)."""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field

from ...database.db import (
    get_connection,
    create_research_job,
    get_research_job,
    list_research_jobs,
    get_job_results,
    set_job_result_selection
)
from ...professions.registry import ProfessionRegistry
from ...research.research_engine import ResearchJobService
from .auth_api import get_optional_user

router = APIRouter(prefix="/api/v2/research", tags=["v2-research"])


class CreateResearchJobRequest(BaseModel):
    profession_id: str = Field(..., description="Meslek kimliği: dentist, industrial_engineer, software_engineer, veterinarian, lawyer")
    city: str = Field(..., description="Hedef il: Eskişehir, Ankara, İstanbul, vb.")
    employer_types: Optional[List[str]] = Field(default_factory=lambda: ["all"], description="Seçilen kurum tipleri")
    districts: Optional[List[str]] = Field(default_factory=list, description="Seçilen ilçeler")
    keywords: Optional[str] = Field("", description="İsteğe bağlı anahtar kelimeler")
    country: Optional[str] = Field("Türkiye", description="Hedef ülke")


class SelectJobResultRequest(BaseModel):
    employer_id: str
    is_selected: bool


@router.get("/professions")
def list_professions():
    """Sistemde kayıtlı meslekleri, mesleğe özel kurum türlerini ve desteklenen konumları döner."""
    return {
        "status": "success",
        "professions": ProfessionRegistry.list_all()
    }


@router.post("/jobs")
def start_research_job(
    req: CreateResearchJobRequest,
    user: Dict[str, Any] = Depends(get_optional_user)
):
    """
    Kullanıcının seçtiği meslek, kurum türleri ve konuma göre dinamik araştırma görevini başlatır.
    """
    prof = ProfessionRegistry.get(req.profession_id)
    if not prof:
        raise HTTPException(status_code=400, detail=f"'{req.profession_id}' meslek tanımı bulunamadı.")

    user_id = user.get("user_id", "user-candidate-rumeysa")
    job_id = create_research_job(
        profession_id=req.profession_id,
        profession_name=prof.name,
        city=req.city,
        employer_types=req.employer_types or ["all"],
        districts=req.districts or [],
        keywords=req.keywords or "",
        user_id=user_id,
        country=req.country or "Türkiye"
    )

    # Arka planda görevi başlat
    ResearchJobService.start_job_async(job_id)

    job_data = get_research_job(job_id)
    return {
        "status": "success",
        "message": f"'{prof.name}' için {req.city} bölgesinde araştırma görevi başlatıldı.",
        "job_id": job_id,
        "job": job_data
    }


@router.get("/jobs")
def get_user_research_jobs(user: Dict[str, Any] = Depends(get_optional_user)):
    """Kullanıcının başlattığı tüm araştırma görevlerini listeler."""
    user_id = user.get("user_id", "user-candidate-rumeysa")
    jobs = list_research_jobs(user_id=user_id)
    return {
        "status": "success",
        "count": len(jobs),
        "jobs": jobs
    }


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str, user: Dict[str, Any] = Depends(get_optional_user)):
    """Araştırma görevinin anlık durumunu, ilerleme yüzdesini ve özet sayılarını döner."""
    job = get_research_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Araştırma görevi bulunamadı.")
    return {
        "status": "success",
        "job": job
    }


@router.get("/jobs/{job_id}/results")
def list_job_results(
    job_id: str,
    filter_reachable: Optional[bool] = Query(False),
    filter_email: Optional[bool] = Query(False),
    filter_whatsapp: Optional[bool] = Query(False),
    filter_unapplied: Optional[bool] = Query(False),
    user: Dict[str, Any] = Depends(get_optional_user)
):
    """Araştırma göreviyle keşfedilen kurumları ve doğrulanmış kanallarını döner."""
    job = get_research_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Araştırma görevi bulunamadı.")

    results = get_job_results(
        job_id=job_id,
        filter_reachable=filter_reachable or False,
        filter_email=filter_email or False,
        filter_whatsapp=filter_whatsapp or False,
        filter_unapplied=filter_unapplied or False,
        candidate_id="candidate-dt-rumeysa-colak"
    )
    return {
        "status": "success",
        "job_id": job_id,
        "total": len(results),
        "items": results
    }


@router.post("/jobs/{job_id}/select")
def select_job_result(
    job_id: str,
    req: SelectJobResultRequest,
    user: Dict[str, Any] = Depends(get_optional_user)
):
    """Başvuru hazırlamak için bir kurumun seçim durumunu günceller."""
    set_job_result_selection(job_id, req.employer_id, req.is_selected)
    return {
        "status": "success",
        "job_id": job_id,
        "employer_id": req.employer_id,
        "is_selected": req.is_selected
    }

