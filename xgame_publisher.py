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
PREDICTHQ_TOKEN = os.getenv("PREDICTHQ_TOKEN")  # 可選：PredictHQ API Access Token

# ==========================================
# 2. 基本資料與分類設定 (含 BIKE 極限單車)
# ==========================================
XGAME_CATEGORIES = {
    "SKATE": {
        "title": "滑板 SKATEBOARDING",
        "query": "skateboarding park athlete",
        "osm_tag": 'node["sport"="skateboard"]',
        "tag": "#Skateboarding #SkatePark #滑板",
    },
    "SURF": {
        "title": "衝浪 SURFING",
        "query": "surfing ocean waves surfer",
        "osm_tag": 'node["sport"="surfing"]',
        "tag": "#Surfing #WaveRider #浪人日常 #衝浪",
    },
    "CLIMB": {
        "title": "攀岩 CLIMBING",
        "query": "bouldering indoor rock climbing athlete",
        "osm_tag": 'node["sport"="climbing"]',
        "tag": "#Bouldering #Climbing #攀岩 #抱石",
    },
    "BIKE": {
        "title": "極限單車 BMX & MTB",
        "query": "bmx freestyle mountain bike athlete",
        "osm_tag": 'node["sport"~"bmx|cycling"]',
        "tag": "#BMX #MTB #FreestyleBMX #極限單車 #越野單車",
    },
    "EVENT": {
        "title": "全球賽事總覽 GLOBAL EVENTS",
        "query": "action sports competition xgames",
        "osm_tag": None,
        "tag": "#XGames #WorldSkate #WSL #IFSC #UCI #RedBull #極限運動",
    },
}

# 城市與地點清單（含香港、台灣、印尼、葡萄牙、瑞典等極限運動勝地）
CITIES = [
    # 亞洲 Asia & 印尼專區 Indonesia
    {"name": "Bali", "country": "Indonesia", "lat": -8.4095, "lon": 115.1889},
    {"name": "Mentawai", "country": "Indonesia", "lat": -2.1333, "lon": 99.5500},
    {"name": "Lombok", "country": "Indonesia", "lat": -8.6509, "lon": 116.3249},
    {"name": "Jakarta", "country": "Indonesia", "lat": -6.2088, "lon": 106.8456},
    {"name": "Hong Kong", "country": "Hong Kong", "lat": 22.3193, "lon": 114.1694},
    {"name": "Taipei", "country": "Taiwan", "lat": 25.0330, "lon": 121.5654},
    {"name": "Taitung", "country": "Taiwan", "lat": 22.7583, "lon": 121.1444},
    {"name": "Yilan", "country": "Taiwan", "lat": 24.7570, "lon": 121.7530},
    {"name": "Tokyo", "country": "Japan", "lat": 35.6762, "lon": 139.6503},
    # 歐洲 Europe
    {"name": "Stockholm", "country": "Sweden", "lat": 59.3293, "lon": 18.0686},
    {"name": "Lisbon", "country": "Portugal", "lat": 38.7223, "lon": -9.1393},
    {"name": "Nazaré", "country": "Portugal", "lat": 39.6028, "lon": -9.0717},
    {"name": "Ericeira", "country": "Portugal", "lat": 38.9622, "lon": -9.4172},
    {"name": "Barcelona", "country": "Spain", "lat": 41.3851, "lon": 2.1734},
    {"name": "Paris", "country": "France", "lat": 48.8566, "lon": 2.3522},
    {"name": "Innsbruck", "country": "Austria", "lat": 47.2692, "lon": 11.4041},
    # 美洲 & 澳洲 Americas & Oceania
    {"name": "Los Angeles", "country": "USA", "lat": 34.0522, "lon": -118.2437},
    {"name": "Sydney", "country": "Australia", "lat": -33.8688, "lon": 151.2093},
    {"name": "Gold Coast", "country": "Australia", "lat": -28.0167, "lon": 153.4000},
]


# ==========================================
# 3. 抓取 Pexels 實景圖片
# ==========================================
def fetch_pexels_image(keyword, width=1200, height=630):
    if not PEXELS_API_KEY:
        print("ℹ️ 未檢測到 PEXELS_API_KEY，將切換至預設幾何底圖。")
        return None

    url = f"https://api.pexels.com/v1/search?query={keyword}&per_page=8&orientation=landscape"
    headers = {"Authorization": PEXELS_API_KEY}

    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            photos = data.get("photos", [])
            if photos:
                photo_url = random.choice(photos)["src"]["large2x"]
                img_res = requests.get(photo_url, timeout=10)
                img = Image.open(io.BytesIO(img_res.content)).convert("RGB")

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

                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(0.40)
                print(f"📸 成功抓取 Pexels 實景圖片: [{keyword}]")
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
    """從 PredictHQ Sports API 抓取極限運動與體育賽事"""
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
                location = item.get("location", [])
                events.append({
                    "org": "PredictHQ Sports",
                    "title": item.get("title", "Extreme Sport Event"),
                    "published": start_date,
                })
            print(f"✅ 成功從 PredictHQ API 抓取到 {len(events)} 筆賽事")
    except Exception as e:
        print(f"⚠️ PredictHQ API 查詢失敗: {e}")

    return events


def fetch_real_upcoming_events():
    """抓取 PredictHQ API 及修復後的有效 RSS Feed 數據"""
    events = []
    
    # 1. 先嘗試抓取 PredictHQ
    predicthq_events = fetch_predicthq_events()
    events.extend(predicthq_events)

    # 2. 修正與擴充 RSS 清單
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
                    events.append({
                        "org": org,
                        "title": entry.title,
                        "published": pub_date.strftime("%Y-%m-%d"),
                    })
        except Exception as e:
            print(f"⚠️ RSS ({org}) 解析失敗: {e}")

    return events[:8]


