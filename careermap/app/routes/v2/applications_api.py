"""CareerMap V2.0 Başvuru Hazırlama, Koordinasyon ve CRM API Uç Noktaları (Applications API)."""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field

from ...database.db import get_connection
from ...tracking.application_crm import ApplicationCRM
from ...candidates.profile_manager import CandidateProfileManager, get_rumeysa_colak_default_profile
from ...matching.employer_matcher import match_candidate_to_employer
from ...application_engine.application_planner import plan_application_workflow
from ...application_engine.message_generator import generate_application_messages
from .auth_api import get_optional_user

router = APIRouter(prefix="/api/v2/applications", tags=["v2-applications"])


class ChannelActionRequest(BaseModel):
    channel: str = Field(..., description="Kullanılan kanal: email, whatsapp, phone, form")
    contact_value: Optional[str] = Field("", description="Gönderilen e-posta, aranan telefon veya WhatsApp numarası")
    action_status: Optional[str] = Field("confirmed_by_user", description="Kanal aksiyon durumu")
    notes: Optional[str] = Field("", description="Adayın başvuru notu veya görüşme detayı")


class StatusUpdateRequest(BaseModel):
    new_status: str = Field(..., description="Yeni CRM durumu: draft, approved, email_sent, whatsapp_opened, whatsapp_confirmed_sent, awaiting_reply, replied, interview, rejected, hired, closed")
    notes: Optional[str] = Field("", description="Durum değişikliği notu")


class BatchPrepareRequest(BaseModel):
    employer_ids: List[str] = Field(..., description="Başvuru paketi hazırlanacak işveren kimlikleri listesi")
    position_title: Optional[str] = Field("Diş Hekimi", description="Hedef pozisyon")


@router.get("/dashboard")
def get_crm_dashboard(user: Dict[str, Any] = Depends(get_optional_user)):
    """Aday kontrol paneli için özet CRM metriklerini ve başvuru kartlarını döner."""
    conn = get_connection()
    crm = ApplicationCRM(conn)
    mgr = CandidateProfileManager(conn)
    cand = mgr.get_candidate_by_user_id(user.get("user_id", "")) or get_rumeysa_colak_default_profile()
    cid = cand.get("candidate_id", "candidate-dt-rumeysa-colak")

    dashboard_data = crm.get_candidate_crm_dashboard(cid)
    return {"status": "success", "dashboard": dashboard_data}


@router.get("")
def list_applications(
    status_filter: Optional[str] = Query(None, alias="status"),
    user: Dict[str, Any] = Depends(get_optional_user)
):
    """Adayın başvuru kayıtlarını filtreli olarak listeler."""
    conn = get_connection()
    crm = ApplicationCRM(conn)
    mgr = CandidateProfileManager(conn)
    cand = mgr.get_candidate_by_user_id(user.get("user_id", "")) or get_rumeysa_colak_default_profile()
    cid = cand.get("candidate_id", "candidate-dt-rumeysa-colak")

    dashboard = crm.get_candidate_crm_dashboard(cid)
    apps = dashboard["applications"]

    if status_filter and status_filter.lower() != "all":
        apps = [a for a in apps if a.get("status", "").lower() == status_filter.lower()]

    return {"status": "success", "count": len(apps), "items": apps}


