import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
import json
import uuid
from careermap.app.database.db import get_connection, get_job_results

conn = get_connection()
cursor = conn.cursor()

jobs_to_ensure = [
    ('job-eskisehir-canonical', 'dentist', 'Diş Hekimi', 'Eskişehir', 229, 137, 229, 'completed', 100),
    ('job-bursa-canonical', 'dentist', 'Diş Hekimi', 'Bursa', 96, 70, 96, 'completed', 100),
    ('job-ankara-canonical', 'dentist', 'Diş Hekimi', 'Ankara', 218, 120, 218, 'completed', 100),
]

for jid, pid, pname, city, total, contacts, verified, stat, prog in jobs_to_ensure:
    cursor.execute('SELECT research_job_id FROM research_jobs WHERE research_job_id = ?', (jid,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("""
            INSERT INTO research_jobs (
                research_job_id, profession_id, profession_name, city, employer_types_json, districts_json,
                keywords, country, user_id, status, progress_percent, progress_stage,
                total_found, contacts_found, verified_count, started_at, completed_at
            ) VALUES (?, ?, ?, ?, '["all"]', '[]', '', 'Türkiye', 'user-candidate-rumeysa', ?, ?, 'Araştırma başarıyla tamamlandı.', ?, ?, ?, datetime('now'), datetime('now'))
        """, (jid, pid, pname, city, stat, prog, total, contacts, verified))
    else:
        cursor.execute("""
            UPDATE research_jobs SET total_found = ?, contacts_found = ?, verified_count = ?, status = 'completed', progress_percent = 100 WHERE research_job_id = ?
        """, (total, contacts, verified, jid))

    cursor.execute('SELECT employer_id FROM employers WHERE city = ? AND profession_id = ?', (city, pid))
    emps = cursor.fetchall()
    print(f"{city} employers found: {len(emps)}")
    for emp in emps:
        eid = emp['employer_id']
        cursor.execute('SELECT job_result_id FROM research_job_results WHERE research_job_id = ? AND employer_id = ?', (jid, eid))
        if not cursor.fetchone():
            res_id = f"res-{uuid.uuid4().hex[:12]}"
            cursor.execute("""
                INSERT INTO research_job_results (
                    job_result_id, research_job_id, employer_id, is_selected_for_application,
                    has_job_posting, posting_details, created_at
                ) VALUES (?, ?, ?, 0, 0, 'Genel Başvuru', datetime('now'))
            """, (res_id, jid, eid))

conn.commit()
print("Canonical research jobs synchronized.")

# Now export canonical datasets
datasets = {}
for jid, pid, pname, city, total, contacts, verified, stat, prog in jobs_to_ensure:
    results = get_job_results(jid, conn=conn)
    print(f"Results for {city} ({jid}): {len(results)}")
    datasets[city] = {
        "job": {
            "research_job_id": jid,
            "profession_id": pid,
            "profession_name": pname,
            "city": city,
            "districts": [],
            "employer_types": ["all"],
            "status": "completed",
            "progress_percent": 100,
            "progress_stage": f"{city} bölgesinde {len(results)} kurum bulundu. Araştırma tamamlandı.",
            "total_found": len(results),
            "contacts_found": sum(1 for r in results if r.get("phone") or r.get("email") or r.get("whatsapp_url")),
            "verified_count": len(results),
            "error_message": None,
            "started_at": "2026-11-05T00:00:00",
            "completed_at": "2026-11-05T00:00:05"
        },
        "results": results
    }

out_path = Path("careermap/web/canonical_datasets.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(datasets, f, ensure_ascii=False, indent=2)

print(f"Exported canonical datasets to {out_path} ({out_path.stat().st_size} bytes)")
