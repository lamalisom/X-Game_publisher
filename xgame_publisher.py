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
# 0. 分類與 RSS 設定
# ==========================================
XGAME_CATEGORIES = {
    "SKATE": "https://www.skateboarding.com/rss",
    "CLIMB": "https://www.climbing.com/feed/",
    "BMX": "https://fatbmx.com/bmx-news?format=feed&type=rss",
    "SURF": "https://www.surfer.com/.rss/full/",
    "SNOW": "https://www.snowboarder.com/.rss/full/"
}

# ==========================================
# 1. SQLite 防重複發帖資料庫
# ==========================================
DB_FILE = "posted_articles.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posted_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE,
            category TEXT,
            posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def is_already_posted(title):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM posted_articles WHERE title = ?', (title,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def record_posted_article(title, category):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO posted_articles (title, category) VALUES (?, ?)', (title, category))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

# ==========================================
# 2. RSS 抓取模組
# ==========================================
def fetch_latest_rss_news(category_key):
    rss_url = XGAME_CATEGORIES.get(category_key.upper())
    if not rss_url:
        return ""
    try:
        feed = feedparser.parse(rss_url)
        articles = []
        for entry in feed.entries[:3]:
            title = entry.get('title', '')
            summary = entry.get('summary', entry.get('description', ''))
            clean_summary = re.sub('<[^<]+?>', '', summary)[:150]
            articles.append(f"- {title}: {clean_summary}")
        if articles:
            return "【最新 RSS 參考新聞】:\n" + "\n".join(articles)
    except Exception as e:
        print(f"⚠️ RSS 抓取失敗 ({category_key}): {e}")
    return ""

