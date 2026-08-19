import os
import re
import sys
import json
import random
import sqlite3
import requests
import feedparser
import asyncio
from datetime import datetime, timedelta
from dateutil.parser import parse as parsedate_to_datetime
import boto3
from google import genai
from playwright.async_api import async_playwright

# ==========================================
# 1. 環境變數與配置檢查
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PREDICTHQ_TOKEN = os.getenv("PREDICTHQ_TOKEN")

# R2 / S3 配置
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
R2_PUBLIC_DOMAIN = os.getenv("R2_PUBLIC_DOMAIN")  # 例: https://pub-xxx.r2.dev

DB_FILE = "xgame_radar.db"

# 運動類別標籤、圖示與專屬 Hashtags
XGAME_CATEGORIES = {
    "CLIMBING": {
        "title": "運動攀登 / Climbing",
        "icon": "🧗",
        "tags": "#Climbing #Bouldering #攀岩 #抱石 #攀登 #OutdoorLife #xGameRadar"
    },
    "SKATE": {
        "title": "滑板 / Skateboarding",
        "icon": "🛹",
        "tags": "#Skateboarding #SkateLife #SkatePark #滑板 #極限運動 #StreetCulture #xGameRadar"
    },
    "SURF": {
        "title": "衝浪 / Surfing",
        "icon": "🏄",
        "tags": "#Surfing #SurfLife #WaveRider #衝浪 #海浪 #OceanVibes #xGameRadar"
    },
    "BMX": {
        "title": "BMX 越野單車",
        "icon": "🚲",
        "tags": "#BMX #BMXFreestyle #BMXLife #極限單車 #單車 #xGameRadar"
    },
    "EVENT": {
        "title": "全球極限賽事前瞻",
        "icon": "🏆",
        "tags": "#xGames #RedBull #WorldSkate #WSL #IFSC #ExtremeSports #極限賽事 #xGameRadar"
    },
}

# 根據主題類別定義的 CTA (Call To Action) 庫
CTA_LIBRARY = {
    "VENUE": [
        "💬 你有去過這個場地嗎？或者有更邪惡的私房打卡點？留言話我知！",
        "📌 快啲 Save 低呢個 Post，下次飛過去玩/打卡就唔會搵唔到路！",
        "🏷️ Tag 你個 Ready 一齊去刷場地嘅 Plate/Bouldering Buddy！"
    ],
    "ATHLETE": [
        "🔥 你最心水嘅極限運動員係邊位？留言話我知，下次為你開箱佢嘅故事！",
        "💬 佢呢招招牌動作你有冇試過？歡迎喺下面留言交流！",
        "❤️ 覺得呢位選手好 Pro 嘅話，記得點讚支持同 Share 給朋友！"
    ],
    "COMPETITION": [
        "🏆 呢場經典賽事你最印象深刻係哪一幕？留言一齊討論！",
        "🔔 記得 Follow 我哋 @Una_next，第一時間獲取全球極限賽事最新情報！",
        "📲 分享俾身邊同你一齊睇比賽嘅發燒友！"
    ],
    "EQUIPMENT": [
        "⚙️ 你平時用緊咩牌子/裝備？留言分享你嘅實戰心得！",
        "📌 裝備保養指南快啲 Bookmark 起來，延長你戰友嘅壽命！",
        "💬 有冇其他裝備問題想問？留言話我知，下集話你知！"
    ],
    "EVENT_OVERVIEW": [
        "🗓️ 未來 3-4 週賽事精采絕倫，你最期待邊一場？留言交流！",
        "📲 記得 Save 低呢份預測清單，順便 Share 俾一齊睇直播嘅 Bro！",
        "🔔 追蹤 @Una_next，緊貼全球最新預測賽期與賽況！"
    ]
}

# 全球極限運動熱點城市
CITIES = [
    {"name": "Tokyo", "country": "Japan", "lat": 35.6762, "lon": 139.6503},
    {"name": "Paris", "country": "France", "lat": 48.8566, "lon": 2.3522},
    {"name": "Los Angeles", "country": "USA", "lat": 34.0522, "lon": -118.2437},
    {"name": "Innsbruck", "country": "Austria", "lat": 47.2692, "lon": 11.4041},
    {"name": "Gold Coast", "country": "Australia", "lat": -28.0167, "lon": 153.4000},
    {"name": "Barcelona", "country": "Spain", "lat": 41.3851, "lon": 2.1734},
]


