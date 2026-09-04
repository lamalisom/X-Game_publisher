import os
import re
import sys
import json
import random
import sqlite3
import base64
import requests
import feedparser
import asyncio
import time
from datetime import datetime
from urllib.parse import quote, urlparse
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

import boto3
from google import genai
from google.genai import types
from playwright.async_api import async_playwright

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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posted_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE,
            link TEXT,
            category TEXT,
            topic_type TEXT,
            posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute("PRAGMA table_info(posted_articles)")
    columns = [col[1] for col in cursor.fetchall()]
    if "category" not in columns:
        cursor.execute("ALTER TABLE posted_articles ADD COLUMN category TEXT")
    if "topic_type" not in columns:
        cursor.execute("ALTER TABLE posted_articles ADD COLUMN topic_type TEXT")
    if "link" not in columns:
        cursor.execute("ALTER TABLE posted_articles ADD COLUMN link TEXT")
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
                # 必須通過 oEmbed 驗證，確保 100% 存在且允許外嵌播放
                oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
                o_res = requests.get(oembed_url, timeout=3)
                if o_res.status_code == 200:
                    data = o_res.json()
                    title = data.get("title", f"{category_key} Official Action")
                    print(f"🎬 自動成功配對 YouTube 官方精華 [{vid}]: {title[:40]}")
                    return vid, title
    except Exception as e:
        print(f"⚠️ YouTube 影片自動搜尋跳過: {e}")

    # 分類備案官方 100% 存在且可播放影片
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

            # 嘗試抓取官方媒體圖片
            if not official_img:
                # 檢查 RSS 內建 media_content
                if 'media_content' in entry and len(entry['media_content']) > 0:
                    official_img = entry['media_content'][0].get('url')
                elif 'media_thumbnail' in entry and len(entry['media_thumbnail']) > 0:
                    official_img = entry['media_thumbnail'][0].get('url')
                elif 'enclosures' in entry and len(entry['enclosures']) > 0:
                    official_img = entry['enclosures'][0].get('href')
                
                # 若 RSS 內無圖片但有文章網址，爬取官網 og:image
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
# 3. GEMINI AI CONTENT ENGINE (RICH PILLARS)
# ==========================================
def generate_xgame_content(category_key="", topic_type="", topic_desc="", target_lang="zh-hk"):
    api_key = clean_token_or_url(os.getenv("GEMINI_API_KEY", ""))
    if not api_key:
        print("❌ 錯誤：未偵測到 GEMINI_API_KEY 環境變數！")
        return {
            "title": "xGame Radar",
            "subtitle": "GLOBAL · EVENT",
            "content": "請設定 GEMINI_API_KEY 環境變數以啟用 AI 自動內容生成。",
            "city_tag": "GLOBAL",
            "gear_keyword": "skateboarding gear",
            "topic_type": "GENERAL"
        }

    client = genai.Client(api_key=api_key)

    if not category_key or not category_key.strip():
        category_key = random.choice(list(XGAME_CATEGORIES.keys()))
    display_category = category_key.strip().upper()

    rss_context, official_img, official_yt = fetch_latest_rss_news(display_category)

    # 內容輪播排程：五大支柱
    weekday = datetime.now().weekday()
    SCHEDULE_MAP = {
        0: {"type": "EVENT", "title": "🗓️ 未來3-12個月賽事雷達與近期戰報"},
        1: {"type": "SPOT", "title": "🛹 全球與亞洲頂級場地導覽"},
        2: {"type": "ATHLETE", "title": "🏆 焦點專家與選手檔案 (PRO PROFILE)"},
        3: {"type": "SAFETY", "title": "🛡️ 安全裝備評測與護具選購指南"},
        4: {"type": "EVENT", "title": "⚡ 賽事精華與頒獎台名次速報"},
        5: {"type": "TIPS", "title": "🎯 花式招式分解與技巧心法庫"},
        6: {"type": "RECORD", "title": "🔥 極限歷史紀錄與經典重溫"}
    }

    current_schedule = SCHEDULE_MAP.get(weekday, SCHEDULE_MAP[0])
    active_topic = topic_type if topic_type else current_schedule["type"]
    active_title = current_schedule["title"]

    lang_map = {
        "zh-hk": "繁體中文（廣東話/香港口語，語氣熱血且極具社群吸引力）",
        "zh-cn": "簡體中文（專業熱血的極限運動社群口吻）",
        "ja": "日文（專業且地道的極限運動風格）",
        "en": "英文（Authentic Action Sports Community Style）"
    }
    selected_lang_desc = lang_map.get(target_lang, lang_map["zh-hk"])

    prompt = f"""
你是一位專注於全球極限運動的專業主編 Una (@Una_next)。
今日專欄主題：【{active_title}】（項目類別：{display_category}，主題類型：{active_topic}）
{rss_context}

【任務要求】:
請生成一篇具備深度專業度、高社群傳播力與極限運動熱血感的文章資料，語言格式：完全使用 **{selected_lang_desc}**。
必須以嚴格的 JSON 格式回傳（請勿輸出 Markdown 區塊或多餘文字），包含以下欄位：

{{
  "title": "精煉且具震撼力的封面主標題（嚴禁【】符號，約 20-35 字）",
  "subtitle": "副標題或一句話亮點總結（約 30-50 字）",
  "city_tag": "舉辦城市英文或主題城市（例如: TOKYO, SYDNEY, CALIFORNIA, GLOBAL）",
  "gear_keyword": "純英文推薦裝備搜尋關鍵字（例如: skate shoes pro / bmx helmet / surfing wetsuit，嚴禁中文）",
  "content": "深度正文內容（約 180-280 字，條理分明，使用熱血 Emoji，適度介紹重點賽事/人物/場地/安全要點）",
  "topic_type": "{active_topic}",
  "expert_info": {{
    "name": "選手或專家姓名（若為 ATHLETE 主題請填寫，否則可留空）",
    "country": "代表國家",
    "stance_or_style": "風格或站姿",
    "signature_tricks": ["招牌動作1", "招牌動作2"],
    "setup_breakdown": "專用裝備配置說明"
  }},
  "spot_info": {{
    "name": "場地名稱（若為 SPOT 主題請填寫）",
    "location": "場地地理位置",
    "difficulty": "All Levels / Beginner / Intermediate / Advanced / Pro",
    "features": ["特點1", "特點2"],
    "fee": "收費方式"
  }},
  "event_info": {{
    "event_name": "賽事名稱（若為 EVENT 主題請填寫）",
    "dates": "賽事日期（未來3-12個月或近期）",
    "event_status": "UPCOMING",
    "location": "賽事地點",
    "tier": "World Championship / X-Games Tier"
  }},
  "trick_info": {{
    "trick_name": "花式招式名稱（若為 TIPS/TRICKS 主題請填寫）",
    "difficulty_rating": 3,
    "prerequisites": ["先修基礎動作1", "先修基礎動作2"]
  }},
  "safety_gear_info": {{
    "gear_type": "裝備品類（若為 SAFETY 主題請填寫）",
    "certification": "ASTM F1492 / CPSC / CE EN1078"
  }},
  "recommended_gear_title": "Amazon 推薦商品中文標題",
  "recommended_gear_reason": "推薦理由"
}}
"""

    print(f"🤖 今日專欄: 【{active_title}】，正在呼叫 Gemini API 生成深度專題...")
    
    # 1. 優先使用標準 Google v1beta REST API (100% 穩定，零 SDK 相容性問題)
    models_to_try = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"]
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.4
            }
        }
        try:
            res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
            if res.status_code == 200:
                data = res.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                # 智慧解析 JSON
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw_text)
                if json_match:
                    raw_text = json_match.group(1).strip()
                start = raw_text.find('{')
                end = raw_text.rfind('}')
                if start != -1 and end != -1:
                    raw_text = raw_text[start:end+1]
                
                parsed = json.loads(raw_text)
                if parsed and isinstance(parsed, dict) and parsed.get("title"):
                    if official_img:
                        parsed["official_cover_image"] = official_img
                    if official_yt:
                        parsed["youtube_video_id"] = official_yt
                    print(f"✅ Google REST API [{model_name}] 成功生成高品質深度專案: {parsed.get('title')}")
                    return parsed
            else:
                print(f"⚠️ REST [{model_name}] 回應碼 {res.status_code}")
        except Exception as e:
            print(f"⚠️ REST [{model_name}] 請求異常: {e}")

    # 2. 次選 Google GenAI SDK
    try:
        client = genai.Client(api_key=api_key)
        for model_name in ["gemini-1.5-flash", "gemini-1.5-pro"]:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if response and response.text:
                    raw_text = response.text.strip()
                    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw_text)
                    if json_match:
                        raw_text = json_match.group(1).strip()
                    start = raw_text.find('{')
                    end = raw_text.rfind('}')
                    if start != -1 and end != -1:
                        raw_text = raw_text[start:end+1]
                    parsed = json.loads(raw_text)
                    if parsed and isinstance(parsed, dict) and parsed.get("title"):
                        if official_img:
                            parsed["official_cover_image"] = official_img
                        if official_yt:
                            parsed["youtube_video_id"] = official_yt
                        print(f"✅ GenAI SDK [{model_name}] 成功生成: {parsed.get('title')}")
                        return parsed
            except Exception as e:
                print(f"⚠️ SDK [{model_name}] 失敗: {e}")
    except Exception as e:
        print(f"⚠️ GenAI Client 初始化跳過: {e}")

    # Fallback default with timestamp to prevent duplicate skips
    timestamp_str = datetime.now().strftime("%m/%d %H:%M")
    fallback_gear = DEFAULT_GEAR_KEYWORDS.get(display_category, "extreme sports gear")
    return {
        "title": f"⚡ {display_category} 極限前線情報 ({timestamp_str})",
        "subtitle": f"Una 帶你直擊全球 {display_category} 最新賽事、場地與裝備亮點",
        "city_tag": "GLOBAL",
        "gear_keyword": fallback_gear,
        "content": f"⚡ 各位極限迷！今日【{display_category}】情報熱血更新中！無論街頭還是碗池，安全第一，盡情挑戰極限！\n\n💬 留言話我知你最想睇咩！\n#Una_next #{display_category} #xGameRadar",
        "topic_type": active_topic,
        "recommended_gear_title": f"{display_category} 專業防護裝備",
        "recommended_gear_reason": "賽事等級安全認證，提供最佳緩震與活動度"
    }

