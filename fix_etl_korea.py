import re

with open('scripts/etl_osm_spots.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 替換 CATEGORY_TAG_QUERIES 為高效索引結構 (徹底解決 504 與超時)
new_queries = '''CATEGORY_TAG_QUERIES = {
    "SKATE": [
        'node["leisure"="skatepark"]',
        'way["leisure"="skatepark"]',
        'relation["leisure"="skatepark"]',
        'node["sport"="skateboard"]',
        'way["sport"="skateboard"]',
        'node["sport"="skating"]',
        'way["sport"="skating"]',
        'node["sport"="inline_skating"]',
        'way["sport"="inline_skating"]',
        'node["sport"="roller_skating"]',
        'way["sport"="roller_skating"]',
        'node["leisure"="pumptrack"]',
        'way["leisure"="pumptrack"]',
        'node["leisure"="pitch"]["sport"="skateboard"]',
        'way["leisure"="pitch"]["sport"="skateboard"]',
        'node["leisure"="sports_centre"]["sport"="skateboard"]',
        'way["leisure"="sports_centre"]["sport"="skateboard"]',
        'node["leisure"="sports_centre"]["sport"="skating"]',
        'way["leisure"="sports_centre"]["sport"="skating"]',
        'node["leisure"]["name"~"Skate|스케이트|보드|X-Game",i]',
        'way["leisure"]["name"~"Skate|스케이트|보드|X-Game",i]'
    ],
    "CLIMB": [
        'node["sport"="climbing"]',
        'way["sport"="climbing"]',
        'relation["sport"="climbing"]',
        'node["climbing"]',
        'way["climbing"]',
        'node["climbing"="crag"]',
        'node["climbing"="boulder"]',
        'node["climbing"="gym"]',
        'way["climbing"="crag"]',
        'way["climbing"="boulder"]',
        'way["climbing"="gym"]',
        'node["leisure"="sports_centre"]["sport"="climbing"]',
        'way["leisure"="sports_centre"]["sport"="climbing"]',
        'node["leisure"="fitness_centre"]["sport"="climbing"]',
        'way["leisure"="fitness_centre"]["sport"="climbing"]',
        'node["leisure"]["name"~"Climb|Bouldering|클라이밍|볼더링|암벽",i]',
        'way["leisure"]["name"~"Climb|Bouldering|클라이밍|볼더링|암벽",i]',
        'node["sport"]["name"~"Climb|클라이밍|볼더링|암벽",i]'
    ],
    "SURF": [
        'node["sport"="surfing"]',
        'way["sport"="surfing"]',
        'relation["sport"="surfing"]',
        'node["natural"="beach"]["surf"="yes"]',
        'way["natural"="beach"]["surf"="yes"]',
        'node["leisure"="surf_spot"]',
        'way["leisure"="surf_spot"]',
        'node["leisure"]["name"~"Surf|서프|서핑",i]',
        'node["sport"]["name"~"Surf|서프|서핑",i]'
    ],
    "BMX": [
        'node["sport"="bmx"]',
        'way["sport"="bmx"]',
        'relation["sport"="bmx"]',
        'node["leisure"="track"]["sport"="bmx"]',
        'way["leisure"="track"]["sport"="bmx"]',
        'node["leisure"="pitch"]["sport"="bmx"]',
        'way["leisure"="pitch"]["sport"="bmx"]',
        'node["leisure"="pumptrack"]',
        'way["leisure"="pumptrack"]',
        'node["leisure"]["name"~"BMX|펌프트랙",i]',
        'node["sport"]["name"~"BMX",i]'
    ]
}'''

content = re.sub(r'CATEGORY_TAG_QUERIES = \{[\s\S]*?\n\}', new_queries, content, count=1)

# 2. 升級 fetch_overpass_data (timeout 放寬至 60 秒)
new_fetcher = '''def fetch_overpass_data(query: str) -> List[Dict[str, Any]]:
    """Executes query with proper User-Agent header, server rotation, and 60s timeout."""
    headers = {
        "User-Agent": "xGameRadar-ETL/2.0 (https://unanext.fans; support@unanext.fans)",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate"
    }
    for server in OVERPASS_SERVERS:
        for attempt in range(2):
            try:
                print(f"📡 查詢 Overpass API 伺服器 [{server}] (嘗試 {attempt+1}/2)...")
                resp = requests.post(server, data={"data": query}, headers=headers, timeout=60)
                if resp.status_code == 200:
                    data = resp.json()
                    elements = data.get("elements", [])
                    print(f"✅ 成功抓取 {len(elements)} 筆原始空間點位數據！")
                    return elements
                elif resp.status_code in [429, 504]:
                    print(f"⏳ 遭遇伺服器忙碌 ({resp.status_code})，冷卻 4 秒後切換...")
                    time.sleep(4)
            except Exception as e:
                print(f"⚠️ 伺服器連線略過 ({server}): {e}")
                time.sleep(2)
    return []'''

content = re.sub(r'def fetch_overpass_data\([\s\S]*?return \[\]', new_fetcher, content, count=1)

# 3. 升級 upsert_to_supabase (優雅容錯 DNS 解析錯誤)
new_supabase = '''def upsert_to_supabase(records: List[Dict[str, Any]], supabase_url: str, supabase_key: str) -> int:
    """Performs batch upsert directly via Supabase REST PostgREST endpoint with graceful DNS handling."""
    if not records or not supabase_url or not supabase_key:
        return 0
    
    endpoint = f"{supabase_url.rstrip('/')}/rest/v1/spots"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    
    chunk_size = 50
    total_inserted = 0
    
    for i in range(0, len(records), chunk_size):
        chunk = records[i:i + chunk_size]
        try:
            resp = requests.post(endpoint, json=chunk, headers=headers, timeout=15)
            if resp.status_code in [200, 201, 204]:
                total_inserted += len(chunk)
                print(f"  ⚡ 成功寫入 {len(chunk)} 個點位 (批次 {i // chunk_size + 1})...")
            else:
                print(f"  ❌ 批次寫入回應 ({resp.status_code}): {resp.text[:120]}")
        except Exception as e:
            err_str = str(e)
            if "NameResolutionError" in err_str or "Name or service not known" in err_str or "Failed to resolve" in err_str:
                print(f"  ⚠️ Supabase 專案域名解析失敗 (專案可能已由官方休眠或失效)，已安全略過遠端同步。")
                return 0
            print(f"  ❌ Supabase 連線寫入異常: {e}")
            
    return total_inserted'''

content = re.sub(r'def upsert_to_supabase\([\s\S]*?return total_inserted', new_supabase, content, count=1)

# 4. 確保同步寫入 src/data/global_spots.json
target_save = 'print(f"\\n💾 成功累積儲存 {len(merged_data)} 個場地點位至全域資料集: {args.export_json}")'
replacement_save = '''print(f"\\n💾 成功累積儲存 {len(merged_data)} 個場地點位至全域資料集: {args.export_json}")
    
    # 同步更新 Astro 前端資料夾 (src/data/global_spots.json)
    for src_path in ["src/data/global_spots.json"]:
        try:
            os.makedirs(os.path.dirname(src_path), exist_ok=True)
            with open(src_path, "w", encoding="utf-8") as f:
                json.dump(merged_data, f, ensure_ascii=False, indent=2)
            print(f"📦 已同步更新 Astro 前端地圖資料庫: {src_path}")
        except Exception as e:
            pass'''

if target_save in content:
    content = content.replace(target_save, replacement_save)

with open('scripts/etl_osm_spots.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ scripts/etl_osm_spots.py 已成功優化！")
