import os
import re
import sys
import json
import random
import sqlite3
import base64
import requests
import feedparser
import asyncio
import time
from datetime import datetime, timedelta
from dateutil.parser import parse as parsedate_to_datetime
from urllib.parse import quote

import boto3
from google import genai
from google.genai import types
from playwright.async_api import async_playwright

# ==========================================
# 1. 全局配置與極限運動類別定義
# ==========================================
DB_FILE = "xgame_radar.db"

XGAME_CATEGORIES = {
    "SKATE": {"name": "Skateboarding", "icon": "🛹", "query": "skateboarding action", "rss": "[https://www.skateboarding.com/.rss/full/](https://www.skateboarding.com/.rss/full/)"},
    "SURF": {"name": "Surfing", "icon": "🏄‍♂️", "query": "surfing big wave", "rss": "[https://www.surfer.com/.rss/full/](https://www.surfer.com/.rss/full/)"},
    "CLIMBING": {"name": "Rock Climbing", "icon": "🧗‍♂️", "query": "rock climbing extreme", "rss": "[https://www.climbing.com/.rss/full/](https://www.climbing.com/.rss/full/)"},
    "BMX": {"name": "BMX Racing / Freestyle", "icon": "🚲", "query": "bmx freestyle", "rss": "[https://bmx.transworld.net/feed/](https://bmx.transworld.net/feed/)"},
    "EVENT": {"name": "Global Extreme Sports Event", "icon": "🏆", "query": "extreme sports event", "rss": "[https://xgames.com/feed](https://xgames.com/feed)"}
}

# 替換已失效的 source.unsplash.com，改用穩定的高解析度極限運動範例圖片
FALLBACK_IMAGES = {
    "SKATE": "[https://images.pexels.com/photos/165236/pexels-photo-165236.jpeg](https://images.pexels.com/photos/165236/pexels-photo-165236.jpeg)",
    "SURF": "[https://images.pexels.com/photos/67386/pexels-photo-67386.jpeg](https://images.pexels.com/photos/67386/pexels-photo-67386.jpeg)",
    "CLIMBING": "[https://images.pexels.com/photos/668353/pexels-photo-668353.jpeg](https://images.pexels.com/photos/668353/pexels-photo-668353.jpeg)",
    "BMX": "[https://images.pexels.com/photos/568805/pexels-photo-568805.jpeg](https://images.pexels.com/photos/568805/pexels-photo-568805.jpeg)",
    "EVENT": "[https://images.pexels.com/photos/848618/pexels-photo-848618.jpeg](https://images.pexels.com/photos/848618/pexels-photo-848618.jpeg)"
}

# ==========================================
# 2. SQLite 資料庫模組
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posted_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE,
            link TEXT,
            posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def is_already_posted(title):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM posted_articles WHERE title = ?", (title,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def record_posted_article(title, link=""):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO posted_articles (title, link) VALUES (?, ?)", (title, link))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

# ==========================================
# 3. RSS Feed 抓取模組
# ==========================================
def fetch_latest_rss_news(category_key):
    cat_info = XGAME_CATEGORIES.get(category_key, XGAME_CATEGORIES["SKATE"])
    rss_url = cat_info.get("rss")
    
    if not rss_url:
        return ""

    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:5]:
            title = entry.get("title", "")
            if not is_already_posted(title):
                summary = entry.get("summary", entry.get("description", ""))
                clean_summary = re.sub('<[^<]+?>', '', summary)[:200]
                return f"【RSS 新聞參考】標題: {title}\n摘要: {clean_summary}"
    except Exception as e:
        print(f"⚠️ RSS 抓取失敗: {e}")
    return ""

