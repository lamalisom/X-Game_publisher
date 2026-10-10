
def get_r2_history(r2_client, bucket_name):
    """從 Cloudflare R2 讀取已發布的歷史文章與圖片清單"""
    history = {'titles': set(), 'images': set(), 'slugs': set()}
    if not r2_client or not bucket_name:
        return history
    try:
        paginator = r2_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket_name, Prefix='posts/'):
            for obj in page.get('Contents', []):
                key = obj.get('Key', '')
                history['slugs'].add(key.replace('posts/', '').replace('.json', ''))
        for page in paginator.paginate(Bucket=bucket_name, Prefix='cards/'):
            for obj in page.get('Contents', []):
                key = obj.get('Key', '')
                history['images'].add(key.replace('cards/', ''))
        print(f"📡 從 Cloudflare R2 成功同步歷史資料庫：{len(history['slugs'])} 篇文章, {len(history['images'])} 張歷史圖片")
    except Exception as e:
        print(f"⚠️ 讀取 R2 歷史記錄失敗 (將使用本地比對): {e}")
    return history
#!/usr/bin/env python3
import os
import re
import sys
import json
import random
import sqlite3
import base64
import requests
import asyncio
import time
from datetime import datetime
from urllib.parse import quote, urlparse

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import boto3
except ImportError:
    boto3 = None

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None

# ==========================================
# 0. CONFIG & SANITIZER UTILS
# ==========================================
def clean_token_or_url(val):
    """徹底清理 Token 與字串，移除所有括號、中括號、引號與多餘空白"""
    if not val:
        return ""
    return re.sub(r'[\[\]\(\)\'"]', '', str(val)).strip()

def extract_clean_url(url_str):
    """精準萃取完整 HTTP/HTTPS 網址，不截斷域名"""
    if not url_str:
        return ""
    match = re.search(r'https?://[^\s\"\'\]\)]+', str(url_str))
    if match:
        clean_u = match.group(0)
        return clean_u.rstrip('.,;)]}')
    return clean_token_or_url(url_str)

def sanitize_single_line_text(val):
    """清理標題與副標，去除換行與多餘前後引號"""
    if not val:
        return ""
    cleaned = str(val).replace('\r', ' ').replace('\n', ' ').strip()
    return re.sub(r'\s+', ' ', cleaned)

def url_to_base64(image_url):
    clean_url = extract_clean_url(image_url)
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(clean_url, headers=headers, timeout=12)
        res.raise_for_status()
        encoded = base64.b64encode(res.content).decode("utf-8")
        print(f"🖼️ Base64 轉換成功！長度: {len(encoded)}")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception as e:
        print(f"⚠️ 圖片 Base64 轉換失敗 ({clean_url}): {e}")
        return clean_url

AMAZON_AFFILIATE_ID = clean_token_or_url(os.getenv("AMAZON_AFFILIATE_ID", "kait02bc-20"))

XGAME_CATEGORIES = {
    "SKATE": "https://www.skateboarding.com/rss",
    "CLIMB": "https://www.climbing.com/feed/",
    "BMX": "https://fatbmx.com/bmx-news?format=feed&type=rss",
    "SURF": "https://www.surfer.com/.rss/full/",
    "SNOW": "https://www.snowboarder.com/.rss/full/"
}

DEFAULT_GEAR_KEYWORDS = {
    "SKATE": "skateboarding shoes helmet protective gear",
    "CLIMB": "climbing shoes chalk bag harness",
    "BMX": "bmx helmet gloves pads",
    "SURF": "surfing wetsuit leash traction pad",
    "SNOW": "snowboard goggles gloves helmet"
}

# ==========================================
# 1. SQLITE ANTI-DUPLICATION DATABASE
# ==========================================
DB_FILE = "xgame_radar.db"

def init_db():
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

def is_already_posted(title):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM posted_articles WHERE title = ?', (title,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def record_posted_article(title, category, topic_type="GENERAL"):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO posted_articles (title, category, topic_type) VALUES (?, ?, ?)',
            (title, category, topic_type)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

