import json
import re
import os

# 1. 修補 global_spots.json 資料集中的韓國點位
for json_file in ['src/data/global_spots.json', 'public/data/global_spots.json']:
    if not os.path.exists(json_file):
        continue
    with open(json_file, 'r', encoding='utf-8') as f:
        spots = json.load(f)
    
    korea_count = 0
    for s in spots:
        lat = s.get('latitude', 0.0)
        lng = s.get('longitude', 0.0)
        name = s.get('name', '').lower()
        
        # 韓國地理坐標框
        if (33.0 <= lat <= 38.8 and 125.0 <= lng <= 129.8) or 'korea' in name or 'seoul' in name or any('\uac00' <= char <= '\ud7a3' for char in s.get('name', '')):
            s['country'] = 'Korea'
            s['countryCode'] = 'KR'
            
            # 分配具體城市
            if not s.get('city') or s.get('city') == 'Global':
                if 33.15 <= lat <= 33.60 and 126.15 <= lng <= 126.95:
                    s['city'] = 'Jeju 濟州'
                elif 35.05 <= lat <= 35.35 and 128.95 <= lng <= 129.30:
                    s['city'] = 'Busan 釜山'
                elif 37.35 <= lat <= 37.60 and 126.50 <= lng <= 126.85:
                    s['city'] = 'Incheon 仁川'
                elif 35.75 <= lat <= 36.00 and 128.45 <= lng <= 128.75:
                    s['city'] = 'Daegu 大邱'
                else:
                    s['city'] = 'Seoul 首爾'
            korea_count += 1
            
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(spots, f, ensure_ascii=False, indent=2)
    print(f"✅ {json_file} 成功修正 {korea_count} 個韓國點位（正式標記 KR / Korea）！")

# 2. 修正 map.astro 與 map/en.astro 中的 resolveLocation (優先判斷韓國)
korea_resolve_zh = """  // 🇰🇷 韓國 (KR) - 必須在前面優先判斷，避免被廣域座標攔截
  if (c === 'KR' || c === 'KOREA' || c === 'SOUTH KOREA' || c === '韓國' || (lat >= 33.0 && lat <= 38.8 && lng >= 125.0 && lng <= 129.8) || name.includes('korea') || name.includes('seoul') || name.includes('busan') || name.includes('jeju')) {
    let city = cityName || '首爾 Seoul';
    if (name.includes('busan') || (lat >= 35.05 && lat <= 35.35 && lng >= 128.95 && lng <= 129.30)) city = '釜山 Busan';
    else if (name.includes('jeju') || (lat >= 33.15 && lat <= 33.60 && lng >= 126.15 && lng <= 126.95)) city = '濟州 Jeju';
    else if (name.includes('incheon') || (lat >= 37.35 && lat <= 37.60 && lng >= 126.50 && lng <= 126.85)) city = '仁川 Incheon';
    return { flag: '🇰🇷', countryCode: 'KR', countryZH: '韓國', countryEN: 'South Korea', cityZH: city, cityEN: city };
  }
"""

korea_resolve_en = """  // 🇰🇷 South Korea (KR) - Must evaluate before Japan
  if (c === 'KR' || c === 'KOREA' || c === 'SOUTH KOREA' || c === '韓國' || (lat >= 33.0 && lat <= 38.8 && lng >= 125.0 && lng <= 129.8) || name.includes('korea') || name.includes('seoul') || name.includes('busan') || name.includes('jeju')) {
    let city = cityName || 'Seoul';
    if (name.includes('busan') || (lat >= 35.05 && lat <= 35.35 && lng >= 128.95 && lng <= 129.30)) city = 'Busan';
    else if (name.includes('jeju') || (lat >= 33.15 && lat <= 33.60 && lng >= 126.15 && lng <= 126.95)) city = 'Jeju';
    else if (name.includes('incheon') || (lat >= 37.35 && lat <= 37.60 && lng >= 126.50 && lng <= 126.85)) city = 'Incheon';
    return { flag: '🇰🇷', countryCode: 'KR', countryZH: 'South Korea', countryEN: 'South Korea', cityZH: city, cityEN: city };
  }
"""

for path, k_code in [('src/pages/spots/map.astro', korea_resolve_zh), ('src/pages/spots/map/en.astro', korea_resolve_en)]:
    if not os.path.exists(path):
        continue
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()
    
    # 移除舊的韓國判斷（若存在）
    c = re.sub(r'  // 🇰🇷[^\n]+\n  if \(c === \'KR\'[\s\S]*?\n  \}', '', c)
    
    # 將韓國插入到 resolveLocation 最開頭（在瑞士/日本之前）
    insert_pos = c.find('function resolveLocation(')
    if insert_pos != -1:
        first_brace = c.find('{', insert_pos)
        c = c[:first_brace+1] + '\n' + k_code + c[first_brace+1:]
        with open(path, 'w', encoding='utf-8') as f:
            f.write(c)
        print(f"✅ {path} resolveLocation 成功將韓國置頂優先解析！")

# 3. 確保 etl_osm_spots.py 自動為韓國點位填入 country
etl_path = 'scripts/etl_osm_spots.py'
if os.path.exists(etl_path):
    with open(etl_path, 'r', encoding='utf-8') as f:
        etl_code = f.read()
    
    # 在 transform_element 中加入如果經緯度在韓國則 country = 'Korea'
    target_geo = 'country = tags.get("addr:country") or tags.get("country") or ""'
    replacement_geo = '''country = tags.get("addr:country") or tags.get("country") or ""
    if not country and (33.0 <= lat <= 38.8 and 125.0 <= lng <= 129.8):
        country = "Korea"'''
    if target_geo in etl_code and 'if not country and (33.0 <= lat <= 38.8' not in etl_code:
        etl_code = etl_code.replace(target_geo, replacement_geo)
        with open(etl_path, 'w', encoding='utf-8') as f:
            f.write(etl_code)
        print("✅ scripts/etl_osm_spots.py 加入韓國自動判定！")