# ==========================================
# 4. Gemini 內容生成模組
# ==========================================
def generate_xgame_content(category_key="", topic_type="", topic_desc="", target_lang="zh-hk"):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ 錯誤：未偵測到 GEMINI_API_KEY 環境變數！")
        return ("xGame Radar", "GLOBAL · EVENT", "請設定 API Key", "GLOBAL")

    client = genai.Client(api_key=api_key)

    if not category_key or not category_key.strip():
        category_key = random.choice(list(XGAME_CATEGORIES.keys()))
    display_category = category_key.strip()

    rss_context = fetch_latest_rss_news(display_category)

    weekday = datetime.now().weekday()
    SCHEDULE_MAP = {
        0: {"type": "EVENT", "title": "🗓️ 賽事雷達"},
        1: {"type": "SPOT", "title": "🛹 場地導覽"},
        2: {"type": "ATHLETE", "title": "🏆 焦點人物"},
        3: {"type": "SAFETY", "title": "🛡️ 安全與裝備"},
        4: {"type": "EVENT", "title": "🗓️ 賽事雷達"},
        5: {"type": "RECORD", "title": "🔥 極限紀錄"},
        6: {"type": "TIPS", "title": "🎯 技巧解密"}
    }

    current_schedule = SCHEDULE_MAP.get(weekday, SCHEDULE_MAP[0])
    active_topic = topic_type if topic_type else current_schedule["type"]
    active_title = current_schedule["title"]

    if active_topic == "EVENT":
        detail_instruction = f"""
請搜尋並整理【{display_category}】領域近期或即將舉辦的 2-3 個真實賽事。
【必須包含內容】:
1. 賽事名稱與舉辦日期（如：2026年11月7日 - 11月8日）。
2. 舉辦地點（城市與場館名稱）。
3. 賽事特質/亮點（如：世界錦標賽積分賽、頂尖選手雲集等）。
4. 參賽/觀賽資訊：請明確指出「公開報名/邀請制」以及「官方購票/觀看直播管道（寫出官方名稱或搜尋關鍵字）」。
* 注意：切勿寫出「未來4-7個月」等字眼，直接呈現日期與資訊即可。
"""
    elif active_topic == "SPOT":
        detail_instruction = f"請搜尋並介紹【{display_category}】領域最著名的 1-2 個國際或區域級極限場地，包含地點、規格與體驗資訊。"
    elif active_topic == "ATHLETE":
        detail_instruction = f"請介紹【{display_category}】領域的一位代表性運動員或新星，包含代表國家、招牌動作與重要成就。"
    elif active_topic == "SAFETY":
        detail_instruction = f"請針對【{display_category}】極限運動，分享重要的安全意識、防護技巧或裝備知識，並給出 3 個具體建議。"
    elif active_topic == "RECORD":
        detail_instruction = f"請介紹【{display_category}】領域一項令人震撼的世界紀錄或歷史性極限挑戰時刻。"
    else:
        detail_instruction = f"請分享【{display_category}】極限運動的一項經典招式進階指南，含動作拆解與新手常犯錯誤。"

    lang_map = {
        "zh-hk": "繁體中文（廣東話/香港口語，語氣熱血且極具社群吸引力）",
        "zh-cn": "簡體中文（專業熱血的極限運動社群口吻）",
        "ja": "日文（專業且地道的極限運動風格）",
        "en": "英文（Authentic Action Sports Community Style）"
    }
    selected_lang_desc = lang_map.get(target_lang, lang_map["zh-hk"])

    prompt = f"""
你是一位專注於全球極限運動的熱血社群小編 Una (@Una_next)。
今日專欄主題：【{active_title}】（項目：{display_category}）
{rss_context}

{detail_instruction}

【語言與風格要求】:
- 完全使用 **{selected_lang_desc}** 撰寫。
- 語氣熱血、幹脆利落，大量善用 Emoji。

【結構與字數限制】:
- 總字數控制在 **250 至 350 字以內**。
- 格式要求：
  - ⚡ **1 句熱血開頭**
  - 📌 **主要內容條列**
  - 🔥 **1 句亮點總結**
  - 💬 **1 句 Call to Action** + 社群 Tag

請嚴格按照以下格式輸出，並用三條橫線 `---` 將各部分分開，不要輸出 Markdown 代碼塊（```）：

封面主標題
---
封面副標題
---
城市英文名或主題關鍵字
---
正文內容
"""

    print(f"🤖 今日專欄: 【{active_title}】，正在呼叫 Gemini API...")

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash"]
    for model_name in models_to_try:
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.4,
                        tools=[{"google_search": {}}]
                    )
                )

                raw_text = response.text.strip()
                raw_text = re.sub(r'^```\w*\n?', '', raw_text)
                raw_text = re.sub(r'\n?```$', '', raw_text)

                parts = [p.strip() for p in raw_text.split("---")]

                if len(parts) >= 4:
                    print(f"✅ 模型 [{model_name}] 生成成功！")
                    return parts[0], parts[1], parts[3], parts[2].upper()
                else:
                    return f"{display_category} {active_title}", f"GLOBAL · {active_topic}", raw_text, "GLOBAL"

            except Exception as e:
                err_msg = str(e)
                print(f"⚠️ [{model_name}] 請求失敗 (第 {attempt} 次): {err_msg[:100]}")
                if "503" in err_msg or "UNAVAILABLE" in err_msg or "429" in err_msg:
                    if attempt < max_retries:
                        time.sleep(5)
                        continue
                break

    return f"{display_category} 熱血企劃", f"GLOBAL · {active_topic}", f"⚡ 各位極限迷！今日【{display_category}】情報熱血更新中！\n\n💬 留言話我知你最想睇咩！👇\n#Una_next #{display_category} #xGameRadar", "GLOBAL"

