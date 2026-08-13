import argparse
import html
import io
import os
import random
import re
import sys
import feedparser
from google import genai
from google.genai.errors import APIError
import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

# ==========================================
# 1. 環境變數設定
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")  # Pexels API 金鑰

# ==========================================
# 2. 基本資料與分類設定
# ==========================================
XGAME_CATEGORIES = {
    "SKATE": {
        "title": "滑板 SKATEBOARDING",
        "query": "skateboarding park",
        "osm_tag": 'node["sport"="skateboard"]',
        "tag": "#Skateboarding #SkatePark",
    },
    "SURF": {
        "title": "衝浪 SURFING",
        "query": "surfing ocean waves",
        "osm_tag": 'node["sport"="surfing"]',
        "tag": "#Surfing #WaveRider #浪人日常",
    },
    "CLIMB": {
        "title": "攀岩 CLIMBING",
        "query": "bouldering climbing wall",
        "osm_tag": 'node["sport"="climbing"]',
        "tag": "#Bouldering #Climbing",
    },
    "EVENT": {
        "title": "全球賽事總覽 GLOBAL EVENTS",
        "query": "action sports event",
        "osm_tag": None,
        "tag": "#XGames #WorldSkate #WSL #極限運動",
    },
}

CITIES = [
    {"name": "Tokyo", "country": "Japan", "lat": 35.6762, "lon": 139.6503},
    {"name": "Barcelona", "country": "Spain", "lat": 41.3851, "lon": 2.1734},
    {"name": "Los Angeles", "country": "USA", "lat": 34.0522, "lon": -118.2437},
    {"name": "Paris", "country": "France", "lat": 48.8566, "lon": 2.3522},
    {"name": "Sydney", "country": "Australia", "lat": -33.8688, "lon": 151.2093},
]


# ==========================================
# 3. 抓取 Pexels 實景圖片
# ==========================================
def fetch_pexels_image(keyword, width=1200, height=630):
  """使用 Pexels API 抓取高畫質地點/運動實景圖"""
  if not PEXELS_API_KEY:
    print("ℹ️ 未檢測到 PEXELS_API_KEY，將切換至預設幾何底圖。")
    return None

  url = f"https://api.pexels.com/v1/search?query={keyword}&per_page=5&orientation=landscape"
  headers = {"Authorization": PEXELS_API_KEY}

  try:
    res = requests.get(url, headers=headers, timeout=10)
    if res.status_code == 200:
      data = res.json()
      photos = data.get("photos", [])
      if photos:
        # 隨機挑選一張圖片避免重複
        photo_url = random.choice(photos)["src"]["large2x"]
        img_res = requests.get(photo_url, timeout=10)
        img = Image.open(io.BytesIO(img_res.content)).convert("RGB")

        # 裁切與縮放至 1200x630
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

        # 壓暗圖片以利文字閱讀
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(0.45)
        print(f"📸 成功抓取 Pexels 實景圖片: [{keyword}]")
        return img
  except Exception as e:
    print(f"⚠️ Pexels 圖片抓取失敗: {e}")

  return None


# ==========================================
# 4. OpenStreetMap & RSS
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


def fetch_real_upcoming_events():
  rss_urls = [
      ("World Skate", "http://www.worldskate.org/news?format=feed&type=rss"),
      ("WSL Surfing", "https://www.worldsurfleague.com/rss"),
  ]
  events = []
  for org, url in rss_urls:
    try:
      feed = feedparser.parse(url)
      for entry in feed.entries[:2]:
        events.append({
            "org": org,
            "title": entry.title,
            "published": getattr(entry, "published", "近期"),
        })
    except Exception as e:
      print(f"⚠️ RSS ({org}) 解析失敗: {e}")
  return events


