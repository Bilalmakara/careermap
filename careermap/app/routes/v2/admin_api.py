"""CareerMap V2.0 Yönetici Paneli API Uç Noktaları (Admin API)."""
from pathlib import Path
import io
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from fastapi.responses import StreamingResponse

from ...database.db import get_connection
from ...services.excel_service import import_employers_from_excel, export_employers_to_excel_stream
from .auth_api import get_optional_user

router = APIRouter(prefix="/api/v2/admin", tags=["v2-admin"])


@router.get("/stats")
def get_system_stats(user: Dict[str, Any] = Depends(get_optional_user)):
    """Sistem geneli işveren, kontak doluluk ve başvuru istatistiklerini döner."""
    conn = get_connection()
    cursor = conn.cursor()

    # İşveren ve kontak sayıları
    cursor.execute("""
    SELECT 
        COUNT(*) as total_employers,
        SUM(CASE WHEN phone != '' AND phone IS NOT NULL THEN 1 ELSE 0 END) as phone_count,
        SUM(CASE WHEN email != '' AND email IS NOT NULL THEN 1 ELSE 0 END) as email_count,
        SUM(CASE WHEN whatsapp_url != '' AND whatsapp_url IS NOT NULL THEN 1 ELSE 0 END) as whatsapp_count,
        SUM(CASE WHEN website != '' AND website IS NOT NULL THEN 1 ELSE 0 END) as website_count,
        SUM(CASE WHEN contact_form_url != '' AND contact_form_url IS NOT NULL THEN 1 ELSE 0 END) as form_count,
        SUM(CASE WHEN 
            (phone != '' AND phone IS NOT NULL) OR 
            (email != '' AND email IS NOT NULL) OR 
            (whatsapp_url != '' AND whatsapp_url IS NOT NULL) OR 
            (contact_form_url != '' AND contact_form_url IS NOT NULL) 
        THEN 1 ELSE 0 END) as reachable_count
    FROM employers
    """)
    emp_stats = cursor.fetchone()
    total_emp = emp_stats[0] if emp_stats else 0
    reachable = emp_stats[6] if emp_stats else 0

    # İlçe kırılımı
    cursor.execute("""
    SELECT district, COUNT(*) as cnt,
           SUM(CASE WHEN (phone != '' OR email != '' OR whatsapp_url != '') THEN 1 ELSE 0 END) as reachable
    FROM employers
    GROUP BY district
    ORDER BY cnt DESC
    """)
    districts = [{"district": r[0], "count": r[1], "reachable": r[2]} for r in cursor.fetchall()]

    # Başvuru CRM durumları
    cursor.execute("""
    SELECT status, COUNT(*) as cnt
    FROM applications
    GROUP BY status
    """)
    app_statuses = {r[0]: r[1] for r in cursor.fetchall()}

    # Kullanıcı sayıları
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]

    return {
        "status": "success",
        "employers": {
            "total": total_emp,
            "reachable": reachable,
            "reachability_rate_percent": round((reachable / total_emp * 100), 1) if total_emp > 0 else 0,
            "with_phone": emp_stats[1] if emp_stats else 0,
            "with_email": emp_stats[2] if emp_stats else 0,
            "with_whatsapp": emp_stats[3] if emp_stats else 0,
            "with_website": emp_stats[4] if emp_stats else 0,
            "with_contact_form": emp_stats[5] if emp_stats else 0
        },
        "districts": districts,
        "applications": app_statuses,
        "users_count": user_count
    }


@router.post("/import-excel")
async def import_excel_endpoint(
    file: Optional[UploadFile] = File(None),
    use_default: bool = Query(False),
    user: Dict[str, Any] = Depends(get_optional_user)
):
    """
    Excel dosyasından 220 işveren ve doğrulanmış kontakları veritabanına aktarır.
    """
    conn = get_connection()

    if use_default or not file:
        default_excel = Path(__file__).resolve().parent.parent.parent.parent / "test_output.xlsx"
        if not default_excel.exists():
            # Workspace root'ta ara
            default_excel = Path(__file__).resolve().parent.parent.parent.parent.parent / "test_output.xlsx"
        if not default_excel.exists():
            raise HTTPException(status_code=400, detail="Varsayılan test_output.xlsx dosyası bulunamadı. Lütfen bir dosya yükleyin.")
        result = import_employers_from_excel(default_excel, conn=conn)
    else:
        content = await file.read()
        bytes_io = io.BytesIO(content)
        result = import_employers_from_excel(bytes_io, conn=conn)

    return result


@router.get("/export-excel")
def export_excel_endpoint(user: Dict[str, Any] = Depends(get_optional_user)):
    """Veritabanındaki güncel işverenleri 7 sekmeli profesyonel Excel olarak indirir."""
    conn = get_connection()
    excel_stream = export_employers_to_excel_stream(conn=conn)
    excel_stream.seek(0)

    filename = "CareerMap_V2_Eskisehir_Dis_Hekimleri.xlsx"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }
    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )

