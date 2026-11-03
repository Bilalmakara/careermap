"""CareerMap V2.0 Aday Profili ve CV Yönetimi API Uç Noktaları (Candidate API)."""
from pathlib import Path
import os
import shutil
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Response
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field

from ...database.db import get_connection
from ...candidates.profile_manager import (
    CandidateProfileManager,
    get_rumeysa_colak_default_profile
)
from .auth_api import get_optional_user

router = APIRouter(prefix="/api/v2/candidate", tags=["v2-candidate"])

CV_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent.parent / "static" / "uploads" / "cv"
CV_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class CandidateProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    title: Optional[str] = "Diş Hekimi"
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = "Eskişehir"
    graduation_school: Optional[str] = None
    graduation_year: Optional[int] = 2026
    clinical_case_count: Optional[int] = 350
    specialties: Optional[List[str]] = None
    experience_summary: Optional[str] = None
    work_preferences: Optional[Dict[str, Any]] = None


@router.get("/profile")
def get_candidate_profile(user: Dict[str, Any] = Depends(get_optional_user)):
    """Aktif adayın doğrulanmış profilini, vaka deneyimlerini ve tercihlerini döner."""
    conn = get_connection()
    mgr = CandidateProfileManager(conn)
    
    user_id = user.get("user_id", "user-candidate-rumeysa")
    cand = mgr.get_candidate_by_user_id(user_id)
    if not cand:
        cand = get_rumeysa_colak_default_profile()
        mgr.upsert_candidate(cand)
        cand = mgr.get_candidate(cand["candidate_id"])

    return {"status": "success", "profile": cand}


@router.put("/profile")
def update_candidate_profile(
    data: CandidateProfileUpdate,
    user: Dict[str, Any] = Depends(get_optional_user)
):
    """Aday profilini günceller."""
    conn = get_connection()
    mgr = CandidateProfileManager(conn)
    user_id = user.get("user_id", "user-candidate-rumeysa")
    current = mgr.get_candidate_by_user_id(user_id) or get_rumeysa_colak_default_profile()

    candidate_id = current.get("candidate_id", "candidate-dt-rumeysa-colak")
    updated_dict = dict(current)
    updated_dict["user_id"] = user_id

    if data.full_name is not None:
        updated_dict["full_name"] = data.full_name
    if data.title is not None:
        updated_dict["title"] = data.title
    if data.email is not None:
        updated_dict["email"] = data.email
    if data.phone is not None:
        updated_dict["phone"] = data.phone
    if data.city is not None:
        updated_dict["city"] = data.city
    if data.graduation_school is not None:
        updated_dict["graduation_school"] = data.graduation_school
    if data.graduation_year is not None:
        updated_dict["graduation_year"] = data.graduation_year
    if data.clinical_case_count is not None:
        updated_dict["clinical_case_count"] = data.clinical_case_count
    if data.specialties is not None:
        updated_dict["specialties"] = data.specialties
    if data.experience_summary is not None:
        updated_dict["experience_summary"] = data.experience_summary
    if data.work_preferences is not None:
        updated_dict["work_preferences"] = data.work_preferences

    mgr.upsert_candidate(updated_dict)
    refreshed = mgr.get_candidate(candidate_id)
    return {"status": "success", "message": "Profil başarıyla güncellendi.", "profile": refreshed}


