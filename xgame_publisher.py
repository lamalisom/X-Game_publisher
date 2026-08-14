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
from datetime import datetime, timedelta
from dateutil import parser  # 需 pip install python-dateutil


# ==========================================
# 1. 環境變數設定
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

# ==========================================
# 2. 基本資料與分類設定 (全球熱門地點)
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
    "EVENT": {
        "title": "全球賽事總覽 GLOBAL EVENTS",
        "query": "action sports competition xgames",
        "osm_tag": None,
        "tag": "#XGames #WorldSkate #WSL #IFSC #極限運動",
    },
}

# 城市與地點清單（含香港、台灣、印尼、葡萄牙、瑞典等極限運動勝地）
CITIES = [
    # 亞洲 Asia & 印尼專區 Indonesia
    {
        "name": "Bali",
        "country": "Indonesia",
        "lat": -8.4095,
        "lon": 115.1889,
    },  # 印尼峇里島
    {
        "name": "Mentawai",
        "country": "Indonesia",
        "lat": -2.1333,
        "lon": 99.5500,
    },  # 印尼棉蘭威群島
    {
        "name": "Lombok",
        "country": "Indonesia",
        "lat": -8.6509,
        "lon": 116.3249,
    },  # 印尼龍目島
    {
        "name": "Jakarta",
        "country": "Indonesia",
        "lat": -6.2088,
        "lon": 106.8456,
    },  # 印尼雅加達
    {
        "name": "Hong Kong",
        "country": "Hong Kong",
        "lat": 22.3193,
        "lon": 114.1694,
    },  # 香港
    {
        "name": "Taipei",
        "country": "Taiwan",
        "lat": 25.0330,
        "lon": 121.5654,
    },  # 台灣台北
    {
        "name": "Taitung",
        "country": "Taiwan",
        "lat": 22.7583,
        "lon": 121.1444,
    },  # 台灣台東
    {
        "name": "Yilan",
        "country": "Taiwan",
        "lat": 24.7570,
        "lon": 121.7530,
    },  # 台灣宜蘭
    {
        "name": "Tokyo",
        "country": "Japan",
        "lat": 35.6762,
        "lon": 139.6503,
    },  # 日本東京
    # 歐洲 Europe
    {
        "name": "Stockholm",
        "country": "Sweden",
        "lat": 59.3293,
        "lon": 18.0686,
    },  # 瑞典斯德哥爾摩
    {
        "name": "Lisbon",
        "country": "Portugal",
        "lat": 38.7223,
        "lon": -9.1393,
    },  # 葡萄牙里斯本
    {
        "name": "Nazaré",
        "country": "Portugal",
        "lat": 39.6028,
        "lon": -9.0717,
    },  # 葡萄牙 Nazaré 巨浪鎮
    {
        "name": "Ericeira",
        "country": "Portugal",
        "lat": 38.9622,
        "lon": -9.4172,
    },  # 葡萄牙衝浪區
    {
        "name": "Barcelona",
        "country": "Spain",
        "lat": 41.3851,
        "lon": 2.1734,
    },  # 西班牙巴塞隆納
    {
        "name": "Paris",
        "country": "France",
        "lat": 48.8566,
        "lon": 2.3522,
    },  # 法國巴黎
    {
        "name": "Innsbruck",
        "country": "Austria",
        "lat": 47.2692,
        "lon": 11.4041,
    },  # 奧地利因斯布魯克
    # 美洲 & 澳洲 Americas & Oceania
    {"name": "Los Angeles", "country": "USA", "lat": 34.0522, "lon": -118.2437},
    {"name": "Sydney", "country": "Australia", "lat": -33.8688, "lon": 151.2093},
    {
        "name": "Gold Coast",
        "country": "Australia",
        "lat": -28.0167,
        "lon": 153.4000,
    },
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
        img = enhancer.enhance(0.40)
        print(f"📸 成功抓取 Pexels 實景圖片: [{keyword}]")
        return img
  except Exception as e:
    print(f"⚠️ Pexels 圖片抓取失敗: {e}")

  return None


# ==========================================
# 4. OpenStreetMap & RSS 賽事抓取
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
  now = datetime.now()
  future_3_months = now + timedelta(days=90)

  for org, url in rss_urls:
    try:
      feed = feedparser.parse(url)
      for entry in feed.entries:
        pub_date_str = getattr(entry, "published", None)
        if pub_date_str:
          try:
            pub_date = parser.parse(pub_date_str).replace(tzinfo=None)
            # 篩選日期落在：今天 ~ 未來 90 天之內（或過去近期發布的未來賽事）
            if now <= pub_date <= future_3_months:
              events.append({
                  "org": org,
                  "title": entry.title,
                  "published": pub_date.strftime("%Y-%m-%d"),
              })
          except Exception:
            continue
    except Exception as e:
      print(f"⚠️ RSS ({org}) 解析失敗: {e}")

  return events[:5]  # 回傳未來3個月內最多 5 筆重點賽事
    
# ==========================================
# 5. Gemini 文案生成 (嚴格分類 + 精簡字數)
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
            f"- {e['org']}: {e['title']} ({e['published']})" for e in real_events
        ])
        if real_events
        else (
            "【熱門賽事參考】：X Games, World Skate 巡迴賽, WSL 錦標賽, IFSC"
            " 攀岩世界盃"
        )
    )

    prompt = f"""
你是一位極限運動特派員 Una (IG: @Una_next)。請以【{target_lang}】針對全球極限賽事生成 Telegram/IG 精簡速報。

{event_snippet}

【嚴格要求】：
1. 開頭包含 Una 短招呼語（如：「👋 我係 Una (@Una_next)！」）。
2. 資訊必須【嚴格分開類別，獨立介紹】，絕不可揉杂在一起。
3. 每個類別 1~2 句，總字數控制在 250 字內，精簡乾淨。
4. 第一行必須輸出：`COVER_TITLE: [簡短封面大標題，10-12字以內]`
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
4. 第一行必須輸出：`COVER_TITLE: [簡短封面大標題，10-12字以內]`
5. 正文格式必須完全符合以下獨立分區：

👋 我係 Una (@Una_next)！今日極限情報：

📍【場地介紹】：[地點/場館名稱 + 地形/浪況/難度分級]

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
# 6. 底圖與壓字繪製 (標題完美居中優化)
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
  font_sub = get_font(26)
  font_main = get_font(52)
  font_footer = get_font(20)

  width, height = img.size  # 1200, 630

  # 1. 主標題自動分行 (限制在中央 580px 寬度內，確保社群媒體 1:1 裁切時完整顯示)
  max_width = 580
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

  display_lines = lines[:2]
  line_height = 70
  title_block_height = len(display_lines) * line_height

  # 2. 計算總區塊高度並進行垂直居中
  total_block_height = 35 + 20 + title_block_height + 40 + 25
  start_y = (height - total_block_height) // 2

  # 3. 繪製副標題 (黃色圓點 + 副標題，組件水平居中)
  dot_radius = 6
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

  # 4. 繪製主標題 (每行水平居中，並加入文字陰影提升閱讀對比度)
  y_title = y_sub + 55
  for line in display_lines:
    line_bbox = draw.textbbox((0, 0), line, font=font_main)
    line_w = line_bbox[2] - line_bbox[0]
    line_x = (width - line_w) // 2

    # 微弱黑色陰影
    draw.text(
        (line_x + 2, y_title + 2), line, font=font_main, fill=(0, 0, 0, 200)
    )
    draw.text((line_x, y_title), line, font=font_main, fill=(255, 255, 255))
    y_title += line_height

  # 5. 繪製頁尾標註 (水平居中)
  footer_text = "xGame Radar · Curated by Una (@Una_next)"
  footer_bbox = draw.textbbox((0, 0), footer_text, font=font_footer)
  footer_w = footer_bbox[2] - footer_bbox[0]
  footer_x = (width - footer_w) // 2
  y_footer = y_title + 15

  draw.text(
      (footer_x, y_footer), footer_text, font=font_footer, fill=(210, 210, 220)
  )

  img.save(output_path, quality=95)
  print(f"🎨 封面圖片已成功生成（已完美雙向居中）: {output_path}")
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

  print(f"🚀 啟動 xGame Radar -> 主題: [{category_key}] | 語言: [{args.lang}]")

  # 1. 生成精簡分區文案與封面標題
  cover_title, sub_title, caption_text, query_keyword = generate_xgame_content(
      category_key, args.lang
  )

  # 2. 下載 Pexels 實景圖片並生成雙向居中壓字封面
  photo_path = create_cover_image(
      cover_title, sub_title, query_keyword, "xgame_post.jpg"
  )

  # 3. 發布至 Telegram
  send_telegram_post(photo_path, caption_text)


if __name__ == "__main__":
  main()
