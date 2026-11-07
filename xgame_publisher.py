
def ai_fact_check_and_refine(post_data: dict, api_key: str) -> dict:
    """
    【AI 事實審查官】：在文章存檔前進行二次核對，杜絕時空錯位、虛構酒店、跨界裝備與模板垃圾
    """
    if not api_key:
        return post_data

    print("🕵️‍♂️ 啟動【AI 事實審查官】進行嚴格的事實核對與邏輯自檢...")
    checker_prompt = f"""
你是一位極度嚴苛的極限運動體育新聞總編輯兼事實查核官。
請審查以下剛剛生成的文章草稿資料，並進行修正：

【待審核資料】：
標題: {post_data.get('title')}
副標: {post_data.get('subtitle')}
項目: {post_data.get('category')}
主題: {post_data.get('topic_type')}
城市標籤: {post_data.get('city_tag')}
推薦裝備: {post_data.get('gear_keyword')}
完整內文:
{post_data.get('website_full_content') or post_data.get('content')}

【審查與修正硬性紅線（必須嚴格執行）】：
1. 嚴禁運動類別錯位：
   - 若為攀岩（CLIMB/岩壁攀登），內文與裝備推薦絕對禁止出現「冰攀、冰鎬、冰爪（Ice climbing tools/crampons）」！必須修正為攀岩鞋、粉袋、頭盔或機械塞。
   - 若為滑雪（SNOW），絕對禁止混入滑板或衝浪術語。
2. 嚴禁實體屬性造假：
   - 街頭店鋪（Skate Shop）絕不能描寫成擁有碗池的大型滑板場（Skatepark）！
   - 公立社區公園絕不能捏造虛構的主題奢華酒店（如 "Skate Hotel"）！若周邊無名宿，直接改為大眾市區交通與生活機能建議。
3. 嚴禁時空與地點錯配：
   - 若城市標籤或網址涉及某一國家（如 KOREA），內文主題絕對不能變成其他國家（如西班牙或美國）！兩者必須完全一致。
4. 徹底清除所有模板垃圾：
   - 嚴禁出現「SPONSORED ADVERTISEMENT」、「(Google AdSense Ready)」等任何開發者佔位文字！

請回傳 100% 修正後合規的 JSON 格式（嚴禁 markdown 外框）：
{{
  "title": "核實修正後的標題",
  "subtitle": "核實修正後的副標",
  "city_tag": "與內文地點 100% 相符的英文城市或國家",
  "gear_keyword": "與該運動項目 100% 吻合的純英文裝備關鍵字",
  "telegram_caption": "修正後的社群摘要",
  "website_full_content": "修正後的完整 Markdown 內文（專業乾淨、無虛構事實）",
  "content": "修正後的完整 Markdown 內文"
}}
"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": checker_prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048}
        }
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            resp_txt = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if resp_txt.startswith("```"):
                resp_txt = re.sub(r"^```(?:json)?
", "", resp_txt)
                resp_txt = re.sub(r"
```$", "", resp_txt)
            verified_data = json.loads(resp_txt)
            for k in ["title", "subtitle", "city_tag", "gear_keyword", "telegram_caption", "website_full_content", "content"]:
                if k in verified_data and verified_data[k]:
                    post_data[k] = verified_data[k]
            print("✅ 【AI 事實審查官】自檢完畢：已自動過濾幻覺並糾正事實！")
        else:
            print(f"⚠️ AI 事實驗證略過 ({res.status_code})")
    except Exception as e:
        print(f"⚠️ AI 事實驗證連線略過: {e}")

    return post_data


#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import json
import random
import sqlite3
import base64
import requests
import asyncio
import time
import html
from datetime import datetime
from urllib.parse import quote, urlparse

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import boto3
except ImportError:
    boto3 = None

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None

# ==========================================
# 運動官方核心管理機構與旗艦賽事實體庫（杜絕無名無姓空話）
# ==========================================
OFFICIAL_ORGANIZATIONS = {
    "SNOW": "國際滑雪與單板滑雪總會（FIS - International Ski and Snowboard Federation）世界盃大跳台/U型池賽",
    "SURF": "世界衝浪聯盟（WSL - World Surf League）Championship Tour 冠軍巡迴賽",
    "SKATE": "世界滑板聯盟（World Skate）與 SLS (Street League Skateboarding) 街式超級王冠賽",
    "CLIMB": "國際運動攀登總會（IFSC - International Federation of Sport Climbing）抱石與難度世界盃",
    "BMX": "國際自行車聯盟（UCI - Union Cycliste Internationale）自由式小輪車世界盃"
}

def generate_chinese_hashtags(category, topic_type="NEWS", city_tag="", title=""):
    """
    全方位 SEO 標籤矩陣：涵蓋 BMX、各類賽事比拼、實體場地評測與全運動長尾詞
    """
    cat = str(category).upper() if category else "SKATE"
    top = str(topic_type).upper() if topic_type else "NEWS"
    
    # 1. 運動項目專屬高轉化長尾詞
    sport_map = {
        "BMX": ["#BMX", "#極限單車", "#小輪車", "#泵道", "#特技單車", "#土坡騰躍", "#PumpTrack"],
        "SKATE": ["#滑板", "#街式滑板", "#碗池", "#滑板公園", "#板仔日常", "#極限滑板"],
        "SNOW": ["#單板滑雪", "#雙板滑雪", "#雪場攻略", "#粉雪聖地", "#野雪Freeride", "#滑雪場"],
        "CLIMB": ["#抱石", "#攀岩", "#室內岩館", "#天然岩場", "#先鋒攀登", "#岩壁挑戰"],
        "SURF": ["#衝浪", "#世界浪點", "#浪人日常", "#浪點推薦", "#衝浪教學", "#大浪征服者"]
    }
    
    # 2. 內容型態專屬標籤（重點補強：比賽與場地）
    topic_map = {
        "SPOT": ["#極限運動場地", "#場地攻略", "#極限探索地圖", "#據點實測", "#朝聖地標", "#滑板公園指南"],
        "EVENT": ["#國際賽事實況", "#賽事雷達", "#世界盃直擊", "#決賽焦點", "#極限大賽", "#頒獎台戰報"],
        "NEWS": ["#最新戰報", "#極限速報", "#即時焦點", "#熱門話題"],
        "FORECAST": ["#賽程時間表", "#賽事預報", "#日程雷達", "#年度巡迴前瞻"],
        "ATHLETE": ["#頂尖選手", "#職業選手專訪", "#奪冠熱門"],
        "SAFETY": ["#裝備評測", "#安全護具指南", "#防護裝備"],
        "TRICKS": ["#動作分解", "#花式技巧", "#進階技術教學"]
    }

    tags = ["#xGameRadar"]
    tags.extend(sport_map.get(cat, ["#極限運動", f"#{cat}"])[:2])
    tags.extend(topic_map.get(top, ["#極限專題"])[:2])
    
    if city_tag:
        c_clean = str(city_tag).strip().upper()
        if len(c_clean) <= 15 and c_clean != "GLOBAL":
            tags.append(f"#{c_clean.title()}")
            
    t_upper = str(title).upper()
    if "X GAMES" in t_upper or "XGAMES" in t_upper:
        tags.append("#XGames")
    elif "WSL" in t_upper:
        tags.append("#WSL衝浪巡迴賽")
    elif "SLS" in t_upper:
        tags.append("#SLS街式滑板聯賽")
    elif "IFSC" in t_upper:
        tags.append("#IFSC攀岩世界盃")
    elif "FIS" in t_upper:
        tags.append("#FIS滑雪世界盃")
    elif "UCI" in t_upper:
        tags.append("#UCI自由式小輪車")

    seen = set()
    res = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            res.append(t)
            
    return " ".join(res[:6])

def generate_rich_hashtags(category_key, topic_type="GENERAL"):
    """自動依運動項目與內容型態產生專業、精準的中英雙語社群標籤"""
    cat = category_key.upper() if category_key else "SKATE"
    
    SPORT_TAGS = {
        "SKATE": ["#滑板", "#街式滑板", "#碗池", "#SKATE"],
        "BMX": ["#BMX", "#極限單車", "#小輪車", "#泵道"],
        "SURF": ["#衝浪", "#世界浪點", "#大浪征服者", "#SURF"],
        "CLIMB": ["#攀岩", "#抱石", "#運動攀登", "#天然岩場", "#CLIMB"],
        "SNOW": ["#單板滑雪", "#大跳台", "#雪場攻略", "#SNOW"]
    }
    
    TOPIC_TAGS = {
        "EVENT": ["#賽事雷達", "#國際賽況速遞"],
        "SPOT": ["#場地攻略", "#極限探索地圖"],
        "ATHLETE": ["#選手專題", "#ProProfile"],
        "SAFETY": ["#裝備評測", "#安全護具指南"]
    }
    
    selected_sport = SPORT_TAGS.get(cat, ["#極限運動", f"#{cat}"])
    selected_topic = TOPIC_TAGS.get(topic_type.upper() if topic_type else "", ["#極限運動"])
    
    all_tags = ["#xGameRadar"] + selected_sport[:3] + selected_topic[:1] + ["#ActionSports"]
    unique_tags = []
    for t in all_tags:
        if t not in unique_tags:
            unique_tags.append(t)
    return " ".join(unique_tags)

# ==========================================
# 工具函式
# ==========================================
def clean_token_or_url(val):
    """徹底清理 Token 與字串，移除所有括號、中括號、引號與多餘空白"""
    if not val:
        return ""
    return re.sub(r'[\[\]\(\)\'"]', '', str(val)).strip()

def extract_clean_url(url_str):
    """精準萃取完整 HTTP/HTTPS 網址，不截斷域名"""
    if not url_str:
        return ""
    match = re.search(r'https?://[^\s\"\'\]\)]+', str(url_str))
    if match:
        clean_u = match.group(0)
        return clean_u.rstrip('.,;)]}')
    return clean_token_or_url(url_str)

def sanitize_single_line_text(val):
    """清理標題與副標，去除換行與多餘前後引號"""
    if not val:
        return ""
    cleaned = str(val).replace('\r', ' ').replace('\n', ' ').strip()
    return re.sub(r'\s+', ' ', cleaned)

def sanitize_gear_keyword(kw):
    """清理並精簡裝備關鍵字，截取核心 4 個單字以確保 Amazon 搜尋命中率"""
    clean_k = clean_token_or_url(kw).replace(',', ' ')
    words = clean_k.split()
    return " ".join(words[:4]) if len(words) > 4 else clean_k

def url_to_base64(image_url):
    clean_url = extract_clean_url(image_url)
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(clean_url, headers=headers, timeout=12)
        res.raise_for_status()
        encoded = base64.b64encode(res.content).decode("utf-8")
        print(f"🖼️ Base64 轉換成功！長度: {len(encoded)}")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception as e:
        print(f"⚠️ 圖片 Base64 轉換失敗 ({clean_url}): {e}")
        return clean_url

# 🛡️ 雙重容錯：相容 AMAZON_AFFILIATE_ID 與 AMAZON_AFFILIATE_TAG，若為空強制帶入 kait02bc-20
AMAZON_AFFILIATE_ID = (
    clean_token_or_url(os.getenv("AMAZON_AFFILIATE_ID")) or 
    clean_token_or_url(os.getenv("AMAZON_AFFILIATE_TAG")) or 
    "kait02bc-20"
)

XGAME_CATEGORIES = {
    "SKATE": "https://www.skateboarding.com/rss",
    "CLIMB": "https://www.climbing.com/feed/",
    "BMX": "https://fatbmx.com/bmx-news?format=feed&type=rss",
    "SURF": "https://www.surfer.com/.rss/full/",
    "SNOW": "https://www.snowboarder.com/.rss/full/"
}

DEFAULT_GEAR_KEYWORDS = {
    "SKATE": "skateboarding shoes helmet pads",
    "CLIMB": "climbing shoes chalk harness",
    "BMX": "bmx helmet gloves pads",
    "SURF": "surfing wetsuit leash traction",
    "SNOW": "snowboard goggles gloves helmet"
}

# ==========================================
# 本地 SQLite 資料庫記錄判重
# ==========================================
DB_FILE = "xgame_radar.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS posted_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE,
            category TEXT,
            topic_type TEXT,
            published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS used_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id TEXT UNIQUE,
            photo_url TEXT,
            category TEXT,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def is_already_posted(title):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id FROM posted_articles WHERE title = ?", (title,))
    row = c.fetchone()
    conn.close()
    return row is not None

def record_posted_article(title, category, topic_type):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO posted_articles (title, category, topic_type) VALUES (?, ?, ?)",
                  (title, category, topic_type))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ 記錄發布文章失敗: {e}")

# ==========================================
# 1. 媒體與 RSS 抓取模組
# ==========================================
def scrape_official_media(article_url):
    if not article_url:
        return None, None
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    found_img = None
    found_video_id = None
    try:
        resp = requests.get(article_url, headers=headers, timeout=8)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            og_img = soup.find('meta', property='og:image')
            if og_img and og_img.get('content'):
                found_img = og_img['content']

            yt_match = re.search(r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/ ]{11})', resp.text)
            if yt_match:
                found_video_id = yt_match.group(1)
    except Exception:
        pass
    return found_img, found_video_id

def search_embeddable_youtube_video(query, category_key="SKATE"):
    """自動搜尋並嚴格審核 YouTube 影片相關性與外嵌播放權限（杜絕不相關內容，符合 Google E-E-A-T 規範）"""
    cat = str(category_key).upper() if category_key else "SKATE"
    
    cat_keywords = {
        "SNOW": ["snow", "ski", "snowboard", "winter", "fis", "halfpipe", "slopestyle", "big air", "滑雪", "單板", "雙板", "雪上"],
        "SURF": ["surf", "wave", "barrel", "wsl", "pipeline", "ocean", "衝浪", "浪人", "滑浪"],
        "SKATE": ["skate", "skateboard", "thrasher", "sls", "ollie", "kickflip", "tony hawk", "滑板"],
        "CLIMB": ["climb", "boulder", "ifsc", "rock", "lead climbing", "dyno", "攀岩", "抱石"],
        "BMX": ["bmx", "bike", "pumptrack", "freestyle", "logan martin", "小輪車", "單車"]
    }
    
    sport_en_names = {
        "SNOW": "snowboard ski FIS world cup",
        "SURF": "surfing WSL championship tour",
        "SKATE": "skateboarding SLS street",
        "CLIMB": "climbing IFSC boulder world cup",
        "BMX": "BMX freestyle UCI"
    }

    try:
        clean_en_term = sport_en_names.get(cat, f"{cat} action sports")
        search_query = f"{clean_en_term} official competition highlights"
        url = f"https://www.youtube.com/results?search_query={quote(search_query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=6)
        if res.status_code == 200:
            vids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', res.text)
            kw_list = cat_keywords.get(cat, [])
            
            for vid in vids[:8]:
                oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
                o_res = requests.get(oembed_url, timeout=3)
                if o_res.status_code == 200:
                    data = o_res.json()
                    v_title = data.get("title", "")
                    t_lower = v_title.lower()
                    
                    if any(k in t_lower for k in kw_list):
                        print(f"🎬 成功配對 100% 相關官方精華 [{vid}]: {v_title[:45]}")
                        return vid, v_title
                    else:
                        print(f"⏩ 略過不相關影片 [{vid}]: {v_title[:35]} (未通過 {cat} 專業相關性審核)")
    except Exception as e:
        print(f"⚠️ YouTube 影片自動搜尋跳過: {e}")

    fallback_map = {
        "SKATE": ("4YYTNkAdDD8", "Tony Hawk Lands FIRST-EVER 900 | World of X Games"),
        "BMX": ("E-VClAvTgSU", "Best of Logan Martin | Men BMX Freestyle Paris 2024 Highlights"),
        "SURF": ("26KzUnEbTUs", "Surfing the Heaviest Wave in the World - Teahupoo"),
        "CLIMB": ("jTVcRSq8IYk", "Janja Garnbret: The Lioness | Climbing Gold Highlights"),
        "SNOW": ("z1diZ6aemag", "FIS Snowboard World Cup Big Air Season Opener Official Highlights"),
        "EVENT": ("riO1y-xyWek", "Men Skateboard Street Best Trick at X Games California"),
        "SPOT": ("zJL5IVvDx1k", "Battle At The Berrics - BATB Highlights"),
        "SAFETY": ("acOvWo88a4w", "How to Kickflip Tutorial & Safety Guide"),
        "TRICKS": ("acOvWo88a4w", "How to Kickflip Tutorial & Safety Guide")
    }
    return fallback_map.get(cat, fallback_map["SKATE"])

def fetch_latest_rss_news(category_key):
    rss_url = XGAME_CATEGORIES.get(category_key.upper())
    if not rss_url:
        return "", None, None

    official_img = None
    official_video_id = None
    articles = []

    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:3]:
            title = entry.get('title', '')
            summary = entry.get('summary', entry.get('description', ''))
            clean_summary = re.sub('<[^<]+?>', '', summary)[:160]
            link = entry.get('link', '')

            if not official_img and link and BeautifulSoup:
                official_img, official_video_id = scrape_official_media(link)

            articles.append(f"• 標題: {title}\n  摘要: {clean_summary}...\n  原文: {link}")

        if articles:
            print(f"🎯 成功從官方來源抓取媒體：圖片={official_img is not None}, 影片ID={official_video_id}")
            return "\n\n".join(articles), official_img, official_video_id
    except Exception as e:
        print(f"⚠️ 讀取官方 RSS 時訊失敗: {e}")

    return "", None, None

# ==========================================
# 2. 備用專題生成引擎 (AI 未啟用時)
# ==========================================
def generate_rich_autonomous_post(category, topic_type, official_img=None, official_yt=None):
    cat = category.upper()
    titles = {
        "SKATE": "🛹 街頭滑行極限全拆解：頂級街式滑板技術、重心轉移與職業裝備配置速報",
        "CLIMB": "🧗 絕壁突圍：世界頂尖先鋒攀登技術解構、動態發力與防墜系統評測",
        "SURF": "🏄 巨浪狂潮：深海大浪核心起乘心法、板緣咬合技巧與裝備抗衝擊拆解",
        "BMX": "🚲 騰空迴旋：BMX 碗池空中抓板難度復盤、著陸緩衝與護具避險心法",
        "SNOW": "🏂 粉雪風暴：單板大跳台空中轉體平衡技術、邊刃切雪與抗寒雪鏡評測"
    }
    return {
        "title": titles.get(cat, f"⚡ {cat} 極限專題"),
        "subtitle": f"專注於頂級 {cat} 極限技術解析、動作拆解與專業選手裝備推薦指南",
        "city_tag": f"{cat}_HEADLINE",
        "gear_keyword": DEFAULT_GEAR_KEYWORDS.get(cat, "extreme sports"),
        "telegram_caption": f"⚡ 今日【{cat}】即時速報更新！\n\n1️⃣ 核心賽況與技術亮點解析\n2️⃣ 選手招牌動作重心心法\n3️⃣ 專業安全防護裝備評測\n\n👉 完整戰報請至官網查閱！",
        "website_full_content": f"### 🏆 賽況復盤與焦點戰報直擊\n\n今日聚焦全球頂尖 {cat} 賽事亮點與焦點戰報。\n\n### ⚡ 關鍵技術亮點與動作分解\n\n深入拆解頂級選手核心動作與身體發力機制。\n\n### ⚙️ 頂級選手賽事專用裝備配置點評\n\n點評選手在重大賽事中使用的專業裝備與防護配置。",
        "content": f"今日【{cat}】即時速報已上線！",
        "topic_type": "EVENT",
        "recommended_gear_title": f"{cat} 專業極限裝備",
        "recommended_gear_reason": "經專業選手測試的高標準防護裝備"
    }

# ==========================================
# 3. GEMINI AI 內容生成核心
# ==========================================
def generate_xgame_content(category_key="", topic_type="", topic_desc="", target_lang="zh-hk"):
    api_key = clean_token_or_url(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "")
    if api_key:
        masked = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "***"
        print(f"🔑 已載入 GEMINI_API_KEY ({masked}, 長度 {len(api_key)})")
    else:
        print("⚠️ 未檢測到 GEMINI_API_KEY，將啟用極限運動備用知識庫！")

    if not category_key or not category_key.strip():
        category_key = random.choice(list(XGAME_CATEGORIES.keys()))
    display_category = category_key.strip().upper()

    rss_context, official_img, official_yt = fetch_latest_rss_news(display_category)

    weekday = datetime.now().weekday()
    SCHEDULE_MAP = {
        0: {"type": "EVENT", "title": "🏆 國際賽況焦點復盤與巡迴戰報"},
        1: {"type": "ATHLETE", "title": "🔥 頂級極限選手深度專訪與招牌動作拆解"},
        2: {"type": "SPOT", "title": "🛹 全球頂級極限場地設施指南"},
        3: {"type": "SAFETY", "title": "🛡️ 安全裝備評測與護具選購指南"},
        4: {"type": "EVENT", "title": "⚡ 賽事精華與頒獎台名次速報"},
        5: {"type": "TIPS", "title": "🎯 花式招式分解與技巧心法庫"},
        6: {"type": "RECORD", "title": "🔥 極限歷史紀錄與經典重溫"}
    }
    current_schedule = SCHEDULE_MAP.get(weekday, SCHEDULE_MAP[0])

    if topic_type and str(topic_type).upper() in ["NEWS", "EVENT", "HEADLINE"]:
        active_topic = "EVENT"
        active_title = f"🏆 {display_category} 國際最新賽事戰報與即時新聞焦點速遞"
        is_pure_news = True
    elif topic_type and str(topic_type).upper() in ["FORECAST", "CALENDAR", "SCHEDULE"]:
        active_topic = "EVENT"
        active_title = f"🗓️ {display_category} 未來重大賽事預報與焦點賽程雷達"
        is_pure_news = False
    elif topic_type and str(topic_type).upper() in ["SPOT", "VENUE"]:
        active_topic = "SPOT"
        active_title = f"🛹 全球頂級 {display_category} 極限場地導覽與巡禮"
        is_pure_news = False
    else:
        active_topic = topic_type if topic_type else current_schedule["type"]
        active_title = current_schedule["title"]
        is_pure_news = False

    if api_key:
        lang_map = {
            "zh-hk": "繁體中文（香港正體字與道地廣東話/口語，100% 嚴禁任何簡體殘體字如 条/條、无/無、动/動、态/態、点/點 等，語氣熱血且極具社群吸引力）",
            "zh-cn": "簡體中文（專業熱血的極限運動社群口吻）",
            "ja": "日文（專業且地道的極限運動風格）",
            "en": "英文（Authentic Action Sports Community Style）"
        }
        selected_lang_desc = lang_map.get(target_lang, lang_map["zh-hk"])

        if is_pure_news:
            prompt = f"""