# ==========================================
# 2. SQLite 數據庫初始化與操作
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fetched_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org TEXT,
            title TEXT,
            published TEXT,
            status TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            topic_type TEXT,
            cover_title TEXT,
            sub_title TEXT,
            image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def save_fetched_events(events):
    if not events:
        return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    for e in events:
        cursor.execute(
            "INSERT INTO fetched_events (org, title, published, status) VALUES (?, ?, ?, ?)",
            (e["org"], e["title"], e["published"], e["status"]),
        )
    conn.commit()
    conn.close()


def save_post_history(category, topic_type, cover_title, sub_title, image_url):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO posts_history (category, topic_type, cover_title, sub_title, image_url) VALUES (?, ?, ?, ?, ?)",
        (category, topic_type, cover_title, sub_title, image_url),
    )
    conn.commit()
    conn.close()


# ==========================================
# 3. OpenStreetMap 地理場地查詢
# ==========================================
def fetch_osm_venue(category_key, city):
    osm_tags = {
        "CLIMBING": '["sport"="climbing"]',
        "SKATE": '["leisure"="pitch"]["sport"="skateboarding"]',
        "SURF": '["natural"="beach"]',
        "BMX": '["sport"="bmx"]',
        "EVENT": '["leisure"="stadium"]',
    }
    tag = osm_tags.get(category_key, '["leisure"="pitch"]')
    overpass_url = "http://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:10];
    (
      node{tag}(around:20000, {city['lat']}, {city['lon']});
      way{tag}(around:20000, {city['lat']}, {city['lon']});
    );
    out center 3;
    """
    try:
        res = requests.post(overpass_url, data={"data": query}, timeout=12)
        if res.status_code == 200:
            elements = res.json().get("elements", [])
            for elem in elements:
                name = elem.get("tags", {}).get("name")
                if name:
                    return name
    except Exception as e:
        print(f"⚠️ OSM 查詢提示: {e}")
    return None


# ==========================================
# 4. PredictHQ & RSS 賽事抓取 (嚴格預測未來 3-4 週事項)
# ==========================================
def fetch_predicthq_events():
    if not PREDICTHQ_TOKEN:
        return []

    url = "https://api.predicthq.com/v1/events/"
    headers = {
        "Authorization": f"Bearer {PREDICTHQ_TOKEN}",
        "Accept": "application/json",
    }

    now = datetime.now()
    start_3w = (now + timedelta(days=21)).strftime("%Y-%m-%d")
    end_4w = (now + timedelta(days=30)).strftime("%Y-%m-%d")

    params = {
        "category": "sports",
        "q": "extreme sports OR bmx OR surfing OR climbing OR skateboarding OR red bull",
        "active.gte": start_3w,
        "active.lte": end_4w,
        "limit": 5,
        "sort": "start",
    }

    events = []
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        if res.status_code == 200:
            results = res.json().get("results", [])
            for item in results:
                start_date = item.get("start", "")[:10]
                events.append({
                    "org": "PredictHQ Sports",
                    "title": item.get("title", "Extreme Sport Event"),
                    "published": start_date,
                    "status": "UPCOMING_3_TO_4_WEEKS",
                })
    except Exception as e:
        print(f"⚠️ PredictHQ API 查詢失敗: {e}")

    return events


def fetch_real_upcoming_events():
    events = []
    events.extend(fetch_predicthq_events())

    rss_urls = [
        ("WSL Surfing", "https://www.worldsurfleague.com/rss"),
        ("IFSC Climbing World Cup", "https://www.ifsc-climbing.org/index.php?option=com_content&view=featured&format=feed&type=rss"),
        ("Red Bull RSS Feed", "https://www.redbull.com/us-en/events/rss"),
        ("World Skate", "http://www.worldskate.org/news?format=feed&type=rss"),
        ("Dew Tour", "https://www.dewtour.com/feed/"),
        ("Surfer Magazine", "https://www.surfer.com/.rss/excerpt/"),
        ("Climbing Magazine", "https://www.climbing.com/feed/"),
        ("Vital BMX", "https://www.vitalbmx.com/news/rss"),
        ("Pinkbike MTB", "https://www.pinkbike.com/pinkbike_xml_feed.php"),
    ]

    now = datetime.now()
    future_3w_start = now + timedelta(days=21)
    future_4w_end = now + timedelta(days=30)

    for org, url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                pub_date = None

                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        pub_date = datetime(*entry.published_parsed[:6])
                    except Exception:
                        pub_date = None

                if not pub_date and hasattr(entry, "published"):
                    try:
                        pub_date = parsedate_to_datetime(entry.published).replace(tzinfo=None)
                    except Exception:
                        pub_date = None

                if pub_date and (future_3w_start <= pub_date <= future_4w_end):
                    events.append({
                        "org": org,
                        "title": entry.title,
                        "published": pub_date.strftime("%Y-%m-%d"),
                        "status": "UPCOMING_PREDICTION",
                    })
        except Exception as e:
            print(f"⚠️ RSS ({org}) 解析失敗: {e}")

    fetched_list = events[:8]
    save_fetched_events(fetched_list)
    return fetched_list


# ==========================================
# 5. Gemini 動態專題文案生成 (含 Tag 與 CTA 拼接)
# ==========================================
def generate_xgame_content(category_key, topic_type="VENUE", topic_desc="", target_lang="zh-hk"):
    cat_info = XGAME_CATEGORIES.get(category_key, XGAME_CATEGORIES["EVENT"])

    if not GEMINI_API_KEY:
        print("❌ 錯誤: 未設定 GEMINI_API_KEY 環境變數")
        sys.exit(1)

    client = genai.Client(api_key=GEMINI_API_KEY)
    city = random.choice(CITIES)

    # 1. 根據 topic_type 定義專屬的正文模組結構
    if topic_type == "EVENT_OVERVIEW" or category_key == "EVENT":
        real_events = fetch_real_upcoming_events()
        now_str = datetime.now().strftime("%Y-%m-%d")
        event_snippet = (
            f"【今天日期】：{now_str}\n"
            "【未來3-4週預測與預告賽事數據】：\n"
            + "\n".join([f"- [{e['org']}] {e['title']} (日期: {e['published']})" for e in real_events])
            if real_events
            else f"【今天日期】：{now_str}\n【未來3-4週預測賽事參考】：Red Bull, WSL, IFSC, World Skate"
        )

        template_structure = """