# ==========================================
# 2. OFFICIAL SITE MEDIA SCRAPER & RSS PARSER
# ==========================================
def scrape_official_media(article_url):
    """從官方網站文章連結中解析 OpenGraph 高清圖片 (og:image) 與 YouTube 官方影片"""
    if not article_url or not article_url.startswith("http"):
        return None, None

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(article_url, headers=headers, timeout=8)
        if res.status_code == 200:
            img_url = None
            youtube_id = None

            if BeautifulSoup:
                soup = BeautifulSoup(res.text, "html.parser")
                og_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
                if og_img and og_img.get("content"):
                    img_url = extract_clean_url(og_img["content"])
                
                yt_iframe = soup.find("iframe", src=re.compile(r"youtube\.com|youtu\.be"))
                if yt_iframe and yt_iframe.get("src"):
                    yt_match = re.search(r"(?:embed/|v/|watch\?v=)([\w-]{11})", yt_iframe["src"])
                    if yt_match:
                        youtube_id = yt_match.group(1)
            else:
                # 無 bs4 時的純正則表達式備案 (100% 零依賴保障)
                og_match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', res.text, re.IGNORECASE) or \
                           re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', res.text, re.IGNORECASE) or \
                           re.search(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', res.text, re.IGNORECASE)
                if og_match:
                    img_url = extract_clean_url(og_match.group(1))

                yt_match = re.search(r'(?:youtube\.com/(?:embed/|watch\?v=)|youtu\.be/)([\w-]{11})', res.text)
                if yt_match:
                    youtube_id = yt_match.group(1)

            if img_url or youtube_id:
                print(f"🎯 成功從官方來源抓取媒體：圖片={bool(img_url)}, 影片ID={youtube_id}")
            return img_url, youtube_id
    except Exception as e:
        print(f"⚠️ 官方頁面媒體解析跳過 ({article_url[:40]}...): {e}")

def search_embeddable_youtube_video(query, category_key="SKATE"):
    """自動搜尋並透過 YouTube oEmbed API 驗證 100% 可外嵌播放的官方極限運動影片"""
    try:
        search_query = f"{query} extreme sports official"
        url = f"https://www.youtube.com/results?search_query={quote(search_query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res = requests.get(url, headers=headers, timeout=6)
        if res.status_code == 200:
            vids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', res.text)
            for vid in vids[:6]:
                oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
                o_res = requests.get(oembed_url, timeout=3)
                if o_res.status_code == 200:
                    data = o_res.json()
                    title = data.get("title", f"{category_key} Official Action")
                    print(f"🎬 自動成功配對 YouTube 官方精華 [{vid}]: {title[:40]}")
                    return vid, title
    except Exception as e:
        print(f"⚠️ YouTube 影片自動搜尋跳過: {e}")

    fallback_map = {
        "SKATE": ("4YYTNkAdDD8", "Tony Hawk Lands FIRST-EVER 900 | World of X Games"),
        "BMX": ("E-VClAvTgSU", "Best of Logan Martin | Men BMX Freestyle Paris 2024 Highlights"),
        "SURF": ("26KzUnEbTUs", "Surfing the Heaviest Wave in the World - Teahupoo"),
        "CLIMB": ("jTVcRSq8IYk", "Janja Garnbret: The Lioness | Climbing Gold Highlights"),
        "SNOW": ("he03dVkhLTM", "Shaun White Snowboard Halfpipe Gold | PyeongChang 2018"),
        "EVENT": ("riO1y-xyWek", "Men Skateboard Street Best Trick at X Games California"),
        "SPOT": ("zJL5IVvDx1k", "Battle At The Berrics - BATB Highlights"),
        "SAFETY": ("acOvWo88a4w", "How to Kickflip Tutorial & Safety Guide"),
        "TRICKS": ("acOvWo88a4w", "How to Kickflip Tutorial & Safety Guide")
    }
    return fallback_map.get(category_key.upper(), fallback_map["SKATE"])

def fetch_latest_rss_news(category_key):
    rss_url = XGAME_CATEGORIES.get(category_key.upper())
    if not rss_url:
        return "", None, None

    official_img = None
    official_video_id = None
    articles = []

    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:3]:
            title = entry.get('title', '')
            summary = entry.get('summary', entry.get('description', ''))
            clean_summary = re.sub('<[^<]+?>', '', summary)[:160]
            link = entry.get('link', '')

            articles.append(f"- {title}: {clean_summary} (來源: {link})")

            if not official_img:
                if 'media_content' in entry and len(entry['media_content']) > 0:
                    official_img = entry['media_content'][0].get('url')
                elif 'media_thumbnail' in entry and len(entry['media_thumbnail']) > 0:
                    official_img = entry['media_thumbnail'][0].get('url')
                elif 'enclosures' in entry and len(entry['enclosures']) > 0:
                    official_img = entry['enclosures'][0].get('href')
                
                if not official_img and link:
                    scraped_img, scraped_yt = scrape_official_media(link)
                    if scraped_img:
                        official_img = scraped_img
                    if scraped_yt:
                        official_video_id = scraped_yt

        if articles:
            context_text = "【最新官方 RSS 參考新聞】:\n" + "\n".join(articles)
            return context_text, official_img, official_video_id
    except Exception as e:
        print(f"⚠️ RSS 抓取失敗 ({category_key}): {e}")

    return "", None, None


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