你是一位專注於全球極限運動賽事實況與國際頭條的新聞主編 Una (@Una_next)。
今日專欄核心任務：【{active_title}】（項目：{display_category}）

【必讀：最新國際官方 RSS 新聞與賽況】:
{rss_context}

【任務嚴格要求】:
1. 必須以讀取到的最新官方新聞/賽事為「唯一核心主題」進行報導！
2. 嚴禁寫成「安全裝備選購指南」或「新手入門教學」，這是一篇專業、熱血且具時效性的【即時新聞專題戰報】！
3. 嚴禁推薦酒店住宿！
4. 語言格式：完全使用 **{selected_lang_desc}**。
5. 必須以嚴格的 JSON 格式回傳，包含以下欄位：
{{
  "title": "精煉且具震撼力的新聞頭條大標題（約 20-35 字，嚴禁換行與【】符號，包含選手名或賽事名）",
  "subtitle": "一句話新聞副標題或勝負關鍵亮點（約 28-50 字）",
  "city_tag": "{display_category}_NEWS",
  "gear_keyword": "純英文裝備關鍵字（例如: surf leash wetsuit / skate shoes pro）",
  "telegram_caption": "【📱 Telegram 即時快訊】：約 100-150 字，熱血 Emoji 列點總結 3 大賽況/事件焦點，帶有強烈社群討論號召！",
  "website_full_content": "【🌐 官方網站長篇深度戰報專題】：約 500-700 字，Markdown 結構化排版，包含章節副標題（如：### 🏆 賽況復盤與焦點直擊、### ⚡ 關鍵技術亮點與動作分解、### ⚙️ 頂級選手賽事專用裝備評測），段落分明！",
  "content": "填入 telegram_caption 備用",
  "topic_type": "EVENT",
  "recommended_gear_title": "該賽事專業裝備名稱",
  "recommended_gear_reason": "推薦理由"
}}
"""
        else:
            prompt = f"""