👋 我係 Una (@Una_next)！今日全球賽事預測情報：

📍【焦點賽期預測】：[未來 3-4 週即將舉辦的重點賽事與地點]

👤【注目參賽陣容】：[預計參賽的焦點選手或熱門奪冠人選]

🏆【賽事分析與看點】：[賽事規模、難度解析與前瞻]

🔰【觀賽情報/直播建議】：[如何追蹤或線上觀賽重點]
"""
        context_data = event_snippet

    elif topic_type == "VENUE":
        venue_name = fetch_osm_venue(category_key, city)
        context_data = f"地點：{city['country']} {city['name']}" + (f"「{venue_name}」" if venue_name else "")
        template_structure = f"""
👋 我係 Una (@Una_next)！今日場地開箱：【{topic_desc}】

📍【場地位置與環境】：[具體地點/場館名稱 + 地形風格與特色]

🧗【設施與難度等級】：[適合新手/進階？場地難度與設施配備]

🏆【歷史/舉辦賽事】：[該場地曾舉辦過的經典賽事或代表性人物]

🔰【場地使用/前往建議】：[開放時間、交通或注意事項]
"""

    elif topic_type == "ATHLETE":
        context_data = f"關聯城市/代表地：{city['country']} {city['name']}"
        template_structure = f"""
👋 我係 Una (@Una_next)！今日極限人物誌：【{topic_desc}】

👤【選手簡介與背景】：[選手姓名 + 國籍/出生地與發跡故事]

🔥【招牌動作與風格】：[最著名招式、比賽個人風格特質]

🏆【生涯代表戰績】：[奪冠紀錄、奧運/X Games/世界賽戰績]

🔰【選手座右銘/最新動態】：[選手經典名言或近期備戰狀態]
"""

    elif topic_type == "COMPETITION":
        context_data = f"關聯賽事發源/主辦地區：{city['country']} {city['name']}"
        template_structure = f"""
