import os
import re
import sys
import json
import random
import sqlite3
import requests
import feedparser
import asyncio
from datetime import datetime, timedelta
from dateutil.parser import parse as parsedate_to_datetime
import boto3
from google import genai
from google.genai import types
from playwright.async_api import async_playwright

# ==========================================
# 1. 類別定義與全局配置 (XGAME_CATEGORIES)
# ==========================================
XGAME_CATEGORIES = {
    "SKATE": {"name": "Skateboarding", "icon": "🛹"},
    "BMX": {"name": "BMX Freestyle", "icon": "🚲"},
    "SURF": {"name": "Surfing", "icon": "🏄‍♂️"},
    "CLIMB": {"name": "Bouldering & Climbing", "icon": "🧗‍♂️"},
    "SNOW": {"name": "Snowboarding", "icon": "🏂"},
    "EVENT": {"name": "Extreme Events", "icon": "🔥"}
}

# ==========================================
# 2. SQLite 數據庫去重與快取機制
# ==========================================
def init_db(db_path="xgame_rss.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_hash TEXT UNIQUE,
            title TEXT,
            published_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def is_post_processed(post_hash, db_path="xgame_rss.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM processed_posts WHERE post_hash = ?", (post_hash,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def mark_post_processed(post_hash, title, db_path="xgame_rss.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO processed_posts (post_hash, title, published_at) VALUES (?, ?, ?)",
        (post_hash, title, datetime.now())
    )
    conn.commit()
    conn.close()

# ==========================================
# 3. Pexels 圖庫背景抓取 (帶空值防呆)
# ==========================================
def get_pexels_bg_url(category_key):
    """ 從 Pexels 抓取高畫質背景圖 URL（帶防錯防呆） """
    pexels_api_key = os.getenv("PEXELS_API_KEY")
    
    # 防呆：確保 category_key 不為空，避免 list index out of range
    if not category_key or not str(category_key).strip():
        clean_query = "skateboarding"
    else:
        parts = str(category_key).strip().split()
        clean_query = parts[0].lower() if parts else "skateboarding"

    if pexels_api_key:
        try:
            url = f"https://api.pexels.com/v1/search?query={clean_query}+action+sports&per_page=10&orientation=sq"
            headers = {"Authorization": pexels_api_key}
            res = requests.get(url, headers=headers, timeout=8)
            if res.status_code == 200:
                photos = res.json().get("photos", [])
                if photos:
                    print(f"✅ Pexels 成功抓取【{clean_query}】背景圖！")
                    return photos[0]["src"]["large2x"]
            print(f"⚠️ Pexels API 回覆狀態: {res.status_code}，切換至純色背景模式。")
        except Exception as e:
            print(f"⚠️ Pexels 抓取過程發生例外: {e}")
            
    print("ℹ️ 使用預設黑色極限風格背景")
    return ""  # 回傳空字串，自動使用 CSS 預設漸層

# ==========================================
# 4. HTML/CSS 卡片渲染與 Playwright 截圖生成 (修復版)
# ==========================================
async def generate_card_image(category_key, cover_title, sub_title, output_filename="xgame_card.png"):
    cat_info = XGAME_CATEGORIES.get(category_key, XGAME_CATEGORIES.get("EVENT", {"icon": "🛹"}))
    icon = cat_info.get("icon", "🛹")

    # 抓取 Pexels 背景圖 URL
    bg_image_url = get_pexels_bg_url(category_key)
    
    # 建立 CSS 背景樣式
    if bg_image_url:
        bg_css = f"background: linear-gradient(rgba(0, 0, 0, 0.65), rgba(0, 0, 0, 0.85)), url('{bg_image_url}') center/cover no-repeat;"
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
          /* 加入 Noto Color Emoji 確保 Linux / GitHub Actions 正常顯示 Emoji */
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif;
          color: #ffffff;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 80px;
          position: relative;
          overflow: hidden;
        }}
        .bg-accent {{
          position: absolute;
          top: -200px;
          right: -200px;
          width: 600px;
          height: 600px;
          background: radial-gradient(circle, rgba(255, 69, 0, 0.35) 0%, rgba(0,0,0,0) 70%);
          border-radius: 50%;
        }}
        .header {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          z-index: 10;
        }}
        .badge {{
          background: #ff4500;
          color: #fff;
          font-weight: 800;
          font-size: 24px;
          padding: 10px 24px;
          border-radius: 50px;
          text-transform: uppercase;
          letter-spacing: 2px;
          box-shadow: 0 4px 15px rgba(255, 69, 0, 0.4);
        }}
        .sub-title {{
          font-size: 28px;
          color: #e0e0e0;
          font-weight: 600;
          letter-spacing: 1px;
          text-shadow: 0 2px 4px rgba(0,0,0,0.8);
        }}
        .center-content {{
          z-index: 10;
          margin-top: 40px;
        }}
        .icon {{
          font-size: 110px;
          margin-bottom: 20px;
          filter: drop-shadow(0 10px 20px rgba(0,0,0,0.5));
          line-height: 1;
        }}
        .main-title {{
          font-size: 76px;
          font-weight: 900;
          line-height: 1.15;
          color: #ffffff;
          text-shadow: 0 10px 30px rgba(0,0,0,0.9);
        }}
        .footer {{
          display: flex;
          justify-content: space-between;
          align-items: flex-end;
          z-index: 10;
          border-top: 2px solid rgba(255, 255, 255, 0.2);
          padding-top: 30px;
        }}
        .author {{
          font-size: 32px;
          font-weight: 700;
          color: #ff4500;
          text-shadow: 0 2px 4px rgba(0,0,0,0.8);
        }}
        .tagline {{
          font-size: 22px;
          color: #ccc;
        }}
      </style>
    </head>
    <body>
      <div class="bg-accent"></div>
      <div class="header">
        <div class="badge">xGame Radar</div>
        <div class="sub-title">{sub_title}</div>
      </div>
      <div class="center-content">
        <div class="icon">{icon}</div>
        <div class="main-title">{cover_title}</div>
      </div>
      <div class="footer">
        <div class="author">By Una (@Una_next)</div>
        <div class="tagline">Global Extreme Sports Daily</div>
      </div>
    </body>
    </html>
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1080, "height": 1080})
        
        # 使用 data:html 載入並等待網路資源（Pexels 圖片）完全下載完成 (networkidle)
        await page.goto(f"data:text/html;charset=utf-8,{requests.utils.quote(html_content)}", wait_until="networkidle")
        
        # 額外延遲 500ms 確保字型與圖片渲染完成
        await page.wait_for_timeout(500)
        
        await page.screenshot(path=output_filename)
        await browser.close()

    print(f"📸 圖片成功生成: {output_filename}")
    return output_filename
    
