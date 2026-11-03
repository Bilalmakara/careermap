import requests
import json

query = """[out:json][timeout:35];
area["name"="Bursa"][admin_level=4]->.searchArea;
(
  node["amenity"="dentist"](area.searchArea);
  way["amenity"="dentist"](area.searchArea);
  relation["amenity"="dentist"](area.searchArea);
  node["healthcare"="dentist"](area.searchArea);
  way["healthcare"="dentist"](area.searchArea);
  relation["healthcare"="dentist"](area.searchArea);
  node["healthcare:speciality"="dental"](area.searchArea);
  way["healthcare:speciality"="dental"](area.searchArea);
  relation["healthcare:speciality"="dental"](area.searchArea);
);
out center tags;
"""

headers = {"User-Agent": "CareerMap/2.5 (Bursa Province Test; info@careermap.local)"}
for ep in ["https://maps.mail.ru/osm/tools/overpass/api/interpreter", "https://overpass-api.de/api/interpreter", "https://lz4.overpass-api.de/api/interpreter"]:
    try:
        print("Querying", ep, "...")
        r = requests.post(ep, data={"data": query}, headers=headers, timeout=30)
        print("Status:", r.status_code)
        if r.status_code == 200:
            data = r.json()
            elements = data.get("elements", [])
            print("Found elements in whole Bursa area:", len(elements))
            for el in elements[:5]:
                print(el.get("type"), el.get("id"), el.get("tags", {}).get("name"))
            break
    except Exception as e:
        print("Error:", e)