@router.post("/cv/upload")
async def upload_candidate_cv(
    file: Optional[UploadFile] = File(None),
    validity_days: int = Form(30),
    user: Dict[str, Any] = Depends(get_optional_user)
):
    """
    Aday için CV PDF yükler veya varsayılan CV'yi 30 günlük güvenli bağlantıyla kaydeder.
    """
    conn = get_connection()
    mgr = CandidateProfileManager(conn)
    user_id = user.get("user_id", "user-candidate-rumeysa")
    cand = mgr.get_candidate_by_user_id(user_id) or get_rumeysa_colak_default_profile()
    cid = cand.get("candidate_id", "candidate-dt-rumeysa-colak")

    if file and file.filename:
        filename = f"{cid}_{file.filename}"
        dest_path = CV_UPLOAD_DIR / filename
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        rel_path = f"static/uploads/cv/{filename}"
    else:
        filename = "Dt_Rumeysa_Colak_CV.pdf"
        dest_path = CV_UPLOAD_DIR / filename
        if not dest_path.exists():
            dest_path.write_text("Dt. Rümeysa Çolak - Diş Hekimi Özgeçmişi ve Klinik Portfolyosu (350+ vaka)", encoding="utf-8")
        rel_path = f"static/uploads/cv/{filename}"

    doc = mgr.register_cv_document(
        candidate_id=cid,
        file_name=filename,
        file_path=rel_path,
        validity_days=validity_days
    )
    return {"status": "success", "message": "CV belgesi ve 30 günlük güvenli bağlantı oluşturuldu.", "document": doc}


@router.get("/cv")
def list_candidate_cvs(user: Dict[str, Any] = Depends(get_optional_user)):
    """Adayın kayıtlı CV belgelerini ve aktif erişim bağlantılarını döner."""
    conn = get_connection()
    mgr = CandidateProfileManager(conn)
    user_id = user.get("user_id", "user-candidate-rumeysa")
    cand = mgr.get_candidate_by_user_id(user_id) or get_rumeysa_colak_default_profile()
    cid = cand.get("candidate_id", "candidate-dt-rumeysa-colak")

    cursor = conn.cursor()
    cursor.execute("""
    SELECT document_id, candidate_id, document_type, file_name, file_path, secure_token, expires_at, view_count, created_at
    FROM candidate_documents
    WHERE candidate_id = ?
    ORDER BY created_at DESC
    """, (cid,))
    cols = [col[0] for col in cursor.description]
    docs = []
    for row in cursor.fetchall():
        d = dict(zip(cols, row))
        d["secure_url"] = f"/api/v2/cv/view/{d['secure_token']}"
        d["direct_download_url"] = f"/{d['file_path']}"
        docs.append(d)

    return {"status": "success", "candidate_id": cid, "documents": docs}


# Doğrudan /api/v2/cv/view/{token} public görüntüleyici router'ı
public_cv_router = APIRouter(prefix="/api/v2/cv", tags=["v2-public-cv"])

