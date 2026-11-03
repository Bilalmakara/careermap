"""Excel ve rapor dışa aktarma uç noktaları."""
from fastapi import APIRouter, Query, Response
from typing import Optional
from urllib.parse import quote
from ..professions.registry import ProfessionRegistry
from ..database.db import query_employers
from ..exports.excel_exporter import generate_careermap_excel

router = APIRouter(prefix="/export", tags=["export"])

@router.get("/excel")
def export_excel(
    profession: str = Query("dentist"),
    city: str = Query("Eskişehir"),
    districts: Optional[str] = Query(None),
    employer_type: Optional[str] = Query("all"),
    verification_status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    only_with_email: bool = Query(False)
):
    """Filtrelenmiş veya tüm sonuçları 5 sekmeli profesyonel Excel olarak indirir."""
    district_list = [d.strip() for d in districts.split(",")] if districts else None
    
    records = query_employers(
        profession_id=profession,
        city=city,
        districts=district_list,
        employer_type=employer_type,
        verification_status=verification_status,
        search_text=q,
        only_with_email=only_with_email
    )

    prof_obj = ProfessionRegistry.get(profession)
    prof_name = prof_obj.name if prof_obj else profession

    excel_stream = generate_careermap_excel(
        records=records,
        profession_name=prof_name,
        city=city
    )

    # Dosya adını güvenli oluştur
    filename = f"CareerMap_{city}_{prof_name.replace(' ', '_')}.xlsx"
    encoded_filename = quote(filename)

    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    }

    return Response(
        content=excel_stream.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )

