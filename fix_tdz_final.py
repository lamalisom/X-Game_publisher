import re
import os

for path in ['src/pages/spots/map/en.astro', 'src/pages/spots/map.astro']:
    if not os.path.exists(path):
        continue
    with open(path, 'r', encoding='utf-8') as f:
        code = f.read()

    # 1. 移除任意位置殘留的變數宣告
    code = re.sub(r'[ \t]*const name = \(spotName \|\| \'\'\)\.toLowerCase\(\);[\r\n]*', '', code)
    code = re.sub(r'[ \t]*const c = \(countryRaw \|\| \'\'\)\.trim\(\)\.toUpperCase\(\);[\r\n]*', '', code)
    code = re.sub(r'[ \t]*const cityLower = \(cityName \|\| \'\'\)\.toLowerCase\(\);[\r\n]*', '', code)

    # 2. 將宣告精準置入在函數最頂端（第 1 行）
    target = 'function resolveLocation(lat: number, lng: number, countryRaw: string, cityName: string, spotName: string) {'
    replacement = '''function resolveLocation(lat: number, lng: number, countryRaw: string, cityName: string, spotName: string) {
  const name = (spotName || '').toLowerCase();
  const c = (countryRaw || '').trim().toUpperCase();
  const cityLower = (cityName || '').toLowerCase();'''

    if target in code:
        code = code.replace(target, replacement)
        print(f"✅ {path}: 已將 const c 置頂宣告！")
    else:
        print(f"⚠️ {path}: 找不到 target")

    # 3. 確保頂部按鈕列有 🇰🇷 韓國 按鈕
    is_en = 'en.astro' in path
    btn_text = '🇰🇷 South Korea' if is_en else '🇰🇷 韓國'
    kr_btn = f'        <button data-country="KR" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">{btn_text}</button>'

    if 'data-country="KR"' not in code:
        if 'data-country="JP"' in code:
            code = code.replace('data-country="JP"', f'data-country="KR"\n{kr_btn}\n        <button data-country="JP"')
            print(f"✅ {path}: 已加入 🇰🇷 韓國標籤按鈕！")

    with open(path, 'w', encoding='utf-8') as f:
        f.write(code)

# 4. 同步確保 global_spots.json 中韓國點位標記為 KR
for jpath in ['src/data/global_spots.json', 'public/data/global_spots.json']:
    if not os.path.exists(jpath):
        continue
    import json
    with open(jpath, 'r', encoding='utf-8') as f:
        spots = json.load(f)
    for s in spots:
        lat = s.get('latitude', 0.0)
        lng = s.get('longitude', 0.0)
        name = s.get('name', '').lower()
        if (33.0 <= lat <= 38.8 and 125.0 <= lng <= 129.8) or 'korea' in name or 'seoul' in name or any('\uac00' <= char <= '\ud7a3' for char in s.get('name', '')):
            s['country'] = 'Korea'
            s['countryCode'] = 'KR'
    with open(jpath, 'w', encoding='utf-8') as f:
        json.dump(spots, f, ensure_ascii=False, indent=2)
    print(f"✅ {jpath} 標記完成！")
