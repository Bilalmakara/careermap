import openpyxl
from collections import Counter

wb = openpyxl.load_workbook('careermap/test_output.xlsx')
ws = wb['Tüm İşverenler']

header = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]

rows = []
for r in range(2, ws.max_row + 1):
    row_data = {header[c-1]: ws.cell(r, c).value for c in range(1, ws.max_column + 1)}
    rows.append(row_data)

total = len(rows)
types = Counter(r.get('Kurum Türü') for r in rows)
districts = Counter(r.get('İlçe') for r in rows)
with_phone = sum(1 for r in rows if r.get('Telefon'))
with_email = sum(1 for r in rows if r.get('Kurumsal E-posta'))
with_web = sum(1 for r in rows if r.get('Web Sitesi'))
with_source = sum(1 for r in rows if r.get('Kaynak URL(ler)'))
with_date = sum(1 for r in rows if r.get('Son Kontrol'))

print(f"Toplam Kayıt: {total}")
print(f"Kurum Türleri: {dict(types)}")
print(f"İlçeler: {dict(districts)}")
print(f"Telefon Olan: {with_phone} (%{with_phone/total*100:.1f})")
print(f"E-posta Olan: {with_email} (%{with_email/total*100:.1f})")
print(f"Web Sitesi Olan: {with_web} (%{with_web/total*100:.1f})")
print(f"Kaynak URL Olan: {with_source} (%{with_source/total*100:.1f})")
print(f"Son Kontrol Tarihi Olan: {with_date} (%{with_date/total*100:.1f})")

print("\n--- E-postası Bulunan Kayıtlar ---")
for r in rows:
    if r.get('Kurumsal E-posta'):
        name = r.get('Klinik / İşveren Adı')
        district = r.get('İlçe')
        email = r.get('Kurumsal E-posta')
        web = r.get('Web Sitesi')
        source_url = r.get('E-posta Kaynak URL')
        print(f"* {name} ({district}): {email} | Web: {web} | Kaynak URL: {source_url}")

# Birebir aynı isim kontrolü
names = [r.get('Klinik / İşveren Adı') for r in rows]
name_counts = Counter(names)
dups = {k: v for k, v in name_counts.items() if v > 1}
print(f"\nBirebir Aynı İsim Tekrarı: {len(dups)}")
for k, v in dups.items():
    print(f"  - {k}: {v} kez")

# Şubeler (aynı ada sahip fakat farklı şube eki olanlar)
branches = [n for n in names if any(x in n.lower() for x in ['şube', 'sube', 'doktorlar', 'sakarya', 'çamlıca', 'emek'])]
print(f"\nFarklı Şube Olan Kurumlar: {len(branches)}")
for b in branches:
    print(f"  - {b}")

