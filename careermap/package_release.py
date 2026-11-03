"""CareerMap V1.6 Dağıtım Arşivi (careermap.zip) Paketleme Betiği.
Gereksiz geçici dosyaları (.pyc, __pycache__, loglar) hariç tutarak
temiz bir arşiv oluşturur.
"""
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

EXCLUDE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "*.db.bak",
    "*.v1_2.bak",
    "*.v1_4.bak",
    ".pytest_cache",
    ".git"
]

def should_exclude(path: Path) -> bool:
    for part in path.parts:
        if part in ["__pycache__", ".pytest_cache", ".git"]:
            return True
    if path.suffix in [".pyc", ".bak"]:
        return True
    return False

def package_zip():
    zip_path = ROOT_DIR.parent / "careermap.zip"
    print(f"Paketleme başlıyor: {zip_path}")
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in ROOT_DIR.rglob("*"):
            if p.is_file() and not should_exclude(p):
                rel_path = Path("careermap") / p.relative_to(ROOT_DIR)
                zf.write(p, rel_path)
                count += 1
    print(f"[OK] {count} dosya arşivlendi: {zip_path} ({zip_path.stat().st_size / (1024 * 1024):.2f} MB)")

if __name__ == "__main__":
    package_zip()

