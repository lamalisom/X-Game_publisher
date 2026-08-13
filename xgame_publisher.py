import argparse
import html
import os
import random
import re
import sys
import feedparser
from google import genai
from google.genai.errors import APIError
import requests
from PIL import Image, ImageDraw, ImageFont

# ==========================================
# 1. 環境變數設定
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ==========================================
# 2. 基本資料與分類設定
# ==========================================
XGAME_CATEGORIES = {
    "SKATE": {
        "title": "滑板 SKATEBOARDING",
        "osm_tag": 'node["sport"="skateboard"]',
        "tag": "#Skateboarding #SkatePark",
    },
    "SURF": {
        "title": "衝浪 SURFING",
        "osm_tag": 'node["sport"="surfing"]',
        "tag": "#Surfing #WaveRider",
    },
    "CLIMB": {
        "title": "攀岩 CLIMBING",
        "osm_tag": 'node["sport"="climbing"]',
        "tag": "#Bouldering #Climbing",
    },
    "EVENT": {
        "title": "全球賽事總覽 GLOBAL EVENTS",
        "osm_tag": None,
        "tag": "#XGames #WorldSkate #WSL #ActionSports",
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
# 3. 抓取 OpenStreetMap 場地資料
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


# ==========================================
# 4. 抓取 RSS 賽事資料
# ==========================================
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
# 5. Gemini 文案生成 (精準細節約束)
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
        else "【熱門賽事】：X Games, World Skate 巡迴賽, WSL 錦標賽"
    )

    prompt = f"""
你是一位極限運動快訊編輯 xGame Radar。請以【{target_lang}】撰寫一份精簡極限運動「賽事快報」。

{event_snippet}

【嚴格要求】：
1. 拒絕籠統套話（例如「全球高手雲集」、「各大平台直播」），必須包含具體賽事名稱、看點或資訊。
2. 總字數必須控制在 150 字以內，清晰易讀。
3. 第一行必須輸出：`COVER_TITLE: [簡短封面大標題，10-12字以內]`
4. 正文格式：
   🏆 **重點賽事**：[具體賽事名稱與舉辦地點]
   ⚡ **核心看點**：[賽程亮點/熱門項目]
   📺 **觀賽途徑**：[官方直播/轉播渠道]
5. 結尾加上標籤：{cat_info['tag']} #xGameRadar
"""
  else:
    venue_name = fetch_osm_venue(category_key, city)
    venue_context = (
        f"地點：{city['country']} {city['name']}「{venue_name}」"
        if venue_name
        else f"地點：{city['country']} {city['name']}"
    )

    prompt = f"""
你是一位極限運動快訊編輯 xGame Radar。請以【{target_lang}】撰寫一份「{cat_info['title']}」精簡焦點情報。

【情境】：{venue_context}

【嚴格要求】：
1. 拒絕抽象套話，請給出明確特色與建議。
2. 總字數必須控制在 150 字以內。
3. 第一行必須輸出：`COVER_TITLE: [簡短封面大標題，10-12字以內]`
4. 正文格式：
   📍 **焦點場地**：[場地名稱與核心特色]
   🔰 **新手必知**：[具體裝備或入門提醒]
   ⚠️ **核心規則**：[具體安全或禮儀規範]
5. 結尾加上標籤：{cat_info['tag']} #{city['name']} #xGameRadar
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
        f"【{cat_info['title']}】今日最新情報更新！\n\n#xGameRadar",
    )


# ==========================================
# 6. 底圖與繪製 (黑曜石科技漸層風格)
# ==========================================
def create_obsidian_background(width=1200, height=630):
  """產生深色霓虹幾何漸層底圖，避免圖片純黑質感差"""
  base = Image.new("RGB", (width, height))
  draw = ImageDraw.Draw(base)

  # 1. 繪製深紫藍至黑色的漸層
  for y in range(height):
    r = int(18 - (y / height) * 12)
    g = int(14 - (y / height) * 10)
    b = int(38 - (y / height) * 24)
    draw.line([(0, y), (width, y)], fill=(r, g, b))

  # 2. 科技感網格與霓虹光斑
  overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
  draw_overlay = ImageDraw.Draw(overlay)

  grid_size = 40
  grid_color = (0, 210, 255, 12)

  for x in range(0, width, grid_size):
    draw_overlay.line([(x, 0), (x, height)], fill=grid_color, width=1)
  for y in range(0, height, grid_size):
    draw_overlay.line([(0, y), (width, y)], fill=grid_color, width=1)

  # 光斑
  draw_overlay.ellipse([-100, -100, 450, 450], fill=(138, 43, 226, 30))
  draw_overlay.ellipse(
      [width - 350, height - 350, width + 100, height + 100],
      fill=(0, 212, 255, 25),
  )

  final_bg = Image.alpha_composite(base.convert("RGBA"), overlay)
  return final_bg.convert("RGB")


def get_font(size):
  """尋找可用中文字型"""
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


def create_cover_image(cover_title, sub_title, output_path="cover.jpg"):
  """生成帶有幾何質感與大標題壓字的封面圖"""
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

  # 頁尾
  draw.text(
      (80, 530),
      "xGame Radar · Global Action Sports Dispatch",
      font=font_footer,
      fill=(160, 160, 170),
  )

  img.save(output_path, quality=95)
  print(f"🎨 封面圖片已成功生成: {output_path}")
  return output_path


# ==========================================
# 7. Telegram 發布 (HTML 模式 + 降級保護)
# ==========================================
def format_text_for_telegram_html(text):
  """將 Markdown 安全轉義為 Telegram HTML"""
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
      # 1. 優先使用 HTML 發送
      payload = {
          "chat_id": TELEGRAM_CHAT_ID,
          "caption": html_caption,
          "parse_mode": "HTML",
      }
      files = {"photo": photo_file}
      res = requests.post(url, data=payload, files=files, timeout=20)

      # 2. 自動降級為純文字發送 (防止語法解析崩潰)
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

  # 1. 生成文案與大標題
  cover_title, sub_title, caption_text = generate_xgame_content(
      category_key, args.lang
  )

  # 2. 生成黑曜石幾何壓字圖片
  photo_path = create_cover_image(cover_title, sub_title, "xgame_post.jpg")

  # 3. 發布至 Telegram
  send_telegram_post(photo_path, caption_text)


if __name__ == "__main__":
  main()
