import argparse
from datetime import datetime, timezone
import os
import random
import feedparser
from google import genai
from google.genai.errors import APIError
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
# 2. 全球城市庫與輪播主題配置
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
        "title": "🏆 全球 xGame 賽事與盛事雷達 (未來 2 個月)",
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
        "org": "World Skate (官方賽事)",
        "url": "https://www.worldskate.org/events.feed?type=rss",
    },
    {
        "org": "Red Bull Extreme Sports",
        "url": "https://www.redbull.com/feed/events.rss",
    },
    {"org": "SurferToday Events", "url": "https://www.surfertoday.com/feed/rss"},
]


# ==========================================
# 3. 數據獲取：OpenStreetMap & RSS
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
# 5. Gemini 2.5 Flash 智能文案生成
# ==========================================
def generate_xgame_post(category_key, target_lang="zh-hk"):
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
請以【{target_lang}】為社交媒體（Instagram / Telegram）撰寫一篇吸引人的「未來 2 個月全球極限運動賽事雷達」。

{event_snippet}

【目標受眾】：極限運動愛好者及剛接觸的新手
【風格要求】：熱血、清晰、排版俐落、多用 Emoji，字數精簡在 300-450 字內。

【文案結構】：
1. 💥 **熱血開場**：帶出極限賽季氛圍。
2. 🏆 **未來 2 個月精選焦點賽事 (2-3 個)**：
   - 介紹看點、選手技術焦點、線上直播/觀賽途徑。
3. 💡 **新手觀賽/入門小指南**：給想開始嘗試該運動的新手 1 點入門心態或裝備建議。
4. 🏷️ 標籤：{cat_info['tag']} #AKOMARO_xGame
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
【風格要求】：充滿熱情、具備實用指南價值、條理分明、避免生硬文字，字數約 300-450 字。

【文案結構】：
1. 📍 **場地介紹與地形亮點**：解析地形規格（如：碗池Bowl、街式Street道具、浪況或抱石壁面難度）。
2. 🔰 **新手友善指南（Beginner Tips）**：入場時段建議（避開擁擠）、必備防護裝備。
3. 🛹/🧗/🌊 **玩家禮儀與安全守則**：分享 1 條場地必知的安全禮儀（如：掉板警示、等待順序）。
4. 🏷️ 標籤：{cat_info['tag']} #{city['name']} #AKOMARO_xGame
"""

  try:
    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt
    )
    return response.text
  except APIError as e:
    print(f"❌ Gemini 生成失敗: {e}")
    return f"【{cat_info['title']}】今日最新情報更新！歡迎持續追蹤。"


# ==========================================
# 6. Telegram 智慧發布 (處理字數超限)
# ==========================================
def send_telegram_local_photo(photo_path, caption_text):
  """上傳本地壓好字體的圖片與文案至 Telegram"""
  url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
  with open(photo_path, "rb") as photo_file:
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": caption_text[:1000],  # 截取在安全字元長度
        "parse_mode": "Markdown",
    }
    files = {"photo": photo_file}
    res = requests.post(url, data=payload, files=files, timeout=20)
    if res.status_code == 200:
      print("✅ 成功發送「壓字封面圖 + 完整排版」至 Telegram！")
  else:
    print(f"⚠️ 發送失敗: {res_text.text}")


# ==========================================
# 7. 主排程進入點 (每週 3 篇自動輪替)
# ==========================================
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="AKOMARO xGame 全球發布系統")
  parser.add_argument(
      "-c",
      "--category",
      default="AUTO",
      choices=["AUTO", "SKATE", "SURF", "CLIMB", "EVENT"],
  )
  parser.add_argument("-l", "--lang", default="zh-hk")
  args = parser.parse_args()

  # 自動輪播：基於天數推算，每週一三五發布時自動推進主題
  if args.category == "AUTO":
    epoch_days = (
        datetime.now(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
    ).days
    cat = ROTATION_CYCLE[epoch_days % len(ROTATION_CYCLE)]
  else:
    cat = args.category

  print(
      f"🚀 啟動 xGame 自動發報 -> 語言: [{args.lang}] | 主題: [{cat}] |"
      f" 時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
  )

  # 1. AI 智能文案
  post_content = generate_xgame_post(cat, args.lang)
  print("--------------------------------------------------")
  print(post_content)
  print("--------------------------------------------------")

  # 2. 抓取高畫質動態素材
  media_url = get_pexels_media(cat)

  # 3. 發送至社群
  send_telegram_post(media_url, post_content)
