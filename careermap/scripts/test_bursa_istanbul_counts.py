import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.db import get_connection, create_research_job, get_research_job, get_job_results
from app.research.research_engine import ResearchJobService

for city in ["Bursa", "İstanbul"]:
    print(f"\n==================== [TEST: {city}] ====================")
    job_id = create_research_job("dentist", "Diş Hekimi", city, districts=[])
    ResearchJobService.execute_job_sync(job_id)
    job = get_research_job(job_id)
    results = get_job_results(job_id)
    
    total = job.get("total_found", 0)
    contacts = job.get("contacts_found", 0)
    verified = job.get("verified_count", 0)
    results_len = len(results)
    
    print(f"Şehir: {city}")
    print(f"Toplam Bulunan Kurum (total_found): {total}")
    print(f"İletişimi Bulunan Kurum (contacts_found): {contacts}")
    print(f"Doğrulanmış / Yayına Hazır Kurum (verified_count): {verified}")
    print(f"Aday Ekranında Listelenen Sonuç Sayısı: {results_len}")
    print(f"İlerleme Mesajı: {job.get('progress_stage')}")
    print(f"Kapsama Özeti: {job.get('coverage_summary')}")