# ==========================================
# 3. Gemini 內容生成模組 (同步修復 404 & 升級商業 Prompt)
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

    lang_map = {
        "zh-hk": "繁體中文（廣東話/香港口語，語氣熱血且極具社群吸引力）",
        "zh-cn": "簡體中文（專業熱血的極限運動社群口吻）",
        "ja": "日文（專業且地道的極限運動風格）",
        "en": "英文（Authentic Action Sports Community Style）"
    }
    selected_lang_desc = lang_map.get(target_lang, lang_map["zh-hk"])

    # 包含商業價值的 Prompt 升級
    prompt = f"""
你是一位專注於全球極限運動的熱血社群小編 Una (@Una_next)。
今日專欄主題：【{active_title}】（項目：{display_category}）
{rss_context}

【撰寫要求】:
1. 請以熱血且專業的口吻撰寫一篇關於【{display_category}】的極限運動報導。
2. 語言格式：完全使用 **{selected_lang_desc}** 撰寫，大量善用 Emoji，總字數控制在 **250 至 350 字以內**。
3. 商業價值優化：在 Content 正文結尾，請以專家身份推薦 1 款該運動必備的裝備（如特定專業鞋款、防具或配件）或推薦場地，並說明推薦理由。

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

    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
    
    for model_name in models_to_try:
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                chat = client.chats.create(
                    model=model_name,
                    config=types.GenerateContentConfig(
                        temperature=0.4,
                        tools=[{"google_search": {}}]
                    )
                )
                response = chat.send_message(prompt)

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
                print(f"⚠️ [{model_name}] 請求失敗 (第 {attempt} 次): {err_msg[:120]}")
                if "503" in err_msg or "UNAVAILABLE" in err_msg or "429" in err_msg or "disconnected" in err_msg:
                    if attempt < max_retries:
                        time.sleep(5)
                        continue
                break

    return f"{display_category} 熱血企劃", f"GLOBAL · {active_topic}", f"⚡ 各位極限迷！今日【{display_category}】情報熱血更新中！\n\n💬 留言話我知你最想睇咩！👇\n#Una_next #{display_category} #xGameRadar", "GLOBAL"

# ==========================================
# 4. Pexels 背景抓圖與 Base64
# ==========================================
def get_pexels_image(keyword):
    pexels_key = os.getenv("PEXELS_API_KEY")
    fallback_urls = [
        "[https://images.pexels.com/photos/1653877/pexels-photo-1653877.jpeg](https://images.pexels.com/photos/1653877/pexels-photo-1653877.jpeg)",
        "[https://images.pexels.com/photos/844322/pexels-photo-844322.jpeg](https://images.pexels.com/photos/844322/pexels-photo-844322.jpeg)",
        "[https://images.pexels.com/photos/1769553/pexels-photo-1769553.jpeg](https://images.pexels.com/photos/1769553/pexels-photo-1769553.jpeg)"
    ]
    if pexels_key:
        try:
            headers = {"Authorization": pexels_key}
            url = f"[https://api.pexels.com/v1/search?query=](https://api.pexels.com/v1/search?query=){keyword}&per_page=1"
            res = requests.get(url, headers=headers, timeout=10).json()
            if res.get("photos"):
                img_url = res["photos"][0]["src"]["large2x"]
                print(f"✅ Pexels 成功抓取【{keyword}】背景圖！")
                return img_url
        except Exception as e:
            print(f"⚠️ Pexels 搜尋失敗: {e}")
    return random.choice(fallback_urls)

def url_to_base64(image_url):
    try:
        res = requests.get(image_url, timeout=10)
        encoded = base64.b64encode(res.content).decode("utf-8")
        print(f"🖼️ Base64 轉換成功！字串長度: {len(encoded)}")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception as e:
        print(f"⚠️ 圖片 Base64 轉換失敗: {e}")
        return image_url

# ==========================================
# 5. Playwright 動態卡片渲染 (異步 async)
# ==========================================
async def render_card_image_async(title, subtitle, tag_city, bg_image_url, output_path):
    bg_base64 = url_to_base64(bg_image_url)
    
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <style>
        body {{ margin: 0; padding: 0; width: 1080px; height: 1080px; display: flex; justify-content: center; align-items: center; background: #000; font-family: 'Helvetica Neue', Arial, sans-serif; }}
        .card {{ width: 1080px; height: 1080px; position: relative; background-image: url('{bg_base64}'); background-size: cover; background-position: center; display: flex; flex-direction: column; justify-content: space-between; padding: 80px; box-sizing: border-box; }}
        .overlay {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(180deg, rgba(0,0,0,0.4) 0%, rgba(0,0,0,0.85) 100%); z-index: 1; }}
        .content {{ position: relative; z-index: 2; height: 100%; display: flex; flex-direction: column; justify-content: space-between; }}
        .top-bar {{ display: flex; justify-content: space-between; align-items: center; }}
        .badge {{ background: #ff3300; color: #fff; padding: 12px 24px; font-weight: bold; font-size: 24px; border-radius: 30px; text-transform: uppercase; letter-spacing: 2px; }}
        .location {{ color: #ffffff; font-size: 24px; font-weight: 600; opacity: 0.9; }}
        .main-title {{ color: #ffffff; font-size: 64px; font-weight: 900; line-height: 1.2; margin-bottom: 20px; text-shadow: 0 4px 12px rgba(0,0,0,0.5); }}
        .author {{ color: #ff3300; font-size: 28px; font-weight: 700; display: flex; align-items: center; gap: 10px; }}
        .footer {{ display: flex; justify-content: space-between; align-items: flex-end; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 30px; }}
        .sub-tag {{ color: #aaaaaa; font-size: 22px; text-transform: uppercase; letter-spacing: 1.5px; }}
    </style>
    </head>
    <body>
        <div class="card">
            <div class="overlay"></div>
            <div class="content">
                <div class="top-bar">
                    <div class="badge">xGame Radar</div>
                    <div class="location">【{subtitle}】</div>
                </div>
                <div>
                    <div class="main-title">🏆<br>{title}</div>
                    <div class="author">By Una (@Una_next)</div>
                </div>
                <div class="footer">
                    <div class="sub-tag">Global Extreme Sports Daily</div>
                    <div class="sub-tag">{tag_city}</div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1080, "height": 1080})
        await page.set_content(html_template)
        await page.screenshot(path=output_path)
        await browser.close()
    print(f"📸 卡片圖片生成完畢: {output_path}")

# ==========================================
# 6. Cloudflare R2 備份上傳
# ==========================================
def upload_to_r2(local_file_path, r2_object_name):
    account_id = os.getenv("R2_ACCOUNT_ID")
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    bucket_name = os.getenv("R2_BUCKET_NAME", "xgame-radar-media")
    public_domain = os.getenv("R2_PUBLIC_DOMAIN", "").rstrip("/")

    if not all([account_id, access_key, secret_key]):
        print("⚠️ 未設置 Cloudflare R2 環境變數，跳過上傳。")
        return None

    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto"
        )
        content_type = "image/png" if local_file_path.endswith(".png") else "application/json"
        s3.upload_file(local_file_path, bucket_name, r2_object_name, ExtraArgs={"ContentType": content_type})
        
        file_url = f"{public_domain}/{r2_object_name}" if public_domain else f"https://***{r2_object_name}"
        print(f"☁️ 檔案已成功上傳至 R2: {file_url}")
        return file_url
    except Exception as e:
        print(f"❌ R2 上傳失敗: {e}")
        return None

# ==========================================
# 7. 本地 Markdown Post 生成模組
# ==========================================
def save_post_as_markdown(category_key, cover_title, sub_title, caption_text, image_url):
    timestamp = datetime.now().strftime("%Y-%m-%d")
    posts_dir = "posts"
    os.makedirs(posts_dir, exist_ok=True)
    filepath = os.path.join(posts_dir, f"{timestamp}_{category_key.lower()}.md")
    
    md_content = f"""---
