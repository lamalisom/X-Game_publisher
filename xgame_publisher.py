import argparse
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import html
import io
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
# 2. 基本資料與分類設定
# ==========================================
XGAME_CATEGORIES = {
    "SKATE": {
        "title": "滑板 SKATEBOARDING",
        "query": "skateboarding skate park skater athlete",
        "osm_tag": 'node["sport"="skateboard"]',
        "tag": "#Skateboarding #SkatePark #滑板",
    },
    "SURF": {
        "title": "衝浪 SURFING",
        "query": "surfing ocean wave surfer athlete",
        "osm_tag": 'node["sport"="surfing"]',
        "tag": "#Surfing #WaveRider #浪人日常 #衝浪",
    },
    "CLIMB": {
        "title": "攀岩 CLIMBING",
        "query": "rock climbing bouldering climber rock wall",
        "osm_tag": 'node["sport"="climbing"]',
        "tag": "#Bouldering #Climbing #攀岩 #抱石",
    },
    "BIKE": {
        "title": "極限單車 BMX & MTB",
        "query": "bmx freestyle mountain biking cyclist",
        "osm_tag": 'node["sport"~"bmx|cycling"]',
        "tag": "#BMX #MTB #FreestyleBMX #極限單車 #越野單車",
    },
    "EVENT": {
        "title": "全球賽事總覽 GLOBAL EVENTS",
        "query": "action sports competition extreme sports athlete",
        "osm_tag": None,
        "tag": "#XGames #WorldSkate #WSL #IFSC #UCI #RedBull #極限運動",
    },
}

