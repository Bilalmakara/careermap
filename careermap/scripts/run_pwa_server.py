"""CareerMap V2.6 PWA Server Launcher.

Supports running CareerMap on 0.0.0.0 with automatic local IP detection,
optional SSL generation for local HTTPS testing, and guidance for iPhone Safari testing.
"""
import os
import sys
import socket
import argparse
import uvicorn
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

def get_local_ip() -> str:
    """Detect local network IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not actually make a connection
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def main():
    parser = argparse.ArgumentParser(description="CareerMap V2.6 iPhone PWA Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address (default: 0.0.0.0 for LAN access)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--ssl", action="store_true", help="Generate and use self-signed SSL cert for HTTPS")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    local_ip = get_local_ip()
    protocol = "https" if args.ssl else "http"

    print("=" * 70)
    print("  🚀 CAREERMAP V2.6 — iPHONE PWA & ULUSAL İSTİHDAM PLATFORMU")
    print("=" * 70)
    print(f"  • Yerel Masaüstü Adresi:  {protocol}://localhost:{args.port}")
    print(f"  • iPhone / Wi-Fi Adresi:  {protocol}://{local_ip}:{args.port}")
    print("-" * 70)
    print("  📲 iPHONE'DA TEST ETMEK İÇİN:")
    print(f"  1. iPhone'unuzu bilgisayarınızla aynı Wi-Fi ağına bağlayın.")
    print(f"  2. Safari'yi açıp '{protocol}://{local_ip}:{args.port}' adresine gidin.")
    print("  3. Alttaki 'Paylaş' (kare ve yukarı ok ⎋) simgesine dokunun.")
    print("  4. 'Ana Ekrana Ekle' seçeneğini seçin.")
    print("-" * 70)
    print("  🔒 ÜCRETSİZ CANLI HTTPS TÜNELİ (ÖNERİLEN):")
    print("  Apple Safari, PWA service worker ve bildirimleri güvenli HTTPS ortamında çalıştırır.")
    print("  Terminalden ücretsiz tünel başlatmak için:")
    print(f"     npx localtunnel --port {args.port}")
    print(f"     veya: cloudflared tunnel --url http://localhost:{args.port}")
    print("=" * 70)

    ssl_keyfile = None
    ssl_certfile = None

    if args.ssl:
        cert_dir = BASE_DIR / "certs"
        cert_dir.mkdir(exist_ok=True)
        ssl_keyfile = str(cert_dir / "key.pem")
        ssl_certfile = str(cert_dir / "cert.pem")
        
        if not os.path.exists(ssl_keyfile) or not os.path.exists(ssl_certfile):
            print("  [SSL] Yerel geliştirme sertifikası oluşturuluyor...")
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            import datetime

            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, local_ip),
            ])
            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.datetime.utcnow()
            ).not_valid_after(
                datetime.datetime.utcnow() + datetime.timedelta(days=365)
            ).sign(key, hashes.SHA256())

            with open(ssl_keyfile, "wb") as f:
                f.write(key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            with open(ssl_certfile, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            print(f"  [SSL] Sertifikalar oluşturuldu: {cert_dir}")

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        ssl_keyfile=ssl_keyfile,
        ssl_certfile=ssl_certfile,
        app_dir=str(BASE_DIR)
    )

if __name__ == "__main__":
    main()

