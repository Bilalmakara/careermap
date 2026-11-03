with open('careermap/app/database/db.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = 'cursor.execute("CREATE INDEX IF NOT EXISTS idx_ident_link_pri ON employer_identity_links(primary_employer_id)")'
addition = '''
    # 9. V2.5 Kalıcı İletişim Zenginleştirme Kuyruğu (Contact Enrichment Queue)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contact_enrichment_queue (
        queue_id TEXT PRIMARY KEY,
        employer_id TEXT NOT NULL,
        research_job_id TEXT DEFAULT '',
        website_url TEXT DEFAULT '',
        status TEXT DEFAULT 'pending',
        attempts INTEGER DEFAULT 0,
        max_attempts INTEGER DEFAULT 3,
        discovered_email TEXT DEFAULT '',
        discovered_phone TEXT DEFAULT '',
        discovered_contact_form TEXT DEFAULT '',
        evidence_json TEXT DEFAULT '{}',
        error_message TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(employer_id) REFERENCES employers(employer_id) ON DELETE CASCADE
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ceq_status ON contact_enrichment_queue(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ceq_empid ON contact_enrichment_queue(employer_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ceq_jobid ON contact_enrichment_queue(research_job_id)")
'''

if target in content:
    content = content.replace(target, target + '\n' + addition, 1)
    with open('careermap/app/database/db.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Successfully added contact_enrichment_queue to db.py')
else:
    print('Target not found')