👋 我係 Una (@Una_next)！今日經典賽事檔案：【{topic_desc}】

🏆【賽事名稱與歷史】：[賽事全稱、創辦年份與極限運動界地位]

📍【賽制與評分規則】：[如何計分？淘汰賽機制或裁判標準]

👤【傳奇選手與紀錄】：[賽事史上最狂紀錄保持者或歷屆王者]

🔰【觀賽重點解析】：[這項比賽最刺激、最不可錯過的看點]
"""

    elif topic_type == "EQUIPMENT":
        context_data = f"測試環境參考：{city['country']} {city['name']}"
        template_structure = f"""
👋 我係 Una (@Una_next)！今日裝備與實戰指南：【{topic_desc}】

⚙️【核心裝備解析】：[關鍵裝備名稱、材質規格與選購重點]

🛡️【防護與安全配備】：[必備防具、安全規範與避坑指南]

💡【進階保養/調校技巧】：[如何日常維護裝備或調整至最佳狀態]

🔰【Una 的實戰小貼士】：[1點新手/玩家最常忽略的實用經驗]
"""

    # 2. 組裝動態 Prompt
    prompt = f"""
你是一位極限運動特派員 Una (IG: @Una_next)。
今日專題：【{cat_info['title']}】之【{topic_desc}】。
語言請嚴格使用【{target_lang}】。

【情境/參考資料】：
{context_data}

【輸出格式約束】：必須僅回傳以下標準 JSON，不要加入 Markdown ```json 標籤之外的額外文字：
{{
  "cover_title": "封面大標題(10字以內，要吸睛並符合今天主題)",
  "city_name_en": "{city['name'] if 'city' in locals() else 'GLOBAL'}",
  "caption": "正文內容"
}}

【正文結構範本（必須嚴格按照以下標題格式輸出 caption）】：
{template_structure}
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"tools": []},
        )
        raw_text = response.text.strip()

        cleaned_json = re.sub(r"^```json\s*", "", raw_text, flags=re.MULTILINE)
        cleaned_json = re.sub(r"```$", "", cleaned_json, flags=re.MULTILINE).strip()

        data = json.loads(cleaned_json)

        cover_title = data.get("cover_title", f"{category_key} {topic_type}")
        city_name_en = data.get("city_name_en", "GLOBAL")
        raw_caption = data.get("caption", raw_text)

        # 3. 自動附加 CTA 與 Hashtags
        selected_cta = random.choice(CTA_LIBRARY.get(topic_type, CTA_LIBRARY["VENUE"]))
        category_tags = cat_info["tags"]

        full_caption = f"{raw_caption.strip()}\n\n---\n{selected_cta}\n\n— By Una (@Una_next)\n{category_tags}"
        sub_title = f"{city_name_en.upper()} · {category_key}"

        return cover_title, sub_title, full_caption, city_name_en

    except Exception as e:
        print(f"⚠️ Gemini JSON 解析失敗，啟用後備設定: {e}")
        selected_cta = random.choice(CTA_LIBRARY.get(topic_type, CTA_LIBRARY["VENUE"]))
        category_tags = cat_info["tags"]
        fallback_caption = (
            f"👋 我係 Una (@Una_next)！今日【{topic_desc}】專題更新～\n\n"
            f"---\n{selected_cta}\n\n— By Una (@Una_next)\n{category_tags}"
        )
        return (
            f"{category_key} {topic_type}",
            f"GLOBAL · {category_key}",
            fallback_caption,
            "GLOBAL",
        )


