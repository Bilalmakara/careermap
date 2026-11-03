import sqlite3

c_prod = sqlite3.connect("careermap/careermap.db")
c_backup = sqlite3.connect("careermap/backups/careermap_pre_v1_6_20261102_224141.db")

cur_p = c_prod.cursor()
cur_b = c_backup.cursor()

cur_b.execute("SELECT employer_id FROM employers WHERE city = 'Eskişehir'")
backup_ids = {r[0] for r in cur_b.fetchall()}
print("Backup Eskişehir count:", len(backup_ids))

cur_p.execute("SELECT employer_id FROM employers WHERE city = 'Eskişehir'")
prod_ids = [r[0] for r in cur_p.fetchall()]
to_delete = [eid for eid in prod_ids if eid not in backup_ids]
print("Extra to delete:", len(to_delete))

for eid in to_delete:
    cur_p.execute("DELETE FROM employers WHERE employer_id = ?", (eid,))

c_prod.commit()
cur_p.execute("SELECT count(1) FROM employers WHERE city = 'Eskişehir'")
print("New prod Eskişehir count:", cur_p.fetchone()[0])

c_prod.close()
c_backup.close()

