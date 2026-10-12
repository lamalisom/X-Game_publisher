import json
import re
import os

def get_clean_resolve_location(is_en=False):
    korea_name = "South Korea" if is_en else "韓國"
    korea_city = "Seoul" if is_en else "首爾 Seoul"
    busan_city = "Busan" if is_en else "釜山 Busan"
    jeju_city = "Jeju" if is_en else "濟州 Jeju"
    incheon_city = "Incheon" if is_en else "仁川 Incheon"

    return f'''function resolveLocation(lat: number, lng: number, countryRaw: string, cityName: string, spotName: string) {{
  const name = (spotName || '').toLowerCase();
  const c = (countryRaw || '').trim().toUpperCase();
  const cityLower = (cityName || '').toLowerCase();

  // 1. 🇰🇷 韓國 (KR) - 必須在最前面優先解析，防止被日本廣域坐標攔截
  if (c === 'KR' || c === 'KOREA' || c === 'SOUTH KOREA' || c === '韓國' || (lat >= 33.0 && lat <= 38.8 && lng >= 125.0 && lng <= 129.8) || name.includes('korea') || name.includes('seoul') || name.includes('busan') || name.includes('jeju')) {{
    let city = cityName || '{korea_city}';
    if (name.includes('busan') || (lat >= 35.05 && lat <= 35.35 && lng >= 128.95 && lng <= 129.30)) city = '{busan_city}';
    else if (name.includes('jeju') || (lat >= 33.15 && lat <= 33.60 && lng >= 126.15 && lng <= 126.95)) city = '{jeju_city}';
    else if (name.includes('incheon') || (lat >= 37.35 && lat <= 37.60 && lng >= 126.50 && lng <= 126.85)) city = '{incheon_city}';
    return {{ flag: '🇰🇷', countryCode: 'KR', countryZH: '{korea_name}', countryEN: 'South Korea', cityZH: city, cityEN: city }};
  }}

  // 2. 🇨🇭 瑞士 (CH)
  if (c === 'CH' || c === 'SWITZERLAND' || c === 'SUI' || c === '瑞士' || (lat >= 45.8 && lat <= 47.9 && lng >= 5.9 && lng <= 10.5) || name.includes('laax') || name.includes('zermatt') || name.includes('verbier') || name.includes('saas-fee') || name.includes('titlis') || name.includes('davos') || name.includes('st. moritz') || name.includes('jungfrau') || name.includes('grindelwald') || name.includes('matterhorn') || name.includes('switzerland') || name.includes('swiss') || name.includes('zurich') || name.includes('geneva')) {{
    let city = cityName || '{"Alps" if is_en else "阿爾卑斯 Alps"}';
    if (name.includes('laax')) city = 'Laax';
    else if (name.includes('zermatt')) city = 'Zermatt';
    else if (name.includes('verbier')) city = 'Verbier';
    else if (name.includes('saas-fee')) city = 'Saas-Fee';
    else if (name.includes('titlis') || name.includes('engelberg')) city = 'Engelberg / Titlis';
    else if (name.includes('davos')) city = 'Davos';
    else if (name.includes('st. moritz') || name.includes('moritz')) city = 'St. Moritz';
    return {{ flag: '🇨🇭', countryCode: 'CH', countryZH: '瑞士', countryEN: 'Switzerland', cityZH: city, cityEN: city }};
  }}

  // 3. 🇫🇷 法國 (FR)
  if (c === 'FR' || c === 'FRANCE' || c === 'FRA' || c === '法國' || (lat >= 41.3 && lat <= 51.1 && lng >= -5.2 && lng <= 9.6) || name.includes('chamonix') || name.includes('tignes') || name.includes('val d') || name.includes('avoriaz') || name.includes('les arcs') || name.includes('alpe d') || name.includes('meribel') || name.includes('courchevel') || name.includes('france') || name.includes('paris') || name.includes('marseille') || name.includes('hossegor') || name.includes('biarritz')) {{
    let city = cityName || '{"Chamonix / Alps" if is_en else "霞慕尼 Chamonix"}';
    if (name.includes('chamonix')) city = 'Chamonix';
    else if (name.includes('tignes') || name.includes('val d')) city = "Val d'Isère / Tignes";
    else if (name.includes('avoriaz') || name.includes('morzine')) city = 'Portes du Soleil';
    else if (name.includes('marseille')) city = 'Marseille';
    else if (name.includes('paris')) city = 'Paris';
    return {{ flag: '🇫🇷', countryCode: 'FR', countryZH: '法國', countryEN: 'France', cityZH: city, cityEN: city }};
  }}

  // 4. 🇸🇪 瑞典 (SE)
  if (c === 'SE' || c === 'SWEDEN' || c === 'SWE' || c === '瑞典' || (lat >= 55.3 && lat <= 69.1 && lng >= 11.0 && lng <= 24.2) || name.includes('sweden') || name.includes('sverige') || name.includes('stockholm') || name.includes('malmö') || name.includes('malmo') || name.includes('are') || name.includes('åre') || name.includes('sälen')) {{
    let city = cityName || '{"Åre / Stockholm" if is_en else "奧勒 Åre / 斯德哥爾摩"}';
    if (name.includes('are') || name.includes('åre')) city = 'Åre';
    else if (name.includes('salen') || name.includes('sälen')) city = 'Sälen';
    else if (name.includes('stockholm')) city = 'Stockholm';
    else if (name.includes('malmo') || name.includes('malmö')) city = 'Malmö';
    return {{ flag: '🇸🇪', countryCode: 'SE', countryZH: '瑞典', countryEN: 'Sweden', cityZH: city, cityEN: city }};
  }}

  // 5. 🇳🇴 挪威 (NO)
  if (c === 'NO' || c === 'NORWAY' || c === 'NOR' || c === '挪威' || (lat >= 57.9 && lat <= 71.2 && lng >= 4.5 && lng <= 11.0) || name.includes('norway') || name.includes('oslo') || name.includes('bergen') || name.includes('trondheim') || name.includes('stavanger') || name.includes('tromsø') || name.includes('hemsedal') || name.includes('trysil') || name.includes('hafjell')) {{
    let city = cityName || '{"Oslo" if is_en else "奧斯陸 Oslo"}';
    if (name.includes('hemsedal')) city = 'Hemsedal';
    else if (name.includes('trysil')) city = 'Trysil';
    else if (name.includes('hafjell')) city = 'Hafjell';
    return {{ flag: '🇳🇴', countryCode: 'NO', countryZH: '挪威', countryEN: 'Norway', cityZH: city, cityEN: city }};
  }}

  // 6. 🇫🇮 芬蘭 (FI)
  if (c === 'FI' || c === 'FINLAND' || c === 'FIN' || c === '芬蘭' || (lat >= 59.7 && lat <= 70.1 && lng >= 20.6 && lng <= 31.6) || name.includes('finland') || name.includes('helsinki') || name.includes('levi') || name.includes('ruka')) {{
    let city = cityName || '{"Helsinki" if is_en else "赫爾辛基 Helsinki"}';
    if (name.includes('levi')) city = 'Levi';
    else if (name.includes('ruka')) city = 'Ruka';
    return {{ flag: '🇫🇮', countryCode: 'FI', countryZH: '芬蘭', countryEN: 'Finland', cityZH: city, cityEN: city }};
  }}

  // 7. 🇯🇵 日本 (JP) - 經度收斂至 129.5+，不再重疊覆蓋韓國
  if (c === 'JP' || c === 'JAPAN' || c === '日本' || (lat >= 24.0 && lat <= 46.0 && lng >= 129.5 && lng <= 154.0) || name.includes('japan') || name.includes('tokyo') || name.includes('osaka') || name.includes('hokkaido') || name.includes('niseko') || name.includes('hakuba') || name.includes('nagano')) {{
    let city = cityName || '{"Tokyo" if is_en else "東京 Tokyo"}';
    if (name.includes('niseko') || name.includes('hokkaido')) city = '{"Hokkaido" if is_en else "北海道 Hokkaido"}';
    else if (name.includes('hakuba') || name.includes('nagano')) city = '{"Nagano / Hakuba" if is_en else "長野 白馬 Hakuba"}';
    return {{ flag: '🇯🇵', countryCode: 'JP', countryZH: '日本', countryEN: 'Japan', cityZH: city, cityEN: city }};
  }}

  // 8. 🇭🇰 香港 (HK)
  if (c === 'HK' || c === 'HONG KONG' || c === '香港' || (lat >= 22.15 && lat <= 22.60 && lng >= 113.80 && lng <= 114.45) || name.includes('hong kong') || name.includes('hongkong') || name.includes('香港')) {{
    return {{ flag: '🇭🇰', countryCode: 'HK', countryZH: '香港', countryEN: 'Hong Kong', cityZH: '{"Hong Kong" if is_en else "香港 Hong Kong"}', cityEN: 'Hong Kong' }};
  }}

  // 9. 🇹🇼 台灣 (TW)
  if (c === 'TW' || c === 'TAIWAN' || c === '台灣' || (lat >= 21.8 && lat <= 25.4 && lng >= 119.9 && lng <= 122.1) || name.includes('taiwan') || name.includes('taipei') || name.includes('kaohsiung') || name.includes('台灣')) {{
    let city = cityName || '{"Taipei" if is_en else "台北 Taipei"}';
    if (name.includes('kaohsiung') || name.includes('高雄')) city = '{"Kaohsiung" if is_en else "高雄 Kaohsiung"}';
    return {{ flag: '🇹🇼', countryCode: 'TW', countryZH: '台灣', countryEN: 'Taiwan', cityZH: city, cityEN: city }};
  }}

  // 10. 🇬🇧 英國 (GB)
  if (c === 'GB' || c === 'UK' || c === 'UNITED KINGDOM' || c === '英國' || (lat >= 49.8 && lat <= 60.9 && lng >= -8.6 && lng <= 1.8) || name.includes('london') || name.includes('manchester') || name.includes('uk')) {{
    let city = cityName || '{"London" if is_en else "倫敦 London"}';
    return {{ flag: '🇬🇧', countryCode: 'GB', countryZH: '英國', countryEN: 'UK', cityZH: city, cityEN: city }};
  }}

  // 11. 🇺🇸 美國 (US)
  if (c === 'US' || c === 'USA' || c === 'UNITED STATES' || c === '美國' || (lat >= 24.0 && lat <= 50.0 && lng >= -125.0 && lng <= -66.0) || name.includes('california') || name.includes('colorado') || name.includes('usa')) {{
    let city = cityName || '{"California" if is_en else "加州 California"}';
    return {{ flag: '🇺🇸', countryCode: 'US', countryZH: '美國', countryEN: 'USA', cityZH: city, cityEN: city }};
  }}

  // 12. 🇦🇺 澳洲 (AU)
  if (c === 'AU' || c === 'AUSTRALIA' || c === '澳洲' || (lat >= -44.0 && lat <= -10.0 && lng >= 113.0 && lng <= 154.0) || name.includes('sydney') || name.includes('melbourne') || name.includes('australia')) {{
    let city = cityName || '{"Sydney" if is_en else "雪梨 Sydney"}';
    return {{ flag: '🇦🇺', countryCode: 'AU', countryZH: '澳洲', countryEN: 'Australia', cityZH: city, cityEN: city }};
  }}

  // 13. 🇮🇩 印尼 (ID)
  if (c === 'ID' || c === 'INDONESIA' || c === '印尼' || (lat >= -11.0 && lat <= 6.0 && lng >= 95.0 && lng <= 141.0) || name.includes('bali') || name.includes('canggu') || name.includes('indonesia')) {{
    let city = cityName || '{"Bali" if is_en else "峇里島 Bali"}';
    return {{ flag: '🇮🇩', countryCode: 'ID', countryZH: '印尼', countryEN: 'Indonesia', cityZH: city, cityEN: city }};
  }}

  // 14. 🇹🇭 泰國 (TH)
  if (c === 'TH' || c === 'THAILAND' || c === '泰國' || (lat >= 5.6 && lat <= 20.5 && lng >= 97.3 && lng <= 105.7) || name.includes('thailand') || name.includes('bangkok') || name.includes('phuket')) {{
    let city = cityName || '{"Bangkok" if is_en else "曼谷 Bangkok"}';
    return {{ flag: '🇹🇭', countryCode: 'TH', countryZH: '泰國', countryEN: 'Thailand', cityZH: city, cityEN: city }};
  }}

  // 15. 🇨🇦 加拿大 (CA)
  if (c === 'CA' || c === 'CANADA' || c === '加拿大' || (lat >= 41.7 && lat <= 83.1 && lng >= -141.0 && lng <= -52.6) || name.includes('canada') || name.includes('whistler') || name.includes('vancouver')) {{
    let city = cityName || '{"Vancouver" if is_en else "溫哥華 Vancouver"}';
    return {{ flag: '🇨🇦', countryCode: 'CA', countryZH: '加拿大', countryEN: 'Canada', cityZH: city, cityEN: city }};
  }}

  return {{ flag: '🌍', countryCode: c || 'OTHER', countryZH: cityName || c || '{"Global" if is_en else "全球"}', countryEN: cityName || c || 'Global', cityZH: cityName || '{"Global" if is_en else "全球"}', cityEN: cityName || 'Global' }};
}}'''