# ==========================================
# 5. Cloudflare R2 / AWS S3 圖床上傳
# ==========================================
def upload_to_r2(file_path, object_name=None):
    account_id = os.getenv("R2_ACCOUNT_ID")
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    bucket_name = os.getenv("R2_BUCKET_NAME")
    public_domain = os.getenv("R2_PUBLIC_DOMAIN")

    if not all([account_id, access_key, secret_key, bucket_name]):
        print("⚠️ 未完整設定 Cloudflare R2 環境變數，跳過圖床上傳步驟。")
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
        s3_client.upload_file(file_path, bucket_name, object_name, ExtraArgs={"ContentType": "image/png"})
        if public_domain:
            url = f"https://{public_domain.rstrip('/')}/{object_name}"
        else:
            url = f"https://{bucket_name}.r2.cloudflarestorage.com/{object_name}"
        print(f"☁️ 圖片已成功上傳至 R2: {url}")
        return url
    except Exception as e:
        print(f"❌ 上傳至 R2 失敗: {e}")
        return None

# ==========================================
# 6. Telegram Bot 推送通知
# ==========================================
def send_telegram_post(caption_text, image_path=None):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("⚠️ 未設定 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID，跳過 Telegram 發送。")
        return False

    # 防呆處理：替換掉 Telegram Markdown 最容易卡死解析的特殊符號，或改用純文字/HTML
    # 若文字過長，Telegram Caption 上限為 1024 字元
    clean_caption = caption_text[:1000]

    try:
        if image_path and os.path.exists(image_path):
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            with open(image_path, "rb") as photo:
                payload = {
                    "chat_id": chat_id,
                    "caption": clean_caption,
                    # 如果內文含有未轉義的 _ 或 *，改用 HTML 比 Markdown 更穩定的預設解析
                    "parse_mode": "HTML" 
                }
                files = {"photo": photo}
                res = requests.post(url, data=payload, files=files, timeout=20)
        else:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id, 
                "text": clean_caption, 
                "parse_mode": "HTML"
            }
            res = requests.post(url, data=payload, timeout=20)

        res_json = res.json()
        if res.status_code == 200 and res_json.get("ok"):
            print("✅ Telegram 圖片卡片與文案已成功發送！")
            return True
        else:
            # 印出 Telegram 回傳的詳細錯誤原因 (例如 Bad Request: can't parse entities)
            print(f"❌ Telegram 發送失敗！HTTP {res.status_code} - API 錯誤 response: {res.text}")
            return False
            
    except Exception as e:
        print(f"❌ 發送至 Telegram 發生例外: {e}")
        return False
        