@router.post("/prepare/{employer_id}")
def prepare_employer_application(
    employer_id: str,
    position_title: Optional[str] = Query("Diş Hekimi"),
    user: Dict[str, Any] = Depends(get_optional_user)
):
    """
    Seçilen işveren için adayın gerçek yetkinliklerine dayalı, sıfır halüsinasyonlu
    başvuru dosyası (E-posta, WhatsApp Model B/C, Telefon Notu, Form Metni) üretir ve CRM'e kaydeder.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM employers WHERE employer_id = ?", (employer_id,))
    emp_row = cursor.fetchone()
    if not emp_row:
        raise HTTPException(status_code=404, detail="İşveren bulunamadı.")
    col_names = [c[0] for c in cursor.description]
    employer = dict(zip(col_names, emp_row))

    # V2.2 P0 Karantina Denetimi: Doğrulanmamış veya karantinaya alınmış kurumlara başvuru kesinlikle engellenir
    from ...discovery.quarantine_manager import is_employer_allowed_for_application
    allowed, reason = is_employer_allowed_for_application(employer)
    if not allowed:
        raise HTTPException(status_code=400, detail=reason)

    mgr = CandidateProfileManager(conn)
    candidate = mgr.get_candidate_by_user_id(user.get("user_id", "")) or get_rumeysa_colak_default_profile()
    cid = candidate.get("candidate_id", "candidate-dt-rumeysa-colak")

    # 1. Eşleştirme analizi
    match_result = match_candidate_to_employer(candidate, employer)

    # 2. Koordinasyon iş akışı planı
    workflow_plan = plan_application_workflow(employer, candidate)

    # 3. Kişiselleştirilmiş mesaj taslakları (sıfır halüsinasyon garantili)
    messages_package = generate_application_messages(employer, candidate)

    # 4. CRM tekil başvuru kaydını oluştur
    crm = ApplicationCRM(conn)
    app_id = crm.create_application_record(
        candidate_id=cid,
        employer_id=employer_id,
        position_title=position_title or "Diş Hekimi",
        match_data=match_result,
        workflow_plan=workflow_plan,
        messages_package=messages_package,
        status="draft"
    )

    return {
        "status": "success",
        "message": f"'{employer.get('name')}' kurumu için başvuru dosyası başarıyla hazırlandı.",
        "application_id": app_id,
        "employer": {
            "employer_id": employer.get("employer_id"),
            "name": employer.get("name"),
            "employer_type": employer.get("employer_type"),
            "district": employer.get("district"),
            "city": employer.get("city")
        },
        "match": match_result,
        "workflow": workflow_plan,
        "messages": messages_package
    }


@router.post("/batch-prepare")
def batch_prepare_applications(
    req: BatchPrepareRequest,
    user: Dict[str, Any] = Depends(get_optional_user)
):
    """
    Seçilen birden fazla işveren için toplu olarak kişiselleştirilmiş başvuru paketlerini hazırlar.
    """
    conn = get_connection()
    cursor = conn.cursor()
    crm = ApplicationCRM(conn)
    mgr = CandidateProfileManager(conn)
    candidate = mgr.get_candidate_by_user_id(user.get("user_id", "")) or get_rumeysa_colak_default_profile()
    cid = candidate.get("candidate_id", "candidate-dt-rumeysa-colak")

    prepared_packages = []

    for emp_id in req.employer_ids:
        cursor.execute("SELECT * FROM employers WHERE employer_id = ?", (emp_id,))
        row = cursor.fetchone()
        if not row:
            continue
        col_names = [c[0] for c in cursor.description]
        employer = dict(zip(col_names, row))

        # V2.2 P0 Karantina Denetimi: Karantinadaki kurumlar atlanır
        from ...discovery.quarantine_manager import is_employer_allowed_for_application
        allowed, reason = is_employer_allowed_for_application(employer)
        if not allowed:
            continue

        match_result = match_candidate_to_employer(candidate, employer)
        workflow_plan = plan_application_workflow(employer, candidate)
        messages_package = generate_application_messages(employer, candidate)

        app_id = crm.create_application_record(
            candidate_id=cid,
            employer_id=emp_id,
            position_title=req.position_title or "Diş Hekimi",
            match_data=match_result,
            workflow_plan=workflow_plan,
            messages_package=messages_package,
            status="draft"
        )

        prepared_packages.append({
            "application_id": app_id,
            "employer_id": emp_id,
            "employer_name": employer.get("name"),
            "district": employer.get("district"),
            "city": employer.get("city"),
            "match_score": match_result.get("match_score", 70),
            "primary_channel": workflow_plan.get("primary_channel", "email"),
            "messages": messages_package
        })

    return {
        "status": "success",
        "message": f"{len(prepared_packages)} kurum için başvuru dosyaları hazırlandı.",
        "prepared_count": len(prepared_packages),
        "packages": prepared_packages
    }


@router.post("/{application_id}/approve")
def approve_application(
    application_id: str,
    user: Dict[str, Any] = Depends(get_optional_user)
):
    """Adayın başvuru taslaklarını onaylaması ve gönderime hazır hale getirmesi."""
    conn = get_connection()
    crm = ApplicationCRM(conn)
    ok = crm.approve_application(application_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Başvuru onaylanamadı.")
    return {"status": "success", "message": "Başvuru ve iletişim taslakları onaylandı.", "application_id": application_id}


@router.post("/{application_id}/action")
def record_application_channel_action(
    application_id: str,
    req: ChannelActionRequest,
    user: Dict[str, Any] = Depends(get_optional_user)
):
    """
    Kullanıcının WhatsApp veya E-posta kanalıyla kuruma gönderim yaptığını kaydeder.
    Başvuru durumunu 'waiting_reply' (yanıt bekleniyor) durumuna taşır.
    """
    conn = get_connection()
    crm = ApplicationCRM(conn)
    attempt_id = crm.record_channel_action(
        application_id=application_id,
        channel=req.channel,
        contact_value=req.contact_value or "",
        action_status=req.action_status or "confirmed_by_user",
        notes=req.notes or ""
    )
    return {
        "status": "success",
        "message": f"{req.channel.upper()} gönderimi başarıyla kaydedildi.",
        "attempt_id": attempt_id,
        "application_status": "waiting_reply"
    }


@router.patch("/{application_id}/status")
def update_application_status(
    application_id: str,
    req: StatusUpdateRequest,
    user: Dict[str, Any] = Depends(get_optional_user)
):
    """Başvuru CRM durumunu (interview, rejected, waiting_reply vb.) günceller."""
    conn = get_connection()
    crm = ApplicationCRM(conn)
    ok = crm.update_application_status(
        application_id=application_id,
        new_status=req.new_status,
        notes=req.notes or ""
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Durum güncellenemedi.")
    return {
        "status": "success",
        "message": f"Başvuru durumu '{req.new_status}' olarak güncellendi.",
        "application_id": application_id,
        "new_status": req.new_status
    }


@router.post("/reset-clean")
def reset_clean_applications(user: Dict[str, Any] = Depends(get_optional_user)):
    """Canlı sürüme geçiş için tüm demo ve sahte başvuruları temizler."""
    conn = get_connection()
    from ...discovery.multi_city_directory import clear_demo_and_test_applications
    deleted_count = clear_demo_and_test_applications(conn)
    conn.close()
    return {
        "status": "success",
        "message": f"Tüm demo başvurular temizlendi ({deleted_count} kayıt). Sistem canlı kullanıma hazır.",
        "deleted_count": deleted_count
    }
