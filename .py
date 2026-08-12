import argparse
from datetime import datetime, timezone
from io import BytesIO
import os
import random
import feedparser
from google import genai
from google.genai.errors import APIError
from PIL import Image, ImageDraw, ImageFont
import requests

# ==========================================
# 1. 環境變數驗證
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

missing_vars = []
if not GEMINI_API_KEY:
  missing_vars.append("GEMINI_API_KEY")
if not TELEGRAM_BOT_TOKEN:
  missing_vars.append("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_CHAT_ID:
  missing_vars.append("TELEGRAM_CHAT_ID")

if missing_vars:
  raise ValueError(f"❌ 缺少必要環境變數: {', '.join(missing_vars)}")

client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 2. 全球城市與主題矩陣配置
# ==========================================
CITIES = [
    {"name": "Tokyo", "country": "Japan", "lat": 35.6762, "lon": 139.6503},
    {
        "name": "Barcelona",
        "country": "Spain",
        "lat": 41.3851,
        "lon": 2.1734,
    },  # 滑板聖地
    {
        "name": "Los Angeles",
        "country": "USA",
        "lat": 34.0522,
        "lon": -118.2437,
    },  # Venice Beach
    {"name": "London", "country": "UK", "lat": 51.5074, "lon": -0.1278},
    {
        "name": "Gold Coast",
        "country": "Australia",
        "lat": -28.0167,
        "lon": 153.4000,
    },  # 衝浪勝地
    {"name": "Lisbon", "country": "Portugal", "lat": 38.7223, "lon": -9.1393},
    {"name": "Hong Kong", "country": "China", "lat": 22.3193, "lon": 114.1694},
]

XGAME_CATEGORIES = {
    "SKATE": {
        "title": "🛹 全球滑板場與街頭 Spot 探索",
        "tag": "#Skateboarding #Skatepark #街頭滑板 #滑板新手",
        "osm_tag": '["sport"="skateboard"]',
        "pexels_queries": [
            "skateboarding trick",
            "skatepark bowl",
            "street skateboarder",
        ],
        "default_img": "https://images.pexels.com/photos/165236/pexels-photo-165236.jpeg",
    },
    "SURF": {
        "title": "🌊 全球浪點與衝浪指南",
        "tag": "#Surfing #SurfSpot #衝浪人生 #浪人日記",
        "osm_tag": '["sport"="surfing"]',
        "pexels_queries": ["surfing barrel ocean", "surfer wave action"],
        "default_img": "https://images.pexels.com/photos/67386/pexels-photo-67386.jpeg",
    },
    "CLIMB": {
        "title": "🧗 抱石與攀岩場地指南",
        "tag": "#Bouldering #RockClimbing #抱石日常 #攀岩初學者",
        "osm_tag": '["sport"="climbing"]',
        "pexels_queries": ["bouldering gym climber", "rock climbing outdoors"],
        "default_img": "https://images.pexels.com/photos/1126384/pexels-photo-1126384.jpeg",
    },
    "EVENT": {
        "title": "🏆 全球 xGame 賽事盛事雷達",
        "tag": "#XGames #WorldSkate #WSL #極限賽事 #賽事速報",
        "osm_tag": None,
        "pexels_queries": [
            "extreme sports action",
            "bmx air contest",
            "skate contest",
        ],
        "default_img": "https://images.pexels.com/photos/2005992/pexels-photo-2005992.jpeg",
    },
}

ROTATION_CYCLE = ["SKATE", "SURF", "CLIMB", "EVENT"]

EVENT_RSS_FEEDS = [
    {
        "org": "World Skate",
        "url": "https://www.worldskate.org/events.feed?type=rss",
    },
    {
        "org": "Red Bull Sports",
        "url": "https://www.redbull.com/feed/events.rss",
    },
    {"org": "SurferToday", "url": "https://www.surfertoday.com/feed/rss"},
]


# ==========================================
# 3. 數據抓取：OpenStreetMap & RSS
# ==========================================
def fetch_osm_venue(category_key, city_obj):
  """調用開源 OpenStreetMap Overpass API 撈取該城市真實場地"""
  osm_filter = XGAME_CATEGORIES[category_key]["osm_tag"]
  if not osm_filter:
    return None

  lat, lon = city_obj["lat"], city_obj["lon"]
  query = f"""
    [out:json][timeout:15];
    (
      node{osm_filter}(around:25000, {lat}, {lon});
      way{osm_filter}(around:25000, {lat}, {lon});
    );
    out tags 5;
    """
  try:
    url = "https://overpass-api.de/api/interpreter"
    res = requests.post(url, data={"data": query}, timeout=12)
    if res.status_code == 200:
      elements = res.json().get("elements", [])
      named_venues = [
          e["tags"]["name"] for e in elements if "name" in e.get("tags", {})
      ]
      if named_venues:
        return random.choice(named_venues)
  except Exception as e:
    print(f"⚠️ OpenStreetMap 請求跳過: {e}")
  return None


def fetch_real_upcoming_events():
  """從開源賽事 RSS 抓取最新官方發布賽程"""
  events = []
  for source in EVENT_RSS_FEEDS:
    try:
      feed = feedparser.parse(source["url"])
      for entry in feed.entries[:2]:
        events.append({
            "org": source["org"],
            "title": entry.title,
            "published": getattr(entry, "published", "近期舉辦"),
        })
    except Exception as e:
      print(f"⚠️ 賽事 RSS 抓取跳過 ({source['org']}): {e}")
  return events


# ==========================================
# 4. 配圖素材抓取 (Pexels API)
# ==========================================
def get_pexels_media(category_key):
  if not PEXELS_API_KEY:
    return XGAME_CATEGORIES[category_key]["default_img"]

  queries = XGAME_CATEGORIES[category_key]["pexels_queries"]
  query = random.choice(queries)
  headers = {"Authorization": PEXELS_API_KEY}
  url = f"https://api.pexels.com/v1/search?query={query}&per_page=8&page={random.randint(1, 2)}&orientation=landscape"

  try:
    res = requests.get(url, headers=headers, timeout=10)
    if res.status_code == 200:
      photos = res.json().get("photos", [])
      if photos:
        return random.choice(photos)["src"]["large"]
  except Exception as e:
    print(f"⚠️ Pexels 抓圖跳過: {e}")

  return XGAME_CATEGORIES[category_key]["default_img"]


# ==========================================
# 5. Gemini 文案與封面標題生成
# ==========================================
def generate_xgame_content(category_key, target_lang="zh-hk"):
  city = random.choice(CITIES)
  cat_info = XGAME_CATEGORIES[category_key]

  if category_key == "EVENT":
    real_events = fetch_real_upcoming_events()
    event_snippet = (
        "【官方最新公開賽程】：\n"
        + "\n".join([
            f"- {e['org']}: {e['title']} ({e['published']})"
            for e in real_events
        ])
        if real_events
        else "【即將來臨的經典賽事】：X Games, World Skate 巡迴賽, WSL 冠軍巡迴賽"
    )

    prompt = f"""
你是一位全球極限運動（Action Sports / xGame）資深情報員。
請以【{target_lang}】為社交媒體（Instagram / Telegram）撰寫一篇「未來 2 個月全球極限運動賽事雷達」。

{event_snippet}

【目標受眾】：極限運動愛好者及剛接觸的新手
【風格要求】：熱血、清晰、排版俐落、多用 Emoji，字數精簡在 300-400 字內。

【輸出格式嚴格要求】：
請務必在文案的最第一行輸出：`COVER_TITLE: [簡短有力的封面大標題，10-14字以內]`
接著換兩行輸出正文內容：
1. 💥 **熱血開場**
2. 🏆 **精選焦點賽事 (2 個)**（看點、選手焦點、線上直播/觀賽途徑）
3. 💡 **新手觀賽/入門小指南**
4. 🏷️ 標籤：{cat_info['tag']} #xGameRadar #ExtremeSports
"""
  else:
    venue_name = fetch_osm_venue(category_key, city)
    venue_context = (
        f"位於 {city['country']} {city['name']} 的真實熱門點「{venue_name}」"
        if venue_name
        else f"{city['country']} {city['name']} 的代表性極限運動場地"
    )

    prompt = f"""
你是一位專業極限運動嚮導。請以【{target_lang}】為社交媒體撰寫一篇關於【{cat_info['title']}】的實用指南。

【場地情境】：{venue_context}
【目標受眾】：極限運動玩家與初學者（Beginners）
【風格要求】：充滿熱情、具備實用指南價值、條理分明，字數約 300-400 字。

【輸出格式嚴格要求】：
請務必在文案的最第一行輸出：`COVER_TITLE: [簡短有力的封面大標題，10-14字以內]`
接著換兩行輸出正文內容：
1. 📍 **場地介紹與地形亮點**（碗池/街式道具/浪況/岩壁特色）
2. 🔰 **新手友善指南（Beginner Tips）**（入場時段、必備裝備）
3. 🛹/🧗/🌊 **安全與玩家禮儀**（1 條核心安全潛規則）
4. 🏷️ 標籤：{cat_info['tag']} #{city['name']} #xGameRadar #ExtremeSports
"""

  try:
    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt
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
    return cover_title, sub_title, caption_text
  except APIError as e:
    print(f"❌ Gemini 生成失敗: {e}")
    return (
        f"{category_key} SPOTLIGHT",
        "XGAME RADAR",
        f"【{cat_info['title']}】今日最新情報更新！",
    )


# ==========================================
# 6. 封面圖片合成 (Pillow 漸層遮罩 + 標題排版)
# ==========================================
def generate_cover_image(
    image_url,
    main_title,
    sub_title="XGAME RADAR",
    output_path="cover_output.jpg",
):
  """下載背景圖，繪製底部暗色漸層保護層並壓印標題"""
  try:
    res = requests.get(image_url, timeout=15)
    img = Image.open(BytesIO(res.content)).convert("RGBA")
  except Exception as e:
    print(f"⚠️ 背景圖片載入失敗，使用備用黑底: {e}")
    img = Image.new("RGBA", (1080, 1080), (20, 20, 20, 255))

  img = img.resize((1080, 1080), Image.Resampling.LANCZOS)
  width, height = img.size

  overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
  draw_overlay = ImageDraw.Draw(overlay)
  grad_start = int(height * 0.50)

  for y in range(grad_start, height):
    alpha = int(210 * ((y - grad_start) / (height - grad_start)))
    draw_overlay.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))

  img = Image.alpha_composite(img, overlay)
  draw = ImageDraw.Draw(img)

  font_paths = [
      "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
      "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
      "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
      "msjh.ttc",
  ]
  font_main, font_sub, font_brand = None, None, None
  for path in font_paths:
    if os.path.exists(path):
      try:
        font_main = ImageFont.truetype(path, 52)
        font_sub = ImageFont.truetype(path, 28)
        font_brand = ImageFont.truetype(path, 22)
        break
      except Exception:
        continue

  if not font_main:
    font_main = ImageFont.load_default()
    font_sub = ImageFont.load_default()
    font_brand = ImageFont.load_default()

  # 繪製分類副標題
  sub_y = int(height * 0.68)
  draw.text(
      (60, sub_y),
      f"● {sub_title}",
      font=font_sub,
      fill=(255, 215, 0),
  )

  # 繪製主標題
  title_y = sub_y + 48
  lines = [main_title[i : i + 12] for i in range(0, len(main_title), 12)]
  for line in lines[:2]:
    draw.text((60, title_y), line, font=font_main, fill=(255, 255, 255))
    title_y += 68

  # 繪製獨立專案浮水印
  draw.text(
      (60, int(height * 0.92)),
      "xGame Radar · Global Action Sports Dispatch",
      font=font_brand,
      fill=(180, 180, 180),
  )

  final_img = img.convert("RGB")
  final_img.save(output_path, "JPEG", quality=92)
  return output_path


