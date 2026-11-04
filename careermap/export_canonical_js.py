import json
from pathlib import Path

json_path = Path("careermap/web/canonical_datasets.json")
with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

js_content = f"window.CAREERMAP_CANONICAL_DATA = {json.dumps(data, ensure_ascii=False)};\n"

# Output to web and frontend_vercel
targets = [
    Path("careermap/web/canonical_datasets.js"),
    Path("careermap/web/app/canonical_datasets.js"),
    Path("careermap/frontend_vercel/canonical_datasets.js"),
    Path("careermap/frontend_vercel/app/canonical_datasets.js"),
]

for t in targets:
    t.parent.mkdir(parents=True, exist_ok=True)
    with open(t, "w", encoding="utf-8") as f:
        f.write(js_content)
    print(f"Written {t} ({t.stat().st_size} bytes)")
