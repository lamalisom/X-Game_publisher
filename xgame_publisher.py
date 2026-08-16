import argparse
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import html
import io
import json
import os
import random
import re
import sys
import feedparser
from google import genai
from google.genai.errors import APIError
from PIL import Image, ImageDraw, ImageEnhance, ImageFont
import requests

# ==========================================
# 1. 環境變數設定
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
PREDICTHQ_TOKEN = os.getenv("PREDICTHQ_TOKEN")

# ==========================================
# 2. 基本資料與分類設定 (精準運動英文關鍵字)
# ==========================================
XGAME_CATEGORIES = {
    "SKATE": {
        "title": "滑板 SKATEBOARDING",
        "keywords": "skateboarding skatepark skater",
        "osm_tag": 'node["sport"="skateboard"]',
        "tag": "#Skateboarding #SkatePark #滑板",
    },
    "SURF": {
        "title": "衝浪 SURFING",
        "keywords": "surfing ocean wave surfer",
        "osm_tag": 'node["sport"="surfing"]',
        "tag": "#Surfing #WaveRider #浪人日常 #衝浪",
    },
    "CLIMB": {
        "title": "攀岩 CLIMBING",
        "keywords": "rock climbing bouldering outdoor rock wall climber",
        "osm_tag": 'node["sport"="climbing"]',
        "tag": "#Bouldering #Climbing #攀岩 #抱石",
    },
    "BIKE": {
        "title": "極限單車 BMX & MTB",
        "keywords": "bmx freestyle mountain biking cyclist",
        "osm_tag": 'node["sport"~"bmx|cycling"]',
        "tag": "#BMX #MTB #FreestyleBMX #極限單車 #越野單車",
    },
    "EVENT": {
        "title": "全球賽事總覽 GLOBAL EVENTS",
        "keywords": "action sports extreme sports competition athlete",
        "osm_tag": None,
        "tag": "#XGames #WorldSkate #WSL #IFSC #UCI #RedBull #極限運動",
    },
}

CITIES = [
    {"name": "Yosemite", "country": "USA", "lat": 37.8651, "lon": -119.5383},
    {"name": "Bali", "country": "Indonesia", "lat": -8.4095, "lon": 115.1889},
    {"name": "Mentawai", "country": "Indonesia", "lat": -2.1333, "lon": 99.5500},
    {"name": "Lombok", "country": "Indonesia", "lat": -8.6509, "lon": 116.3249},
    {"name": "Hong Kong", "country": "Hong Kong", "lat": 22.3193, "lon": 114.1694},
    {"name": "Taipei", "country": "Taiwan", "lat": 25.0330, "lon": 121.5654},
    {"name": "Tokyo", "country": "Japan", "lat": 35.6762, "lon": 139.6503},
    {"name": "Stockholm", "country": "Sweden", "lat": 59.3293, "lon": 18.0686},
    {"name": "Lisbon", "country": "Portugal", "lat": 38.7223, "lon": -9.1393},
    {"name": "Barcelona", "country": "Spain", "lat": 41.3851, "lon": 2.1734},
    {"name": "Paris", "country": "France", "lat": 48.8566, "lon": 2.3522},
    {"name": "Los Angeles", "country": "USA", "lat": 34.0522, "lon": -118.2437},
    {"name": "Sydney", "country": "Australia", "lat": -33.8688, "lon": 151.2093},
]