# ==========================================
# 6. HTML/CSS 卡片渲染與 Playwright 截圖生成
# ==========================================
async def generate_card_image(category_key, cover_title, sub_title, output_filename="xgame_card.png"):
    cat_info = XGAME_CATEGORIES.get(category_key, XGAME_CATEGORIES["EVENT"])
    icon = cat_info["icon"]

    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-HK">
    <head>
      <meta charset="UTF-8">
      <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
          width: 1080px;
          height: 1080px;
          background: linear-gradient(135deg, #0d0d0d 0%, #1a1a1a 100%);
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          color: #ffffff;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 80px;
          position: relative;
          overflow: hidden;
        }}
        .bg-accent {{
          position: absolute;
          top: -200px;
          right: -200px;
          width: 600px;
          height: 600px;
          background: radial-gradient(circle, rgba(255, 69, 0, 0.25) 0%, rgba(0,0,0,0) 70%);
          border-radius: 50%;
        }}
        .header {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          z-index: 10;
        }}
        .badge {{
          background: #ff4500;
          color: #fff;
          font-weight: 800;
          font-size: 24px;
          padding: 10px 24px;
          border-radius: 50px;
          text-transform: uppercase;
          letter-spacing: 2px;
        }}
        .sub-title {{
          font-size: 28px;
          color: #a0a0a0;
          font-weight: 600;
          letter-spacing: 1px;
        }}
        .center-content {{
          z-index: 10;
          margin-top: 40px;
        }}
        .icon {{
          font-size: 110px;
          margin-bottom: 20px;
        }}
        .main-title {{
          font-size: 80px;
          font-weight: 900;
          line-height: 1.15;
          color: #ffffff;
          text-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }}
        .footer {{
          display: flex;
          justify-content: space-between;
          align-items: flex-end;
          z-index: 10;
          border-top: 2px solid #333;
          padding-top: 30px;
        }}
        .author {{
          font-size: 32px;
          font-weight: 700;
          color: #ff4500;
        }}
        .tagline {{
          font-size: 22px;
          color: #666;
        }}
      </style>
    </head>
    <body>
      <div class="bg-accent"></div>
      <div class="header">
        <div class="badge">xGame Radar</div>
        <div class="sub-title">{sub_title}</div>
      </div>
      <div class="center-content">
        <div class="icon">{icon}</div>
        <div class="main-title">{cover_title}</div>
      </div>
      <div class="footer">
        <div class="author">By Una (@Una_next)</div>
        <div class="tagline">Global Extreme Sports Daily</div>
      </div>
    </body>
    </html>
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1080, "height": 1080})
        await page.set_content(html_content)
        await page.screenshot(path=output_filename)
        await browser.close()

    print(f"📸 圖片成功生成: {output_filename}")
    return output_filename


# ==========================================
# 7. 圖片上傳至 Cloudflare R2 / AWS S3
# ==========================================
def upload_to_r2(file_path, object_name):
    if not all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME]):
        print("⚠️ 未完全設定 R2/S3 認證資訊，跳過圖片上傳")
        return None

    s3_endpoint = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

    s3_client = boto3.client(
        "s3",
        endpoint_url=s3_endpoint,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )

    try:
        s3_client.upload_file(
            file_path,
            R2_BUCKET_NAME,
            object_name,
            ExtraArgs={"ContentType": "image/png"},
        )
        public_url = (
            f"{R2_PUBLIC_DOMAIN.rstrip('/')}/{object_name}"
            if R2_PUBLIC_DOMAIN
            else f"{s3_endpoint}/{R2_BUCKET_NAME}/{object_name}"
        )
        print(f"☁️ 圖片已成功上傳至 R2: {public_url}")
        return public_url
    except Exception as e:
        print(f"❌ R2 上傳失敗: {e}")
        return None

import requests

def send_telegram_post(caption_text, image_path=None):
    # 從環境變數讀取 GitHub Secrets
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not telegram_token or not chat_id:
        print("⚠️ 未偵測到 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID，跳過 Telegram 發送")
        return

    print("🚀 正在發送帖文與圖片至 Telegram...")

    # 1. 優先嘗試發送圖片 + Caption
    if image_path and os.path.exists(image_path):
        url = f"https://api.telegram.org/bot{telegram_token}/sendPhoto"
        try:
            with open(image_path, "rb") as photo:
                payload = {
                    "chat_id": chat_id,
                    "caption": caption_text
                }
                files = {"photo": photo}
                res = requests.post(url, data=payload, files=files, timeout=15)
                if res.status_code == 200:
                    print("✅ Telegram 圖片卡片與文案已成功發送！")
                    return
                else:
                    print(f"⚠️ 發送圖片失敗 ({res.status_code}): {res.text}，轉為純文字發送...")
        except Exception as e:
            print(f"⚠️ 發送 Telegram 圖片時發生例外: {e}")

    # 2. 若發送圖片失敗或無圖片，降級發送純文字
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": caption_text
    }
    try:
        res = requests.post(url, data=payload, timeout=15)
        if res.status_code == 200:
            print("✅ Telegram 純文字訊息成功發送！")
        else:
            print(f"❌ Telegram 文字發送失敗: {res.text}")
    except Exception as e:
        print(f"❌ 發送 Telegram 文字時發生例外: {e}")
        
