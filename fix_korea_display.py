import re
import os
import json

# 1. 修復 map.astro 與 map/en.astro 的 code: 'KR' 欄位與雙重保險
for path in ['src/pages/spots/map.astro', 'src/pages/spots/map/en.astro']:
    if not os.path.exists(path):
        continue
    with open(path, 'r', encoding='utf-8') as f:
        code = f.read()

    # 確保 resolveLocation 回傳 code: 'KR'
    old_ret_1 = "return { flag: '🇰🇷', countryCode: 'KR', countryZH: '韓國', countryEN: 'South Korea', cityZH: city, cityEN: city };"
    new_ret_1 = "return { flag: '🇰🇷', code: 'KR', countryCode: 'KR', countryZH: '韓國', countryEN: 'South Korea', cityZH: city, cityEN: city };"
    code = code.replace(old_ret_1, new_ret_1)

    old_ret_2 = "return { flag: '🇰🇷', countryCode: 'KR', countryZH: 'South Korea', countryEN: 'South Korea', cityZH: city, cityEN: city };"
    new_ret_2 = "return { flag: '🇰🇷', code: 'KR', countryCode: 'KR', countryZH: 'South Korea', countryEN: 'South Korea', cityZH: city, cityEN: city };"
    code = code.replace(old_ret_2, new_ret_2)

    # 確保 countryCode: geo.code 支援 fallback
    code = code.replace("countryCode: geo.code,", "countryCode: geo.code || geo.countryCode || 'KR',")

    with open(path, 'w', encoding='utf-8') as f:
        f.write(code)
    print(f"✅ {path}: 已修復 code: 'KR' 屬性！")