# ==========================================
# 3. GEMINI AI CONTENT ENGINE (RICH PILLARS)
# ==========================================
def generate_rich_autonomous_post(category, topic_type, official_img=None, official_yt=None):
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

def generate_xgame_content(category_key="", topic_type="", topic_desc="", target_lang="zh-hk"):
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
  "telegram_caption": "【📱 Telegram 社群專用速報短文】：約 120-180 字，極致精練熱血！以 Emoji 列點總結：\\n1️⃣ 🏟️ 場地設施規格\\n2️⃣ 🎯 適合技術難度\\n3️⃣ 🏨 附近精選住宿\\n4️⃣ 🗺️ 官方地圖直達 https://unanext.fans/spots/map/\\n帶有強烈社群互動號召！",
  "website_full_content": "【🌐 官方網站長篇深度專題】：約 550-800 字，結構化 Markdown 排版，包含以下章節：\\n### 📍 今日精選極限據點：{featured_spot['name']}\\n### 🏟️ 核心設施規格與地形亮點全拆解\\n### 🎯 適合技術難度與新手實戰建議\\n### 🏨 周邊精選住宿推薦（極限旅者首選）\\n### 🗺️ 即刻探索 xGame Radar 全球極限運動地圖\\n（在文末熱情號召讀者點擊 https://unanext.fans/spots/map/ 探索全球 3,400+ 個經過驗證的極限運動據點！）",
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

def attach_affiliate_link(content_text, gear_keyword, category_key):
    clean_kw = re.sub(r'[^a-zA-Z0-9\s]', '', gear_keyword).strip()
    if not clean_kw or len(clean_kw) < 2:
        clean_kw = DEFAULT_GEAR_KEYWORDS.get(category_key.upper(), "extreme sports gear")

    encoded_kw = quote(clean_kw)
    amazon_url = f"https://www.amazon.com/s?k={encoded_kw}&tag={AMAZON_AFFILIATE_ID}"
    display_name = clean_kw.title()

    affiliate_block = (
        f"\n\n🛒 *Una 裝備選購建議*:\n"
        f"👉 [{display_name} Amazon 直送門市]({amazon_url})\n"
        f"*(透過連結購買可支持本頻道與網站運作)*"
    )
    return content_text + affiliate_block

# ==========================================
# 5. ACTION SPORTS IMAGE REPOSITORY & PEXELS FETCHER
# ==========================================
CATEGORY_ACTION_IMAGES = {
    "SKATE": [
        "https://images.unsplash.com/photo-1516762689617-e1cffcef479d?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1547447134-cd3f5c716030?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1564769662533-4f00a87b4056?auto=format&fit=crop&w=1200&q=80"
    ],
    "BMX": [
        "https://images.unsplash.com/photo-1508780709619-79562169bc64?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1576435728678-68d0fbf94e91?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1508780709619-79562169bc64?auto=format&fit=crop&w=1200&q=80"
    ],
    "SURF": [
        "https://images.unsplash.com/photo-1502680390469-be75c86b636f?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1459749411175-04bf5292ceea?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80"
    ],
    "CLIMB": [
        "https://images.unsplash.com/photo-1522163182402-834f871fd851?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1564769662533-4f00a87b4056?auto=format&fit=crop&w=1200&q=80"
    ],
    "SNOW": [
        "https://images.unsplash.com/photo-1551698618-1dfe5d97d256?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1491553895911-0055eca6402d?auto=format&fit=crop&w=1200&q=80"
    ],
    "EVENT": [
        "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1508780709619-79562169bc64?auto=format&fit=crop&w=1200&q=80"
    ],
    "SPOT": [
        "https://images.unsplash.com/photo-1564769662533-4f00a87b4056?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1516762689617-e1cffcef479d?auto=format&fit=crop&w=1200&q=80"
    ],
    "SAFETY": [
        "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1547447134-cd3f5c716030?auto=format&fit=crop&w=1200&q=80"
    ]
}