# ==========================================
# 8. 主流程控制器 (每日發帖模式 + 支援手動觸發覆寫)
# ==========================================
async def main():
    print("🚀 啟動 xGame Radar 自動化內容生成引擎...")
    init_db()

    now = datetime.now()
    weekday = now.weekday()  # 0=Mon, 1=Tue, ..., 6=Sun
    day_of_year = now.timetuple().tm_yday

    # 讀取 GitHub Actions 傳入的環境變數 (若無則使用預設值)
    cat_input = os.getenv("CAT_INPUT", "AUTO").upper()
    lang_input = os.getenv("LANG_INPUT", "zh-hk").lower()

    # 1. 每日主題輪替 (星期一至星期日)
    DAILY_TOPICS = [
        {"type": "VENUE", "desc": "世界級極限場館與地標開箱"},          # Mon
        {"type": "ATHLETE", "desc": "傳奇與當紅極限選手人物誌"},        # Tue
        {"type": "COMPETITION", "desc": "經典極限賽事歷史與賽制解析"}, # Wed
        {"type": "EQUIPMENT", "desc": "專業裝備挑選與實戰保養指南"},   # Thu
        {"type": "EVENT_OVERVIEW", "desc": "未來 3-4 週全球極限賽事預測與情報"}, # Fri
        {"type": "VENUE", "desc": "週末熱門極限場地與玩家打卡點"},      # Sat
        {"type": "EQUIPMENT", "desc": "週末裝備實戰保養與選購技巧"},    # Sun
    ]

    current_topic = DAILY_TOPICS[weekday]
    topic_type = current_topic["type"]
    topic_desc = current_topic["desc"]

    # 2. 運動類別判斷 (支援手動指定類別)
    sports_rotation = ["CLIMBING", "SKATE", "SURF", "BMX"]
    
    if cat_input != "AUTO":
        category_key = cat_input
        print(f"🎯 手動指定類別: {category_key}")
    else:
        if topic_type == "EVENT_OVERVIEW":
            category_key = "EVENT"
        else:
            category_key = sports_rotation[day_of_year % len(sports_rotation)]
        print(f"🔄 自動輪替類別: {category_key}")

    print(f"📅 今日日期: {now.strftime('%Y-%m-%d')} (星期{weekday+1})")
    print(f"📌 今日主題: 【{topic_type}】 - {topic_desc}")
    print(f"🌐 語言設定: {lang_input}")

    # 3. 呼叫 Gemini 生成內容
    cover_title, sub_title, caption_text, city_name_en = generate_xgame_content(
        category_key=category_key,
        topic_type=topic_type,
        topic_desc=topic_desc,
        target_lang=lang_input,
    )

    print("\n--- [生成標題] ---")
    print(f"主標題: {cover_title}")
    print(f"副標題: {sub_title}")
    print("\n--- [正文預覽 (含 CTA & Tag)] ---")
    print(caption_text[-300:])  # 預覽底部 CTA 與 Tags

    # 4. 生成卡片圖片
    image_filename = f"xgame_{now.strftime('%Y%m%d_%H%M%S')}.png"
    await generate_card_image(category_key, cover_title, sub_title, image_filename)

    # 5. 上傳圖片至 R2
    remote_object_name = f"cards/{image_filename}"
    image_url = upload_to_r2(image_filename, remote_object_name)

    # 6. 保存歷史紀錄至 SQLite
    save_post_history(
        category=category_key,
        topic_type=topic_type,
        cover_title=cover_title,
        sub_title=sub_title,
        image_url=image_url or image_filename,
    )

    # 7. 發送至 Telegram 頻道/群組 (關鍵補齊)
    send_telegram_post(caption_text=caption_text, image_path=image_filename)

    print("🎉 自動發帖任務執行完成！")
if __name__ == "__main__":
    asyncio.run(main())