@public_cv_router.get("/view/{token}")
def view_secure_cv(token: str):
    """
    WhatsApp veya e-posta ile kuruma gönderilen 30 günlük güvenli CV önizleme sayfası.
    Görüntüleme sayısını artırır ve adayın vaka deneyimlerini sunar.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT d.document_id, d.candidate_id, d.file_name, d.file_path, d.expires_at, d.view_count,
           c.full_name, c.title, c.email, c.phone, c.city, c.graduation_school, c.graduation_year,
           c.clinical_case_count, c.specialties_json, c.experience_summary
    FROM candidate_documents d
    JOIN candidates c ON d.candidate_id = c.candidate_id
    WHERE d.secure_token = ?
    """, (token,))
    row = cursor.fetchone()
    if not row:
        return HTMLResponse(
            status_code=404,
            content="""<div style="font-family:sans-serif; text-align:center; padding:50px;">
                <h2>Geçersiz veya Süresi Dolmuş Özgeçmiş Bağlantısı</h2>
                <p>Bu bağlantının süresi dolmuş veya güvenli belirteç bulunamamış olabilir.</p>
            </div>"""
        )

    cols = [c[0] for c in cursor.description]
    data = dict(zip(cols, row))

    # Görüntüleme sayacını 1 artır
    cursor.execute("UPDATE candidate_documents SET view_count = view_count + 1 WHERE secure_token = ?", (token,))
    conn.commit()

    import json
    specialties = json.loads(data.get("specialties_json") or "[]")
    spec_badges = "".join([f'<span style="background:#e0f2fe; color:#0369a1; padding:6px 12px; border-radius:20px; font-size:13px; font-weight:600; margin:4px; display:inline-block;">{s}</span>' for s in specialties])

    html_content = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{data['full_name']} — Klinik Özgeçmiş & Vaka Portfolyosu</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f8fafc; color: #1e293b; margin: 0; padding: 20px; }}
        .cv-card {{ max-width: 760px; margin: 30px auto; background: #ffffff; border-radius: 16px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.08); overflow: hidden; border: 1px solid #e2e8f0; }}
        .cv-header {{ background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%); color: white; padding: 36px 32px; }}
        .cv-header h1 {{ margin: 0 0 6px 0; font-size: 28px; font-weight: 700; }}
        .cv-header p {{ margin: 0; font-size: 16px; opacity: 0.9; }}
        .cv-badge {{ display: inline-block; background: rgba(255,255,255,0.2); padding: 4px 12px; border-radius: 12px; font-size: 12px; margin-top: 12px; }}
        .cv-body {{ padding: 32px; }}
        .section-title {{ font-size: 16px; font-weight: 700; color: #0f172a; text-transform: uppercase; letter-spacing: 0.05em; margin: 24px 0 12px 0; border-bottom: 2px solid #f1f5f9; padding-bottom: 6px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
        .stat-box {{ background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 12px; padding: 16px; text-align: center; }}
        .stat-val {{ font-size: 26px; font-weight: 800; color: #15803d; }}
        .stat-label {{ font-size: 13px; color: #166534; font-weight: 500; margin-top: 4px; }}
        .contact-info {{ background: #f8fafc; border-radius: 10px; padding: 16px; margin-top: 24px; border: 1px solid #e2e8f0; font-size: 14px; line-height: 1.8; }}
        .actions {{ margin-top: 28px; text-align: center; }}
        .btn {{ display: inline-block; background: #0284c7; color: white; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: 600; font-size: 15px; }}
        .footer-note {{ text-align: center; font-size: 12px; color: #94a3b8; margin-top: 24px; }}
    </style>
</head>
<body>
    <div class="cv-card">
        <div class="cv-header">
            <h1>{data['full_name']}</h1>
            <p>{data['title']} — {data['graduation_school']} ({data['graduation_year']})</p>
            <span class="cv-badge">🔒 Doğrulanmış Güvenli Aday Bağlantısı • Görüntülenme: {data['view_count']}</span>
        </div>
        <div class="cv-body">
            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-val">{data['clinical_case_count']}+</div>
                    <div class="stat-label">Tamamlanan Klinik Vaka</div>
                </div>
                <div class="stat-box" style="background:#eff6ff; border-color:#bfdbfe;">
                    <div class="stat-val" style="color:#1d4ed8;">{data['graduation_year']}</div>
                    <div class="stat-label" style="color:#1e40af;">SDÜ Mezuniyet</div>
                </div>
                <div class="stat-box" style="background:#faf5ff; border-color:#e9d5ff;">
                    <div class="stat-val" style="color:#7e22ce;">{data['city']}</div>
                    <div class="stat-label" style="color:#6b21a8;">Hedef Hizmet Bölgesi</div>
                </div>
            </div>

            <div class="section-title">Uzmanlık ve Odak Tedavi Alanları</div>
            <div>{spec_badges}</div>

            <div class="section-title">Mesleki Deneyim & Klinik Özet</div>
            <p style="font-size: 14px; line-height: 1.7; color: #334155;">{data['experience_summary']}</p>

            <div class="contact-info">
                <strong>İletişim & Başvuru Kanalları:</strong><br>
                📧 E-posta: <a href="mailto:{data['email']}">{data['email']}</a><br>
                📱 Telefon / WhatsApp: {data['phone']}<br>
                📍 Lokasyon: {data['city']}, Türkiye
            </div>

            <div class="actions">
                <a class="btn" href="/{data['file_path']}" download>📥 Tam CV Dosyasını İndir (PDF)</a>
            </div>
            <div class="footer-note">
                Bu profil CareerMap V2.0 Akıllı Başvuru Koordinasyon Motoru tarafından üretilmiş olup 30 gün boyunca aktiftir.
            </div>
        </div>
    </div>
</body>
</html>"""

    return HTMLResponse(content=html_content)

