"""CareerMap V2.0 İşveren Keşif ve Detay API Uç Noktaları (Employers API)."""
from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional, List, Dict, Any
from ...database.db import get_connection
from ...matching.employer_matcher import match_candidate_to_employer
from ...candidates.profile_manager import CandidateProfileManager, get_rumeysa_colak_default_profile
from .auth_api import get_optional_user

router = APIRouter(prefix="/api/v2/employers", tags=["v2-employers"])

@router.get("")
def list_employers(
    city: str = Query("Eskişehir"),
    district: Optional[str] = Query(None),
    employer_type: Optional[str] = Query("all"),
    has_email: Optional[bool] = Query(None),
    has_whatsapp: Optional[bool] = Query(None),
    has_website: Optional[bool] = Query(None),
    has_form: Optional[bool] = Query(None),
    reachable_only: Optional[bool] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=220),
    user: Dict[str, Any] = Depends(get_optional_user)
):
    """İşverenleri çok kriterli filtreler, sayfalama ve eşleşme puanlarıyla listeler."""
    conn = get_connection()
    conn.row_factory = None
    cursor = conn.cursor()

    candidate_profile = get_rumeysa_colak_default_profile()

    conditions = ["city = ?"]
    params = [city]

    if district and district.lower() != "all":
        conditions.append("LOWER(district) = LOWER(?)")
        params.append(district)

    if employer_type and employer_type.lower() != "all":
        if "poliklinik" in employer_type.lower():
            conditions.append("employer_type LIKE '%poliklinik%'")
        elif "muayenehane" in employer_type.lower():
            conditions.append("(employer_type LIKE '%muayenehane%' OR name LIKE 'Dt.%')")

    if has_email is True:
        conditions.append("email != '' AND email IS NOT NULL")
    if has_whatsapp is True:
        conditions.append("whatsapp_url != '' AND whatsapp_url IS NOT NULL")
    if has_website is True:
        conditions.append("website != '' AND website IS NOT NULL")
    if has_form is True:
        conditions.append("contact_form_url != '' AND contact_form_url IS NOT NULL")

    if reachable_only is True:
        conditions.append("""(
            (phone != '' AND phone IS NOT NULL) OR
            (email != '' AND email IS NOT NULL) OR
            (whatsapp_url != '' AND whatsapp_url IS NOT NULL) OR
            (contact_form_url != '' AND contact_form_url IS NOT NULL)
        )""")

    if q and q.strip():
        search_term = f"%{q.strip()}%"
        conditions.append("(name LIKE ? OR address LIKE ? OR district LIKE ?)")
        params.extend([search_term, search_term, search_term])

    where_clause = " AND ".join(conditions)

    # Toplam sayı
    cursor.execute(f"SELECT COUNT(*) FROM employers WHERE {where_clause}", tuple(params))
    total_count = cursor.fetchone()[0]

    # Sayfalama
    offset = (page - 1) * page_size
    query = f"""
    SELECT 
        employer_id, profession_id, city, district, name, employer_type,
        address, phone, phone_type, phone_verification_status,
        email, email_type, email_verification_status,
        website, website_verification_status,
        career_url, contact_form_url, whatsapp_url,
        confidence_score, confidence_level, business_status
    FROM employers
    WHERE {where_clause}
    ORDER BY 
        (CASE WHEN email != '' AND whatsapp_url != '' THEN 3 WHEN email != '' THEN 2 WHEN phone != '' THEN 1 ELSE 0 END) DESC,
        employer_type DESC, name ASC
    LIMIT ? OFFSET ?
    """
    cursor.execute(query, tuple(params + [page_size, offset]))
    
    col_names = [col[0] for col in cursor.description]
    rows = [dict(zip(col_names, row)) for row in cursor.fetchall()]

    # Aday başvurusu var mı kontrolü
    cursor.execute("SELECT employer_id, status FROM applications WHERE candidate_id = ?", ("candidate-dt-rumeysa-colak",))
    app_map = {r[0]: r[1] for r in cursor.fetchall()}

    items = []
    for r in rows:
        channels = []
        if r.get("email"): channels.append("email")
        if r.get("whatsapp_url"): channels.append("whatsapp")
        if r.get("phone"): channels.append("phone")
        if r.get("website"): channels.append("website")
        if r.get("contact_form_url"): channels.append("contact_form")

        is_reachable = bool(r.get("email") or r.get("whatsapp_url") or r.get("phone") or r.get("contact_form_url"))
        match_info = match_candidate_to_employer(candidate_profile, r)

        r["available_channels"] = channels
        r["is_reachable"] = is_reachable
        r["match_score"] = match_info["match_score"]
        r["application_status"] = app_map.get(r["employer_id"])
        items.append(r)

    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

    return {
        "status": "success",
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "items": items
    }

@router.get("/{employer_id}")
def get_employer_detail(
    employer_id: str,
    user: Dict[str, Any] = Depends(get_optional_user)
):
    """Tek bir işverenin tam profilini, kontak kanıtlarını ve başvuru geçmişini döner."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM employers WHERE employer_id = ?", (employer_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="İşveren kaydı bulunamadı.")

    col_names = [c[0] for c in cursor.description]
    emp = dict(zip(col_names, row))

    # Çoklu kontakları çek
    cursor.execute("""
    SELECT contact_type, contact_value, contact_category, source_url, discovery_method, evidence_text, verification_status
    FROM employer_contacts
    WHERE employer_id = ?
    ORDER BY contact_type, verification_status DESC
    """, (employer_id,))
    contact_cols = [c[0] for c in cursor.description]
    contacts = [dict(zip(contact_cols, c_row)) for c_row in cursor.fetchall()]
    emp["contacts"] = contacts

    # Aday eşleşme bilgisi
    cand_profile = get_rumeysa_colak_default_profile()
    emp["matching"] = match_candidate_to_employer(cand_profile, emp)

    # Varsa mevcut başvuru kaydı
    cursor.execute("SELECT application_id, status, primary_channel, orchestration_step, created_at, updated_at FROM applications WHERE candidate_id = ? AND employer_id = ?", ("candidate-dt-rumeysa-colak", employer_id))
    app_row = cursor.fetchone()
    if app_row:
        emp["existing_application"] = {
            "application_id": app_row[0],
            "status": app_row[1],
            "primary_channel": app_row[2],
            "orchestration_step": app_row[3],
            "created_at": app_row[4],
            "updated_at": app_row[5]
        }
    else:
        emp["existing_application"] = None

    return {"status": "success", "employer": emp}

@router.get("/{employer_id}/match")
def get_employer_match(
    employer_id: str,
    user: Dict[str, Any] = Depends(get_optional_user)
):
    """İşveren ile aday arasındaki yetkinlik ve kanal uyum analizini döner."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employers WHERE employer_id = ?", (employer_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="İşveren bulunamadı.")
    col_names = [c[0] for c in cursor.description]
    emp = dict(zip(col_names, row))

    cand = get_rumeysa_colak_default_profile()
    match_result = match_candidate_to_employer(cand, emp)
    return {
        "status": "success",
        "employer_name": emp.get("name"),
        "match_score": match_result["match_score"],
        "match_reasons": match_result["match_reasons"],
        "primary_channel": match_result["primary_channel"],
        "planned_channels": match_result["planned_channels"],
        "is_recommended": match_result["is_recommended"]
    }

