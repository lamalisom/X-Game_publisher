import re

def fix_ui(file_path, is_en=False):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if not is_en:
        new_buttons = '''      <!-- 國家標籤切換 -->
      <div class="flex flex-wrap items-center gap-2 pt-1 text-xs">
        <span class="text-gray-400 font-bold whitespace-nowrap mr-1 flex items-center gap-1">
          <span>🌐</span> 熱門地區：
        </span>
        <button data-country="ALL" class="country-filter-btn active whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-bold bg-xorange text-white shadow-lg shadow-xorange/20 transition cursor-pointer">🔥 全部國家</button>
        <button data-country="CH" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇨🇭 瑞士</button>
        <button data-country="FR" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇫🇷 法國</button>
        <button data-country="SE" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇸🇪 瑞典</button>
        <button data-country="GB" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇬🇧 英國</button>
        <button data-country="JP" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇯🇵 日本</button>
        <button data-country="KR" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇰🇷 韓國</button>
        <button data-country="HK" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇭🇰 香港</button>
        <button data-country="TW" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇹🇼 台灣</button>
        <button data-country="US" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇺🇸 美國</button>
        <button data-country="CA" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇨🇦 加拿大</button>
        <button data-country="NO" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇳🇴 挪威</button>
        <button data-country="FI" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇫🇮 芬蘭</button>
        <button data-country="TH" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇹🇭 泰國</button>
        <button data-country="ID" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇮🇩 印尼</button>
      </div>'''
    else:
        new_buttons = '''      <!-- Country Filters -->
      <div class="flex flex-wrap items-center gap-2 pt-1 text-xs">
        <span class="text-gray-400 font-bold whitespace-nowrap mr-1 flex items-center gap-1">
          <span>🌐</span> Popular Regions:
        </span>
        <button data-country="ALL" class="country-filter-btn active whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-bold bg-xorange text-white shadow-lg shadow-xorange/20 transition cursor-pointer">🔥 All Countries</button>
        <button data-country="CH" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇨🇭 Switzerland</button>
        <button data-country="FR" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇫🇷 France</button>
        <button data-country="SE" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇸🇪 Sweden</button>
        <button data-country="GB" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇬🇧 UK</button>
        <button data-country="JP" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇯🇵 Japan</button>
        <button data-country="KR" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇰🇷 Korea</button>
        <button data-country="HK" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇭🇰 Hong Kong</button>
        <button data-country="TW" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇹🇼 Taiwan</button>
        <button data-country="US" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇺🇸 USA</button>
        <button data-country="CA" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇨🇦 Canada</button>
        <button data-country="NO" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇳🇴 Norway</button>
        <button data-country="FI" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇫🇮 Finland</button>
        <button data-country="TH" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇹🇭 Thailand</button>
        <button data-country="ID" class="country-filter-btn whitespace-nowrap shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-gray-900/80 text-gray-300 hover:text-white border border-xborder transition hover:border-gray-500 cursor-pointer">🇮🇩 Indonesia</button>
      </div>'''

    content = re.sub(
        r'<!-- (?:國家標籤切換|Country Filters) -->[\s\S]*?</div>\s*</div>\s*<!-- 統計',
        new_buttons + '\n    </div>\n\n    <!-- 統計',
        content
    )

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'✅ Beautified layout in {file_path}')

fix_ui('src/pages/spots/map.astro', is_en=False)
fix_ui('src/pages/spots/map/en.astro', is_en=True)
