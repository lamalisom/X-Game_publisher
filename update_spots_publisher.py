import re
import sys

with open('xgame_publisher.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. init_db 加入 featured_spots 與 used_photos
new_init_db = '''def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posted_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE,
            category TEXT,
            topic_type TEXT,
            posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS used_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id TEXT UNIQUE,
            photo_url TEXT,
            category TEXT,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS featured_spots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spot_name TEXT UNIQUE,
            city TEXT,
            country TEXT,
            category TEXT,
            featured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
'''
old_init = content.find('def init_db():')
old_init_end = content.find('def is_already_posted(', old_init)
if old_init != -1 and old_init_end != -1:
    content = content[:old_init] + new_init_db + '\n' + content[old_init_end:]

# 2. 全球場地與酒店相片推薦引擎
spot_hotel_engine = '''
# ==========================================
# 2.5 GLOBAL SPOTS & HOTELS INTELLIGENCE ENGINE
# ==========================================
TOP_PRESET_SPOTS = {
    "SKATE": [
        {
            "name": "Bondi Skate Park", "city": "Sydney", "country": "Australia", "lat": -33.891, "lng": 151.277,
            "facilities": "3.5 米傳奇深碗池、標準街式階梯扶手、海濱平地滑行訓練區",
            "difficulty": "初階平地至職業碗池全級別",
            "hotels": [{"name": "QT Bondi", "distance": "步行 3 分鐘", "features": "直通沙灘海岸線、專屬滑板與衝浪板存放室、極簡精品設計"}]
        },
        {
            "name": "Venice Beach Skatepark", "city": "Los Angeles", "country": "USA", "lat": 33.987, "lng": -118.473,
            "facilities": "傳奇街頭雙碗池、Snake Run 蛇行起伏道、街式大階梯與 Hubba 大理石滑台",
            "difficulty": "中階至職業選手挑戰級",
            "hotels": [{"name": "Hotel Erwin Venice Beach", "distance": "步行 4 分鐘", "features": "頂樓無敵海景夕陽露台、街頭潮流藝術客房、滑手專屬置物服務"}]
        },
        {
            "name": "Tampa Skatepark (SPoT)", "city": "Tampa", "country": "USA", "lat": 27.979, "lng": -82.428,
            "facilities": "世界級木質室內街式賽道、Pro 級迷你坡道、戶外高難度水泥碗池",
            "difficulty": "全年齡友善至世界巡迴賽高難度",
            "hotels": [{"name": "Hotel Haya", "distance": "車程 8 分鐘", "features": "歷史文化街區精品酒店、寬敞裝備空間、戶外恆溫泳池"}]
        },
        {
            "name": "Komazawa Olympic Skate Park", "city": "Tokyo", "country": "Japan", "lat": 35.626, "lng": 139.661,
            "facilities": "超平整全混凝土路面、金字塔斜台、平桿磨桿、階梯滑台組合",
            "difficulty": "新手練習友善至進階技術流",
            "hotels": [{"name": "Cerulean Tower Tokyu Hotel", "distance": "澀谷站車程 15 分鐘", "features": "俯瞰東京天際線、頂級水療放鬆中心、交通極為便利"}]
        }
    ],
    "CLIMB": [
        {
            "name": "Kletterzentrum Innsbruck", "city": "Innsbruck", "country": "Austria", "lat": 47.269, "lng": 11.404,
            "facilities": "奧運規格攀岩中心、17 米戶外懸挑岩壁、難度賽/速度賽/抱石三項全能牆、600+ 條定線",
            "difficulty": "新手入門至奧運國手極限挑戰",
            "hotels": [{"name": "Hotel Schwarzer Adler", "distance": "車程 5 分鐘", "features": "阿爾卑斯頂級水療 SPA、頂樓三溫暖舒緩肌群、專業設備烘乾存放室"}]
        },
        {
            "name": "Squamish Smoke Bluffs", "city": "Squamish", "country": "Canada", "lat": 49.701, "lng": -123.142,
            "facilities": "花崗岩天然裂隙攀登、經典抱石森林、400+ 條天然傳統攀與運動攀線路",
            "difficulty": "5.7 入門級至 5.14 極限傳統攀",
            "hotels": [{"name": "Executive Suites Hotel & Resort", "distance": "車程 6 分鐘", "features": "壯麗雪山景觀套房、私人陽台、附設戶外運動裝備儲藏室"}]
        },
        {
            "name": "Fontainebleau Forest", "city": "Fontainebleau", "country": "France", "lat": 48.404, "lng": 2.701,
            "facilities": "全球抱石發源地與最高殿堂、天然白砂岩塊、經典黃/藍/紅/黑難度循環標註",
            "difficulty": "全難度覆蓋（Fb 2 至 8C+）",
            "hotels": [{"name": "Aigle Noir Fontainebleau Mgallery", "distance": "車程 10 分鐘", "features": "18 世紀拿破崙時代法式莊園、抱石墊租借諮詢、頂級法式早餐"}]
        }
    ],
    "SURF": [
        {
            "name": "Bells Beach", "city": "Torquay", "country": "Australia", "lat": -38.371, "lng": 144.281,
            "facilities": "傳奇右手礁石定點浪（Right-hand Point Break）、大落差長浪壁、Rip Curl Pro 永久賽場",
            "difficulty": "中高階至職業選手（浪高 4-15 呎）",
            "hotels": [{"name": "RACV Torquay Resort", "distance": "車程 7 分鐘", "features": "俯瞰衝浪海岸線高爾夫度假村、衝浪後恆溫水療按摩池、專屬衝浪板清洗區"}]
        },
        {
            "name": "Supertubos", "city": "Peniche", "country": "Portugal", "lat": 39.345, "lng": -9.362,
            "facilities": "歐洲管浪之都、厚重高速圓管沙灘浪（Beach Break Barrel）、左右雙向開口",
            "difficulty": "進階管浪獵手與世界巡迴賽標準",
            "hotels": [{"name": "MH Peniche", "distance": "步行 8 分鐘", "features": "全海景陽台客房、衝浪學院專業合作、室內溫水泳池與修復桑拿"}]
        },
        {
            "name": "Uluwatu", "city": "Bali", "country": "Indonesia", "lat": -8.814, "lng": 115.088,
            "facilities": "懸崖洞穴天然出海口、多段長浪壁（Temples, The Peak, Racetrack 長管浪）",
            "difficulty": "中高階與管浪狂熱者",
            "hotels": [{"name": "Suarga Padang Padang", "distance": "車程 8 分鐘", "features": "可持續全竹奢華別墅、懸崖海景餐廳、私密無人沙灘通道"}]
        }
    ],
    "BMX": [
        {
            "name": "Adrenaline Alley", "city": "Corby", "country": "UK", "lat": 52.493, "lng": -0.686,
            "facilities": "歐洲最大室內極限運動公園、海綿安全池、木質高拋台、Resi 安全落地軟墊",
            "difficulty": "全等級入門練習至奧運選手備戰",
            "hotels": [{"name": "The Raven Hotel Corby", "distance": "車程 6 分鐘", "features": "英式經典莊園、大型免費停車場、充裕極限單車存放空間"}]
        },
        {
            "name": "Woodward West", "city": "Tehachapi", "country": "USA", "lat": 35.132, "lng": -118.448,
            "facilities": "全球極限運動訓練聖地、MegaRamp 巨型拋台、多座室內外極限街區與土坡場",
            "difficulty": "各階段技巧晉升與職業選手集訓",
            "hotels": [{"name": "Best Western Plus Tehachapi", "distance": "車程 15 分鐘", "features": "山景度假酒店、戶外熱水浴池、充裕高蛋白運動早餐"}]
        }
    ],
    "SNOW": [
        {
            "name": "Whistler Blackcomb", "city": "Whistler", "country": "Canada", "lat": 50.116, "lng": -122.957,
            "facilities": "北美最大地形公園（Highest Level Park）、超大 U 型槽、野雪粉雪樹林區",
            "difficulty": "初學綠道至雙黑鑽職業地形",
            "hotels": [{"name": "Fairmont Chateau Whistler", "distance": "直通滑雪纜車（Ski-in/Ski-out）", "features": "奢華滑雪門房、戶外加熱按摩池、雪具專業保養中心"}]
        },
        {
            "name": "Niseko United (Grand Hirafu)", "city": "Niseko", "country": "Japan", "lat": 42.862, "lng": 140.704,
            "facilities": "全球頂級頂級粉雪（Japow）、夜間夜滑照明、天然野雪樹林區",
            "difficulty": "粉雪愛好者與進階玩家",
            "hotels": [{"name": "Aya Niseko", "distance": "直通雪道（Ski-in/Ski-out）", "features": "天然露天溫泉、專屬雪具儲藏室、全景羊蹄山景觀"}]
        }
    ]
}

def get_daily_featured_spot(category_key="SKATE"):
    cat = category_key.upper() if category_key else "SKATE"
    candidates = []
    
    json_paths = ["src/data/global_spots.json", "data/global_spots.json"]
    for jp in json_paths:
        if os.path.exists(jp):
            try:
                with open(jp, "r", encoding="utf-8") as f:
                    spots = json.load(f)
                    for s in spots:
                        if s.get("category", "").upper() == cat and s.get("name"):
                            candidates.append(s)
                if candidates:
                    print(f"🗺️ 成功從 {jp} 讀取到 {len(candidates)} 個【{cat}】場地資料！")
                    break
            except Exception as e:
                print(f"⚠️ 讀取 {jp} 失敗: {e}")

    featured_history = set()
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT spot_name FROM featured_spots")
        for row in cursor.fetchall():
            if row[0]: featured_history.add(row[0])
        conn.close()
    except Exception:
        pass

    unfeatured_candidates = [s for s in candidates if s.get("name") not in featured_history]
    if unfeatured_candidates:
        chosen = random.choice(unfeatured_candidates)
        s_name = chosen.get("name")
        s_city = chosen.get("city") or chosen.get("country") or "Global"
        s_country = chosen.get("country") or ""
        s_lat = chosen.get("lat") or 0.0
        s_lng = chosen.get("lng") or 0.0
        photos = chosen.get("photos") or []
        spot_img = photos[0] if photos and photos[0].startswith("http") else None
        
        preset_hotels = [{"name": f"{s_city} Boutique Resort", "distance": "車程 5 分鐘", "features": "極限運動裝備存放空間、運動後舒緩泳池、交通便利"}]
        return {
            "name": s_name,
            "city": s_city,
            "country": s_country,
            "lat": s_lat,
            "lng": s_lng,
            "category": cat,
            "spot_photo": spot_img,
            "facilities": "專業滑行道、標準規格坡道與障礙地形、夜間照明與休息維護區",
            "difficulty": "初階入門至進階技術流皆宜",
            "hotels": preset_hotels
        }

    presets = TOP_PRESET_SPOTS.get(cat, TOP_PRESET_SPOTS["SKATE"])
    unfeatured_presets = [p for p in presets if p["name"] not in featured_history]
    chosen = random.choice(unfeatured_presets) if unfeatured_presets else random.choice(presets)
    return {
        "name": chosen["name"],
        "city": chosen["city"],
        "country": chosen["country"],
        "lat": chosen.get("lat", 0.0),
        "lng": chosen.get("lng", 0.0),
        "category": cat,
        "spot_photo": None,
        "facilities": chosen.get("facilities", "世界級標準全規格競技場地"),
        "difficulty": chosen.get("difficulty", "全難度適用"),
        "hotels": chosen.get("hotels", [])
    }

HOTEL_FALLBACK_IMAGES = [
    "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1582719508461-905c673771fd?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1571896349842-33c89424de2d?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1564501049412-61c2a3083791?auto=format&fit=crop&w=1200&q=80"
]

def get_hotel_image(city="Global", hotel_name="Boutique Resort"):
    used_photos = get_used_photos_set()
    pexels_key = clean_token_or_url(os.getenv("PEXELS_API_KEY", ""))
    
    if pexels_key:
        try:
            headers = {"Authorization": pexels_key}
            search_queries = [
                f"luxury boutique hotel room {city}".strip(),
                f"resort hotel interior {city}".strip(),
                f"hotel swimming pool resort {city}".strip(),
                "luxury boutique resort suite interior"
            ]
            for query in search_queries:
                clean_kw = quote(query)
                url = f"https://api.pexels.com/v1/search?query={clean_kw}&per_page=20&orientation=landscape"
                res = requests.get(url, headers=headers, timeout=10).json()
                if res.get("photos"):
                    for photo in res["photos"]:
                        pid = str(photo.get("id"))
                        img_url = extract_clean_url(photo["src"]["large2x"])
                        if pid not in used_photos and img_url not in used_photos:
                            record_used_photo(pid, img_url, "HOTEL")
                            print(f"🏨 Pexels 成功選中【{hotel_name} / {city}】全新未重複酒店相片 (ID: {pid}): {img_url}")
                            return img_url
                        else:
                            print(f"⏩ 略過已重複酒店相片 (ID: {pid})")
        except Exception as e:
            print(f"⚠️ Pexels 酒店相片搜尋異常: {e}")

    for fb in HOTEL_FALLBACK_IMAGES:
        if fb not in used_photos:
            record_used_photo(fb, fb, "HOTEL")
            print(f"🏨 選用未重複備用酒店相片: {fb}")
            return fb

    random_seed = int(time.time()) + 999
    dynamic_url = f"https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1200&q=80&sig={random_seed}"
    record_used_photo(str(random_seed), dynamic_url, "HOTEL")
    return dynamic_url
'''
pos_engine = content.find('# ==========================================\n# 3. GEMINI AI CONTENT ENGINE')
if pos_engine != -1 and 'def get_daily_featured_spot' not in content:
    content = content[:pos_engine] + spot_hotel_engine + '\n' + content[pos_engine:]

# 3. 升級 generate_rich_autonomous_post
new_offline = '''def generate_rich_autonomous_post(category, topic_type, official_img=None, official_yt=None):
    cat = category.upper()
    spot = get_daily_featured_spot(cat)
    s_name = spot["name"]
    s_city = spot["city"]
    s_country = spot["country"]
    s_fac = spot["facilities"]
    s_diff = spot["difficulty"]
    s_hotels = spot.get("hotels", [])
    hotel = s_hotels[0] if s_hotels else {"name": f"{s_city} Boutique Resort", "distance": "車程 5 分鐘", "features": "極限運動裝備存放空間、運動後舒緩泳池、交通便利"}
    h_name = hotel["name"]
    h_dist = hotel["distance"]
    h_feat = hotel["features"]

    gear_map = {
        "SKATE": ("skate shoes pro helmet", "Pro-Tec 經典款雙認證極限滑板安全頭盔", "CPSC & ASTM 雙重安全認證，高抗衝擊 EPS 核心泡沫"),
        "CLIMB": ("climbing shoes chalk bag harness", "La Sportiva Solution Comp 頂級抱石攀岩鞋", "極致下彎鞋弓與足跟包裹力，提供微小晶體岩點強大踩踏支撐"),
        "SURF": ("surfing wetsuit leash traction pad", "Rip Curl Flashbomb 4/3mm 頂級防寒衣", "無縫貼合技術，頂級速乾保暖材質，大浪防護首選"),
        "BMX": ("bmx helmet gloves pads", "Fox Racing Proframe 全罩式輕量極限頭盔", "DH / BMX 賽事指定標準，高透氣整合下巴防護"),
        "SNOW": ("snowboard goggles gloves helmet", "Oakley Flight Deck M 頂級無框滑雪鏡", "Prizm 鏡片技術增強雪道地形對比度，全天候防霧")
    }
    gear_kw, gear_title, gear_reason = gear_map.get(cat, gear_map["SKATE"])

    title = f"🛹 全球極限巡禮：直擊 {s_city} {s_name}！設施全拆解、難度評測與周邊住宿指南"
    subtitle = f"探索全球頂尖 {cat} 朝聖聖地！深入解析核心設施地形、適合難度級別與旅者首選旅宿"

    tg_caption = f"""⚡ 各位 {cat} 極限玩家！今日精選據點速報來襲！

📍 朝聖地標：{s_name} ({s_city}, {s_country})
1️⃣ 🏟️ 核心設施：{s_fac}
2️⃣ 🎯 適合難度：{s_diff}
3️⃣ 🏨 周邊精選住宿：{h_name} ({h_dist})，{h_feat}
4️⃣ 🗺️ 全球地圖直達：https://unanext.fans/spots/map/

💬 你想唔想去朝聖挑戰？即刻話我知！"""

    web_content = f"""### 📍 今日精選極限據點：{s_name}

位於 **{s_country} {s_city}** 的 **{s_name}**，是全球與在地 {cat} 愛好者公認的標誌性極限運動聖地。無論是獨特的地形結構、優質的氣候條件，還是深厚的極限運動文化氛圍，都吸引著無數運動員與旅行者前往朝聖與突破極限。

### 🏟️ 核心設施規格與地形亮點全拆解

本場地在規劃與施工上達到極高標準，能全面滿足技術練習與高難度挑戰需求：
- **主要設施配置**：{s_fac}。
- **地形流暢度**：動線設計兼顧速度維持與安全緩衝，起伏道與障礙銜接極具連貫性，讓玩家能輕鬆串聯連續高難度動作（Lines）。
- **配套設施**：具備良好的周邊視野、休息整備區與安全護欄，為極限愛好者提供舒適專注的訓練空間。

### 🎯 適合技術難度與新手實戰建議

- **難度等級評定**：**{s_diff}**。
- **新手進階指引**：初學者建議避開尖峰時段，在平緩緩衝區熟悉地面反饋；練習高難度動作前請務必佩戴安全頭盔與護具。
- **在地玩家貼士**：早晨與傍晚通常具備最佳溫度與風向條件，是挑戰個人最佳技巧的最佳時機。

### 🏨 周邊精選住宿推薦（極限旅者首選）

出門朝聖頂級運動場地，舒適且便利的休憩之所至關重要：
- **推薦旅宿**：**{h_name}**
- **距離場地**：**{h_dist}**
- **住宿亮點**：{h_feat}。房間環境舒適寬敞，讓你在高強度訓練後能徹底放鬆恢復體力。

### 🗺️ 即刻探索 xGame Radar 全球極限運動地圖

想發掘更多散佈於全球的秘密滑板場、野外岩場、世界級浪點與周邊住宿？
立即點擊進入 👉 **[xGame Radar 全球運動地圖 (https://unanext.fans/spots/map/)](https://unanext.fans/spots/map/)**，探索超過 3,400+ 個經過驗證的專業據點，開啟你的下一場極限冒險！"""

    return {
        "title": title,
        "subtitle": subtitle,
        "city_tag": s_city.upper(),
        "gear_keyword": gear_kw,
        "recommended_gear_title": gear_title,
        "recommended_gear_reason": gear_reason,
        "telegram_caption": tg_caption,
        "website_full_content": web_content,
        "content": tg_caption,
        "topic_type": "SPOT",
        "featured_spot": spot,
        "spot_info": {
            "name": s_name,
            "location": f"{s_city}, {s_country}",
            "difficulty": s_diff,
            "facilities": [s_fac],
            "map_url": "https://unanext.fans/spots/map/"
        },
        "hotel_info": {
            "hotel_name": h_name,
            "distance": h_dist,
            "features": h_feat
        },
        "youtube_video_id": official_yt or "jTVcRSq8IYk",
        "youtube_video_title": f"{s_name} Action Highlights",
        "official_cover_image": official_img or spot.get("spot_photo")
    }
'''
s_off = content.find('def generate_rich_autonomous_post(')
e_off = content.find('def generate_xgame_content(', s_off)
if s_off != -1 and e_off != -1:
    content = content[:s_off] + new_offline + '\n' + content[e_off:]

# 4. 升級 generate_xgame_content
new_gen_content = '''def generate_xgame_content(category_key="", topic_type="", topic_desc="", target_lang="zh-hk"):
    api_key = clean_token_or_url(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "")
    if api_key:
        masked = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "***"
        print(f"🔑 已載入 GEMINI_API_KEY ({masked}, 長度 {len(api_key)})")
    else:
        print("⚠️ 未檢測到 GEMINI_API_KEY，將啟用極限運動智慧知識庫生成深度專題！")

    if not category_key or not category_key.strip():
        category_key = random.choice(list(XGAME_CATEGORIES.keys()))
    display_category = category_key.strip().upper()

    rss_context, official_img, official_yt = fetch_latest_rss_news(display_category)

    featured_spot = get_daily_featured_spot(display_category)
    active_topic = "SPOT"
    active_title = f"🛹 全球頂級極限場地與住宿巡禮: {featured_spot['name']}"

    if api_key:
        lang_map = {
            "zh-hk": "繁體中文（廣東話/香港口語，語氣熱血且極具社群吸引力）",
            "zh-cn": "簡體中文（專業熱血的極限運動社群口吻）",
            "ja": "日文（專業且地道的極限運動風格）",
            "en": "英文（Authentic Action Sports Community Style）"
        }
        selected_lang_desc = lang_map.get(target_lang, lang_map["zh-hk"])

        prompt = f"""
你是一位專注於全球極限運動與戶外旅行地圖的專業主編 Una (@Una_next)。
今日核心專欄任務：【全球極限運動場地巡禮與周邊住宿全攻略 (Daily Spot & Nearby Hotels Guide)】
全力宣傳與推廣官方全球極限運動地圖：https://unanext.fans/spots/map/

【今日精選運動場地資訊】:
- 場地名稱：{featured_spot['name']}
- 所在城市與國家：{featured_spot['city']}, {featured_spot['country']}
- 運動項目類別：{display_category}
- 場地核心設施：{featured_spot['facilities']}
- 難度等級參考：{featured_spot['difficulty']}
{rss_context}

【任務要求】:
請生成一篇具備深度專業度、極限運動熱血感、同時極具旅行指南實用價值的文章資料，語言格式：完全使用 **{selected_lang_desc}**。
必須以嚴格的 JSON 格式回傳（請勿輸出額外 Markdown 區塊或多餘文字），包含以下欄位：

{{
  "title": "精煉且具震撼力的封面主標題（嚴禁換行與【】符號，包含場地名稱與城市，約 22-38 字，例如：🛹 澳洲雪梨 Bondi Skate Park 極限朝聖：碗池設施全拆解、難度評測與海景酒店精選）",
  "subtitle": "副標題或一句話亮點總結（嚴禁換行，約 30-55 字，涵蓋設施特色、技術挑戰與周邊住宿推薦）",
  "city_tag": "{featured_spot['city'].upper() if featured_spot['city'] else 'GLOBAL'}",
  "gear_keyword": "純英文推薦裝備搜尋關鍵字（例如: skate shoes pro / climbing shoes / surfing wetsuit，嚴禁中文）",
  "spot_info": {{
    "name": "{featured_spot['name']}",
    "location": "{featured_spot['city']}, {featured_spot['country']}",
    "difficulty": "初階入門 / 中階進階 / 職業挑戰級（詳細分析適合哪類滑手/攀爬者/衝浪者）",
    "facilities": ["核心設施1（如深碗池/大階梯/抱石牆規格）", "核心設施2（如夜間照明/器材租借）", "核心設施3"],
    "features": ["亮點特色1", "亮點特色2"],
    "insider_tips": "在地玩家私房貼士（如最佳練習時段、防護建議等）",
    "map_url": "https://unanext.fans/spots/map/"
  }},
  "hotel_info": {{
    "hotel_name": "真實推薦的附近高品質/特色酒店名稱（1間最具代表性酒店）",
    "distance": "距離場地步行或車程（例如：步行 3 分鐘 / 車程 5 分鐘）",
    "features": "住宿亮點（例如：極限裝備存放專區、運動後放鬆按摩水療 SPA、無敵景觀客房）",
    "price_range": "中高性價比 / 輕奢精品 / 度假村"
  }},
  "telegram_caption": "【📱 Telegram 社群專用速報短文】：約 120-180 字，極致精練熱血！以 Emoji 列點總結：\\\\n1️⃣ 🏟️ 場地設施規格\\\\n2️⃣ 🎯 適合技術難度\\\\n3️⃣ 🏨 附近精選住宿\\\\n4️⃣ 🗺️ 官方地圖直達 https://unanext.fans/spots/map/\\\\n帶有強烈社群互動號召！",
  "website_full_content": "【🌐 官方網站長篇深度專題】：約 550-800 字，結構化 Markdown 排版，包含以下章節：\\\\n### 📍 今日精選極限據點：{featured_spot['name']}\\\\n### 🏟️ 核心設施規格與地形亮點全拆解\\\\n### 🎯 適合技術難度與新手實戰建議\\\\n### 🏨 周邊精選住宿推薦（極限旅者首選）\\\\n### 🗺️ 即刻探索 xGame Radar 全球極限運動地圖\\\\n（在文末熱情號召讀者點擊 https://unanext.fans/spots/map/ 探索全球 3,400+ 個經過驗證的極限運動據點！）",
  "content": "保留備用字段（填入 telegram_caption）",
  "topic_type": "SPOT",
  "recommended_gear_title": "Amazon 推薦商品中文標題",
  "recommended_gear_reason": "推薦理由"
}}
"""
        print(f"🤖 今日專欄: 【{active_title}】，正在呼叫 Gemini API 生成深度專題...")
        
        available_models = []
        try:
            list_res = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}", timeout=10)
            if list_res.status_code == 200:
                models_data = list_res.json().get("models", [])
                for m in models_data:
                    if "generateContent" in m.get("supportedGenerationMethods", []):
                        m_name = m["name"].replace("models/", "")
                        if "gemini" in m_name:
                            available_models.append(m_name)
        except Exception:
            pass

        if not available_models:
            available_models = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-2.0-flash-exp", "gemini-1.5-pro"]

        for model_name in available_models:
            for api_ver in ["v1beta", "v1"]:
                url = f"https://generativelanguage.googleapis.com/{api_ver}/models/{model_name}:generateContent?key={api_key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.4}
                }
                try:
                    res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
                    if res.status_code == 200:
                        data = res.json()
                        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw_text)
                        if json_match:
                            raw_text = json_match.group(1).strip()
                        start = raw_text.find('{')
                        end = raw_text.rfind('}')
                        if start != -1 and end != -1:
                            raw_text = raw_text[start:end+1]
                        
                        parsed = json.loads(raw_text)
                        if parsed and isinstance(parsed, dict) and parsed.get("title"):
                            parsed["title"] = sanitize_single_line_text(parsed.get("title", ""))
                            parsed["subtitle"] = sanitize_single_line_text(parsed.get("subtitle", ""))
                            parsed["city_tag"] = sanitize_single_line_text(parsed.get("city_tag", featured_spot["city"].upper()))
                            parsed["featured_spot"] = featured_spot
                            if official_img:
                                parsed["official_cover_image"] = official_img
                            if official_yt:
                                parsed["youtube_video_id"] = official_yt
                            print(f"✅ Google API [{model_name}] 成功生成高質量專題: {parsed.get('title')}")
                            return parsed
                except Exception:
                    pass

    print(f"⚡ 啟用極限運動精選知識庫生成【{display_category}】深度專題...")
    offline_post = generate_rich_autonomous_post(display_category, active_topic, official_img, official_yt)
    offline_post["featured_spot"] = featured_spot
    return offline_post
'''
s_gen = content.find('def generate_xgame_content(')
e_gen = content.find('def attach_affiliate_link(', s_gen)
if s_gen != -1 and e_gen != -1:
    content = content[:s_gen] + new_gen_content + '\n' + content[e_gen:]

# 5. frontmatter 支援 hotel_info
target_fm = 'if post_data.get("spot_info") and isinstance(post_data["spot_info"], dict) and post_data["spot_info"].get("name"):\n        frontmatter_dict["spot_info"] = post_data["spot_info"]'
replacement_fm = '''if post_data.get("spot_info") and isinstance(post_data["spot_info"], dict) and post_data["spot_info"].get("name"):
        frontmatter_dict["spot_info"] = post_data["spot_info"]

    if post_data.get("hotel_info") and isinstance(post_data["hotel_info"], dict) and post_data["hotel_info"].get("hotel_name"):
        frontmatter_dict["hotel_info"] = post_data["hotel_info"]'''
if target_fm in content and 'frontmatter_dict["hotel_info"]' not in content:
    content = content.replace(target_fm, replacement_fm)

# 6. main_async 全流程整合
new_main_async = '''async def main_async():
    print("🚀 啟動 xGame Radar Magazine 全自動化發布引擎...")
    init_db()

    category_arg = sys.argv[1] if len(sys.argv) > 1 else ""
    lang_arg = sys.argv[2] if len(sys.argv) > 2 else "zh-hk"
    topic_arg = sys.argv[3] if len(sys.argv) > 3 else ""

    category = category_arg.strip().upper() if category_arg and category_arg.upper() != "AUTO" else random.choice(list(XGAME_CATEGORIES.keys()))

    # 1. AI 內容與結構化資料生成 (場地 + 附近住宿 + 難度設施)
    post_data = generate_xgame_content(category_key=category, topic_type=topic_arg, target_lang=lang_arg)
    featured_spot = post_data.get("featured_spot") or get_daily_featured_spot(category)
    spot_info = post_data.get("spot_info", {})
    hotel_info = post_data.get("hotel_info", {})

    spot_name = spot_info.get("name") or featured_spot.get("name", "極限運動場地")
    hotel_name = hotel_info.get("hotel_name") or (featured_spot.get("hotels", [{}])[0].get("name") if featured_spot.get("hotels") else "周邊推薦旅宿")

    title = post_data.get("title", f"{category} 極限場地巡禮")
    subtitle = post_data.get("subtitle", "")
    content = post_data.get("content", "")
    city_tag = post_data.get("city_tag", featured_spot.get("city", "GLOBAL").upper())
    gear_kw = post_data.get("gear_keyword", "extreme sports gear")
    topic_type = post_data.get("topic_type", "SPOT")

    if is_already_posted(title):
        now_time = datetime.now().strftime("%H:%M")
        title = f"{title} (Vol. {now_time})"
        post_data["title"] = title

    # 2. 提取文案
    tg_caption = post_data.get("telegram_caption") or post_data.get("content", "")
    web_content = post_data.get("website_full_content") or post_data.get("content", "")

    today_date_str = datetime.now().strftime("%Y-%m-%d")
    clean_slug = re.sub(r'[^a-zA-Z0-9]', '_', city_tag.lower())[:15]
    if not clean_slug or clean_slug == "_":
        clean_slug = "global"
    post_slug = f"{today_date_str}_{category.lower()}_{clean_slug}"
    post_web_url = f"https://unanext.fans/posts/{post_slug}/"
    amazon_search_url = f"https://www.amazon.com/s?k={quote(gear_kw)}&tag={AMAZON_AFFILIATE_ID}"

    # 3. 獲取場地與酒店相片 (防重複過濾)
    official_img = post_data.get("official_cover_image") or featured_spot.get("spot_photo")
    source_label = "Official Spot / OSM" if official_img else "Editorial / Action Sports"
    bg_image = official_img if official_img else get_action_sports_image(f"{spot_name} {city_tag}", category)
    hotel_image = get_hotel_image(city_tag, hotel_name)

    # 4. 在文章中注入酒店相片與全球地圖推廣 Banner
    if hotel_image:
        hotel_embed = f"\\n\\n![{hotel_name}]({hotel_image})\\n*▲ 周邊精選住宿推薦：{hotel_name}*\\n"
        if "### 🏨 周邊精選住宿推薦" in web_content:
            web_content = web_content.replace("### 🏨 周邊精選住宿推薦", f"### 🏨 周邊精選住宿推薦{hotel_embed}")
        else:
            web_content += f"\\n\\n{hotel_embed}"

    map_promo_banner = """

---

> 🗺️ **探索更多全球極限運動場地與周邊住宿**  
> 想發掘更多身邊的滑板場、攀岩館、衝浪點與旅宿？立即前往 [xGame Radar 全球運動地圖 (https://unanext.fans/spots/map/)](https://unanext.fans/spots/map/)，一鍵探索全球超過 3,400+ 個經過官方驗證的專業極限運動據點！
"""
    if "https://unanext.fans/spots/map/" not in web_content:
        web_content += map_promo_banner

    monetized_web_content = attach_affiliate_link(web_content, gear_kw, category)
    post_data["category"] = category
    post_data["content"] = monetized_web_content

    if not post_data.get("youtube_video_id"):
        yt_id, yt_title = search_embeddable_youtube_video(title, category)
        post_data["youtube_video_id"] = yt_id
        post_data["youtube_video_title"] = yt_title

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    card_filename = f"xgame_{timestamp}.png"

    # 5. Playwright 生成 1080x1080 社群卡片
    await render_card_image_async(title, subtitle, city_tag, bg_image, card_filename)

    # 6. 上傳至 Cloudflare R2
    r2_img_url = upload_to_r2(card_filename, f"cards/{card_filename}")
    img_link_for_record = r2_img_url if r2_img_url else bg_image

    # 7. JSON 備份
    json_filename = f"{timestamp}_{category}.json"
    backup_payload = {
        "id": timestamp,
        "title": title,
        "subtitle": subtitle,
        "category": category,
        "topic_type": topic_type,
        "content": monetized_web_content,
        "telegram_caption": tg_caption,
        "spot_info": spot_info,
        "hotel_info": hotel_info,
        "image_url": img_link_for_record,
        "hotel_image_url": hotel_image,
        "created_at": datetime.now().isoformat(),
        "author": "Una (@Una_next)"
    }
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(backup_payload, f, ensure_ascii=False, indent=2)
    upload_to_r2(json_filename, f"posts/{json_filename}")

    # 8. 儲存至 Astro 靜態網站
    save_post_as_markdown(post_data, img_link_for_record, source_label)

    # 9. 推送至 Telegram 頻道 (帶地圖直達連結)
    tg_message = (
        f"🏆 *{title}*\\n"
        f"⚡ _{subtitle}_\\n\\n"
        f"{tg_caption}\\n\\n"
        f"🗺️ *xGame Radar 全球運動地圖*:\\n"
        f"👉 [點擊直達探索 3,400+ 場地與周邊旅宿](https://unanext.fans/spots/map/)\\n\\n"
        f"🛒 *Una 裝備推薦*:\\n"
        f"👉 [{gear_kw.title()} Amazon 直送門市]({amazon_search_url})\\n\\n"
        f"🌐 *閱讀本期完整深度專題*:\\n"
        f"👉 [點擊進入 xGame Magazine 官方專題]({post_web_url})\\n\\n"
        f"#xGameRadar #{category} #SpotsMap #Una_next"
    )
    send_telegram_post(tg_message, image_path=card_filename)

    # 10. 記錄於 SQLite 並清理暫存檔
    record_posted_article(title, category, topic_type)
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO featured_spots (spot_name, city, country, category) VALUES (?, ?, ?, ?)",
                       (featured_spot.get('name'), featured_spot.get('city'), featured_spot.get('country'), category))
        conn.commit()
        conn.close()
        print(f"📌 已記錄今日精選場地至資料庫: {featured_spot.get('name')}")
    except Exception as e:
        print(f"⚠️ 記錄 featured_spots 失敗: {e}")

    if os.path.exists(card_filename):
        os.remove(card_filename)
    if os.path.exists(json_filename):
        os.remove(json_filename)

    print("🎉 xGame Radar Magazine 今日自動化發布與網站文章生成圓滿完成！")

if __name__ == "__main__":
    asyncio.run(main_async())
'''
m_start = content.find('async def main_async():')
if m_start != -1:
    content = content[:m_start] + new_main_async

with open('xgame_publisher.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ xgame_publisher.py 升級成功！")