def get_used_photos_set():
    """從資料庫與 Markdown 檔案中收集所有已使用過的照片 URL / ID"""
    used = set()
    # 1. 從 SQLite 讀取
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT photo_id, photo_url FROM used_photos")
        for pid, purl in cursor.fetchall():
            if pid: used.add(str(pid))
            if purl: used.add(purl)
        conn.close()
    except Exception as e:
        print(f"⚠️ 讀取 used_photos 失敗: {e}")

    # 2. 從 posts 目錄掃描
    import glob
    for md_file in glob.glob("src/content/posts/*.md"):
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                txt = f.read()
                for line in txt.splitlines():
                    if line.startswith("cover_image:"):
                        val = line.split("cover_image:", 1)[1].strip().strip('"').strip("'")
                        if val: used.add(val)
                    elif "![" in line and "](<" in line:
                        m_url = line.split("](", 1)[1].split(")", 1)[0].strip()
                        if m_url.startswith("http"): used.add(m_url)
        except Exception:
            pass
    return used

def record_used_photo(photo_id, photo_url, category):
    """記錄已使用的照片"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO used_photos (photo_id, photo_url, category) VALUES (?, ?, ?)", (str(photo_id), photo_url, category))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ 記錄照片失敗: {e}")

def get_action_sports_image(keyword, category_key="SKATE"):
    cat = category_key.upper() if category_key else "SKATE"
    used_photos = get_used_photos_set()
    print(f"🛡️ 目前已使用過的照片資料庫：共 {len(used_photos)} 張，將自動排除重複。")

    pexels_key = clean_token_or_url(os.getenv("PEXELS_API_KEY", ""))
    if pexels_key:
        try:
            headers = {"Authorization": pexels_key}
            search_queries = [
                f"{cat.lower()} action sports {keyword}".strip(),
                f"{cat.lower()} extreme sports professional",
                f"{cat.lower()} competition athlete",
                f"{cat.lower()} trick outdoor",
            ]
            
            for query in search_queries:
                clean_keyword = quote(query)
                # 抓取 20 張候選照片以供去重篩選
                url = f"https://api.pexels.com/v1/search?query={clean_keyword}&per_page=20&orientation=landscape"
                res = requests.get(url, headers=headers, timeout=10).json()
                
                if res.get("photos"):
                    for photo in res["photos"]:
                        pid = str(photo.get("id"))
                        img_url = extract_clean_url(photo["src"]["large2x"])
                        
                        # 檢查照片 ID 與 URL 是否曾被使用
                        if pid not in used_photos and img_url not in used_photos:
                            record_used_photo(pid, img_url, cat)
                            print(f"✅ Pexels 成功選中【{cat}】全新未重複相片 (ID: {pid}): {img_url}")
                            return img_url
                        else:
                            print(f"⏩ 略過已重複相片 (ID: {pid})")
        except Exception as e:
            print(f"⚠️ Pexels 搜尋異常: {e}")

    # 備用高品質動態相片庫
    fallback_pool = CATEGORY_ACTION_IMAGES.get(cat, CATEGORY_ACTION_IMAGES.get("SKATE", []))
    for fb_url in fallback_pool:
        if fb_url not in used_photos:
            record_used_photo(fb_url, fb_url, cat)
            print(f"📸 選用【{cat}】未重複備用相片: {fb_url}")
            return fb_url

    # 若備用庫全部用過，使用動態亂數種子生成唯一定製圖
    random_seed = int(time.time())
    dynamic_url = f"https://images.unsplash.com/photo-1516762689617-e1cffcef479d?auto=format&fit=crop&w=1200&q=80&sig={random_seed}"
    record_used_photo(str(random_seed), dynamic_url, cat)
    return dynamic_url

async def render_card_image_async(title, subtitle, tag_city, bg_image_url, output_path):
    bg_base64 = url_to_base64(bg_image_url).replace("'", "%27")

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <style>
        body {{ margin: 0; padding: 0; width: 1080px; height: 1080px; display: flex; justify-content: center; align-items: center; background: #000; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .card {{ width: 1080px; height: 1080px; position: relative; background-image: url('{bg_base64}'); background-size: cover; background-position: center; display: flex; flex-direction: column; justify-content: space-between; padding: 75px; box-sizing: border-box; }}
        .overlay {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(180deg, rgba(8,8,10,0.4) 0%, rgba(8,8,10,0.88) 100%); z-index: 1; }}
        .content {{ position: relative; z-index: 2; height: 100%; display: flex; flex-direction: column; justify-content: space-between; }}
        .top-bar {{ display: flex; justify-content: space-between; align-items: center; }}
        .badge {{ background: #ff4d00; color: #fff; padding: 10px 24px; font-weight: 900; font-size: 22px; border-radius: 30px; text-transform: uppercase; letter-spacing: 2px; box-shadow: 0 0 20px rgba(255,77,0,0.5); }}
        .location {{ color: #ffffff; font-size: 22px; font-weight: 700; opacity: 0.95; }}
        .main-title {{ color: #ffffff; font-size: 58px; font-weight: 900; line-height: 1.25; margin-bottom: 20px; text-shadow: 0 4px 16px rgba(0,0,0,0.8); }}
        .subtitle {{ color: #00f2fe; font-size: 26px; font-weight: 700; line-height: 1.4; margin-bottom: 15px; }}
        .author {{ color: #ff4d00; font-size: 26px; font-weight: 800; display: flex; align-items: center; gap: 10px; }}
        .footer {{ display: flex; justify-content: space-between; align-items: flex-end; border-top: 1px solid rgba(255,255,255,0.25); padding-top: 25px; }}
        .sub-tag {{ color: #cccccc; font-size: 20px; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600; }}
    </style>
    </head>
    <body>
        <div class="card">
            <div class="overlay"></div>
            <div class="content">
                <div class="top-bar">
                    <div class="badge">xGame Radar</div>
                    <div class="location">【{tag_city}】</div>
                </div>
                <div>
                    <div class="subtitle">⚡ {subtitle}</div>
                    <div class="main-title">🏆 {title}</div>
                    <div class="author">By Una (@Una_next)</div>
                </div>
                <div class="footer">
                    <div class="sub-tag">Global Extreme Sports Magazine</div>
                    <div class="sub-tag">{tag_city} · RADAR</div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1080, "height": 1080})
        await page.set_content(html_template)
        await page.screenshot(path=output_path)
        await browser.close()
    print(f"📸 1080x1080 卡片圖片生成完畢: {output_path}")

# ==========================================
# 7. CLOUDFLARE R2 STORAGE UPLOADER
# ==========================================
def upload_to_r2(local_file_path, r2_object_name):
    account_id = clean_token_or_url(os.getenv("R2_ACCOUNT_ID", ""))
    access_key = clean_token_or_url(os.getenv("R2_ACCESS_KEY_ID", ""))
    secret_key = clean_token_or_url(os.getenv("R2_SECRET_ACCESS_KEY", ""))
    bucket_name = clean_token_or_url(os.getenv("R2_BUCKET_NAME", "xgame-radar-media"))
    public_domain = extract_clean_url(os.getenv("R2_PUBLIC_DOMAIN", "")).rstrip("/")

    if not all([account_id, access_key, secret_key]):
        print("⚠️ 未設置 Cloudflare R2 環境變數，跳過雲端上傳。")
        return None

    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto"
        )
        content_type = "image/png" if local_file_path.endswith(".png") else "application/json"
        s3.upload_file(local_file_path, bucket_name, r2_object_name, ExtraArgs={"ContentType": content_type})

        file_url = f"{public_domain}/{r2_object_name}" if public_domain else f"https://pub-{account_id}.r2.dev/{r2_object_name}"
        print(f"☁️ 檔案已成功上傳至 R2: {file_url}")
        return file_url
    except Exception as e:
        print(f"❌ R2 上傳失敗: {e}")
        return None

# ==========================================
# 8. MARKDOWN POST GENERATOR (100% ASTRO & YAML SAFE)
# ==========================================
def save_post_as_markdown(post_data, image_url, source_label="Official / Editorial"):
    timestamp = datetime.now().strftime("%Y-%m-%d")
    category_key = post_data.get("category", "SKATE").upper()
    topic_type = post_data.get("topic_type", "GENERAL").upper()
    
    # 徹底清除標題與副標換行符號
    title = sanitize_single_line_text(post_data.get("title", f"{category_key} 特刊"))
    subtitle = sanitize_single_line_text(post_data.get("subtitle", ""))
    city_tag = sanitize_single_line_text(post_data.get("city_tag", "GLOBAL"))
    gear_kw = post_data.get("gear_keyword", "extreme sports gear").strip()
    
    clean_slug = re.sub(r'[^a-zA-Z0-9]', '_', city_tag.lower())[:15]
    if not clean_slug or clean_slug == "_":
        clean_slug = "global"
    
    posts_dir = os.path.join("src", "content", "posts")
    os.makedirs(posts_dir, exist_ok=True)
    filename = f"{timestamp}_{category_key.lower()}_{clean_slug}.md"
    filepath = os.path.join(posts_dir, filename)

    # 組合 YAML Frontmatter 字典
    frontmatter_dict = {
        "title": title,
        "subtitle": subtitle,
        "date": datetime.now().isoformat(),
        "category": category_key if category_key in ["SKATE", "BMX", "SURF", "CLIMB", "SNOW", "EVENT", "SPOT", "ATHLETE", "SAFETY", "TRICKS"] else "SKATE",
        "topic_type": topic_type if topic_type in ["EVENT", "SPOT", "ATHLETE", "SAFETY", "RECORD", "TIPS", "GEAR", "GENERAL"] else "GENERAL",
        "cover_image": image_url,
        "cover_image_source": source_label,
        "author": "Una (@Una_next)",
        "city_tag": city_tag,
        "featured": True,
        "gear_keyword": gear_kw
    }

    if post_data.get("youtube_video_id"):
        frontmatter_dict["youtube_video_id"] = str(post_data["youtube_video_id"]).strip()
        frontmatter_dict["youtube_video_title"] = sanitize_single_line_text(post_data.get("youtube_video_title", "官方精彩精華"))

    if post_data.get("expert_info") and isinstance(post_data["expert_info"], dict) and post_data["expert_info"].get("name"):
        frontmatter_dict["expert_info"] = post_data["expert_info"]

    if post_data.get("spot_info") and isinstance(post_data["spot_info"], dict) and post_data["spot_info"].get("name"):
        frontmatter_dict["spot_info"] = post_data["spot_info"]

    if post_data.get("hotel_info") and isinstance(post_data["hotel_info"], dict) and post_data["hotel_info"].get("hotel_name"):
        frontmatter_dict["hotel_info"] = post_data["hotel_info"]

    if post_data.get("event_info") and isinstance(post_data["event_info"], dict) and post_data["event_info"].get("event_name"):
        frontmatter_dict["event_info"] = post_data["event_info"]

    if post_data.get("trick_info") and isinstance(post_data["trick_info"], dict) and post_data["trick_info"].get("trick_name"):
        frontmatter_dict["trick_info"] = post_data["trick_info"]

    if post_data.get("safety_gear_info") and isinstance(post_data["safety_gear_info"], dict) and post_data["safety_gear_info"].get("gear_type"):
        frontmatter_dict["safety_gear_info"] = post_data["safety_gear_info"]

    # Affiliate Product Object
    amazon_search_url = f"https://www.amazon.com/s?k={quote(gear_kw)}&tag={AMAZON_AFFILIATE_ID}"
    frontmatter_dict["affiliate_products"] = [
        {
            "title": sanitize_single_line_text(post_data.get("recommended_gear_title", f"{gear_kw.title()} 專業裝備")),
            "subtitle": "Amazon 官方直送・全球職業選手信賴",
            "search_term": gear_kw,
            "amazon_url": amazon_search_url,
            "recommended_for": sanitize_single_line_text(post_data.get("recommended_gear_reason", "日常訓練與賽事高強度防護必備")),
            "badge_text": "Una 編輯推薦"
        }
    ]

    # 100% 絕對安全的 YAML 生成邏輯 (使用 json.dumps 自動處理所有引號、冒號與換行)
    yaml_lines = ["---"]
    for k, v in frontmatter_dict.items():
        if isinstance(v, (dict, list)):
            yaml_lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        elif isinstance(v, bool):
            yaml_lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            yaml_lines.append(f"{k}: {v}")
        else:
            # 使用 json.dumps 保證字串被嚴格且安全地轉義，徹底杜絕 YAML 報錯
            yaml_lines.append(f"{k}: {json.dumps(str(v), ensure_ascii=False)}")
    yaml_lines.append("---")
    yaml_lines.append("")
    yaml_lines.append(f"![{title}]({image_url})")
    yaml_lines.append("")
    yaml_lines.append(post_data.get("content", ""))

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(yaml_lines))
    print(f"📝 Astro Markdown 文章已生成 (100% YAML Safe): {filepath}")
    return filepath

# ==========================================
# 9. TELEGRAM DISPATCHER
# ==========================================
def clean_markdown_for_telegram(text):
    parts = re.split(r'(https?://[^\s\)]+)', text)
    for i in range(0, len(parts), 2):
        parts[i] = parts[i].replace("_", " ")
        if parts[i].count("*") % 2 != 0:
            parts[i] = parts[i].replace("*", "")
    return "".join(parts)

def send_telegram_post(caption_text, image_path=None):
    bot_token = clean_token_or_url(os.getenv("TELEGRAM_BOT_TOKEN", ""))
    chat_id = clean_token_or_url(os.getenv("TELEGRAM_CHAT_ID", ""))

    if not bot_token or not chat_id:
        print("⚠️ 未設定 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID，跳過社群推播。")
        return

    clean_caption = clean_markdown_for_telegram(caption_text)

    def make_tg_request(parse_mode="Markdown"):
        if image_path and os.path.exists(image_path):
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            payload = {"chat_id": chat_id, "caption": clean_caption}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            with open(image_path, "rb") as photo:
                return requests.post(url, data=payload, files={"photo": photo}, timeout=15)
        else:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {"chat_id": chat_id, "text": clean_caption}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            return requests.post(url, data=payload, timeout=15)

    try:
        response = make_tg_request(parse_mode="Markdown")
        res_json = response.json()
        if res_json.get("ok"):
            print("✅ Telegram 卡片與文案成功發送！")
            return

        print(f"⚠️ Telegram 第一次發送失敗: {res_json.get('description', '')}，嘗試純文字模式...")
        fallback_res = make_tg_request(parse_mode=None)
        if fallback_res.json().get("ok"):
            print("✅ Telegram (純文字模式) 發送成功！")
    except Exception as e:
        print(f"❌ Telegram 發送異常: {e}")

# ==========================================
# 10. MAIN ASYNC PIPELINE
# ==========================================
async def main_async():
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
        hotel_embed = f"\n\n![{hotel_name}]({hotel_image})\n*▲ 周邊精選住宿推薦：{hotel_name}*\n"
        if "### 🏨 周邊精選住宿推薦" in web_content:
            web_content = web_content.replace("### 🏨 周邊精選住宿推薦", f"### 🏨 周邊精選住宿推薦{hotel_embed}")
        else:
            web_content += f"\n\n{hotel_embed}"

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
        f"🏆 *{title}*\n"
        f"⚡ _{subtitle}_\n\n"
        f"{tg_caption}\n\n"
        f"🗺️ *xGame Radar 全球運動地圖*:\n"
        f"👉 [點擊直達探索 3,400+ 場地與周邊旅宿](https://unanext.fans/spots/map/)\n\n"
        f"🛒 *Una 裝備推薦*:\n"
        f"👉 [{gear_kw.title()} Amazon 直送門市]({amazon_search_url})\n\n"
        f"🌐 *閱讀本期完整深度專題*:\n"
        f"👉 [點擊進入 xGame Magazine 官方專題]({post_web_url})\n\n"
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
