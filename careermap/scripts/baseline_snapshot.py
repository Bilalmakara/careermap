"""Baseline snapshot + DB backup before V1.6 full-coverage scan."""
import sqlite3, json, shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(r"c:/Users/user/Desktop/Other Projects/Job Finder/careermap")
db = ROOT / "careermap.db"
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = ROOT / "backups" / f"careermap_pre_v1_6_{stamp}.db"
backup.parent.mkdir(exist_ok=True)
shutil.copy2(db, backup)

conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
cols = [r[1] for r in conn.execute("PRAGMA table_info(employers)")]
print("employers columns:", cols)
print("employer_contacts columns:", [r[1] for r in conn.execute("PRAGMA table_info(employer_contacts)")])
print("tables:", [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")])
rows = [dict(r) for r in conn.execute("SELECT * FROM employers")]
f = lambda k: sum(1 for r in rows if (r.get(k) or "").strip()) if k in cols else None
snap = {
    "taken_at": datetime.now().isoformat(),
    "backup": str(backup),
    "total": len(rows),
    "website": f("website"), "phone": f("phone"), "email": f("email"),
    "contact_form_url": f("contact_form_url"), "career_url": f("career_url"),
    "any_channel": sum(1 for r in rows if any((r.get(k) or "").strip() for k in ("phone", "email", "contact_form_url") if k in cols)),
    "contacts_by_type": {r[0]: r[1] for r in conn.execute("SELECT contact_type, COUNT(*) FROM employer_contacts GROUP BY contact_type")},
}
print(json.dumps(snap, ensure_ascii=False, indent=2))
(ROOT / "baseline_v1_6.json").write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")

