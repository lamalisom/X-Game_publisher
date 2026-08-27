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
from datetime import datetime, timedelta
from dateutil.parser import parse as parsedate_to_datetime
from urllib.parse import quote

import boto3
from google import genai
from google.genai import types
from playwright.async_api import async_playwright

# ==========================================
# 1. 類別定義與全局配置 (XGAME_CATEGORIES)
# ==========================================

# 分類字典映射
XGAME_CATEGORIES = {
    "SKATE": {"name": "Skateboarding", "icon": "🛹", "query": "skateboarding action"},
    "SURF": {"name": "Surfing", "icon": "🏄‍♂️", "query": "surfing ocean wave"},
    "CLIMBING": {"name": "Rock Climbing", "icon": "🧗‍♂️", "query": "rock climbing extreme"},
    "BMX": {"name": "BMX", "icon": "🚲", "query": "bmx trick park"},
    "EVENT": {"name": "xGame Event", "icon": "🏆", "query": "extreme sports event"}
}

def resolve_selected_category():
    """ 優先讀取 CAT_INPUT / XGAME_CATEGORY，保留原有的 AUTO 隨機機制 """
    category_input = os.getenv("CAT_INPUT", os.getenv("XGAME_CATEGORY", "AUTO")).upper().strip()

    if category_input == "AUTO" or category_input not in XGAME_CATEGORIES:
        # 保留原 AUTO 隨機選擇邏輯
        selected = random.choice(list(XGAME_CATEGORIES.keys()))
        print(f"🎲 AUTO 模式自動選擇主題: {selected}")
        return selected
    else:
        return category_input

# ==========================================
# 2. SQLite 數據庫去重與快取機制 (完整保留)
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
# 3. Pexels 圖庫背景抓取（含 Unsplash 終極保底）
# ==========================================
def get_pexels_bg_url(category_key):
    """ 抓取背景圖 URL（Pexels API -> 通用搜尋 -> Unsplash 保底） """
    pexels_api_key = os.getenv("PEXELS_API_KEY")
    
    cat_info = XGAME_CATEGORIES.get(category_key, XGAME_CATEGORIES.get("SKATE", {}))
    search_term = cat_info.get("query", "action sports")

    # 備用免費極限運動圖片（當 API 失效或未設定時使用，確保絕對不會黑屏）
    FALLBACK_IMAGES = {
        "SKATE": "https://images.unsplash.com/photo-1520045892732-304bc3ac5d8e?auto=format&fit=crop&w=1080&q=80",
        "SURF": "https://images.unsplash.com/photo-1502680390469-be75c86b636f?auto=format&fit=crop&w=1080&q=80",
        "CLIMBING": "https://images.unsplash.com/photo-1522163182402-834f871fd851?auto=format&fit=crop&w=1080&q=80",
        "BMX": "https://images.unsplash.com/photo-1568772585407-9361f9bf3a87?auto=format&fit=crop&w=1080&q=80",
        "EVENT": "https://images.unsplash.com/photo-1517649763962-0c623266ddc0?auto=format&fit=crop&w=1080&q=80"
    }

    if pexels_api_key:
        # 嘗試使用 Pexels API
        for query_attempt in [search_term, "extreme sports"]:
            try:
                url = f"https://api.pexels.com/v1/search?query={quote(query_attempt)}&per_page=10&orientation=square"
                headers = {
                    "Authorization": pexels_api_key.strip(),
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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
                else:
                    print(f"⚠️ Pexels 狀態碼: {res.status_code} - {res.text[:80]}")
            except Exception as e:
                print(f"⚠️ Pexels 抓取例外: {e}")

    # 若 Pexels 抓取失敗，觸發第三層保底機制
    fallback_url = FALLBACK_IMAGES.get(category_key, FALLBACK_IMAGES["EVENT"])
    print(f"ℹ️ 啟用 Unsplash 極限運動保底背景圖: {category_key}")
    return fallback_url
    
# ==========================================
# 4. HTML/CSS 卡片渲染與 Playwright 截圖生成 (完整保留)
# ==========================================
def get_image_base64(url_or_path):
    if not url_or_path:
        print("⚠️ 警告: 傳入的圖片 URL 為空，無法轉碼 Base64！")
        return None
    try:
        if url_or_path.startswith("http"):
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url_or_path, headers=headers, timeout=10)
            if resp.status_code == 200:
                encoded = base64.b64encode(resp.content).decode("utf-8")
                print(f"🖼️ Base64 轉換成功！字串長度: {len(encoded)}")
                return f"data:image/jpeg;base64,{encoded}"
            else:
                print(f"❌ 下載圖片失敗 HTTP {resp.status_code}")
    except Exception as e:
        print(f"❌ 圖片轉換 Base64 例外錯誤: {e}")
    return None
    
