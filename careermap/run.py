#!/usr/bin/env python3
"""CareerMap Başlatıcı: Web Arayüzü veya CLI Tarayıcısı."""
import argparse
import sys
import uvicorn
from pathlib import Path

# Paket kök dizinini Python yoluna ekle
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from app.services.scanner import run_pipeline
from app.exports.excel_exporter import generate_careermap_excel
from app.professions.registry import ProfessionRegistry

def main():
    parser = argparse.ArgumentParser(description="CareerMap - Potansiyel İşveren Keşif Platformu")
    parser.add_argument("--host", default="127.0.0.1", help="Web sunucusu host adresi")
    parser.add_argument("--port", type=int, default=8000, help="Web sunucusu port numarası")
    parser.add_argument("--reload", action="store_true", help="Uvicorn auto-reload")
    parser.add_argument("--cli", action="store_true", help="Web arayüzü yerine terminalden doğrudan tara ve Excel üret")
    parser.add_argument("--profession", default="dentist", help="Hedef meslek kimliği (varsayılan: dentist)")
    parser.add_argument("--city", default="Eskişehir", help="Hedef şehir (varsayılan: Eskişehir)")
    parser.add_argument("--output", default="CareerMap_Eskisehir_Dis_Hekimi.xlsx", help="Çıktı Excel dosya adı")
    parser.add_argument("--refresh", action="store_true", help="Önbelleği zorla temizle ve sıfırdan tara")

    args = parser.parse_args()

    if args.cli:
        print(f"=== CareerMap CLI Modu ===")
        print(f"Meslek: {args.profession} | Şehir: {args.city}")
        print("Açık kaynaklar taranıyor ve kayıtlar birleştiriliyor...")
        records = run_pipeline(profession_id=args.profession, city=args.city, force_refresh=args.refresh, enrich_emails=True)
        print(f"Toplam {len(records)} tekilleştirilmiş işletme bulundu.")
        
        prof_obj = ProfessionRegistry.get(args.profession)
        prof_name = prof_obj.name if prof_obj else args.profession
        
        stream = generate_careermap_excel(records, profession_name=prof_name, city=args.city)
        out_path = Path(args.output)
        out_path.write_bytes(stream.getvalue())
        print(f"Başarılı! 4 sekmeli Excel raporu üretildi: {out_path.resolve()}")
    else:
        print(f"=== CareerMap Web Sunucusu Başlatılıyor ===")
        print(f"Adres: http://{args.host}:{args.port}")
        uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)

if __name__ == "__main__":
    main()