title: "{cover_title}"
subtitle: "{sub_title}"
date: {datetime.now().isoformat()}
category: "{category_key}"
cover_image: "{image_url}"
author: "Una (@Una_next)"
---

![{cover_title}]({image_url})

{caption_text}
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"📝 Markdown 文章已生成: {filepath}")

# ==========================================
# 8. Telegram 推送模組 (含降級機制)
# ==========================================
def send_telegram_post(caption_text, image_path=None):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip("'\" ")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip("'\" ")
    
    if not bot_token or not chat_id:
        print("⚠️ 未設定 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID，跳過社群發送。")
        return

    clean_caption = caption_text.replace("**", "*")

    def make_tg_request(parse_mode="Markdown"):
        if image_path and os.path.exists(image_path):
            url = f"[https://api.telegram.org/bot](https://api.telegram.org/bot){bot_token}/sendPhoto"
            payload = {"chat_id": chat_id, "caption": clean_caption}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            with open(image_path, "rb") as photo:
                return requests.post(url, data=payload, files={"photo": photo}, timeout=15)
        else:
            url = f"[https://api.telegram.org/bot](https://api.telegram.org/bot){bot_token}/sendMessage"
            payload = {"chat_id": chat_id, "text": clean_caption}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            return requests.post(url, data=payload, timeout=15)

    try:
        response = make_tg_request(parse_mode="Markdown")
        res_json = response.json()

        if res_json.get("ok"):
            print("✅ Telegram 卡片與文案成功發送！")
            return

        print(f"⚠️ Telegram 第一次發送失敗: {res_json.get('description', '')}，嘗試純文字降級發送...")
        fallback_res = make_tg_request(parse_mode=None)
        fallback_json = fallback_res.json()

        if fallback_json.get("ok"):
            print("✅ Telegram (純文字降級模式) 發送成功！")
        else:
            print(f"❌ Telegram 最終發送失敗！錯誤訊息: {fallback_json}")

    except Exception as e:
        print(f"❌ Telegram 發送過程發生異常例外: {e}")

# ==========================================
# 9. 主程式執行流程 (支援 CLI 參數傳遞)
# ==========================================
async def main_async():
    print("🚀 啟動 xGame Radar 每日自動化內容生成引擎...")
    init_db()

    # 保留 CLI 參數解析功能（如：python main.py SKATE zh-hk）
    category_arg = sys.argv[1] if len(sys.argv) > 1 else ""
    lang_arg = sys.argv[2] if len(sys.argv) > 2 else "zh-hk"

    category = category_arg.strip().upper() if category_arg else random.choice(list(XGAME_CATEGORIES.keys()))

    # 1. 生成內容
    title, subtitle, content, city_tag = generate_xgame_content(category_key=category, target_lang=lang_arg)

    # 防重複檢查
    if is_already_posted(title):
        print(f"ℹ️ 文章 [{title}] 今日已發布過，跳過重複發送。")
        return

    # 2. 獲取圖片與渲染卡片 (異步呼叫 async playwright)
    bg_image = get_pexels_image(f"{category.lower()} action")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    card_filename = f"xgame_{timestamp}.png"
    
    await render_card_image_async(title, subtitle, city_tag, bg_image, card_filename)

    # 3. 上傳圖片卡片至 R2
    r2_img_url = upload_to_r2(card_filename, f"cards/{card_filename}")
    img_link_for_record = r2_img_url if r2_img_url else bg_image

    # 4. 生成並上傳 JSON 備份至 R2
    json_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{category}.json"
    post_data = {
        "id": timestamp,
        "title": title,
        "subtitle": subtitle,
        "category": category,
        "content": content,
        "image_url": img_link_for_record,
        "created_at": datetime.now().isoformat(),
        "author": "Una (@Una_next)"
    }
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(post_data, f, ensure_ascii=False, indent=2)
    
    upload_to_r2(json_filename, f"posts/{json_filename}")
    print(f"📄 文章 JSON 已成功備份至 R2: posts/{json_filename}")

    # 5. 生成本地 Markdown Post
    save_post_as_markdown(category, title, subtitle, content, img_link_for_record)

    # 6. 發送至 Telegram
    tg_message = f"🏆 *{title}*\n\n{subtitle}\n\n{content}\n\n#xGameRadar #{category} #Una_next"
    send_telegram_post(tg_message, image_path=card_filename)

    # 7. 記錄已發布
    record_posted_article(title, category)

    # 清理臨時本地檔案
    if os.path.exists(card_filename):
        os.remove(card_filename)
    if os.path.exists(json_filename):
        os.remove(json_filename)

    print("🎉 今日自動發帖任務完全執行完成！")

if __name__ == "__main__":
    asyncio.run(main_async())