# ==========================================
# 5. Pexels 背景圖片抓取模組
# ==========================================
def get_pexels_bg_url(category_key):
    pexels_api_key = os.getenv("PEXELS_API_KEY", "").strip("'\" ")
    cat_info = XGAME_CATEGORIES.get(category_key, XGAME_CATEGORIES.get("SKATE", {}))
    search_term = cat_info.get("query", "action sports")

    if pexels_api_key:
        for query_attempt in [search_term, "extreme sports"]:
            try:
                url = f"https://api.pexels.com/v1/search?query={quote(query_attempt)}&per_page=10&orientation=square"
                headers = {
                    "Authorization": pexels_api_key,
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                res = requests.get(url, headers=headers, timeout=8)
                if res.status_code == 200:
                    photos = res.json().get("photos", [])
                    if photos:
                        selected = random.choice(photos[:5])
                        img_url = selected["src"].get("large2x") or selected["src"].get("large")
                        if img_url:
                            print(f"✅ Pexels 成功抓取【{query_attempt}】背景圖！")
                            return img_url
            except Exception as e:
                print(f"⚠️ Pexels 抓取例外: {e}")

    fallback_url = FALLBACK_IMAGES.get(category_key, FALLBACK_IMAGES["EVENT"])
    print(f"ℹ️ 啟用保底背景圖: {category_key}")
    return fallback_url

def get_image_base64(url_or_path):
    if not url_or_path:
        return None
    try:
        if url_or_path.startswith("http"):
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url_or_path, headers=headers, timeout=10)
            if resp.status_code == 200:
                encoded = base64.b64encode(resp.content).decode("utf-8")
                print(f"🖼️ Base64 轉換成功！字串長度: {len(encoded)}")
                return f"data:image/jpeg;base64,{encoded}"
    except Exception as e:
        print(f"❌ Base64 轉換錯誤: {e}")
    return None

