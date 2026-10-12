# 讀取剛剛寫好的中文版檔案
with open('src/pages/spots/map.astro', 'r', encoding='utf-8') as f:
    zh_content = f.read()

# 修正英文版的正確相對路徑 (3 層 ../)
en_content = zh_content.replace('../../layouts/Layout.astro', '../../../layouts/Layout.astro')
en_content = en_content.replace('../../data/global_spots.json', '../../../data/global_spots.json')

with open('src/pages/spots/map/en.astro', 'w', encoding='utf-8') as f:
    f.write(en_content)

print('✅ Successfully fixed en.astro import paths!')