async def generate_card_image(category_key, cover_title, sub_title, output_filename="xgame_card.png"):
    cat_info = XGAME_CATEGORIES.get(category_key, XGAME_CATEGORIES.get("EVENT"))
    icon = cat_info.get("icon", "🛹")

    bg_image_url = get_pexels_bg_url(category_key)
    base64_bg = get_image_base64(bg_image_url) if bg_image_url else None
    
    # ⚠️ 修正：減輕黑罩濃度 (0.3 ~ 0.65)，讓背景圖清晰可見；同時將底色設為透明防遮蓋
    if base64_bg:
        bg_css = f"""
          background-image: linear-gradient(180deg, rgba(0, 0, 0, 0.35) 0%, rgba(0, 0, 0, 0.75) 100%), url('{base64_bg}');
          background-position: center center;
          background-size: cover;
          background-repeat: no-repeat;
        """
    else:
        # 當圖片抓取失敗時的備用漸層
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
        
        # 改用 load 確保 CSS 背景與圖片資源徹底渲染完成
        await page.set_content(html_content, wait_until="load")
        await page.wait_for_timeout(800) # 給予 0.8 秒繪製時間
        
        await page.screenshot(path=output_filename)
        await browser.close()

    print(f"📸 卡片圖片生成完畢: {output_filename}")
    return output_filename

# ==========================================
# 5. Cloudflare R2 / AWS S3 圖床上傳 (完整保留)
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

def save_post_data_to_r2(category_key, cover_title, sub_title, caption_text, image_url):
    """ 將生成的賽事文案與元數據 (Metadata) 轉為 JSON 並上傳至 Cloudflare R2 """
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
    
    # 寫入本地臨時 JSON 檔
    temp_json_path = f"temp_{timestamp}.json"
    with open(temp_json_path, "w", encoding="utf-8") as f:
        json.dump(post_data, f, ensure_ascii=False, indent=2)
        
    # 上傳 JSON 至 Cloudflare R2
    upload_to_r2(temp_json_path, object_name=json_filename)
    
    # 清除本地臨時檔
    if os.path.exists(temp_json_path):
        os.remove(temp_json_path)
        
    print(f"📄 賽事 JSON 資料已成功備份至 R2: {json_filename}")