# ==========================================
# 3. Pexels 圖片抓取 (絕對鎖定運動種類)
# ==========================================
def fetch_pexels_image(category_key, city_name, cover_title="", width=1200, height=630):
    if not PEXELS_API_KEY:
        print("ℹ️ 未檢測到 PEXELS_API_KEY，將切換至預設幾何底圖。")
        return None

    cat_info = XGAME_CATEGORIES.get(category_key, XGAME_CATEGORIES["EVENT"])
    base_keywords = cat_info["keywords"]

    # 若為 EVENT 類別，嘗試從標題或城市推斷更精準的運動關鍵字
    if category_key == "EVENT":
        if any(w in cover_title for w in ["攀岩", "攀山", "Rock", "Climb"]):
            base_keywords = XGAME_CATEGORIES["CLIMB"]["keywords"]
        elif any(w in cover_title for w in ["滑板", "Skate"]):
            base_keywords = XGAME_CATEGORIES["SKATE"]["keywords"]
        elif any(w in cover_title for w in ["衝浪", "Surf"]):
            base_keywords = XGAME_CATEGORIES["SURF"]["keywords"]
        elif any(w in cover_title for w in ["單車", "BMX", "MTB"]):
            base_keywords = XGAME_CATEGORIES["BIKE"]["keywords"]

    clean_city = re.sub(r'[^a-zA-Z\s]', '', city_name).strip()
    if clean_city.upper() in ["GLOBAL", "WORLD", "NONE", ""]:
        clean_city = ""

    # 建立多層級搜尋順序
    search_queries = []
    if clean_city:
        search_queries.append(f"{clean_city} {base_keywords}".strip())
        search_queries.append(clean_city)
    search_queries.append(base_keywords)

    headers = {"Authorization": PEXELS_API_KEY}

    for query in search_queries:
        url = f"https://api.pexels.com/v1/search?query={requests.utils.quote(query)}&per_page=15&orientation=landscape"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                photos = res.json().get("photos", [])
                if photos:
                    photo_url = random.choice(photos)["src"]["large2x"]
                    img_res = requests.get(photo_url, timeout=10)
                    img = Image.open(io.BytesIO(img_res.content)).convert("RGB")

                    # 比例裁切
                    img_ratio = img.width / img.height
                    target_ratio = width / height

                    if img_ratio > target_ratio:
                        new_width = int(target_ratio * img.height)
                        left = (img.width - new_width) // 2
                        img = img.crop((left, 0, left + new_width, img.height))
                    else:
                        new_height = int(img.width / target_ratio)
                        top = (img.height - new_height) // 2
                        img = img.crop((0, top, img.width, top + new_height))

                    img = img.resize((width, height), Image.Resampling.LANCZOS)

                    # 壓暗底圖確保文字閱讀性
                    enhancer = ImageEnhance.Brightness(img)
                    img = enhancer.enhance(0.38)
                    print(f"📸 成功抓取精準主題圖片 (關鍵字: [{query}])")
                    return img
        except Exception as e:
            print(f"⚠️ Pexels 抓圖失敗 ({query}): {e}")

    return None
# ==========================================
# 4. OpenStreetMap, PredictHQ & RSS 賽事抓取
# ==========================================
def fetch_osm_venue(category_key, city):
    cat_info = XGAME_CATEGORIES.get(category_key)
    if not cat_info or not cat_info["osm_tag"]:
        return None

    lat, lon = city["lat"], city["lon"]
    overpass_url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:10];
    (
      {cat_info['osm_tag']}(around:20000, {lat}, {lon});
    );
    out body 5;
    """
    try:
        res = requests.post(overpass_url, data={"data": query}, timeout=10)
        if res.status_code == 200:
            data = res.json()
            elements = data.get("elements", [])
            named_elements = [
                e for e in elements if "tags" in e and "name" in e["tags"]
            ]
            if named_elements:
                chosen = random.choice(named_elements)
                return chosen["tags"].get("name")
    except Exception as e:
        print(f"⚠️ Overpass API 查詢失敗: {e}")
    return None


def fetch_predicthq_events():
    if not PREDICTHQ_TOKEN:
        return []

    url = "https://api.predicthq.com/v1/events/"
    headers = {
        "Authorization": f"Bearer {PREDICTHQ_TOKEN}",
        "Accept": "application/json",
    }
    now_str = datetime.now().strftime("%Y-%m-%d")
    params = {
        "category": "sports",
        "q": "extreme sports OR bmx OR surfing OR climbing OR skateboarding OR red bull",
        "active.gte": now_str,
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
                    "status": "UPCOMING"
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
    past_margin = now - timedelta(days=14)
    future_3_months = now + timedelta(days=90)

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

                if pub_date and (past_margin <= pub_date <= future_3_months):
                    status = "PAST_RESULT" if pub_date <= now else "UPCOMING"
                    events.append({
                        "org": org,
                        "title": entry.title,
                        "published": pub_date.strftime("%Y-%m-%d"),
                        "status": status
                    })
        except Exception as e:
            print(f"⚠️ RSS ({org}) 解析失敗: {e}")

    return events[:8]


# ==========================================
# 5. Gemini 文案生成 (JSON 格式徹底解決 Parsing 失敗)
# ==========================================
def generate_xgame_content(category_key, target_lang="zh-hk"):
    cat_info = XGAME_CATEGORIES.get(category_key, XGAME_CATEGORIES["EVENT"])

    if not GEMINI_API_KEY:
        print("❌ 錯誤: 未設定 GEMINI_API_KEY 環境變數")
        sys.exit(1)

    client = genai.Client(api_key=GEMINI_API_KEY)

    if category_key == "EVENT":
        real_events = fetch_real_upcoming_events()
        now_str = datetime.now().strftime("%Y-%m-%d")
        event_snippet = (
            f"【今天日期】：{now_str}\n"
            "【最新賽程與新聞數據】：\n"
            + "\n".join([
                f"- [{e['org']}] {e['title']} (日期: {e['published']}, 狀態: {e['status']})" for e in real_events
            ])
            if real_events
            else f"【今天日期】：{now_str}\n【賽事參考】：Red Bull, WSL, IFSC, World Skate"
        )

        prompt = f"""