# ==========================================
# 7. Gemini API 核心文案生成器 (全新修正版)
# ==========================================
def generate_xgame_content(category_key="", topic_type="", topic_desc="", target_lang="zh-hk"):
    """
    呼叫 Gemini API 生成精煉流暢的廣東話社群文案
    """
    display_category = category_key.strip() if category_key and category_key.strip() else "SKATE"
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ 錯誤：未偵測到 GEMINI_API_KEY 環境變數！")
        return (
            f"{display_category} 焦點企劃",
            f"GLOBAL · {display_category}",
            f"👋 我係 Una (@Una_next)！今日同大家關注【{display_category}】嘅最新戰術與裝備情報！\n\n📌 記得關注我哋！\n— By Una (@Una_next)\n#xGameRadar #{display_category}",
            "GLOBAL"
        )

    client = genai.Client(api_key=api_key)

    lang_map = {
        "zh-hk": "繁體中文（廣東話/香港口語，語氣熱血且極具社群吸引力）",
        "zh-cn": "簡體中文（專業熱血的極限運動社群口吻）",
        "ja": "日文（專業且地道的極限運動風格）",
        "en": "英文（Authentic Action Sports Community Style）"
    }
    selected_lang_desc = lang_map.get(target_lang, lang_map["zh-hk"])

    prompt = f"""
你是一位專注於全球極限運動的社群小編 Una (@Una_next)。
請針對極限運動項目【{display_category}】，以及主題【{topic_type}: {topic_desc}】，撰寫一份高品質的社群帖文與圖文卡片文字。

【語言要求】:
- 請完全使用 **{selected_lang_desc}** 撰寫。

【字數與結構嚴格限制】:
1. 精簡幹練，開門見山，總字數嚴格控制在 **250 至 350 字以內**。
2. 採用「重點條列式」，去除非必要的客套開門白與贅詞。

請嚴格按照以下格式輸出，並用三條橫線 `---` 將各部分分開，不要輸出任何 Markdown 代碼塊（如 ```）：

封面主標題
---
封面副標題
---
城市英文名
---
正文內容
"""

    print(f"🤖 正在呼叫 Gemini API 生成【{display_category}】內容...")

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
            )
        )

        raw_text = response.text.strip()
        raw_text = re.sub(r'^```\w*\n?', '', raw_text)
        raw_text = re.sub(r'\n?```$', '', raw_text)

        parts = [p.strip() for p in raw_text.split("---")]

        if len(parts) >= 4:
            cover_title = parts[0]
            sub_title = parts[1]
            city_name_en = parts[2].upper()
            caption_text = parts[3]
        elif len(parts) == 3:
            cover_title = parts[0]
            sub_title = parts[1]
            city_name_en = "GLOBAL"
            caption_text = parts[2]
        else:
            cover_title = f"{display_category} 突破極限"
            sub_title = f"GLOBAL · {display_category}"
            city_name_en = "GLOBAL"
            caption_text = raw_text

        cover_title = re.sub(r'[*"\'«»]', '', cover_title)
        sub_title = re.sub(r'[*"\'«»]', '', sub_title)

        print("✅ Gemini 內容生成成功！")
        return cover_title, sub_title, caption_text, city_name_en

    except Exception as e:
        print(f"❌ Gemini 主模型呼叫失敗！詳細錯誤: {type(e).__name__} - {str(e)}")
        
        # 降級備用機制
        for fallback_model in ["gemini-2.0-flash-lite"]:
            try:
                print(f"🔄 嘗試使用備用模型 [{fallback_model}]...")
                response = client.models.generate_content(
                    model=fallback_model,
                    contents=prompt,
                )
                raw_text = response.text.strip()
                raw_text = re.sub(r'^```\w*\n?', '', raw_text)
                raw_text = re.sub(r'\n?```$', '', raw_text)
                parts = [p.strip() for p in raw_text.split("---")]
                if len(parts) >= 4:
                    print(f"✅ 備用模型 [{fallback_model}] 生成成功！")
                    return parts[0], parts[1], parts[3], parts[2].upper()
            except Exception as fb_err:
                print(f"❌ 備用模型 [{fallback_model}] 失敗: {fb_err}")

        fallback_title = f"{display_category} 焦點企劃"
        fallback_sub = f"GLOBAL · {display_category}"
        fallback_caption = f"👋 我係 Una (@Una_next)！今日同大家關注【{display_category}】嘅最新情報！\n\n📌 記得關注我哋！\n— By Una (@Una_next)\n#xGameRadar #{display_category}"
        return fallback_title, fallback_sub, fallback_caption, "GLOBAL"