# ==========================================
# 6. Playwright 卡片圖片生成模組
# ==========================================
async def generate_card_image(category_key, cover_title, sub_title, output_filename="xgame_card.png"):
    cat_info = XGAME_CATEGORIES.get(category_key, XGAME_CATEGORIES.get("EVENT"))
    icon = cat_info.get("icon", "🛹")

    bg_image_url = get_pexels_bg_url(category_key)
    base64_bg = get_image_base64(bg_image_url)

    if base64_bg:
        bg_css = f"""
          background-image: linear-gradient(180deg, rgba(0, 0, 0, 0.35) 0%, rgba(0, 0, 0, 0.75) 100%), url('{base64_bg}');
          background-position: center center;
          background-size: cover;
          background-repeat: no-repeat;
        """
    else:
        bg_css = "background: linear-gradient(135deg, #0d0d0d 0%, #1a1a1a 100%);"

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
          {bg_css}
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          color: #ffffff;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 80px;
        }}
        .header {{ display: flex; justify-content: space-between; align-items: center; }}
        .badge {{ background: #FF4500; color: #fff; font-weight: bold; padding: 12px 24px; border-radius: 30px; font-size: 24px; letter-spacing: 2px; }}
        .subtitle-top {{ font-size: 26px; color: #dddddd; letter-spacing: 1px; }}
        .content {{ margin-top: auto; margin-bottom: 60px; }}
        .icon {{ font-size: 80px; margin-bottom: 20px; }}
        .title {{ font-size: 64px; font-weight: 900; line-height: 1.25; text-shadow: 0 4px 20px rgba(0,0,0,0.8); }}
        .footer {{ border-top: 2px solid rgba(255,255,255,0.2); padding-top: 30px; display: flex; justify-content: space-between; align-items: center; }}
        .author {{ font-size: 28px; color: #FF4500; font-weight: bold; }}
        .tags {{ font-size: 22px; color: #aaaaaa; }}
      </style>
    </head>
    <body>
      <div class="header">
        <div class="badge">XGAME RADAR</div>
        <div class="subtitle-top">{sub_title}</div>
      </div>
      <div class="content">
        <div class="icon">{icon}</div>
        <div class="title">{cover_title}</div>
      </div>
      <div class="footer">
        <div class="author">By Una (@Una_next)</div>
        <div class="tags">Global Extreme Sports Daily</div>
      </div>
    </body>
    </html>
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1080, "height": 1080})
        await page.set_content(html_content, wait_until="load")
        await page.wait_for_timeout(800)
        await page.screenshot(path=output_filename)
        await browser.close()
    print(f"📸 卡片圖片生成完畢: {output_filename}")

# ==========================================
# 7. Cloudflare R2 圖床與 JSON 備份模組
# ==========================================
def upload_to_r2(file_path, object_name=None):
    account_id = os.getenv("R2_ACCOUNT_ID")
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    bucket_name = os.getenv("R2_BUCKET_NAME")
    public_domain = os.getenv("R2_PUBLIC_DOMAIN")

    if not all([account_id, access_key, secret_key, bucket_name]):
        print("⚠️ 未完整設定 Cloudflare R2，跳過上傳。")
        return None

    if object_name is None:
        object_name = f"cards/{os.path.basename(file_path)}"

    s3_client = boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto"
    )

    try:
        content_type = "application/json" if file_path.endswith(".json") else "image/png"
        s3_client.upload_file(file_path, bucket_name, object_name, ExtraArgs={"ContentType": content_type})
        
        if public_domain:
            url = f"https://{public_domain.rstrip('/')}/{object_name}"
        else:
            url = f"https://{bucket_name}.r2.cloudflarestorage.com/{object_name}"
            
        print(f"☁️ 檔案已成功上傳至 R2: {url}")
        return url
    except Exception as e:
        print(f"❌ R2 上傳失敗: {e}")
        return None

def save_post_data_to_r2(category_key, cover_title, sub_title, caption_text, image_url):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_filename = f"posts/{timestamp}_{category_key}.json"
    
    post_data = {
        "id": timestamp,
        "category": category_key,
        "title": cover_title,
        "subtitle": sub_title,
        "content": caption_text,
        "image_url": image_url,
        "created_at": datetime.now().isoformat(),
        "author": "Una (@Una_next)"
    }
    
    temp_json_path = f"temp_{timestamp}.json"
    with open(temp_json_path, "w", encoding="utf-8") as f:
        json.dump(post_data, f, ensure_ascii=False, indent=2)
        
    upload_to_r2(temp_json_path, object_name=json_filename)
    if os.path.exists(temp_json_path):
        os.remove(temp_json_path)
    print(f"📄 文章 JSON 已成功備份至 R2: {json_filename}")

# ==========================================
# 8. Telegram 推送模組
# ==========================================
def send_telegram_post(caption_text, image_path=None):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip("'\" ")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip("'\" ")
    
    if not bot_token or not chat_id:
        print("⚠️ 未設定 Telegram Token 或 Chat ID，跳過社群發送。")
        return

    try:
        # 清除可能導致 Telegram Markdown 解析失敗的語法標記
        clean_caption = caption_text.replace("**", "*")
        
        if image_path and os.path.exists(image_path):
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            with open(image_path, "rb") as photo:
                requests.post(url, data={"chat_id": chat_id, "caption": clean_caption, "parse_mode": "Markdown"}, files={"photo": photo}, timeout=15)
        else:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            requests.post(url, data={"chat_id": chat_id, "text": clean_caption, "parse_mode": "Markdown"}, timeout=15)
        print("✅ Telegram 卡片與文案成功發送！")
    except Exception as e:
        print(f"❌ Telegram 發送失敗: {e}")

# ==========================================
# 9. 主流程控制器
# ==========================================
async def main(category_key="AUTO", target_lang="zh-hk"):
    print("🚀 啟動 xGame Radar 每日自動化內容生成引擎...")
    init_db()

    if not category_key or category_key == "AUTO":
        category_key = random.choice(list(XGAME_CATEGORIES.keys()))

    cover_title, sub_title, caption_text, city_tag = generate_xgame_content(
        category_key=category_key, 
        target_lang=target_lang
    )

    record_posted_article(cover_title)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_filename = f"xgame_{timestamp}.png"

    await generate_card_image(category_key, cover_title, sub_title, image_filename)

    r2_image_url = upload_to_r2(image_filename)

    save_post_data_to_r2(category_key, cover_title, sub_title, caption_text, r2_image_url)

    send_telegram_post(caption_text, image_path=image_filename)

    # 善後清理：刪除本地生成的卡片圖片
    if os.path.exists(image_filename):
        os.remove(image_filename)

    print("🎉 今日自動發帖任務完全執行完成！")

if __name__ == "__main__":
    cat_arg = "AUTO"
    lang_arg = "zh-hk"

    if len(sys.argv) > 1 and sys.argv[1] != "AUTO":
        cat_arg = sys.argv[1]
    if len(sys.argv) > 2:
        lang_arg = sys.argv[2]

    asyncio.run(main(category_key=cat_arg, target_lang=lang_arg))