# ==========================================
# 6. Telegram Bot 推送通知 (完整保留)
# ==========================================
def send_telegram_post(caption_text, image_path=None):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("⚠️ 未設定 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID，跳過 Telegram 發送。")
        return False

    clean_caption = caption_text[:1000]

    try:
        if image_path and os.path.exists(image_path):
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            with open(image_path, "rb") as photo:
                payload = {
                    "chat_id": chat_id,
                    "caption": clean_caption,
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
            print(f"❌ Telegram 發送失敗！HTTP {res.status_code} - API 錯誤 response: {res.text}")
            return False
            
    except Exception as e:
        print(f"❌ 發送至 Telegram 發生例外: {e}")
        return False

# ==========================================
# 7. Gemini API 核心文案生成器 (完整保留 Prompt 與模型降級機制)
# ==========================================
def generate_xgame_content(category_key="", topic_type="", topic_desc="", target_lang="zh-hk"):
    display_category = category_key.strip() if category_key and category_key.strip() else "EVENT"
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ 錯誤：未偵測到 GEMINI_API_KEY 環境變數！")
        return ("EVENT 焦點企劃", "GLOBAL · EVENT", "請設定 API Key", "GLOBAL")

    client = genai.Client(api_key=api_key)

    lang_map = {
        "zh-hk": "繁體中文（廣東話/香港口語，語氣熱血且極具社群吸引力）",
        "zh-cn": "簡體中文（專業熱血的極限運動社群口吻）",
        "ja": "日文（專業且地道的極限運動風格）",
        "en": "英文（Authentic Action Sports Community Style）"
    }
    selected_lang_desc = lang_map.get(target_lang, lang_map["zh-hk"])

    # ⚠️ 修改 Prompt：明確要求搜尋並列出未來 4-7 個月的真實賽事資訊
    prompt = f"""
你是一位專注於全球極限運動的熱血社群小編 Una (@Una_next)。
請搜尋並整理未來 4 至 7 個月內，全球【{display_category}】領域最受矚目的真實極限運動大賽（例如 X Games、SLS、WSL、IFSC、Red Bull 賽事等）。

【語言與風格要求】:
- 完全使用 **{selected_lang_desc}** 撰寫。
- 語氣熱血、幹脆利落，大量善用 Emoji（🔥 🛹 🏄‍♂️ 🏆 📍 🗓️ 等）。

【內容必須包含真實資訊】:
1. 必須列出 **2 到 3 個未來 4-7 個月內會舉辦的真實比賽**。
2. 每個比賽必須明確標註：**比賽名稱**、**預計月份/日期**、**舉辦城市/地點**。

【結構與字數限制】:
- 總字數控制在 **200 至 300 字以內**。
- 格式：
  - ⚡ **1 句熱血開頭**
  - 🗓️ **未來 4-7 個月賽事預告**（用 Emoji 條列 2-3 個真實比賽，含日期地點）
  - 🔥 **1 句賽事亮點或觀賽期待**
  - 💬 **1 句 Call to Action** + 社群 Tag

請嚴格按照以下格式輸出，並用三條橫線 `---` 將各部分分開，不要輸出 Markdown 代碼塊（```）：

封面主標題
---
封面副標題
---
城市英文名
---
正文內容
"""

    print(f"🤖 正在呼叫 Gemini API (開啟即時搜尋模式) 生成【{display_category}】未來賽事情報...")

    try:
        # ⚠️ 關鍵修正：加入 tools=[{"google_search": {}}] 開啟 Google 搜尋實時抓取
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.5, # 降低溫度以確保資訊準確
                tools=[{"google_search": {}}] # 強制啟用 Google 搜尋工具
            )
        )

        raw_text = response.text.strip()
        raw_text = re.sub(r'^```\w*\n?', '', raw_text)
        raw_text = re.sub(r'\n?```$', '', raw_text)

        parts = [p.strip() for p in raw_text.split("---")]

        if len(parts) >= 4:
            return parts[0], parts[1], parts[3], parts[2].upper()
        else:
            return f"{display_category} 未來賽事熱血預告", "GLOBAL · EVENT", raw_text, "GLOBAL"

    except Exception as e:
        print(f"❌ Gemini 搜尋生成失敗: {e}")
        return f"{display_category} 賽事情報", "GLOBAL · EVENT", "生成失敗，請檢查 API 與網絡。", "GLOBAL"
        
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

    # 取得當前執行主題（支援 CAT_INPUT / XGAME_CATEGORY / AUTO）
    category_key = resolve_selected_category()
    
    topic_type = os.getenv("TOPIC_TYPE", "EVENT_OVERVIEW").strip()
    topic_desc = os.getenv("TOPIC_DESC", "全球賽事動態情報").strip()
    target_lang = os.getenv("TARGET_LANG", "zh-hk").strip()

    print(f"🎯 執行類別: {category_key} ({XGAME_CATEGORIES[category_key]['name']})")
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
