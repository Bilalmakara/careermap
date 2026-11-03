"""CareerMap V1.4.1 Güncel Excel Üretici Betiği.
careermap.db veritabanındaki 220 temizlenmiş ve denetlenmiş kaydı okur,
7 sekmeli profesyonel test_output.xlsx dosyasını üretir.
"""
import sys
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from app.exports.excel_exporter import generate_careermap_excel

def main():
    db_path = ROOT_DIR / "careermap.db"
    out_path = ROOT_DIR / "test_output.xlsx"
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM employers ORDER BY employer_type, name")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    print(f"Veritabanından {len(rows)} işveren kaydı okundu.")
    
    excel_stream = generate_careermap_excel(
        records=rows,
        profession_name="Diş Hekimi",
        city="Eskişehir"
    )
    
    out_path.write_bytes(excel_stream.getvalue())
    print(f"[OK] test_output.xlsx başarıyla üretildi: {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")

if __name__ == "__main__":
    main()

