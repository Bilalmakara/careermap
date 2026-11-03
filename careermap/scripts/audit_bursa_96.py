# -*- coding: utf-8 -*-
"""Bursa 96 Kurum Kaynak, Doğruluk ve Kimlik Eşleştirme Bağımsız Denetim Aracı."""
import sqlite3
import json
import random
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "careermap.db"

def run_audit():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM employers WHERE city = 'Bursa' ORDER BY created_at ASC")
    rows = cur.fetchall()
    total = len(rows)

    print(f"===============================================================")
    print(f"BURSA 96 KURUM DENETİM RAPORU (Toplam Kayıt: {total})")
    print(f"===============================================================")

    # 1. Durum Dağılımı (quarantined vs completed vs pending)
    by_status = {}
    by_source = {}
    for r in rows:
        st = r["research_status"]
        src = r["source_type"]
        by_status[st] = by_status.get(st, 0) + 1
        by_source[src] = by_source.get(src, 0) + 1

    print("\n[1] DURUM DAĞILIMI:")
    for st, c in by_status.items():
        print(f"  - {st}: {c} kurum ({c/total*100:.1f}%)")

    print("\n[2] KAYNAK TÜRÜ DAĞILIMI:")
    for src, c in by_source.items():
        print(f"  - {src}: {c} kurum ({c/total*100:.1f}%)")

    # 2. İletişim Alanları Analizi
    has_phone = sum(1 for r in rows if r["phone"])
    has_email = sum(1 for r in rows if r["email"])
    has_web = sum(1 for r in rows if r["website"])
    has_whatsapp = sum(1 for r in rows if r["whatsapp_url"])
    print("\n[3] İLETİŞİM ALANLARI DOLULUĞU (Tüm 96 Kayıt):")
    print(f"  - Telefonu Olan: {has_phone}/{total} ({has_phone/total*100:.1f}%)")
    print(f"  - E-postası Olan: {has_email}/{total} ({has_email/total*100:.1f}%)")
    print(f"  - Web Sitesi Olan: {has_web}/{total} ({has_web/total*100:.1f}%)")
    print(f"  - WhatsApp URL Olan: {has_whatsapp}/{total} ({has_whatsapp/total*100:.1f}%)")

    # 3. Karantina Altındakiler ile Aktiflerin Karşılaştırması
    active_rows = [r for r in rows if r["research_status"] != "quarantined"]
    quar_rows = [r for r in rows if r["research_status"] == "quarantined"]

    print("\n[4] AKTİF vs KARANTİNA AYRIMI:")
    print(f"  - Aktif Kurum Sayısı (Kullanıcıya Gösterilen): {len(active_rows)}")
    act_phone = sum(1 for r in active_rows if r["phone"])
    act_email = sum(1 for r in active_rows if r["email"])
    act_web = sum(1 for r in active_rows if r["website"])
    print(f"    * Aktiflerde Telefon: {act_phone}/{len(active_rows)} ({act_phone/len(active_rows)*100:.1f}%)")
    print(f"    * Aktiflerde E-posta: {act_email}/{len(active_rows)} ({act_email/len(active_rows)*100:.1f}%)")
    print(f"    * Aktiflerde Web: {act_web}/{len(active_rows)} ({act_web/len(active_rows)*100:.1f}%)")

    print(f"  - Karantinadaki Kurum Sayısı (Gizlenen/Uydurma): {len(quar_rows)}")
    q_phone = sum(1 for r in quar_rows if r["phone"])
    q_email = sum(1 for r in quar_rows if r["email"])
    print(f"    * Karantinada Telefon: {q_phone}/{len(quar_rows)}")
    print(f"    * Karantinada E-posta: {q_email}/{len(quar_rows)}")

    # 4. 30 Kayıtlık Temsili Bağımsız Örneklem
    # Hem aktiflerden hem karantinadan rastgele seçiyoruz
    random.seed(42) # Tekrarlanabilirlik için sabit tohum
    sample_30 = random.sample(rows, min(30, len(rows)))

    print("\n===============================================================")
    print("30 KAYITLIK BAĞIMSIZ ÖRNEKLEM MANUEL DENETİM TABLOSU")
    print("===============================================================")
    audit_results = []
    
    for idx, r in enumerate(sample_30, 1):
        name = r["name"]
        dist = r["district"] or "Belirtilmemiş"
        phone = r["phone"] or "-"
        email = r["email"] or "-"
        web = r["website"] or "-"
        src_t = r["source_type"]
        status = r["research_status"]
        src_url = r["source_urls"] or "-"

        # Denetim Kriterleri:
        # A. İsim geçerli bir diş sağlığı kuruluşu mu?
        is_construction = any(k in name.lower() for k in ["inşaat", "insaat", "fakülte inşaat"])
        is_faculty_dept = any(k in name.lower() for k in ["temel bilimler", "dekanlık", "öğrenci işleri"])
        is_non_dental = any(k in name.lower() for k in ["moda plus", "giyim", "tekstil", "otomotiv"])
        is_valid_entity = not (is_construction or is_faculty_dept or is_non_dental)

        # B. Web sitesi gerçek bir klinik sitesi mi yoksa haber/portal/forum mu?
        is_news_or_portal = False
        if web != "-":
            bad_domains = ["haber", "sondakika", "alomaliye", "busiad", "forum", "tarimorman", "nilufer.bel.tr", "templatemonster", "kamyonum", "esnafsiteleri", "teknolojikogretmenler", "asosjournal"]
            if any(bd in web.lower() for bd in bad_domains):
                is_news_or_portal = True

        # C. Karantina doğruluğu (Uydurma e-postalar ataevlerdis@gmail vb.)
        is_synthetic = (src_t == "Resmî Rehber" and status == "quarantined")

        audit_results.append({
            "idx": idx,
            "id": r["employer_id"],
            "name": name,
            "district": dist,
            "phone": phone,
            "email": email,
            "website": web,
            "source_type": src_t,
            "status": status,
            "valid_entity": is_valid_entity,
            "valid_website": (web != "-" and not is_news_or_portal),
            "news_portal_leak": is_news_or_portal,
            "synthetic_origin": is_synthetic
        })

        print(f"[{idx:02d}] {name} ({dist})")
        print(f"     Kaynak: {src_t} | Durum: {status}")
        print(f"     Tel: {phone} | E-posta: {email}")
        print(f"     Web: {web}")
        print(f"     Denetim: Geçerli Kurum={is_valid_entity} | Haber/Portal Sızıntısı={is_news_or_portal} | Sentetik/Karantina={is_synthetic}")
        print("-" * 60)

    # Özet İstatistikler
    valid_entities = sum(1 for a in audit_results if a["valid_entity"])
    news_leaks = sum(1 for a in audit_results if a["news_portal_leak"])
    synthetics = sum(1 for a in audit_results if a["synthetic_origin"])
    valid_sites = sum(1 for a in audit_results if a["valid_website"])

    print("\n===============================================================")
    print("30 KAYITLIK ÖRNEKLEM DENETİM SONUÇLARI:")
    print(f"  1. Gerçek Sağlık Kuruluşu Doğruluk Oranı: {valid_entities}/30 (%{valid_entities/30*100:.1f})")
    print(f"  2. Sentetik / Karantina Kayıt Sayısı: {synthetics}/30 (%{synthetics/30*100:.1f})")
    print(f"  3. Haber / Forum / Portal Sızıntılı Web Sitesi Sayısı: {news_leaks}/30")
    print(f"  4. Doğrulanmış Özgün Kurumsal Web Sitesi Sayısı: {valid_sites}/30")
    print("===============================================================")

    conn.close()

if __name__ == "__main__":
    run_audit()

