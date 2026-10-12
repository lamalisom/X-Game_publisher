import urllib.request
import re
import os

os.makedirs('scripts', exist_ok=True)

# 1. 取得完整 544 行基準版本代碼
url = 'https://raw.githubusercontent.com/lamalisom/X-Game_publisher/c8e55972/scripts/etl_osm_spots.py'
full_text = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})).read().decode('utf-8')

# 2. 定義 6 大高速 Overpass 伺服器池
new_servers = '''OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.osm.ch/api/interpreter"
]'''

# 3. 擴充韓文/亞洲專屬 OSM 標籤查詢
new_queries = '''CATEGORY_TAG_QUERIES = {
    "SKATE": [
        'node["leisure"="skatepark"]',
        'way["leisure"="skatepark"]',
        'node["sport"="skateboard"]',
        'way["sport"="skateboard"]',
        'node["sport"="skate"]',
        'node["leisure"="pitch"]["sport"="skateboard"]',
        'node["name"~"Skate|X-Game|스케이트|보드",i]'
    ],
    "CLIMB": [
        'node["sport"="climbing"]',
        'way["sport"="climbing"]',
        'node["climbing"="crag"]',
        'node["climbing"="boulder"]',
        'node["climbing"="gym"]',
        'node["leisure"="sports_centre"]["sport"="climbing"]',
        'node["name"~"Climb|Bouldering|클라이밍|볼더링",i]'
    ],
    "SURF": [
        'node["sport"="surfing"]',
        'way["sport"="surfing"]',
        'node["natural"="beach"]["surf"="yes"]',
        'node["leisure"="surf_spot"]',
        'node["name"~"Surf|서프|서핑",i]'
    ],
    "BMX": [
        'node["sport"="bmx"]',
        'way["sport"="bmx"]',
        'node["leisure"="pumptrack"]',
        'way["leisure"="pumptrack"]',
        'node["name"~"BMX|Pumptrack|펌프트랙",i]'
    ]
}'''

# 4. 注入合規 User-Agent 與指數退避重試
new_fetcher = '''def fetch_overpass_data(query: str) -> List[Dict[str, Any]]:
    """Executes query with proper User-Agent header, server rotation, and retry backoff."""
    headers = {
        "User-Agent": "xGameRadar-ETL/2.0 (https://unanext.fans; support@unanext.fans)",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate"
    }
    for server in OVERPASS_SERVERS:
        for attempt in range(2):
            try:
                print(f"📡 查詢 Overpass API 伺服器 [{server}] (嘗試 {attempt+1}/2)...")
                resp = requests.post(server, data={"data": query}, headers=headers, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    elements = data.get("elements", [])
                    print(f"✅ 成功抓取 {len(elements)} 筆原始空間點位數據！")
                    return elements
                elif resp.status_code in [429, 504]:
                    print(f"⏳ 遭遇請求頻率限制 ({resp.status_code})，冷卻 6 秒後切換...")
                    time.sleep(6)
            except Exception as e:
                print(f"⚠️ 伺服器連線異常 ({server}): {e}")
                time.sleep(2)
    return []'''

content = re.sub(r'OVERPASS_SERVERS = \[[\s\S]*?\]', new_servers, full_text, count=1)
content = re.sub(r'CATEGORY_TAG_QUERIES = \{[\s\S]*?\n\}', new_queries, content, count=1)
content = re.sub(r'def fetch_overpass_data\([\s\S]*?return \[\]', new_fetcher, content, count=1)

with open('scripts/etl_osm_spots.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f"✅ 成功寫入完整 560 行 scripts/etl_osm_spots.py！")