你是一位極限運動特派員 Una (IG: @Una_next)。請針對以下數據以 JSON 格式回應，語言使用【{target_lang}】。

{event_snippet}

【輸出格式約束】：必須僅回傳以下標準 JSON，不要加入 Markdown ```json 標籤之外的額外文字：
{{
  "cover_title": "封面大標題(10字以內，如：極限速報：攀岩新線·滑板解禁！)",
  "city_name_en": "內文中提到的主要城市或地區英文名稱(例如 Yosemite / Paris / Tokyo / Global)",
  "caption": "正文內容"
}}

【正文格式要求】：
👋 我係 Una (@Una_next)！今日賽事情報速遞：

📍【比賽場地】：[具體賽事場館/城市與環境重點]

👤【參賽選手】：[具體列出 1-2 位焦點選手與亮點/成績]

🏆【比賽資料】：[賽事全名 + 時間/階段 + 結果(已發生) 或 預告(未來3個月)]

🔰【觀賽建議】：[1點觀賽指南]

— By Una (@Una_next)
{cat_info['tag']} #xGameRadar
"""
    else:
        city = random.choice(CITIES)
        venue_name = fetch_osm_venue(category_key, city)
        venue_context = f"地點：{city['country']} {city['name']}" + (f"「{venue_name}」" if venue_name else "")

        prompt = f"""
你是一位極限運動特派員 Una (IG: @Una_next)。請針對主題 [{cat_info['title']}] 以 JSON 格式回應，語言使用【{target_lang}】。

【情境資訊】：{venue_context}

【輸出格式約束】：必須僅回傳以下標準 JSON：
{{
  "cover_title": "封面大標題(10字以內)",
  "city_name_en": "{city['name']}",
  "caption": "正文內容"
}}

【正文格式要求】：
👋 我係 Una (@Una_next)！今日極限情報：

📍【場地介紹】：[地點/場館名稱 + 地形/設施/難度]

👤【代表選手】：[列出 1-2 位知名選手與簡短背景]

🏆【比賽資料】：[相關賽事名稱/巡迴賽資訊]

🔰【裝備與建議】：[必備裝備 + 1點安全提醒]

— By Una (@Una_next)
{cat_info['tag']} #{city['name']} #xGameRadar
"""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"tools": []}  # 關閉 AFC 警告
        )
        raw_text = response.text.strip()
        
        cleaned_json = re.sub(r"^```json\s*", "", raw_text, flags=re.MULTILINE)
        cleaned_json = re.sub(r"```$", "", cleaned_json, flags=re.MULTILINE).strip()
        
        data = json.loads(cleaned_json)
        
        cover_title = data.get("cover_title", f"{category_key} SPOTLIGHT")
        city_name_en = data.get("city_name_en", "GLOBAL")
        caption_text = data.get("caption", raw_text)
        
        sub_title = f"{city_name_en.upper()} · {category_key}"

        return cover_title, sub_title, caption_text, city_name_en

    except Exception as e:
        print(f"⚠️ Gemini JSON 解析失敗，啟用後備設定: {e}")
        return (
            f"{category_key} SPOTLIGHT",
            f"GLOBAL · {category_key}",
            f"👋 我係 Una (@Una_next)！今日最新極限情報更新～\n\n{cat_info['tag']} #xGameRadar",
            "GLOBAL",
        )