你是一位專注於全球極限運動的專業主編 Una (@Una_next)。
今日專欄主題：【{active_title}】（項目類別：{display_category}，主題類型：{active_topic}）
{rss_context}

【運動項目術語硬性規範】：
- 若類別為 CLIMB（攀岩）：核心環境必須為「天然岩壁 (Crag) / 抱石 (Bouldering) / 先鋒運動攀 (Sport Climbing)」，抓點多為微小岩點 (Crimps) 或石縫。嚴禁出現「滑行道」、「坡道 (Ramps)」、「障礙地形」等滑板術語！
- 若類別為 SURF（衝浪）：必須為浪點、礁石浪或沙灘浪，嚴禁陸地坡道。

【地理與周邊住宿防幻覺規範】：
- 嚴禁捏造「車程只需 10 分鐘」等虛假距離！
- 若推薦周邊住宿，必須是該場地所在的同一城鎮或車程 30 分鐘內的地區；若是野外天然場地，請客觀建議下榻「鄰近主要城鎮之湖區木屋營地或 B&B」，嚴禁跨區推薦數百公里外的極光奢華酒店！

【專題寫作語氣與開頭絕對禁令】：
- 嚴禁以「我是 Una (@Una_next)」或「Hello 各位極限狂迷！我是 Una」等個人問候語開頭！
- 文章必須以頂級極限運動雜誌（xGame Radar Magazine）客觀、熱血、權威的編輯部專題視角，直接開門見山切入賽況或場地核心亮點！
- 內文嚴禁頻繁自我重複「Una 推薦」、「Una 強力建議」等贅詞，改以「編輯部推薦」或「職業選手配置建議」。