# ==========================================
# 5. Gemini 文案生成 (含 Una 個人簡介)
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
        "【最新賽程數據】：\n"
        + "\n".join([
            f"- {e['org']}: {e['title']} ({e['published']})"
            for e in real_events
        ])
        if real_events
        else "【熱門賽事參考】：X Games, World Skate 巡迴賽, WSL 錦標賽"
    )

    prompt = f"""
你是一位極限運動與浪人特派員 Una (IG: @Una_next)。請以【{target_lang}】針對主題 [{category_key}] 生成 Telegram 報報文案。

{event_snippet}

【嚴格要求】：
1. 開頭必須包含 Una 的簡短招呼（例如：「👋 我係 Una (@Una_next)，今日為大家帶來...」）。
2. 拒絕籠統套話，必須提供具體比賽日期、舉辦城市場館、重點選手與官方連結。
3. 第一行必須輸出：`COVER_TITLE: [簡短封面大標題，10-12字以內]`
4. 正文排版請嚴格保持以下結構：

🏆 賽事名稱：[具體全名]
📅 舉辦時間：[YYYY/MM/DD 或具體時區時間]
📍 比賽地點：[城市, 場館]
🔥 核心看點：[具體選手/熱門對決項目]
📺 直播/官網：[附上官方網址]

— By Una (@Una_next)
{cat_info['tag']} #xGameRadar
"""
  else:
    venue_name = fetch_osm_venue(category_key, city)
    venue_context = (
        f"地點：{city['country']} {city['name']}「{venue_name}」"
        if venue_name
        else f"地點：{city['country']} {city['name']}"
    )

    prompt = f"""
你是一位極限運動與浪人特派員 Una (IG: @Una_next)。請以【{target_lang}】針對主題 [{cat_info['title']}] 生成 Telegram/IG 報報文案。

【情境資訊】：{venue_context}

【嚴格要求】：
1. 開頭必須包含 Una 的個人化簡介語（例如：「👋 我係 Una (@Una_next)，今日帶大家探索...」）。
2. 若為滑浪點/場地，請提供具體浪況/場地特色與裝備建議。
3. 第一行必須輸出：`COVER_TITLE: [簡短封面大標題，10-12字以內]`
4. 正文排版請嚴格保持以下結構：

📍 焦點場地：[場地名稱與具體位置]
🔥 核心特色：[浪況/地形/場地設施]
🔰 新手建議：[具體裝備或浪況提醒]
⚠️ 注意事項：[安全規範或在地禮儀]
🌐 相關資訊：[官方或社群搜尋關鍵字/連結]

— By Una (@Una_next)
{cat_info['tag']} #{city['name']} #xGameRadar
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
    return cover_title, sub_title, caption_text, cat_info["query"]
  except APIError as e:
    print(f"❌ Gemini 生成失敗: {e}")
    return (
        f"{category_key} SPOTLIGHT",
        "XGAME RADAR",
        (
            "👋 我係 Una (@Una_next)！今日最新極限情報更新～\n\n"
            f"#xGameRadar"
        ),
        cat_info["query"],
    )


# ==========================================
# 6. 底圖與壓字繪製
# ==========================================
def create_obsidian_background(width=1200, height=630):
  """預設備用底圖"""
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
  """優先抓取 Pexels 實景圖，抓不到則退回備用底圖並壓字"""
  img = fetch_pexels_image(query_keyword)
  if img is None:
    img = create_obsidian_background(1200, 630)

  draw = ImageDraw.Draw(img)
  font_sub = get_font(24)
  font_main = get_font(52)
  font_footer = get_font(20)

  # 黃色圓點 + 副標題
  draw.ellipse([80, 215, 92, 227], fill=(255, 204, 0))
  draw.text((102, 208), sub_title, font=font_sub, fill=(255, 204, 0))

  # 主標題自動分行
  max_width = 1000
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

  y_offset = 260
  for line in lines[:2]:
    draw.text((80, y_offset), line, font=font_main, fill=(255, 255, 255))
    y_offset += 70

  # 頁尾標註 Una_next 專屬 Sign-off
  draw.text(
      (80, 530),
      "xGame Radar · Curated by Una (@Una_next)",
      font=font_footer,
      fill=(200, 200, 210),
  )

  img.save(output_path, quality=95)
  print(f"🎨 封面圖片已成功生成: {output_path}")
  return output_path


# ==========================================
# 7. Telegram 發布 (HTML 模式 + 降級保護)
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
      choices=["AUTO", "SKATE", "SURF", "CLIMB", "EVENT"],
      help="主題類別",
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
    category_key = random.choice(["SKATE", "SURF", "CLIMB", "EVENT"])

  print(
      f"🚀 啟動 xGame Radar -> 主題: [{category_key}] | 語言: [{args.lang}]"
  )

  # 1. 生成文案與大標題 (含 Una 簡介)
  cover_title, sub_title, caption_text, query_keyword = generate_xgame_content(
      category_key, args.lang
  )

  # 2. 下載 Pexels 實景圖片並生成壓字封面
  photo_path = create_cover_image(
      cover_title, sub_title, query_keyword, "xgame_post.jpg"
  )

  # 3. 發布至 Telegram
  send_telegram_post(photo_path, caption_text)


if __name__ == "__main__":
  main()
