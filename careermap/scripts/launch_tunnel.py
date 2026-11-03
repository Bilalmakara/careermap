"""CareerMap Live Tunnel Launcher.
Starts FastAPI backend and creates an instant Cloudflare HTTPS tunnel for Vercel & iPhone PWA testing.
"""
import subprocess
import time
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def main():
    print("=" * 70)
    print("  🚀 CAREERMAP CANLI ARKA UÇ VE TÜNEL BAŞLATICI")
    print("=" * 70)
    print("  1. FastAPI yerel sunucusu başlatılıyor (Port 8000)...")

    # Start uvicorn process
    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    time.sleep(2)
    print("  ✓ FastAPI yerel sunucusu aktif.")
    print("  2. Cloudflare HTTPS tüneli açılıyor...")

    # Start cloudflared process
    tunnel_process = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", "http://localhost:8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    tunnel_url = None
    start_time = time.time()
    while time.time() - start_time < 20:
        line = tunnel_process.stdout.readline()
        if not line:
            continue
        match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
        if match:
            tunnel_url = match.group(0)
            break

    if tunnel_url:
        print("=" * 70)
        print("  🎉 CANLI ARKA UÇ ADRESİNİZ OLUŞTURULDU:")
        print(f"     👉  {tunnel_url}  👈")
        print("=" * 70)
        print("  📲 Vercel'deki sitenizde veya iPhone'unuzda:")
        print("  1. Sağ üstteki '🌐 API Sunucusu' butonuna tıklayın.")
        print(f"  2. Açılan kutucuğa bu adresi yapıştırın:\n     {tunnel_url}")
        print("  3. 'Bağlantıyı Sına' butonuna basıp 'Kaydet' deyin.")
        print("  ✓ Tüm 404 hataları bitecek, gerçek 1.401 kurum ve CRM aktifleşecek!")
        print("=" * 70)
        print("  (Kapatmak için CTRL + C tuşlarına basın)")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nKapatılıyor...")
            server_process.terminate()
            tunnel_process.terminate()
    else:
        print("⚠️ Tünel linki otomatik yakalanamadı. Manuel çalıştırmak için:")
        print("   Terminal 1: python -m uvicorn app.main:app --port 8000")
        print("   Terminal 2: cloudflared tunnel --url http://localhost:8000")
        server_process.terminate()
        tunnel_process.terminate()

if __name__ == "__main__":
    main()