# ==========================================
# 6. 底圖與繪製 (高對比標題壓字)
# ==========================================
def create_obsidian_background(width=1200, height=630):
    base = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(base)

    for y in range(height):
        r = int(18 - (y / height) * 12)
        g = int(14 - (y / height) * 10)
        b = int(38 - (y / height) * 24)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)

    grid_size = 40
    grid_color = (0, 210, 255, 12)

    for x in range(0, width, grid_size):
        draw_overlay.line([(x, 0), (x, height)], fill=grid_color, width=1)
    for y in range(0, height, grid_size):
        draw_overlay.line([(0, y), (width, y)], fill=grid_color, width=1)

    draw_overlay.ellipse([-100, -100, 450, 450], fill=(138, 43, 226, 30))
    draw_overlay.ellipse(
        [width - 350, height - 350, width + 100, height + 100],
        fill=(0, 212, 255, 25),
    )

    return Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")


def get_font(size):
    font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/msjh.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()

def create_cover_image(
    cover_title, sub_title, category_key, city_name, output_path="cover.jpg"
):
    # 帶入 cover_title 以便 EVENT 模式自動分析主運動類別
    img = fetch_pexels_image(category_key, city_name, cover_title=cover_title)
    if img is None:
        img = create_obsidian_background(1200, 630)

    draw = ImageDraw.Draw(img)
    font_sub = get_font(26)
    font_main = get_font(44)
    font_footer = get_font(18)

    width, height = img.size

    # 1. 自動斷行處理
    max_line_width = 850
    lines = []
    current_line = ""
    for char in cover_title:
        test_line = current_line + char
        bbox = draw.textbbox((0, 0), test_line, font=font_main)
        if bbox[2] - bbox[0] > max_line_width:
            lines.append(current_line)
            current_line = char
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)

    display_lines = lines[:2]
    line_height = 60
    title_block_height = len(display_lines) * line_height

    total_block_height = 35 + title_block_height + 40
    start_y = (height - total_block_height) // 2

    # 2. 繪製副標題 (黃點 + 黃字)
    dot_radius = 5
    dot_spacing = 10
    sub_bbox = draw.textbbox((0, 0), sub_title, font=font_sub)
    sub_w = sub_bbox[2] - sub_bbox[0]
    sub_h = sub_bbox[3] - sub_bbox[1]

    total_sub_w = (dot_radius * 2) + dot_spacing + sub_w
    sub_start_x = (width - total_sub_w) // 2

    y_sub = start_y
    dot_x = sub_start_x
    dot_y = y_sub + (sub_h // 2) + 2
    draw.ellipse(
        [
            dot_x,
            dot_y - dot_radius,
            dot_x + (dot_radius * 2),
            dot_y + dot_radius,
        ],
        fill=(255, 204, 0),
    )

    text_x = dot_x + (dot_radius * 2) + dot_spacing
    draw.text((text_x, y_sub), sub_title, font=font_sub, fill=(255, 204, 0))

    # 3. 繪製主標題
    y_title = y_sub + 45
    for line in display_lines:
        line_bbox = draw.textbbox((0, 0), line, font=font_main)
        line_w = line_bbox[2] - line_bbox[0]
        line_x = (width - line_w) // 2

        for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2), (0, 3)]:
            draw.text((line_x + dx, y_title + dy), line, font=font_main, fill=(0, 0, 0, 255))

        draw.text((line_x, y_title), line, font=font_main, fill=(255, 255, 255))
        y_title += line_height

    # 4. Footer 落款
    footer_text = "xGame Radar · Curated by Una (@Una_next)"
    footer_bbox = draw.textbbox((0, 0), footer_text, font=font_footer)
    footer_w = footer_bbox[2] - footer_bbox[0]
    footer_x = (width - footer_w) // 2
    y_footer = y_title + 15

    draw.text((footer_x, y_footer), footer_text, font=font_footer, fill=(220, 220, 230))

    img.save(output_path, quality=95)
    print(f"🎨 封面成功繪製（主標題: [{cover_title}] | 副標題: [{sub_title}]）: {output_path}")
    return output_path