# ==========================================
# 4. AFFILIATE LINK BUILDER
# ==========================================
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

def get_action_sports_image(keyword, category_key="SKATE"):
    """精準抓取對應運動項目的高畫質相片，徹底杜絕披薩與多肉植物等無關圖片"""
    cat = category_key.upper() if category_key else "SKATE"
    if cat not in CATEGORY_ACTION_IMAGES:
        cat = "SKATE"

    pexels_key = clean_token_or_url(os.getenv("PEXELS_API_KEY", ""))
    if pexels_key:
        try:
            headers = {"Authorization": pexels_key}
            # 確保搜尋詞強烈關聯極限運動
            search_query = f"{cat.lower()} action sports {keyword}".strip()
            clean_keyword = quote(search_query)
            url = f"https://api.pexels.com/v1/search?query={clean_keyword}&per_page=3&orientation=landscape"
            res = requests.get(url, headers=headers, timeout=10).json()
            if res.get("photos") and len(res["photos"]) > 0:
                img_url = extract_clean_url(res["photos"][0]["src"]["large2x"])
                print(f"✅ Pexels 成功抓取【{cat}】極限動作圖: {img_url}")
                return img_url
        except Exception as e:
            print(f"⚠️ Pexels 搜尋跳過: {e}")

    # 預設使用真實極限運動相片庫
    selected = random.choice(CATEGORY_ACTION_IMAGES.get(cat, CATEGORY_ACTION_IMAGES["SKATE"]))
    print(f"📸 選用【{cat}】高畫質運動相片庫: {selected}")
    return selected

