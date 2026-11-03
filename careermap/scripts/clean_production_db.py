import sqlite3
from pathlib import Path

db_path = Path("careermap/careermap.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 1. Clear any fake or test applications
cur.execute("DELETE FROM applications")
cur.execute("DELETE FROM application_events")

# 2. Reset research_jobs to clean canonical initial job
cur.execute("DELETE FROM research_jobs")
cur.execute("""
INSERT INTO research_jobs (
    research_job_id, user_id, profession_id, profession_name, employer_types_json,
    country, city, districts_json, keywords, status, total_found, contacts_found,
    verified_count, progress_percent, progress_stage, created_at, started_at, completed_at, coverage_summary
) VALUES (
    'job-eskisehir-canonical', 'user-candidate-rumeysa', 'dentist', 'Diş Hekimi', '["all"]',
    'Türkiye', 'Eskişehir', '[]', '', 'completed', 220, 220, 220, 100, 'Tamamlandı',
    datetime('now'), datetime('now'), datetime('now'),
    '{"total_raw_candidates": 220, "unique_after_dedup": 220, "filtered_results": 220, "sources": ["official_chambers"]}'
)
""")

conn.commit()
print("Applications count:", cur.execute("SELECT count(1) FROM applications").fetchone()[0])
print("Research jobs count:", cur.execute("SELECT count(1) FROM research_jobs").fetchone()[0])
print("Employers count:", cur.execute("SELECT count(1) FROM employers").fetchone()[0])
conn.close()

