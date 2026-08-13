import argparse
from datetime import datetime, timezone
import glob
import os
import random
import feedparser
from google import genai
from google.genai.errors import APIError
from PIL import Image, ImageDraw, ImageFont
import requests

# ==========================================
# 1. 環境變數驗證 (已移除 Pexels API Key)
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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
    },  # 衝浪聖地
    {"name": "Lisbon", "country": "Portugal", "lat": 38.7223, "lon": -9.1393},
    {"name": "Hong Kong", "country": "China", "lat": 22.3193, "lon": 114.1694},
]

XGAME_CATEGORIES = {
    "SKATE": {
        "title": "🛹 全球滑板場與街頭 Spot 探索",
        "tag": "#Skateboarding #Skatepark #街頭滑板 #滑板新手",
        "osm_tag": '["sport"="skateboard"]',
    },
    "SURF": {
        "title": "🌊 全球浪點與衝浪指南",
        "tag": "#Surfing #SurfSpot #衝浪人生 #浪人日記",
        "osm_tag": '["sport"="surfing"]',
    },
    "CLIMB": {
        "title": "🧗 抱石與攀岩場地指南",
        "tag": "#Bouldering #RockClimbing #抱石日常 #攀岩初學者",
        "osm_tag": '["sport"="climbing"]',
    },
    "EVENT": {
        "title": "🏆 全球 xGame 賽事盛事雷達",
        "tag": "#XGames #WorldSkate #WSL #極限賽事 #賽事速報",
        "osm_tag": None,
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
# 4. 本地圖片讀取 (方案 A 核心邏輯)
# ==========================================
def get_local_media(category_key):
  """隨機讀取 assets/<category>/ 資料夾內的圖片"""
  category_dir = os.path.join("assets", category_key.lower())

  image_extensions = ("*.jpg", "*.jpeg", "*.png", "*.webp")
  image_files = []

  # 1. 優先從專屬主題資料夾撈圖 (如 assets/skate/)
  if os.path.exists(category_dir):
    for ext in image_extensions:
      image_files.extend(glob.glob(os.path.join(category_dir, ext)))

  # 2. 若專屬資料夾沒圖，嘗試從 assets/ 根目錄撈圖
  if not image_files and os.path.exists("assets"):
    for ext in image_extensions:
      image_files.extend(glob.glob(os.path.join("assets", ext)))

  if image_files:
    chosen_file = random.choice(image_files)
    print(f"🖼️ 使用本地素材照片: {chosen_file}")
    return chosen_file

  print("⚠️ 找不到本地圖片素材，將使用預設黑曜石幾何底圖。")
  return None

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
# 5. Gemini 文案與封面標題生成 (極簡精華版)
# ==========================================
def generate_xgame_content(category_key, target_lang="zh-hk"):
  city = random.choice(CITIES)
  cat_info = XGAME_CATEGORIES[category_key]

  if category_key == "EVENT":
    real_events = fetch_real_upcoming_events()
    event_snippet = (
        "【最新賽程數據】：\n"
        + "\n".join([
            f"- {e['org']}: {e['title']} ({e['published']})"
            for e in real_events
        ])
        if real_events
        else "【熱門賽事】：X Games, World Skate 巡迴賽, WSL 錦標賽"
    )

    prompt = f"""
你是一位極限運動快訊編輯。請以【{target_lang}】撰寫一份「極簡賽事快報」。

{event_snippet}

【嚴格字數與格式要求】：
1. 總字數必須控制在 120 字以內（不含標籤），只保留核心重要標題與重點，禁止長篇大論。
2. 必須在第一行輸出：`COVER_TITLE: [簡短封面大標題，10-12字以內]`
3. 正文只輸出 3 個極短列點：
   - 🏆 **重點賽事**
   - ⚡ **看點/時間**
   - 📺 **觀賽途徑**
4. 結尾加上標籤：{cat_info['tag']} #xGameRadar
"""
  else:
    venue_name = fetch_osm_venue(category_key, city)
    venue_context = (
        f"地點：{city['country']} {city['name']}「{venue_name}」"
        if venue_name
        else f"地點：{city['country']} {city['name']}"
    )

    prompt = f"""
你是一位極限運動快訊編輯。請以【{target_lang}】撰寫一份「{cat_info['title']}」極簡重點情報。

【情境】：{venue_context}

【嚴格字數與格式要求】：
1. 總字數必須控制在 120 字以內（不含標籤），只保留核心重要標題與重點，禁止長篇大論。
2. 必須在第一行輸出：`COVER_TITLE: [簡短封面大標題，10-12字以內]`
3. 正文只輸出 3 個極短列點：
   - 📍 **焦點場地**（一句話講述亮點）
   - 🔰 **新手必知**（一句話重點提醒）
   - ⚠️ **核心規則**（一句話安全/禮儀）
4. 結尾加上標籤：{cat_info['tag']} #{city['name']} #xGameRadar
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
# 6. 封面圖片合成 (Pillow 本地圖片 + 遮罩排版)
# ==========================================
def generate_cover_image(
    image_path,
    main_title,
    sub_title="XGAME RADAR",
    output_path="cover_output.jpg",
):
  """載入本地圖片，繪製漸層遮罩並壓印標題"""
  if image_path and os.path.exists(image_path):
    try:
      img = Image.open(image_path).convert("RGBA")
    except Exception as e:
      print(f"⚠️ 開啟本地圖片失敗: {e}，改用深色底圖")
      img = Image.new("RGBA", (1080, 1080), (18, 18, 18, 255))
  else:
    # 若沒有圖片素材，使用黑曜石極簡底底色
    img = Image.new("RGBA", (1080, 1080), (18, 18, 18, 255))

  # 統一裁切與縮放為正方形 1080x1080
  img = img.resize((1080, 1080), Image.Resampling.LANCZOS)
  width, height = img.size

  # 建立底部暗色漸層遮罩
  overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
  draw_overlay = ImageDraw.Draw(overlay)
  grad_start = int(height * 0.48)

  for y in range(grad_start, height):
    alpha = int(220 * ((y - grad_start) / (height - grad_start)))
    draw_overlay.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))

  img = Image.alpha_composite(img, overlay)
  draw = ImageDraw.Draw(img)

  # 載入字型
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

  # 繪製分類副標題 (螢光黃)
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

  # 繪製品牌標籤
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
# 7. Telegram 發布
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
        print("✅ 成功發送「壓字圖片 + 完整文章」至 Telegram！")
        return
      else:
        print(f"⚠️ Telegram 發送報錯: {res.text}")
  except Exception as e:
    print(f"⚠️ 圖片發送異常: {e}")


# ==========================================
# 8. 主程式進入點
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

  print(f"🚀 啟動 xGame Radar -> 主題: [{cat}] | 語言: [{args.lang}]")

  # 1. 產生文案與封面標題
  cover_title, sub_title, post_caption = generate_xgame_content(cat, args.lang)

  # 2. 獲取本地圖片路徑 (方案 A)
  local_image_path = get_local_media(cat)

  # 3. 合成封面圖片
  cover_file = generate_cover_image(
      local_image_path, cover_title, sub_title, "xgame_cover.jpg"
  )

  # 4. 發布至 Telegram
  send_telegram_post(cover_file, post_caption)