# ==========================================
# 7. Telegram 本地合成圖文發布
# ==========================================
def send_telegram_post(photo_path, message_text):
  url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
  caption = (
      message_text[:950] + "..." if len(message_text) > 950 else message_text
  )

  try:
    with open(photo_path, "rb") as photo_file:
      payload = {
          "chat_id": TELEGRAM_CHAT_ID,
          "caption": caption,
          "parse_mode": "Markdown",
      }
      files = {"photo": photo_file}
      res = requests.post(url, data=payload, files=files, timeout=20)
      if res.status_code == 200:
        print("✅ 成功以【封面圖 + 完整排版】發布至 Telegram！")
        return
      else:
        print(f"⚠️ 圖片發布返回錯誤: {res.text}")
  except Exception as e:
    print(f"⚠️ 圖片發布異常: {e}")

  print("🔄 切換為純文字訊息發送...")
  text_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
  requests.post(
      text_url,
      json={
          "chat_id": TELEGRAM_CHAT_ID,
          "text": message_text,
          "parse_mode": "Markdown",
      },
      timeout=10,
  )


# ==========================================
# 8. 主程式排程進入點
# ==========================================
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="xGame Radar 全球發報系統")
  parser.add_argument(
      "-c",
      "--category",
      default="AUTO",
      choices=["AUTO", "SKATE", "SURF", "CLIMB", "EVENT"],
  )
  parser.add_argument("-l", "--lang", default="zh-hk")
  args = parser.parse_args()

  if args.category == "AUTO":
    epoch_days = (
        datetime.now(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
    ).days
    cat = ROTATION_CYCLE[epoch_days % len(ROTATION_CYCLE)]
  else:
    cat = args.category

  print(
      f"🚀 啟動 xGame Radar 發報 -> 主題: [{cat}] | 語言: [{args.lang}] |"
      f" 時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
  )

  # 1. 產生文案與封面標題
  cover_title, sub_title, post_caption = generate_xgame_content(cat, args.lang)
  print(f"📌 封面大標: {cover_title}")
  print("--------------------------------------------------")
  print(post_caption)
  print("--------------------------------------------------")

  # 2. 獲取背景底圖
  bg_image_url = get_pexels_media(cat)

  # 3. 本地合成封面圖片 (Pillow)
  local_cover_file = generate_cover_image(
      bg_image_url, cover_title, sub_title, "xgame_cover.jpg"
  )

  # 4. 發布至社群
  send_telegram_post(local_cover_file, post_caption)