CITIES = [
    {"name": "Yosemite", "country": "USA", "lat": 37.8651, "lon": -119.5383},
    {"name": "Bali", "country": "Indonesia", "lat": -8.4095, "lon": 115.1889},
    {"name": "Mentawai", "country": "Indonesia", "lat": -2.1333, "lon": 99.5500},
    {"name": "Lombok", "country": "Indonesia", "lat": -8.6509, "lon": 116.3249},
    {"name": "Jakarta", "country": "Indonesia", "lat": -6.2088, "lon": 106.8456},
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
# 3. Pexels 圖片抓取 (精準運動類型鎖定)
# ==========================================
def fetch_pexels_image(category_key, city_name, width=1200, height=630):
    if not PEXELS_API_KEY:
        print("ℹ️ 未檢測到 PEXELS_API_KEY，將切換至預設幾何底圖。")
        return None

    cat_info = XGAME_CATEGORIES.get(category_key, XGAME_CATEGORIES["EVENT"])
    # 強制將運動關鍵字放在首位，避免城市名導致搜尋出球類或風景照片
    search_keyword = f"{cat_info['query']} {city_name}".strip()

    url = f"https://api.pexels.com/v1/search?query={requests.utils.quote(search_keyword)}&per_page=10&orientation=landscape"
    headers = {"Authorization": PEXELS_API_KEY}

    try:
        res = requests.get(url, headers=headers, timeout=10)
        photos = []
        if res.status_code == 200:
            photos = res.json().get("photos", [])

        # 若加上城市名找不到圖片，退回純運動項目搜尋
        if not photos:
            search_keyword = cat_info['query']
            url = f"https://api.pexels.com/v1/search?query={requests.utils.quote(search_keyword)}&per_page=10&orientation=landscape"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                photos = res.json().get("photos", [])

        if photos:
            photo_url = random.choice(photos)["src"]["large2x"]
            img_res = requests.get(photo_url, timeout=10)
            img = Image.open(io.BytesIO(img_res.content)).convert("RGB")

            # 裁切為 1200x630
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

            # 適度壓暗底圖以突出標題文字
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(0.40)
            print(f"📸 成功抓取精準主題圖片: [{search_keyword}]")
            return img
    except Exception as e:
        print(f"⚠️ Pexels 圖片抓取失敗: {e}")

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
            print(f"✅ 成功從 PredictHQ API 抓取到 {len(events)} 筆賽事")
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
# 5. Gemini 文案與標題生成
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
                f"- [{e['org']}] {e['title']} (日期: {e['published']}, 狀態標記: {e['status']})" for e in real_events
            ])
            if real_events
            else (
                f"【今天日期】：{now_str}\n"
                "【熱門賽事參考】：Red Bull Content Pool 極限賽事, PredictHQ 體育盛事, WSL 衝浪錦標賽, IFSC 攀岩世界盃, World Skate 巡迴賽"
            )
        )

        prompt = f"""
你是一位極限運動特派員 Una (IG: @Una_next)。請以【{target_lang}】針對提供的真實數據生成 Telegram/IG 精簡速報。

{event_snippet}

【嚴格要求】：
1. 開頭包含 Una 短招呼語（如：「👋 我係 Una (@Una_next)！」）。
2. 資訊必須【嚴格分開類別，獨立介紹】，絕不可混在一起。
3. 每個類別 1~2 句，總字數控制在 250 字內，精簡乾淨。
4. 【賽事時態要求】：
   - 若賽事在今天之前（已發生）：必須報導**比賽結果、獲勝者或創新紀錄亮點**。
   - 若賽事在未來 3 個月內：必須報導**舉行時間、地點及看點預告**。
5. 前兩行必須嚴格按照以下格式輸出提取出的標題與地點：
   `COVER_TITLE: [簡短封面大標題，8-12字以內，例如：極限速報：攀岩新線·滑板解禁！]`
   `CITY_NAME: [主要賽事發生的真實城市或國家英文名稱，例如 Yosemite / Paris / Tokyo / Global]`
6. 正文格式必須完全符合以下獨立分區：

👋 我係 Una (@Una_next)！今日賽事情報速遞：

📍【比賽場地】：[具體賽事場館/城市與環境重點]

👤【參賽選手】：[具體列出 1-2 位焦點選手與亮點/成績]

🏆【比賽資料】：[賽事全名 + 時間/階段 + 結果或賽程預告]

🔰【觀賽建議】：[1點重點注意事項或觀賽指南]

— By Una (@Una_next)
{cat_info['tag']} #xGameRadar
"""
    else:
        city = random.choice(CITIES)
        venue_name = fetch_osm_venue(category_key, city)
        venue_context = (
            f"地點：{city['country']} {city['name']}「{venue_name}」"
            if venue_name
            else f"地點：{city['country']} {city['name']} 知名{cat_info['title']}場地"
        )

        prompt = f"""
你是一位極限運動與浪人特派員 Una (IG: @Una_next)。請以【{target_lang}】針對主題 [{cat_info['title']}] 生成 Telegram/IG 精簡介紹。

【情境資訊】：{venue_context}

【嚴格要求】：
1. 開頭包含 Una 短招呼語（如：「👋 我係 Una (@Una_next)！」）。
2. 資訊必須【嚴格分開類別，獨立介紹】，絕不可混在一起。
3. 每個類別 1~2 句即可，字數精簡短練（總字數 250 字內）。
4. 前兩行必須嚴格按照以下格式輸出：
   `COVER_TITLE: [簡短封面大標題，8-12字以內]`
   `CITY_NAME: {city['name']}`
5. 正文格式必須完全符合以下獨立分區：

👋 我係 Una (@Una_next)！今日極限情報：

📍【場地介紹】：[地點/場館名稱 + 地形/設施/難度分級]

👤【代表選手】：[列出 1-2 位具體知名選手與簡短背景]

🏆【比賽資料】：[相關賽事名稱/國際巡迴賽/協會資訊]

🔰【裝備與建議】：[必備裝備 + 1點安全提醒]

— By Una (@Una_next)
{cat_info['tag']} #{city['name']} #xGameRadar
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        full_text = response.text.strip()

        cover_title = f"{cat_info['title'][:10]} SPOTLIGHT"
        city_name = "GLOBAL"

        # 解析 COVER_TITLE 與 CITY_NAME
        lines = full_text.split("\n")
        parsed_caption_lines = []
        for line in lines:
            if line.startswith("COVER_TITLE:"):
                cover_title = line.replace("COVER_TITLE:", "").strip().replace("[", "").replace("]", "").replace("*", "")
            elif line.startswith("CITY_NAME:"):
                city_name = line.replace("CITY_NAME:", "").strip().replace("[", "").replace("]", "").replace("*", "")
            else:
                parsed_caption_lines.append(line)

        caption_text = "\n".join(parsed_caption_lines).strip()
        sub_title = f"{city_name.upper()} · EVENT" if category_key == "EVENT" else f"{city_name.upper()} · {category_key}"

        return cover_title, sub_title, caption_text, city_name
    except APIError as e:
        print(f"❌ Gemini 生成失敗: {e}")
        return (
            f"{category_key} SPOTLIGHT",
            "GLOBAL · XGAME RADAR",
            "👋 我係 Una (@Una_next)！今日最新極限情報更新～\n\n#xGameRadar",
            "GLOBAL",
        )


# ==========================================
# 6. 底圖與壓字繪製 (確定標題壓印與視覺置中)
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
    img = fetch_pexels_image(category_key, city_name)
    if img is None:
        img = create_obsidian_background(1200, 630)

    draw = ImageDraw.Draw(img)
    font_sub = get_font(26)
    font_main = get_font(44)
    font_footer = get_font(18)

    width, height = img.size  # 1200, 630

    # 1. 斷詞處理 (確保主標題完美顯示)
    max_line_width = 800
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

    display_lines = lines[:2]  # 最多顯示 2 行標題
    line_height = 58
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

    # 3. 繪製主標題 (帶陰影，確保清楚突出)
    y_title = y_sub + 45
    for line in display_lines:
        line_bbox = draw.textbbox((0, 0), line, font=font_main)
        line_w = line_bbox[2] - line_bbox[0]
        line_x = (width - line_w) // 2

        # 暗黑陰影
        draw.text((line_x + 2, y_title + 2), line, font=font_main, fill=(0, 0, 0, 240))
        # 主白字
        draw.text((line_x, y_title), line, font=font_main, fill=(255, 255, 255))
        y_title += line_height

    # 4. 繪製 Footer 落款
    footer_text = "xGame Radar · Curated by Una (@Una_next)"
    footer_bbox = draw.textbbox((0, 0), footer_text, font=font_footer)
    footer_w = footer_bbox[2] - footer_bbox[0]
    footer_x = (width - footer_w) // 2
    y_footer = y_title + 15

    draw.text((footer_x, y_footer), footer_text, font=font_footer, fill=(210, 210, 220))

    img.save(output_path, quality=95)
    print(f"🎨 封面圖片已成功繪製並儲存: {output_path} (標題: {cover_title} | 副標題: {sub_title})")
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

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    html_caption = format_text_for_telegram_html(message_text)

    if len(html_caption) > 980:
        html_caption = html_caption[:950] + "\n\n...(內容較長已折疊)"

    try:
        with open(photo_path, "rb") as photo_file:
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": html_caption,
                "parse_mode": "HTML",
            }
            files = {"photo": photo_file}
            res = requests.post(url, data=payload, files=files, timeout=20)

            if res.status_code != 200:
                print(
                    f"⚠️ HTML 解析異常 ({res.text})，自動降級為純文字模式重新發送..."
                )
                photo_file.seek(0)
                plain_text = re.sub(r"<[^>]+>", "", html_caption)
                payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": plain_text}
                res = requests.post(url, data=payload, files=files, timeout=20)

            if res.status_code == 200:
                print("✅ 成功發送「壓字圖片 + 精簡文章」至 Telegram！")
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

    # 1. 呼叫 Gemini 生成文案與提取標題/城市名稱
    cover_title, sub_title, caption_text, city_name = generate_xgame_content(
        category_key, args.lang
    )

    # 2. 呼叫圖片生成 (帶入 category_key 與 city_name 精準配對圖片與繪製標題)
    photo_path = create_cover_image(
        cover_title=cover_title,
        sub_title=sub_title,
        category_key=category_key,
        city_name=city_name,
        output_path="xgame_post.jpg"
    )

    # 3. 發送至 Telegram
    send_telegram_post(photo_path, caption_text)


if __name__ == "__main__":
    main()