# ==========================================
# 7. Telegram 發布
# ==========================================
def format_text_for_telegram_html(text):
    safe_text = html.escape(text)
    safe_text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", safe_text)
    return safe_text

def send_telegram_post(photo_path, message_text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ 缺少 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID 環境變數")
        return

    # 清理 Token：若不小心填入完整 URL 或包含 brackets，自動提煉純 Token
    token = TELEGRAM_BOT_TOKEN.strip()
    token = re.sub(r"^https?://api\.telegram\.org/bot", "", token, flags=re.IGNORECASE)
    token = token.strip("[]/'\"")

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    html_caption = format_text_for_telegram_html(message_text)

    if len(html_caption) > 980:
        html_caption = html_caption[:950] + "\n\n...(內容較長已折疊)"

    try:
        with open(photo_path, "rb") as photo_file:
            payload = {
                "chat_id": TELEGRAM_CHAT_ID.strip("[]'\""),
                "caption": html_caption,
                "parse_mode": "HTML",
            }
            files = {"photo": photo_file}
            res = requests.post(url, data=payload, files=files, timeout=20)

            if res.status_code != 200:
                print(f"⚠️ HTML 解析異常 ({res.text})，自動降級為純文字模式重新發送...")
                photo_file.seek(0)
                plain_text = re.sub(r"<[^>]+>", "", html_caption)
                payload["caption"] = plain_text
                payload.pop("parse_mode", None)
                res = requests.post(url, data=payload, files=files, timeout=20)

            if res.status_code == 200:
                print("✅ 成功發送壓字圖片與完整貼文至 Telegram！")
            else:
                print(f"❌ Telegram 發送失敗: {res.text}")
    except Exception as e:
        print(f"⚠️ Telegram 發送過程異常: {e}")
        
# ==========================================
# 8. 主程式進入點
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="xGame Publisher Script")
    parser.add_argument(
        "-c",
        "--category",
        default="AUTO",
        choices=["AUTO", "SKATE", "SURF", "CLIMB", "BIKE", "EVENT"],
        help="主題類別 (AUTO, SKATE, SURF, CLIMB, BIKE, EVENT)",
    )
    parser.add_argument(
        "-l",
        "--lang",
        default="zh-hk",
        choices=["zh-hk", "zh-cn", "ja", "en"],
        help="發布語言",
    )
    args = parser.parse_args()

    category_key = args.category
    if category_key == "AUTO":
        category_key = random.choice(["SKATE", "SURF", "CLIMB", "BIKE", "EVENT"])

    print(f"🚀 啟動 xGame Radar -> 主題: [{category_key}] | 語言: [{args.lang}]")

    # 1. 呼叫 Gemini 生成內文與 JSON 格式數據
    cover_title, sub_title, caption_text, city_name_en = generate_xgame_content(
        category_key, args.lang
    )

    # 2. 呼叫圖片生成 (完全精準匹配地點與壓寫標題)
    photo_path = create_cover_image(
        cover_title=cover_title,
        sub_title=sub_title,
        category_key=category_key,
        city_name=city_name_en,
        output_path="xgame_post.jpg"
    )

    # 3. 發送 Telegram 貼文
    send_telegram_post(photo_path, caption_text)


if __name__ == "__main__":
    main()