# ==========================================
# 8. 主流程運行控制 (Main Execution)
# ==========================================
async def main():
    print("🚀 啟動 xGame Radar 自動化內容生成引擎...")
    init_db()

    category_key = os.getenv("XGAME_CATEGORY", "BMX").strip()
    topic_type = os.getenv("TOPIC_TYPE", "EVENT_OVERVIEW").strip()
    topic_desc = os.getenv("TOPIC_DESC", "全球賽事動態情報").strip()
    target_lang = os.getenv("TARGET_LANG", "zh-hk").strip()

    print(f"🎯 執行類別: {category_key}")
    print(f"📅 今日日期: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"📌 今日主題: 【{topic_type}】 - {topic_desc}")
    print(f"🌐 語言設定: {target_lang}")

    cover_title, sub_title, caption_text, city_name_en = generate_xgame_content(
        category_key=category_key,
        topic_type=topic_type,
        topic_desc=topic_desc,
        target_lang=target_lang
    )

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_filename = f"xgame_{timestamp_str}.png"

    await generate_card_image(category_key, cover_title, sub_title, image_filename)

    print("\n--- [生成標題] ---")
    print(f"主標題: {cover_title}")
    print(f"副標題: {sub_title}")
    print("\n--- [正文預覽 (含 CTA & Tag)] ---")
    print(caption_text)

    # 選擇性上傳至 Cloudflare R2
    upload_to_r2(image_filename)

    # 發送至 Telegram 社群
    send_telegram_post(caption_text, image_path=image_filename)

    print("🎉 自動發帖任務執行完成！")

if __name__ == "__main__":
    asyncio.run(main())
