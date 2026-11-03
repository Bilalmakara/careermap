"""CareerMap V2.0 Dağıtım Paketi Üreticisi (careermap.zip)."""
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SOURCE_DIR = ROOT_DIR / "careermap"
OUTPUT_ZIP = ROOT_DIR / "careermap.zip"

EXCLUDE_PATTERNS = {
    "__pycache__",
    ".pytest_cache",
    ".git",
    "node_modules",
    ".DS_Store",
    ".pbf"
}

def should_exclude(path: Path) -> bool:
    for part in path.parts:
        if part in EXCLUDE_PATTERNS:
            return True
        if part.endswith(".pyc"):
            return True
    return False

def package_zip():
    count = 0
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zipf:
        for p in SOURCE_DIR.rglob("*"):
            if p.is_file() and not should_exclude(p):
                rel = p.relative_to(ROOT_DIR)
                zipf.write(p, rel)
                count += 1
    print(f"Başarıyla paketlendi: {OUTPUT_ZIP} ({count} dosya)")

if __name__ == "__main__":
    package_zip()

