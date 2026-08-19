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

# 運動類別標籤與圖示配置
XGAME_CATEGORIES = {
    "CLIMBING": {"title": "運動攀登 / Climbing", "icon": "🧗", "tag": "#Climbing #Bouldering #攀岩"},
    "SKATE": {"title": "滑板 / Skateboarding", "icon": "🛹", "tag": "#Skateboarding #SkateLife #滑板"},
    "SURF": {"title": "衝浪 / Surfing", "icon": "🏄", "tag": "#Surfing #SurfLife #衝浪"},
    "BMX": {"title": "BMX 越野單車", "icon": "🚲", "tag": "#BMX #BMXFreestyle #極限單車"},
    "EVENT": {"title": "全球極限賽事前瞻", "icon": "🏆", "tag": "#xGames #RedBull #ExtremeSports"},
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

# 5 週主題循環對照表
TOPIC_ROTATION = {
    1: {"type": "VENUE", "desc": "世界級極限場館與地標開箱"},
    2: {"type": "ATHLETE", "desc": "傳奇與當紅極限選手人物誌"},
    3: {"type": "COMPETITION", "desc": "經典極限賽事歷史與賽制解析"},
    4: {"type": "EQUIPMENT", "desc": "專業裝備挑選與實戰保養指南"},
    5: {"type": "EVENT_OVERVIEW", "desc": "未來 3-4 週全球極限賽事預測與情報"},
}


# ==========================================
# 2. SQLite 數據庫初始化與操作
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # 建立抓取的賽事資料表
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
    # 建立發佈紀錄表
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

    # 計算未來第 3 週至第 4 週的時間範圍 (21天至30天後)
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
    # 優先載入 PredictHQ 未來 3-4 週預測賽事
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
    # 時間窗口過濾：只保留未來 21 至 30 天內的賽事預告
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

                # 嚴格篩選未來 3-4 週 (21-30天後) 的比賽項目
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
# 5. Gemini 動態專題文案生成 (格式隨主題自動適配)
# ==========================================
def generate_xgame_content(category_key, topic_type="VENUE", topic_desc="", target_lang="zh-hk"):
    cat_info = XGAME_CATEGORIES.get(category_key, XGAME_CATEGORIES["EVENT"])

    if not GEMINI_API_KEY:
        print("❌ 錯誤: 未設定 GEMINI_API_KEY 環境變數")
        sys.exit(1)

    client = genai.Client(api_key=GEMINI_API_KEY)
    city = random.choice(CITIES)

    # 1. 根據 topic_type 定義專屬的正文模組結構與參考資料
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

— By Una (@Una_next)
{cat_info['tag']} #xGameRadar
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
        caption_text = data.get("caption", raw_text)

        sub_title = f"{city_name_en.upper()} · {category_key}"

        return cover_title, sub_title, caption_text, city_name_en

    except Exception as e:
        print(f"⚠️ Gemini JSON 解析失敗，啟用後備設定: {e}")
        return (
            f"{category_key} {topic_type}",
            f"GLOBAL · {category_key}",
            f"👋 我係 Una (@Una_next)！今日【{topic_desc}】專題更新～\n\n{cat_info['tag']} #xGameRadar",
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


# ==========================================
# 8. 主流程控制器
# ==========================================
async def main():
    print("🚀 啟動 xGame Radar 自動化內容生成引擎...")
    init_db()

    # 1. 計算週數以進行 5 週話題輪替
    week_num = datetime.now().isocalendar()[1]
    rotation_key = ((week_num - 1) % 5) + 1
    current_topic = TOPIC_ROTATION[rotation_key]

    topic_type = current_topic["type"]
    topic_desc = current_topic["desc"]

    # 2. 隨機選擇運動項目類別
    category_key = random.choice(["CLIMBING", "SKATE", "SURF", "BMX", "EVENT"])

    print(f"📅 本週輪替 (W{week_num}): 【{topic_type}】 - {topic_desc}")
    print(f"🏷️ 選用極限運動項目: {category_key}")

    # 3. 呼叫 Gemini 生成內容
    cover_title, sub_title, caption_text, city_name_en = generate_xgame_content(
        category_key=category_key,
        topic_type=topic_type,
        topic_desc=topic_desc,
        target_lang="zh-hk",
    )

    print("\n--- [生成標題] ---")
    print(f"主標題: {cover_title}")
    print(f"副標題: {sub_title}")
    print("\n--- [正文預覽] ---")
    print(caption_text[:200] + "...\n")

    # 4. 生成卡片圖片
    image_filename = f"xgame_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
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

    print("🎉 自動化任務執行 completed！")


if __name__ == "__main__":
    asyncio.run(main())
