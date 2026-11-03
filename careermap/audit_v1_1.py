import openpyxl
from collections import Counter

wb = openpyxl.load_workbook('careermap/test_output.xlsx')
print('=== CareerMap V1.1 Excel Rapor Denetimi ===')
print('Sayfalar:', wb.sheetnames)

ws_all = wb['Tüm İşverenler']
headers = [ws_all.cell(1, c).value for c in range(1, ws_all.max_column + 1)]

rows = []
for r in range(2, ws_all.max_row + 1):
    row_data = {headers[c-1]: ws_all.cell(r, c).value for c in range(1, ws_all.max_column + 1)}
    rows.append(row_data)

total = len(rows)
with_phone = sum(1 for r in rows if (r.get('Telefon') or '').strip())
with_email = sum(1 for r in rows if (r.get('Kurumsal E-posta') or '').strip())
with_web = sum(1 for r in rows if (r.get('Web Sitesi') or '').strip())
verified_count = sum(1 for r in rows if r.get('Doğrulama Durumu') == 'verified')
tdb_count = sum(1 for r in rows if r.get('Doğrulama Yöntemi') == 'tdb_registry')
manual_count = sum(1 for r in rows if r.get('Doğrulama Durumu') == 'manual_review')
conflict_count = sum(1 for r in rows if r.get('Doğrulama Durumu') == 'conflict')
with_phone_src = sum(1 for r in rows if (r.get('Telefon Kaynak URL') or '').strip())

print(f"Toplam Kayıt: {total}")
print(f"Telefonu Olan: {with_phone} (%{with_phone/total*100:.1f})")
print(f"Telefon Kaynak URL Olan: {with_phone_src} (%{with_phone_src/total*100:.1f})")
print(f"E-postası Olan: {with_email} (%{with_email/total*100:.1f})")
print(f"Web Sitesi Olan: {with_web} (%{with_web/total*100:.1f})")
print(f"Resmî Sicil ile Doğrulanan (verified): {verified_count} (%{verified_count/total*100:.1f})")
print(f"TDB'den Telefonu Gelen Hekim: {tdb_count}")
print(f"Manuel İnceleme Gereken (manual_review): {manual_count}")
print(f"Çelişkili Telefon (conflict): {conflict_count}")

print("\n--- Örnek TDB Resmî Sicilinden Doğrulanan Hekimler ---")
count = 0
for r in rows:
    if r.get('Doğrulama Yöntemi') == 'tdb_registry':
        print(f"* {r.get('Klinik / İşveren Adı')} ({r.get('İlçe')}): Tel: {r.get('Telefon')} | Tel Kaynak URL: {r.get('Telefon Kaynak URL')} | Teyit Tarihi: {r.get('İletişim Teyit Tarihi')}")
        count += 1
        if count >= 6:
            break

# Abdülkadir Özyıldırım kontrolü
print("\n--- Dt. Abdülkadir ÖZYILDIRIM Özel Kontrolü ---")
for r in rows:
    if 'özyıldırım' in (r.get('Klinik / İşveren Adı') or '').lower():
        print(f"Adı: {r.get('Klinik / İşveren Adı')}")
        print(f"Tür: {r.get('Kurum Türü')}")
        print(f"Web: {r.get('Web Sitesi')}")
        print(f"Tel: {r.get('Telefon')}")
        print(f"Tel Kaynak: {r.get('Telefon Kaynak URL')}")
        print(f"Doğrulama Yöntemi: {r.get('Doğrulama Yöntemi')}")
        print(f"Doğrulama Durumu: {r.get('Doğrulama Durumu')}")

