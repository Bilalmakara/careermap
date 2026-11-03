import requests

query = """[out:json][timeout:25];
area["ISO3166-1"="TR"][admin_level=2]->.turkey;
(
  node["amenity"="dentist"](area.turkey);
);
out count;
"""
headers = {"User-Agent": "CareerMap/2.5 (OSM Test; info@careermap.local)"}
for ep in ["https://maps.mail.ru/osm/tools/overpass/api/interpreter", "https://overpass-api.de/api/interpreter"]:
    try:
        r = requests.post(ep, data={"data": query}, headers=headers, timeout=25)
        print(ep, "Status:", r.status_code)
        if r.status_code == 200:
            print("Response:", r.text[:300])
            break
    except Exception as e:
        print(ep, "Error:", e)