def patch_astro_file(filepath, is_en=False):
    if not os.path.exists(filepath):
        print(f"⚠️ 檔案不存在: {filepath}")
        return
    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()

    # 1. 替換 resolveLocation 函數主體
    s = code.find('function resolveLocation(')
    if s != -1:
        e = code.find('\nconst spots =', s)
        if e == -1:
            e = code.find('\n// ---', s)
        if e != -1:
            clean_func = get_clean_resolve_location(is_en)
            code = code[:s] + clean_func + '\n' + code[e:]
            print(f"✅ {filepath} 成功替換為乾淨 resolveLocation (變數宣告安全置頂)！")

    # 2. 確保頂部按鈕列含有 🇰🇷 韓國 按鈕
    btn_zh = '        <button data-country="KR" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇰🇷 韓國</button>'
    btn_en = '        <button data-country="KR" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇰🇷 South Korea</button>'
    kr_btn = btn_en if is_en else btn_zh

    if 'data-country="KR"' not in code:
        target_marker = 'data-country="JP"'
        if target_marker in code:
            code = code.replace(target_marker, f'data-country="KR"\n{kr_btn}\n        <button data-country="JP"')
            print(f"✅ {filepath} 成功加入 🇰🇷 韓國篩選標籤按鈕！")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(code)

patch_astro_file('src/pages/spots/map.astro', is_en=False)
patch_astro_file('src/pages/spots/map/en.astro', is_en=True)

# 3. 修復 global_spots.json 中的韓國數據
for jpath in ['src/data/global_spots.json', 'public/data/global_spots.json']:
    if not os.path.exists(jpath):
        continue
    with open(jpath, 'r', encoding='utf-8') as f:
        spots = json.load(f)
    
    count = 0
    for s in spots:
        lat = s.get('latitude', 0.0)
        lng = s.get('longitude', 0.0)
        name = s.get('name', '').lower()
        if (33.0 <= lat <= 38.8 and 125.0 <= lng <= 129.8) or 'korea' in name or 'seoul' in name or any('\uac00' <= char <= '\ud7a3' for char in s.get('name', '')):
            s['country'] = 'Korea'
            s['countryCode'] = 'KR'
            count += 1
            
    with open(jpath, 'w', encoding='utf-8') as f:
        json.dump(spots, f, ensure_ascii=False, indent=2)
    print(f"✅ {jpath} 成功標記 {count} 個韓國場地點位 (countryCode: KR)！")