# ==========================================
# 6. ASYNC PLAYWRIGHT CARD RENDERER
# ==========================================
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
# 8. MARKDOWN POST GENERATOR (ASTRO COMPATIBLE)
# ==========================================
def save_post_as_markdown(post_data, image_url, source_label="Official / Editorial"):
    timestamp = datetime.now().strftime("%Y-%m-%d")
    category_key = post_data.get("category", "SKATE").upper()
    topic_type = post_data.get("topic_type", "GENERAL").upper()
    title = post_data.get("title", "").replace('"', '\\"')
    subtitle = post_data.get("subtitle", "").replace('"', '\\"')
    gear_kw = post_data.get("gear_keyword", "extreme sports gear")
    clean_slug = re.sub(r'[^a-zA-Z0-9]', '_', post_data.get("city_tag", "global").lower())[:15]
    
    posts_dir = os.path.join("src", "content", "posts")
    os.makedirs(posts_dir, exist_ok=True)
    filename = f"{timestamp}_{category_key.lower()}_{clean_slug}.md"
    filepath = os.path.join(posts_dir, filename)

    # 組合 YAML Frontmatter
    frontmatter_dict = {
        "title": title,
        "subtitle": subtitle,
        "date": datetime.now().isoformat(),
        "category": category_key if category_key in ["SKATE", "BMX", "SURF", "CLIMB", "SNOW", "EVENT", "SPOT", "ATHLETE", "SAFETY", "TRICKS"] else "SKATE",
        "topic_type": topic_type if topic_type in ["EVENT", "SPOT", "ATHLETE", "SAFETY", "RECORD", "TIPS", "GEAR", "GENERAL"] else "GENERAL",
        "cover_image": image_url,
        "cover_image_source": source_label,
        "author": "Una (@Una_next)",
        "city_tag": post_data.get("city_tag", "GLOBAL"),
        "featured": True,
        "gear_keyword": gear_kw
    }

    if post_data.get("youtube_video_id"):
        frontmatter_dict["youtube_video_id"] = post_data["youtube_video_id"]
        frontmatter_dict["youtube_video_title"] = post_data.get("youtube_video_title", "官方精彩精華")

    if post_data.get("expert_info") and post_data["expert_info"].get("name"):
        frontmatter_dict["expert_info"] = post_data["expert_info"]

    if post_data.get("spot_info") and post_data["spot_info"].get("name"):
        frontmatter_dict["spot_info"] = post_data["spot_info"]

    if post_data.get("event_info") and post_data["event_info"].get("event_name"):
        frontmatter_dict["event_info"] = post_data["event_info"]

    if post_data.get("trick_info") and post_data["trick_info"].get("trick_name"):
        frontmatter_dict["trick_info"] = post_data["trick_info"]

    if post_data.get("safety_gear_info") and post_data["safety_gear_info"].get("gear_type"):
        frontmatter_dict["safety_gear_info"] = post_data["safety_gear_info"]

    # Affiliate Product Object
    amazon_search_url = f"https://www.amazon.com/s?k={quote(gear_kw)}&tag={AMAZON_AFFILIATE_ID}"
    frontmatter_dict["affiliate_products"] = [
        {
            "title": post_data.get("recommended_gear_title", f"{gear_kw.title()} 專業裝備"),
            "subtitle": "Amazon 官方直送・全球職業選手信賴",
            "search_term": gear_kw,
            "amazon_url": amazon_search_url,
            "recommended_for": post_data.get("recommended_gear_reason", "日常訓練與賽事高強度防護必備"),
            "badge_text": "Una 編輯推薦"
        }
    ]

    # 格式化 YAML Frontmatter
    yaml_lines = ["---"]
    for k, v in frontmatter_dict.items():
        if isinstance(v, (dict, list)):
            json_str = json.dumps(v, ensure_ascii=False)
            # 轉換為標準 YAML 物件結構
            yaml_lines.append(f"{k}: {json_str}")
        elif isinstance(v, bool):
            yaml_lines.append(f"{k}: {'true' if v else 'false'}")
        else:
            yaml_lines.append(f"{k}: \"{v}\"")
    yaml_lines.append("---")
    yaml_lines.append("")
    yaml_lines.append(f"![{title}]({image_url})")
    yaml_lines.append("")
    yaml_lines.append(post_data.get("content", ""))

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(yaml_lines))
    print(f"📝 Astro Markdown 文章已生成: {filepath}")
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

    # 1. AI 內容與結構化資料生成
    post_data = generate_xgame_content(category_key=category, topic_type=topic_arg, target_lang=lang_arg)
    title = post_data.get("title", f"{category} 極限特刊")
    subtitle = post_data.get("subtitle", "")
    content = post_data.get("content", "")
    city_tag = post_data.get("city_tag", "GLOBAL")
    gear_kw = post_data.get("gear_keyword", "extreme sports gear")
    topic_type = post_data.get("topic_type", "GENERAL")

    if is_already_posted(title):
        print(f"ℹ️ 文章 [{title}] 今日已發布過，跳過重複發布。")
        return

    # 2. 注入 Amazon Affiliate 推薦文字
    monetized_content = attach_affiliate_link(content, gear_kw, category)
    post_data["category"] = category
    post_data["content"] = monetized_content

    # 確保每篇文章都擁有 100% 官方可外嵌播放的 YouTube 精華
    if not post_data.get("youtube_video_id"):
        yt_id, yt_title = search_embeddable_youtube_video(title, category)
        post_data["youtube_video_id"] = yt_id
        post_data["youtube_video_title"] = yt_title

    # 3. 官方圖片或精準運動項目高解析度相片（杜絕披薩與植物）
    official_img = post_data.get("official_cover_image")
    source_label = "Official Source" if official_img else "Editorial / Action Sports"
    bg_image = official_img if official_img else get_action_sports_image(f"{category.lower()} action sports", category)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    card_filename = f"xgame_{timestamp}.png"

    # 4. Playwright 生成 1080x1080 社群卡片
    await render_card_image_async(title, subtitle, city_tag, bg_image, card_filename)

    # 5. 上傳卡片圖片至 Cloudflare R2
    r2_img_url = upload_to_r2(card_filename, f"cards/{card_filename}")
    img_link_for_record = r2_img_url if r2_img_url else bg_image

    # 6. 生成並上傳 JSON 備份至 Cloudflare R2
    json_filename = f"{timestamp}_{category}.json"
    backup_payload = {
        "id": timestamp,
        "title": title,
        "subtitle": subtitle,
        "category": category,
        "topic_type": topic_type,
        "content": monetized_content,
        "image_url": img_link_for_record,
        "created_at": datetime.now().isoformat(),
        "author": "Una (@Una_next)"
    }
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(backup_payload, f, ensure_ascii=False, indent=2)
    upload_to_r2(json_filename, f"posts/{json_filename}")

    # 7. 儲存至 Astro 靜態網站 (src/content/posts/)
    save_post_as_markdown(post_data, img_link_for_record, source_label)

    # 8. 推送至 Telegram 頻道
    tg_message = f"🏆 *{title}*\n\n_{subtitle}_\n\n{monetized_content}\n\n#xGameRadar #{category} #Una_next"
    send_telegram_post(tg_message, image_path=card_filename)

    # 9. 記錄於 SQLite 並清理暫存檔
    record_posted_article(title, category, topic_type)

    if os.path.exists(card_filename):
        os.remove(card_filename)
    if os.path.exists(json_filename):
        os.remove(json_filename)

    print("🎉 xGame Radar Magazine 今日自動化發布與網站文章生成圓滿完成！")

if __name__ == "__main__":
    asyncio.run(main_async())
