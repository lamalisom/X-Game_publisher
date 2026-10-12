import os, re

for fpath in ['src/pages/spots/map.astro', 'src/pages/spots/map/en.astro']:
    if not os.path.exists(fpath):
        print(f"Not found: {fpath}")
        continue
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 替換瑞士判定，使其絕對優先於法國
    if "rawCountry === 'CH'" not in content:
        # 尋找 function getCountry 開頭
        old_pattern = r'function getCountry\s*\([^\)]*\)\s*\{'
        replacement = """function getCountry(spot: any) {
    const rawCountry = (spot.country || '').toUpperCase().trim();
    if (rawCountry === 'CH' || rawCountry === 'SWITZERLAND' || rawCountry === 'SUI') return { code: 'CH', nameZh: '瑞士 Switzerland', flag: '🇨🇭' };
    if (rawCountry === 'FR' || rawCountry === 'FRANCE') return { code: 'FR', nameZh: '法國 France', flag: '🇫🇷' };
    if (rawCountry === 'JP' || rawCountry === 'JAPAN') return { code: 'JP', nameZh: '日本 Japan', flag: '🇯🇵' };
    if (rawCountry === 'GB' || rawCountry === 'UK') return { code: 'GB', nameZh: '英國 UK', flag: '🇬🇧' };
    if (rawCountry === 'SE' || rawCountry === 'SWEDEN') return { code: 'SE', nameZh: '瑞典 Sweden', flag: '🇸🇪' };
    if (rawCountry === 'NO' || rawCountry === 'NORWAY') return { code: 'NO', nameZh: '挪威 Norway', flag: '🇳🇴' };
    if (rawCountry === 'FI' || rawCountry === 'FINLAND') return { code: 'FI', nameZh: '芬蘭 Finland', flag: '🇫🇮' };
    if (rawCountry === 'TW' || rawCountry === 'TAIWAN') return { code: 'TW', nameZh: '台灣 Taiwan', flag: '🇹🇼' };
    if (rawCountry === 'HK' || rawCountry === 'HONG KONG') return { code: 'HK', nameZh: '香港 Hong Kong', flag: '🇭🇰' };
    if (rawCountry === 'KR' || rawCountry === 'KOREA') return { code: 'KR', nameZh: '韓國 Korea', flag: '🇰🇷' };
    if (rawCountry === 'US' || rawCountry === 'USA') return { code: 'US', nameZh: '美國 USA', flag: '🇺🇸' };
    if (rawCountry === 'CA' || rawCountry === 'CANADA') return { code: 'CA', nameZh: '加拿大 Canada', flag: '🇨🇦' };
    if (rawCountry === 'TH' || rawCountry === 'THAILAND') return { code: 'TH', nameZh: '泰國 Thailand', flag: '🇹🇭' };
    if (rawCountry === 'ID' || rawCountry === 'INDONESIA') return { code: 'ID', nameZh: '印尼 Indonesia', flag: '🇮🇩' };
"""
        content = re.sub(old_pattern, replacement, content, count=1)
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {fpath}")
    else:
        print(f"Already updated {fpath}")