# ==========================================
# 5. Gemini 文案生成
# ==========================================
def generate_xgame_content(category_key, target_lang="zh-hk"):
    city = random.choice(CITIES)
    cat_info = XGAME_CATEGORIES.get(category_key, XGAME_CATEGORIES["EVENT"])

    if not GEMINI_API_KEY:
        print("❌ 錯誤: 未設定 GEMINI_API_KEY 環境變數")
        sys.exit(1)

    client = genai.Client(api_key=GEMINI_API_KEY)

    if category_key == "EVENT":
        real_events = fetch_real_upcoming_events()
        event_snippet = (
            "【最新賽程與新聞數據】：\n"
            + "\n".join([
                f"- [{e['org']}] {e['title']} ({e['published']})" for e in real_events
            ])
            if real_events
            else (
                "【熱門賽事參考】：Red Bull Content Pool 極限賽事, PredictHQ 體育盛事, WSL 衝浪錦標賽, IFSC 攀岩世界盃, World Skate 巡迴賽"
            )
        )

        prompt = f"""
你是一位極限運動特派員 Una (IG: @Una_next)。請以【{target_lang}】針對全球極限賽事生成 Telegram/IG 精簡速報。

{event_snippet}

【嚴格要求】：
1. 開頭包含 Una 短招呼語（如：「👋 我係 Una (@Una_next)！」）。
2. 資訊必須【嚴格分開類別，獨立介紹】，絕不可揉杂在一起。
3. 每個類別 1~2 句，總字數控制在 250 字內，精簡乾淨。
4. 第一行必須輸出：`COVER_TITLE: [簡短封面大標題，8-10字以內]`
5. 正文格式必須完全符合以下獨立分區：

👋 我係 Una (@Una_next)！今日賽事情報速遞：

📍【比賽場地】：[具體賽事場館/城市與環境重點]

👤【參賽選手】：[具體列出 1-2 位焦點選手與亮點]

🏆【比賽資料】：[賽事全名 + 舉辦時間/階段 + 官方連結]

🔰【觀賽建議】：[1點重點注意事項或觀賽指南]

— By Una (@Una_next)
{cat_info['tag']} #xGameRadar
"""
    else:
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
4. 第一行必須輸出：`COVER_TITLE: [簡短封面大標題，8-10字以內]`
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

        cover_title = f"{city['name']} · {cat_info['title'][:10]}"
        caption_text = full_text

        if "COVER_TITLE:" in full_text:
            parts = full_text.split("COVER_TITLE:", 1)[1].split("\n", 1)
            cover_title = (
                parts[0].strip().replace("[", "").replace("]", "").replace("*", "")
            )
            caption_text = parts[1].strip() if len(parts) > 1 else full_text

        sub_title = f"{city['name'].upper()} · {category_key}"
        search_query = f"{cat_info['query']} {city['name']} {city['country']}"
        return cover_title, sub_title, caption_text, search_query
    except APIError as e:
        print(f"❌ Gemini 生成失敗: {e}")
        return (
            f"{category_key} SPOTLIGHT",
            "XGAME RADAR",
            "👋 我係 Una (@Una_next)！今日最新極限情報更新～\n\n#xGameRadar",
            cat_info["query"],
        )


# ==========================================
# 6. 底圖與壓字繪製 (IG 安全區域最適化)
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
    cover_title, sub_title, query_keyword, output_path="cover.jpg"
):
    img = fetch_pexels_image(query_keyword)
    if img is None:
        img = create_obsidian_background(1200, 630)

    draw = ImageDraw.Draw(img)
    font_sub = get_font(24)
    font_main = get_font(42)
    font_footer = get_font(18)

    width, height = img.size  # 1200, 630

    # 控制寬度至 410px 以符合 IG 正方形裁切安全區域
    max_width = 410
    lines = []
    current_line = ""
    for char in cover_title:
        test_line = current_line + char
        bbox = draw.textbbox((0, 0), test_line, font=font_main)
        if bbox[2] - bbox[0] > max_width:
            lines.append(current_line)
            current_line = char
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)

    display_lines = lines[:3]
    line_height = 56
    title_block_height = len(display_lines) * line_height

    total_block_height = 30 + 18 + title_block_height + 35 + 20
    start_y = (height - total_block_height) // 2

    dot_radius = 5
    dot_spacing = 8
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

    y_title = y_sub + 45
    for line in display_lines:
        line_bbox = draw.textbbox((0, 0), line, font=font_main)
        line_w = line_bbox[2] - line_bbox[0]
        line_x = (width - line_w) // 2

        draw.text(
            (line_x + 2, y_title + 2), line, font=font_main, fill=(0, 0, 0, 220)
        )
        draw.text((line_x, y_title), line, font=font_main, fill=(255, 255, 255))
        y_title += line_height

    footer_text = "xGame Radar · Curated by Una (@Una_next)"
    footer_bbox = draw.textbbox((0, 0), footer_text, font=font_footer)
    footer_w = footer_bbox[2] - footer_bbox[0]
    footer_x = (width - footer_w) // 2
    y_footer = y_title + 10

    draw.text(
        (footer_x, y_footer), footer_text, font=font_footer, fill=(210, 210, 220)
    )

    img.save(output_path, quality=95)
    print(f"🎨 封面圖片已成功生成（已適應 IG 裁切安全區域）: {output_path}")
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
# 8. 主程式進入點 (明確註冊 BIKE 選項)
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

    cover_title, sub_title, caption_text, query_keyword = generate_xgame_content(
        category_key, args.lang
    )

    photo_path = create_cover_image(
        cover_title, sub_title, query_keyword, "xgame_post.jpg"
    )

    send_telegram_post(photo_path, caption_text)


if __name__ == "__main__":
    main()