【核心事實與實名制要求（嚴禁假大空套話）】:
1. 嚴禁使用「今日國際大賽」、「全球頂尖好手」、「雪國之巔」等毫無實質內容的空泛套話！
2. 必須具體寫出：
   - 賽事正式全名與所屬機構（如 FIS、X Games、Dew Tour、SLS、WSL、IFSC 等）。
   - 舉辦城市、國家與具體賽場/雪場名稱（如瑞士庫爾 Chur、奧地利 Sölden）。
   - 冠軍、亞軍、季軍等關鍵選手姓名（附英文原名）與官方決賽得分/成績。
   - 選手決勝時施展的關鍵動作招式名稱（如 Cab 1800、Double Cork 1080、Backside Triple 等）。

【重大時間錨點與防穿越禁令】:
1. 當前現實年份為 **2026 年**（賽事週期涵蓋 2026–2027 賽季）。
2. 嚴禁在標題或內文中輸出任何已過期年份（如 2024、2023 或更早年份）的「未來預報」或「年度大賽即將開打」！
3. 所有賽事名稱、巡迴賽季度與前瞻必須嚴格鎖定在 2026–2027 最新賽季！

【任務要求】:
請生成一篇具備深度專業度、高社群傳播力與極限運動熱血感的文章資料，語言格式：完全使用 **{selected_lang_desc}**。
必須以嚴格的 JSON 格式回傳，包含以下欄位：
{{
  "title": "精煉且具震撼力的封面主標題（嚴禁換行與【】符號，約 20-35 字）",
  "subtitle": "副標題或一句話亮點總結（嚴禁換行，約 30-50 字）",
  "city_tag": "舉辦城市英文或主題標籤（例如: TOKYO, SYDNEY, CALIFORNIA, GLOBAL）",
  "gear_keyword": "純英文推薦裝備搜尋關鍵字（例如: skate shoes pro / bmx helmet，嚴禁中文）",
  "telegram_caption": "【📱 Telegram 社群專用速報短文】：約 100-150 字，熱血 Emoji 列點總結 3 大亮點，並帶有強烈互動號召！",
  "website_full_content": "【🌐 官方網站長篇深度專題】：約 450-650 字，Markdown 結構化排版，包含副標題（### 🏆 賽況焦點、### ⚡ 動作分解、### ⚙️ 裝備建議），段落分明！",
  "content": "填入 telegram_caption",
  "topic_type": "{active_topic}",
  "recommended_gear_title": "推薦裝備名稱",
  "recommended_gear_reason": "推薦理由"
}}
"""
        print(f"🤖 今日專欄: 【{active_title}】，正在呼叫 Gemini API 生成深度專題...")

        available_models = []
        try:
            m_res = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}", timeout=6)
            if m_res.status_code == 200:
                for m in m_res.json().get("models", []):
                    name = m.get("name", "").replace("models/", "")
                    if "gemini" in name and "embedding" not in name and "vision" not in name:
                        available_models.append(name)
        except Exception:
            pass

        priority_order = [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
            "gemini-2.5-pro"
        ]
        sorted_candidates = [m for m in priority_order if m in available_models]
        for m in available_models:
            if m not in sorted_candidates:
                sorted_candidates.append(m)

        if not sorted_candidates:
            sorted_candidates = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-flash-lite-latest"]

        print(f"📡 自動偵測到可用模型清單: {sorted_candidates}")

        for model_candidate in sorted_candidates:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_candidate}:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048}
            }

            try:
                res = requests.post(url, headers=headers, json=payload, timeout=25)
                if res.status_code == 200:
                    text_resp = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                    clean_json_str = text_resp.strip()
                    if clean_json_str.startswith("```"):
                        clean_json_str = re.sub(r"^```(?:json)?\n", "", clean_json_str)
                        clean_json_str = re.sub(r"\n```$", "", clean_json_str)

                    data = json.loads(clean_json_str)
                    data["title"] = sanitize_single_line_text(data.get("title", ""))
                    data["subtitle"] = sanitize_single_line_text(data.get("subtitle", ""))
                    data["official_image"] = official_img
                    data["official_video_id"] = official_yt
                    print(f"✅ Google API [{model_candidate} / v1beta] 成功生成高品質深度專題: {data['title']}")
                    return data
                else:
                    print(f"⚠️ [{model_candidate}/v1beta] 回應 ({res.status_code}): {res.text[:120]}...")
            except Exception as e:
                print(f"⚠️ [{model_candidate}/v1beta] 連線異常: {e}")

    print("⚠️ 呼叫 Gemini 失敗或金鑰缺失，採用內建智慧極限運動資料庫生成...")
    return generate_rich_autonomous_post(display_category, active_topic, official_img, official_yt)

# ==========================================
# 4. AMAZON 聯盟行銷與圖片管理
# ==========================================
def attach_affiliate_link(keyword, affiliate_id="kait02bc-20"):
    """
    產生精準且帶有佣金 Tag 的 Amazon 官方搜尋網址
    【核心防護】絕對強制帶入 kait02bc-20，絕不允許輸出 &tag= 為空
    """
    clean_kw = sanitize_gear_keyword(keyword)
    clean_tag = clean_token_or_url(affiliate_id) or "kait02bc-20"
    encoded_kw = quote(clean_kw)
    return f"https://www.amazon.com/s?k={encoded_kw}&tag={clean_tag}"

def get_used_photos_set():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT photo_id FROM used_photos")
    rows = c.fetchall()
    conn.close()
    return {row[0] for row in rows}

def record_used_photo(photo_id, photo_url, category):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO used_photos (photo_id, photo_url, category) VALUES (?, ?, ?)",
                  (str(photo_id), photo_url, category))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ 記錄相片失敗: {e}")

def get_r2_history(r2_client, bucket_name):
    """從 Cloudflare R2 讀取已發布的歷史文章與圖片清單"""
    history = {'titles': set(), 'images': set(), 'slugs': set()}
    if not r2_client or not bucket_name:
        return history
    try:
        paginator = r2_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket_name, Prefix='posts/'):
            for obj in page.get('Contents', []):
                key = obj.get('Key', '')
                history['slugs'].add(key.replace('posts/', '').replace('.json', ''))
        for page in paginator.paginate(Bucket=bucket_name, Prefix='cards/'):
            for obj in page.get('Contents', []):
                key = obj.get('Key', '')
                history['images'].add(key.replace('cards/', ''))
        print(f"📡 從 Cloudflare R2 成功同步歷史資料庫：{len(history['slugs'])} 篇文章, {len(history['images'])} 張歷史圖片")
    except Exception as e:
        print(f"⚠️ 讀取 R2 歷史記錄失敗 (將使用本地比對): {e}")
    return history

def get_action_sports_image(query_category, pexels_api_key=None, r2_history=None):
    clean_cat = clean_token_or_url(query_category).upper()
    used_ids = get_used_photos_set()
    r2_used_images = r2_history.get('images', set()) if r2_history else set()

    clean_key = clean_token_or_url(pexels_api_key)
    if clean_key:
        query_map = {
            "SKATE": "skateboard professional tricks street park",
            "CLIMB": "rock climber bouldering mountain crag",
            "BMX": "bmx bicycle extreme stunts dirt jump",
            "SURF": "surfing huge wave barrel ocean professional",
            "SNOW": "snowboarding powder mountain jump winter"
        }
        search_q = query_map.get(clean_cat, f"{clean_cat} extreme sports")
        headers = {"Authorization": clean_key}
        url = f"https://api.pexels.com/v1/search?query={quote(search_q)}&per_page=40&orientation=square"

        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                photos = res.json().get("photos", [])
                unused_photos = [
                    p for p in photos
                    if str(p["id"]) not in used_ids
                    and f"card_{p['id']}.png" not in r2_used_images
                    and f"{p['id']}.jpg" not in r2_used_images
                ]
                if not unused_photos:
                    unused_photos = photos

                selected = random.choice(unused_photos)
                photo_id = selected["id"]
                image_url = selected["src"]["large2x"]
                record_used_photo(str(photo_id), image_url, clean_cat)
                print(f"📷 Pexels 成功獲取全新未重複相片 (ID: {photo_id}): {image_url}")
                return image_url
        except Exception as e:
            print(f"⚠️ Pexels API 請求失敗: {e}")

    random_seed = random.randint(100, 99999)
    unsplash_cat = {
        "SKATE": "skateboarding",
        "CLIMB": "climbing",
        "BMX": "bmx",
        "SURF": "surfing",
        "SNOW": "snowboard"
    }.get(clean_cat, "extreme-sports")
    dynamic_url = f"https://images.unsplash.com/featured/?{unsplash_cat}&sig={random_seed}"
    record_used_photo(str(random_seed), dynamic_url, clean_cat)
    return dynamic_url

# ==========================================
# 5. 封面渲染模組 (雙重容錯降級機制)
# ==========================================
async def render_card_image_async(title, subtitle, tag_city, bg_image_url, output_path):
    bg_base64 = url_to_base64(bg_image_url).replace("'", "%27")

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@500;700;900&display=swap" rel="stylesheet">
    <style>
        body {{ margin: 0; padding: 0; width: 1080px; height: 1080px; display: flex; justify-content: center; align-items: center; background: #000; font-family: 'Noto Sans TC', 'Noto Sans CJK TC', 'WenQuanYi Zen Hei', 'Microsoft JhengHei', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .card {{ width: 1080px; height: 1080px; position: relative; background-image: url('{bg_base64}'); background-size: cover; background-position: center; display: flex; flex-direction: column; justify-content: space-between; padding: 75px; box-sizing: border-box; }}
        .overlay {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(180deg, rgba(8,8,10,0.4) 0%, rgba(8,8,10,0.88) 100%); z-index: 1; }}
        .content {{ position: relative; z-index: 2; height: 100%; display: flex; flex-direction: column; justify-content: space-between; }}
        .top-bar {{ display: flex; justify-content: space-between; align-items: center; }}
        .badge {{ background: #ff4d00; color: #fff; padding: 10px 24px; font-weight: 900; font-size: 22px; border-radius: 30px; text-transform: uppercase; letter-spacing: 2px; box-shadow: 0 0 20px rgba(255,77,0,0.5); }}
        .location {{ color: #ffffff; font-size: 22px; font-weight: 700; opacity: 0.95; }}
        .main-title {{ color: #ffffff; font-size: 58px; font-weight: 900; line-height: 1.25; margin-bottom: 20px; text-shadow: 0 4px 16px rgba(0,0,0,0.8); }}
        .subtitle {{ color: #00f2fe; font-size: 26px; font-weight: 700; line-height: 1.4; margin-bottom: 15px; }}
        .author {{ color: #ff4d00; font-size: 26px; font-weight: 800; display: flex; align-items: center; gap: 10px; }}
        .footer {{ display: flex; justify-content: space-between; align-items: flex-end; border-top: 1px solid rgba(255,255,255,0.25); padding-top: 25px; }}
        .sub-tag {{ color: #cccccc; font-size: 20px; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600; }}
    </style>
    </head>
    <body>
        <div class="card">
            <div class="overlay"></div>
            <div class="content">
                <div class="top-bar">
                    <div class="badge">xGame Radar</div>
                    <div class="location">【{tag_city}】</div>
                </div>
                <div>
                    <div class="subtitle">⚡ {subtitle}</div>
                    <div class="main-title">🏆 {title}</div>
                    <div class="author">By Una (@Una_next)</div>
                </div>
                <div class="footer">
                    <div class="sub-tag">Global Extreme Sports Magazine</div>
                    <div class="sub-tag">{tag_city} · RADAR</div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    if not async_playwright:
        print("⚠️ 未檢測到 Playwright，自動使用 PIL 生成 1080x1080 封面卡片...")
        try:
            from PIL import Image, ImageDraw
            clean_bg = extract_clean_url(bg_image_url)
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(clean_bg, headers=headers, timeout=12)
            with open("temp_bg.jpg", "wb") as f_tmp:
                f_tmp.write(r.content)
            img = Image.open("temp_bg.jpg").convert("RGB").resize((1080, 1080))
            overlay = Image.new("RGBA", (1080, 1080), (0, 0, 0, 0))
            d_overlay = ImageDraw.Draw(overlay)
            d_overlay.rectangle([(0, 650), (1080, 1080)], fill=(0, 0, 0, 190))
            img.paste(overlay, (0, 0), overlay)
            img.save(output_path, "PNG")
            if os.path.exists("temp_bg.jpg"):
                os.remove("temp_bg.jpg")
            print(f"📸 PIL 成功降級生成 1080x1080 卡片: {output_path}")
            return output_path
        except Exception as e:
            print(f"⚠️ PIL 封面生成失敗: {e}")
            return None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1080, "height": 1080})
            await page.set_content(html_template)
            await page.screenshot(path=output_path)
            await browser.close()
        print(f"📸 1080x1080 卡片圖片生成完畢: {output_path}")
        return output_path
    except Exception as e:
        print(f"⚠️ Playwright 渲染失敗 ({e})，降級使用 PIL 處理...")
        try:
            from PIL import Image, ImageDraw
            clean_bg = extract_clean_url(bg_image_url)
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(clean_bg, headers=headers, timeout=12)
            with open("temp_bg.jpg", "wb") as f_tmp:
                f_tmp.write(r.content)
            img = Image.open("temp_bg.jpg").convert("RGB").resize((1080, 1080))
            overlay = Image.new("RGBA", (1080, 1080), (0, 0, 0, 0))
            d_overlay = ImageDraw.Draw(overlay)
            d_overlay.rectangle([(0, 650), (1080, 1080)], fill=(0, 0, 0, 190))
            img.paste(overlay, (0, 0), overlay)
            img.save(output_path, "PNG")
            if os.path.exists("temp_bg.jpg"):
                os.remove("temp_bg.jpg")
            print(f"📸 PIL 成功降級生成 1080x1080 卡片: {output_path}")
            return output_path
        except Exception as ex:
            print(f"⚠️ 降級生成卡片亦失敗: {ex}")
            return None

# ==========================================
# 6. R2 雲端儲存與 ASTRO MARKDOWN
# ==========================================
def upload_to_r2(local_file_path, r2_object_name):
    account_id = clean_token_or_url(os.getenv("R2_ACCOUNT_ID", ""))
    access_key = clean_token_or_url(os.getenv("R2_ACCESS_KEY_ID", ""))
    secret_key = clean_token_or_url(os.getenv("R2_SECRET_ACCESS_KEY", ""))
    bucket_name = clean_token_or_url(os.getenv("R2_BUCKET_NAME", "xgame-radar-media"))
    public_domain = extract_clean_url(os.getenv("R2_PUBLIC_DOMAIN", "")).rstrip("/")

    if not all([account_id, access_key, secret_key]):
        print("⚠️ 未設置 Cloudflare R2 環境變數，跳過雲端上傳。")
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

        if public_domain:
            uploaded_url = f"{public_domain}/{r2_object_name}"
        else:
            uploaded_url = f"https://{account_id}.r2.cloudflarestorage.com/{bucket_name}/{r2_object_name}"

        print(f"🚀 Cloudflare R2 上傳成功: {uploaded_url}")
        return uploaded_url
    except Exception as e:
        print(f"⚠️ Cloudflare R2 上傳失敗: {e}")
        return None

def backfill_results_to_forecast(new_title, new_slug, category):
    import glob
    posts_dir = os.path.join('src', 'content', 'posts')
    if not os.path.exists(posts_dir):
        return False
    forecast_files = glob.glob(os.path.join(posts_dir, f'*_{category.lower()}_*.md'))
    for fpath in forecast_files:
        if new_slug in fpath:
            continue
        try:
            with open(fpath, 'r', encoding='utf-8') as pf:
                txt = pf.read()
            if ('EVENT' in txt or 'FORECAST' in txt) and '賽事最新結果' not in txt:
                block = chr(10) * 2 + '---' + chr(10) * 2 + '### 🏆 賽事最新結果速報' + chr(10) + f'👉 最新戰況直擊：[{new_title}](/posts/{new_slug}/)' + chr(10)
                txt += block
                txt = txt.replace('UPCOMING', 'COMPLETED')
                with open(fpath, 'w', encoding='utf-8') as pf:
                    pf.write(txt)
                print(f'🔗 成功回填賽果至預報文章: {os.path.basename(fpath)}')
        except Exception as e:
            print(f'⚠️ 回填略過: {e}')
    return True

def ensure_traditional_chinese(text):
    """確保 100% 繁體中文與香港正字，自動過濾常見簡體字"""
    if not text or not isinstance(text, str):
        return text
    sc_tc_pairs = {
        '条': '條', '无': '無', '动': '動', '态': '態', '点': '點',
        '发': '發', '实': '實', '线': '線', '标': '標', '准': '準',
        '极': '極', '头': '頭', '体': '體', '关': '關', '后': '後',
        '里': '裏', '获': '獲', '胜': '勝', '场': '場', '团': '團',
        '队': '隊', '员': '員', '赛': '賽', '经': '經', '历': '歷',
        '险': '險', '飞': '飛', '跃': '躍', '轮': '輪', '节': '節',
        '总': '總', '结': '結', '军': '軍', '亚': '亞', '录': '錄',
        '纪': '紀', '难': '難', '装': '裝', '备': '備', '评': '評',
        '测': '測', '导': '導', '览': '覽', '区': '區', '馆': '館',
        '网': '網', '链': '鏈', '购': '購', '买': '買', '选': '選',
        '择': '擇', '荐': '薦', '专': '專', '栏': '欄', '题': '題',
        '访': '訪', '谈': '談', '说': '說', '华': '華', '视': '視',
        '频': '頻', '图': '圖'
    }
    return text.translate(str.maketrans(sc_tc_pairs))

def check_content_authenticity(content_text):
    """檢查文章是否包含嚴重泛化的空話套話"""
    forbidden_generic_patterns = [
        r"今日國際滑雪大賽迎來最為白熱化",
        r"全球頂尖滑雪好手齊聚雪國之巔",
        r"多位奪冠熱門選手在跳台區使出渾身解數",
        r"完美演繹了極限雪上運動的力與美"
    ]
    for pat in forbidden_generic_patterns:
        if re.search(pat, content_text):
            print(f"⚠️ 警告：文章觸發空話黑名單 [{pat}]，將自動進行實名制過濾！")
            return False
    return True

def save_post_as_markdown(post_data, image_url, source_label="Official / Editorial"):
    """
    【100% YAML 安全鎖】生成標準 Astro Markdown
    補齊 description, city_tag, featured, tags 等 SEO 與列表渲染必備欄位
    """
    timestamp = datetime.now().strftime("%Y-%m-%d")
    category_key = str(post_data.get("category", "SKATE")).upper()
    topic_type = str(post_data.get("topic_type", "GENERAL")).upper()

    title = sanitize_single_line_text(post_data.get("title", f"{category_key} 特刊"))
    subtitle = sanitize_single_line_text(post_data.get("subtitle", ""))
    city_tag = sanitize_single_line_text(post_data.get("city_tag", "GLOBAL"))
    gear_kw = str(post_data.get("gear_keyword", "extreme sports gear")).strip()

    # 自動在文章末尾附加精準中文標籤列（強化 SEO 長尾詞檢索）
    if "🏷️ **熱門標籤**:" not in post_data.get("content", ""):
        ch_tags = generate_chinese_hashtags(category_key, topic_type, city_tag, title)
        post_data["content"] = post_data.get("content", "").rstrip() + "\n\n---\n\n🏷️ **熱門標籤**: " + str(ch_tags) + "\n"

    # 清理 slug，只保留英數底線
    clean_slug = re.sub(r'[^a-zA-Z0-9]', '_', city_tag.lower())[:15]
    if not clean_slug or clean_slug == "_":
        clean_slug = "global"

    posts_dir = os.path.join("src", "content", "posts")
    os.makedirs(posts_dir, exist_ok=True)
    filename = f"{timestamp}_{category_key.lower()}_{clean_slug}.md"
    filepath = os.path.join(posts_dir, filename)

    # 提取純標籤陣列供 Astro Collections 使用
    tag_list = [t.replace("#", "") for t in ch_tags.split() if t.startswith("#")][:6]

    frontmatter_dict = {
        "title": title,
        "subtitle": subtitle,
        "description": subtitle if subtitle else title,
        "date": datetime.now().isoformat(),
        "category": category_key if category_key in ["SKATE", "BMX", "SURF", "CLIMB", "SNOW", "EVENT", "SPOT", "ATHLETE", "SAFETY", "TRICKS"] else "SKATE",
        "topic_type": topic_type if topic_type in ["EVENT", "SPOT", "ATHLETE", "SAFETY", "RECORD", "TIPS", "GEAR", "GENERAL"] else "GENERAL",
        "cover_image": image_url,
        "cover_image_source": source_label,
        "author": "Una (@Una_next)",
        "city_tag": city_tag,
        "featured": True,
        "gear_keyword": gear_kw,
        "tags": tag_list,
        "slug": f"{timestamp}_{category_key.lower()}_{clean_slug}"
    }

    yaml_lines = ["---"]
    for k, v in frontmatter_dict.items():
        if isinstance(v, list):
            yaml_lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        elif isinstance(v, bool):
            yaml_lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            yaml_lines.append(f"{k}: {v}")
        else:
            yaml_lines.append(f"{k}: {json.dumps(str(v), ensure_ascii=False)}")
    yaml_lines.append("---")
    yaml_lines.append("")
    yaml_lines.append(f"![{title}]({image_url})")
    yaml_lines.append("")
    yaml_lines.append(post_data.get("content", ""))

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(yaml_lines))
    print(f"📝 Astro Markdown 文章已生成 (100% YAML Safe): {filepath}")
    return filepath

# ==========================================
# 7. TELEGRAM 強化推播模組 (HTML + 純文字雙重容錯)
# ==========================================
def send_telegram_post(title, subtitle, caption_text, website_url, affiliate_url, category, image_path=None, topic_type='GENERAL'):
    bot_token = clean_token_or_url(os.getenv("TELEGRAM_BOT_TOKEN", ""))
    chat_id = clean_token_or_url(os.getenv("TELEGRAM_CHAT_ID", ""))

    if not bot_token or not chat_id:
        print("⚠️ 未設定 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID，略過社群推播。")
        return

    safe_title = html.escape(str(title).strip())
    safe_subtitle = html.escape(str(subtitle).strip())
    clean_cap = re.sub(r"[*_`]", "", str(caption_text).strip())
    safe_caption = html.escape(clean_cap)

    msg_html = f"🔥 <b>{safe_title}</b>\n"
    if safe_subtitle:
        msg_html += f"<i>{safe_subtitle}</i>\n\n"
    else:
        msg_html += "\n"

    msg_html += f"{safe_caption}\n\n"
    if website_url:
        msg_html += f'🌐 <a href="{website_url}">閱讀官網完整戰報</a>\n'
    if affiliate_url:
        msg_html += f'⚙️ <a href="{affiliate_url}">專業裝備選購</a>\n'

    current_topic = topic_type if topic_type else 'GENERAL'
    msg_html += f"\n{generate_rich_hashtags(category, current_topic)}"

    if len(msg_html) > 1000:
        msg_html = msg_html[:990] + "..."

    def post_tg(content, parse_mode="HTML"):
        if image_path and os.path.exists(image_path):
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            data = {"chat_id": chat_id, "caption": content}
            if parse_mode:
                data["parse_mode"] = parse_mode
            with open(image_path, "rb") as photo:
                return requests.post(url, data=data, files={"photo": photo}, timeout=20)
        else:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {"chat_id": chat_id, "text": content}
            if parse_mode:
                data["parse_mode"] = parse_mode
            return requests.post(url, json=data, timeout=15)

    try:
        r = post_tg(msg_html, parse_mode="HTML")
        if r.status_code == 200:
            print("🚀 Telegram 極限專欄推播發送成功！")
            return
        
        print(f"⚠️ Telegram HTML 發送回應 ({r.status_code})，自動啟用純文字備用模式重發...")
        plain_text = re.sub(r"<[^<]+?>", "", msg_html)[:1000]
        r_plain = post_tg(plain_text, parse_mode=None)
        if r_plain.status_code == 200:
            print("🚀 Telegram (純文字備用模式) 發送成功！")
        else:
            print(f"⚠️ Telegram 發布回應 ({r_plain.status_code}): {r_plain.text[:120]}")
    except Exception as e:
        print(f"⚠️ Telegram 發布異常: {e}")

# ==========================================
# 8. 主排程與全自動管線
# ==========================================
async def main_async():
    print("🚀 啟動 xGame Radar Magazine 全自動化發布引擎...")
    init_db()

    category_arg = sys.argv[1] if len(sys.argv) > 1 else ""
    lang_arg = sys.argv[2] if len(sys.argv) > 2 else "zh-hk"
    topic_arg = sys.argv[3] if len(sys.argv) > 3 else ""

    category = category_arg.strip().upper() if category_arg and category_arg.upper() != "AUTO" else random.choice(list(XGAME_CATEGORIES.keys()))

    post_data = generate_xgame_content(category_key=category, topic_type=topic_arg, target_lang=lang_arg)
    api_key_check = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    post_data = ai_fact_check_and_refine(post_data, clean_token_or_url(api_key_check))
    title = post_data.get("title", f"{category} 極限特刊")
    subtitle = post_data.get("subtitle", "")
    city_tag = post_data.get("city_tag", "GLOBAL")
    gear_kw = post_data.get("gear_keyword", "extreme sports gear")
    topic_type = post_data.get("topic_type", "GENERAL")

    if is_already_posted(title):
        now_time = datetime.now().strftime("%H:%M")
        print(f"ℹ️ 偵測到文章 [{title}] 今日已存在，自動加上刊號以確保發布...")
        title = f"{title} (Vol. {now_time})"
        post_data["title"] = title

    tg_caption = post_data.get("telegram_caption") or post_data.get("content", "")
    web_content = post_data.get("website_full_content") or post_data.get("content", "")

    today_date_str = datetime.now().strftime("%Y-%m-%d")
    clean_slug = re.sub(r'[^a-zA-Z0-9]', '_', city_tag.lower())[:15]
    if not clean_slug or clean_slug == "_":
        clean_slug = "global"
    post_slug = f"{today_date_str}_{category.lower()}_{clean_slug}"

    website_article_url = f"https://unanext.fans/posts/{post_slug}/"
    affiliate_url = attach_affiliate_link(gear_kw, AMAZON_AFFILIATE_ID)

    official_img = post_data.get("official_image")
    official_yt = post_data.get("official_video_id")

    if not official_yt:
        official_yt, yt_title = search_embeddable_youtube_video(title, category)

    r2_client = None
    account_id = clean_token_or_url(os.getenv("R2_ACCOUNT_ID", ""))
    access_key = clean_token_or_url(os.getenv("R2_ACCESS_KEY_ID", ""))
    secret_key = clean_token_or_url(os.getenv("R2_SECRET_ACCESS_KEY", ""))
    bucket_name = clean_token_or_url(os.getenv("R2_BUCKET_NAME", "xgame-radar-media"))

    if boto3 and all([account_id, access_key, secret_key]):
        try:
            r2_client = boto3.client(
                "s3",
                endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name="auto"
            )
        except Exception:
            pass

    r2_history = get_r2_history(r2_client, bucket_name)

    bg_image = official_img if official_img else get_action_sports_image(category, os.getenv("PEXELS_API_KEY"), r2_history)

    card_filename = f"card_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    await render_card_image_async(title, subtitle, city_tag, bg_image, card_filename)

    r2_image_url = None
    if os.path.exists(card_filename):
        r2_object_name = f"cards/{card_filename}"
        r2_image_url = upload_to_r2(card_filename, r2_object_name)

    final_image_url = r2_image_url if r2_image_url else bg_image

    formatted_web_article = f"{web_content}\n\n"
    if official_yt:
        formatted_web_article += f"### 🎬 官方精華與動作直擊\n\n"
        # 📱 採用 16:9 RWD 自適應容器，徹底解決手機瀏覽排版破裂問題
        formatted_web_article += (
            f'<div style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;border-radius:12px;margin:20px 0;">'
            f'<iframe style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" src="https://www.youtube.com/embed/{official_yt}" allowfullscreen></iframe>'
            f'</div>\n\n'
        )

    formatted_web_article += f"### 🛒 裝備焦點推薦\n\n"
    formatted_web_article += f"👉 [點此前往 Amazon 查看推薦裝備: {gear_kw}]({affiliate_url}) *(含聯盟連結 #ad)*\n"

    post_data["content"] = formatted_web_article
    post_data["category"] = category

    # 自動過濾 AI 偶發的個人自我介紹贅詞並轉繁體
    if lang_arg == "zh-hk":
        for k in ["title", "subtitle", "content"]:
            if k in post_data and isinstance(post_data[k], str):
                post_data[k] = ensure_traditional_chinese(post_data[k])
        title = ensure_traditional_chinese(title)
        subtitle = ensure_traditional_chinese(subtitle)

    if "content" in post_data and isinstance(post_data["content"], str):
        post_data["content"] = re.sub(r'^(?:Hello|嗨|哈囉)[^。\n]*?我是\s*Una[^\n。！？]*[。！？\n]*', '', post_data["content"], flags=re.IGNORECASE)
        post_data["content"] = re.sub(r'我是\s*Una\s*(?:\(@Una_next\)|@Una_next)?[，。、\s]*', '', post_data["content"], flags=re.IGNORECASE)

    save_post_as_markdown(post_data, final_image_url, "Official / Editorial")

    # 若發布的是賽事新聞或預報，自動關聯並更新歷史預報文章
    if str(topic_type).upper() in ["EVENT", "NEWS", "FORECAST"]:
        backfill_results_to_forecast(title, post_slug, category)

    json_filename = f"{post_slug}.json"
    r2_json_payload = {
        "title": title,
        "subtitle": subtitle,
        "category": category,
        "city_tag": city_tag,
        "date": today_date_str,
        "image": final_image_url,
        "content": formatted_web_article,
        "affiliate_url": affiliate_url,
        "youtube_id": official_yt
    }
    with open(json_filename, "w", encoding="utf-8") as jf:
        json.dump(r2_json_payload, jf, ensure_ascii=False, indent=2)

    upload_to_r2(json_filename, f"posts/{json_filename}")

    # 推送至 Telegram 頻道
    send_telegram_post(
        title=title,
        subtitle=subtitle,
        caption_text=tg_caption,
        website_url=website_article_url,
        affiliate_url=affiliate_url,
        category=category,
        image_path=card_filename,
        topic_type=topic_type
    )

    record_posted_article(title, category, topic_type)

    if os.path.exists(card_filename):
        os.remove(card_filename)
    if os.path.exists(json_filename):
        os.remove(json_filename)

    print("🎉 xGame Radar Magazine 今日自動化發布與網站文章生成圓滿完成！")

if __name__ == "__main__":
    asyncio.run(main_async())
