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
# 0. CONFIG & SANITIZER UTILS
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

AMAZON_AFFILIATE_ID = clean_token_or_url(os.getenv("AMAZON_AFFILIATE_ID", "kait02bc-20"))

XGAME_CATEGORIES = {
    "SKATE": "https://www.skateboarding.com/rss",
    "CLIMB": "https://www.climbing.com/feed/",
    "BMX": "https://fatbmx.com/bmx-news?format=feed&type=rss",
    "SURF": "https://www.surfer.com/.rss/full/",
    "SNOW": "https://www.snowboarder.com/.rss/full/"
}

DEFAULT_GEAR_KEYWORDS = {
    "SKATE": "skateboarding shoes helmet protective gear",
    "CLIMB": "climbing shoes chalk bag harness",
    "BMX": "bmx helmet gloves pads",
    "SURF": "surfing wetsuit leash traction pad",
    "SNOW": "snowboard goggles gloves helmet"
}

# ==========================================
# 1. SQLITE ANTI-DUPLICATION DATABASE
# ==========================================
DB_FILE = "xgame_radar.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posted_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE,
            link TEXT,
            category TEXT,
            topic_type TEXT,
            posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute("PRAGMA table_info(posted_articles)")
    columns = [col[1] for col in cursor.fetchall()]
    if "category" not in columns:
        cursor.execute("ALTER TABLE posted_articles ADD COLUMN category TEXT")
    if "topic_type" not in columns:
        cursor.execute("ALTER TABLE posted_articles ADD COLUMN topic_type TEXT")
    if "link" not in columns:
        cursor.execute("ALTER TABLE posted_articles ADD COLUMN link TEXT")
    conn.commit()
    conn.close()

def is_already_posted(title):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM posted_articles WHERE title = ?', (title,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def record_posted_article(title, category, topic_type="GENERAL"):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO posted_articles (title, category, topic_type) VALUES (?, ?, ?)',
            (title, category, topic_type)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

# ==========================================
# 2. OFFICIAL SITE MEDIA SCRAPER & RSS PARSER
# ==========================================
def scrape_official_media(article_url):
    """從官方網站文章連結中解析 OpenGraph 高清圖片 (og:image) 與 YouTube 官方影片"""
    if not article_url or not article_url.startswith("http"):
        return None, None

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(article_url, headers=headers, timeout=8)
        if res.status_code == 200:
            img_url = None
            youtube_id = None

            if BeautifulSoup:
                soup = BeautifulSoup(res.text, "html.parser")
                og_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
                if og_img and og_img.get("content"):
                    img_url = extract_clean_url(og_img["content"])
                
                yt_iframe = soup.find("iframe", src=re.compile(r"youtube\.com|youtu\.be"))
                if yt_iframe and yt_iframe.get("src"):
                    yt_match = re.search(r"(?:embed/|v/|watch\?v=)([\w-]{11})", yt_iframe["src"])
                    if yt_match:
                        youtube_id = yt_match.group(1)
            else:
                # 無 bs4 時的純正則表達式備案 (100% 零依賴保障)
                og_match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', res.text, re.IGNORECASE) or \
                           re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', res.text, re.IGNORECASE) or \
                           re.search(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', res.text, re.IGNORECASE)
                if og_match:
                    img_url = extract_clean_url(og_match.group(1))

                yt_match = re.search(r'(?:youtube\.com/(?:embed/|watch\?v=)|youtu\.be/)([\w-]{11})', res.text)
                if yt_match:
                    youtube_id = yt_match.group(1)

            if img_url or youtube_id:
                print(f"🎯 成功從官方來源抓取媒體：圖片={bool(img_url)}, 影片ID={youtube_id}")
            return img_url, youtube_id
    except Exception as e:
        print(f"⚠️ 官方頁面媒體解析跳過 ({article_url[:40]}...): {e}")

def search_embeddable_youtube_video(query, category_key="SKATE"):
    """自動搜尋並透過 YouTube oEmbed API 驗證 100% 可外嵌播放的官方極限運動影片"""
    try:
        search_query = f"{query} extreme sports official"
        url = f"https://www.youtube.com/results?search_query={quote(search_query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res = requests.get(url, headers=headers, timeout=6)
        if res.status_code == 200:
            vids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', res.text)
            for vid in vids[:6]:
                # 必須通過 oEmbed 驗證，確保 100% 存在且允許外嵌播放
                oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
                o_res = requests.get(oembed_url, timeout=3)
                if o_res.status_code == 200:
                    data = o_res.json()
                    title = data.get("title", f"{category_key} Official Action")
                    print(f"🎬 自動成功配對 YouTube 官方精華 [{vid}]: {title[:40]}")
                    return vid, title
    except Exception as e:
        print(f"⚠️ YouTube 影片自動搜尋跳過: {e}")

    # 分類備案官方 100% 存在且可播放影片
    fallback_map = {
        "SKATE": ("4YYTNkAdDD8", "Tony Hawk Lands FIRST-EVER 900 | World of X Games"),
        "BMX": ("E-VClAvTgSU", "Best of Logan Martin | Men BMX Freestyle Paris 2024 Highlights"),
        "SURF": ("26KzUnEbTUs", "Surfing the Heaviest Wave in the World - Teahupoo"),
        "CLIMB": ("jTVcRSq8IYk", "Janja Garnbret: The Lioness | Climbing Gold Highlights"),
        "SNOW": ("he03dVkhLTM", "Shaun White Snowboard Halfpipe Gold | PyeongChang 2018"),
        "EVENT": ("riO1y-xyWek", "Men Skateboard Street Best Trick at X Games California"),
        "SPOT": ("zJL5IVvDx1k", "Battle At The Berrics - BATB Highlights"),
        "SAFETY": ("acOvWo88a4w", "How to Kickflip Tutorial & Safety Guide"),
        "TRICKS": ("acOvWo88a4w", "How to Kickflip Tutorial & Safety Guide")
    }
    return fallback_map.get(category_key.upper(), fallback_map["SKATE"])

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

            articles.append(f"- {title}: {clean_summary} (來源: {link})")

            # 嘗試抓取官方媒體圖片
            if not official_img:
                # 檢查 RSS 內建 media_content
                if 'media_content' in entry and len(entry['media_content']) > 0:
                    official_img = entry['media_content'][0].get('url')
                elif 'media_thumbnail' in entry and len(entry['media_thumbnail']) > 0:
                    official_img = entry['media_thumbnail'][0].get('url')
                elif 'enclosures' in entry and len(entry['enclosures']) > 0:
                    official_img = entry['enclosures'][0].get('href')
                
                # 若 RSS 內無圖片但有文章網址，爬取官網 og:image
                if not official_img and link:
                    scraped_img, scraped_yt = scrape_official_media(link)
                    if scraped_img:
                        official_img = scraped_img
                    if scraped_yt:
                        official_video_id = scraped_yt

        if articles:
            context_text = "【最新官方 RSS 參考新聞】:\n" + "\n".join(articles)
            return context_text, official_img, official_video_id
    except Exception as e:
        print(f"⚠️ RSS 抓取失敗 ({category_key}): {e}")

    return "", None, None

# ==========================================
# 3. GEMINI AI CONTENT ENGINE (RICH PILLARS)
# ==========================================
def generate_rich_autonomous_post(category, topic_type, official_img=None, official_yt=None):
    """當 Gemini API 離線或未提供金鑰時，自動從極限運動精選知識庫生成深度專題"""
    cat = category.upper()
    timestamp_str = datetime.now().strftime("%Y-%m-%d")

    autonomous_db = {
        "CLIMB": {
            "title": f"🏆 IFSC 運動攀登世界巡迴焦點戰報：解析 8b+ 極限抱石與雙料路線密碼",
            "subtitle": "直擊世界頂級攀岩大賽！全球頂尖選手齊聚，難度賽 45 度仰角牆與極限 Dyno 動態跳躍深度剖析",
            "city_tag": "INNSBRUCK",
            "gear_keyword": "climbing shoes chalk bag petzl harness",
            "recommended_gear_title": "La Sportiva Solution Comp 頂級抱石攀岩鞋",
            "recommended_gear_reason": "奧運金牌選手御用鞋款，極致下彎鞋弓與足跟包裹力，提供微小晶體岩點強大踩踏支撐",
            "telegram_caption": "⚡ 各位極限攀爬迷！IFSC 運動攀登世界巡迴賽焦點戰報速遞！\n\n🧗 3大核心看點：\n1️⃣ 決賽牆高達 15 米、仰角超過 45 度，考驗極致指力！\n2️⃣ 第 32 個微型手點過渡 + 終點超遠距 Dyno 動態跳躍\n3️⃣ 頂級選手選用不對稱弓形鞋與高純度碳酸鎂粉精準發力\n\n💬 你覺得邊個動作最震撼？留言話我知！",
            "website_full_content": """### 🏆 賽況復盤與頂級岩壁挑戰

本站 IFSC 國際運動攀登世界盃在奧地利因斯布魯克盛大開賽。作為巴黎奧運後的首場頂級大賽，主辦方在路線設計上展現了極高的難度與觀賞性。決賽難度牆高達 15 米，整體岩壁向外傾斜超過 45 度，極大考驗選手的核心抗疲勞能力與瞬間爆發力。

關鍵計分點集中在第 32 個手點的微型捏點（Micro-Crimp）過渡區。選手必須在 6 分鐘規定時間內完成路線判讀，並在高空進行一次超過 1.8 米的超遠距離動態跳躍（Dyno）。

### ⚡ 關鍵技術亮點與動作分解

1. **屋頂天花板掛腳（Heel/Toe Hook）**：在倒掛屋頂地形中，選手利用腳跟與腳尖鎖死岩點，減輕手臂 40% 以上的負重。
2. **微小晶體邊緣踩踏（Micro-Edge Smearing）**：鞋尖橡膠必須精準嵌入 3 毫米以下的微小岩縫，產生強大的摩擦抓地力。

### ⚙️ 職業選手專用裝備配置深度解析

面對高摩擦係數的現代競技岩壁，頂級攀爬者普遍選用高不對稱、下彎鞋弓設計的專業抱石鞋（如 La Sportiva Solution Comp）。搭配高透氣輕量安全帶與超細顆粒高純度碳酸鎂粉，確保手指在極限出汗狀態下依然具備頂級乾爽抓握力。""",
            "video_id": "jTVcRSq8IYk",
            "video_title": "Janja Garnbret: The Lioness | Climbing Gold Highlights",
            "expert_info": {
                "name": "Janja Garnbret",
                "country": "斯洛維尼亞 (Slovenia)",
                "stance_or_style": "抱石與難度雙料統治級選手",
                "signature_tricks": ["Dyno to Heel Hook", "Campus on Micro-Edges", "Flash on 8b Boulder"],
                "setup_breakdown": "La Sportiva Solution Comp + Petzl Sitta 安全帶 + FrictionLabs 頂級攀岩粉"
            }
        },
        "SKATE": {
            "title": f"🏆 SLS 街式滑板超級王冠總決賽倒數：全球頂級滑手終極陣容與招牌大招前瞻",
            "subtitle": "直擊 SLS Super Crown 街式滑板最高殿堂！Nyjah Huston 與堀米雄斗的極限技術對決",
            "city_tag": "LOS ANGELES",
            "gear_keyword": "skateboarding shoes helmet protective gear",
            "recommended_gear_title": "Pro-Tec 經典款雙認證極限滑板安全頭盔",
            "recommended_gear_reason": "CPSC & ASTM 雙重安全認證，高抗衝擊 EPS 核心泡沫，大落差台階失誤防護首選",
            "telegram_caption": "⚡ 各位滑板迷！SLS Super Crown 街式滑板總決賽前瞻火熱登場！\n\n🛹 3大焦點搶先睇：\n1️⃣ 12 階大扶手 + 雙層 Hubba 階梯頂級訂製賽道\n2️⃣ Nyjah Huston 對決 堀米雄斗，爭奪最高積分王座\n3️⃣ 8.25 吋高彈性加拿大楓木板身 + 99A-101A 耐磨輪組解析\n\n💬 你今屆撐邊個？即刻留言！",
            "website_full_content": """### 🏆 賽事背景與 SLS 頂級街式殿堂

SLS (Street League Skateboarding) Super Crown 總決賽作為全球最具含金量的街式滑板職業賽事，匯聚了全球排名前八位的頂級職業滑手。本屆大會特別打造了融合街頭真實地形與賽事標準的頂級場地，包含 12 階大落差樓梯、金字塔斜台與超長雙層 Hubba 大理石滑台。

賽事分為 Line Section（連續動作線路）與 Best Trick Section（單一大招評分），每一輪動作均由 5 位國際裁判以精確至 0.1 分進行極限評分。

### ⚡ 關鍵技術拆解：冠軍級殺手鐧

- **Caballerial Backside Lipslide**：在 12 階大扶手上完成 360 度倒板轉體並順勢鎖定板身中段滑行，對起跳高度與滯空平衡要求極高。
- **Switch Frontside Crooked Grind**：非慣用腳（Switch）起跳並以斜角輪架鎖死金屬邊緣，展現毫釐不差的磨桿控制力。

### ⚙️ 職業滑手裝備配置深度評測

面對連續高衝擊落地，職業選手選用 8.25 吋高壓 7 層加拿大硬楓木板身，搭配輕量化鈦合金輪架（Titanium Trucks）與 99A-101A 軟硬度的高回彈聚氨酯滑板輪，確保高速滑行不平點，落地兼具極致吸震與回彈回饋。""",
            "video_id": "-Lra51BUgEs",
            "video_title": "NYJAH’S BACK ON TOP! Top Moments from his SLS Super Crown Win",
            "expert_info": {
                "name": "Nyjah Huston",
                "country": "美國 (USA)",
                "stance_or_style": "Goofy / 頂尖街式大扶手與高難度翻板磨桿 (Big Rail & Technical)",
                "signature_tricks": ["Cab Backside Lipslide", "Switch Frontside Crooked Grind", "Nollie Heel Backside Tailslide"],
                "setup_breakdown": "Disorder 8.125 板身 + Thunder Titanium Lights 支架 + Bones STF 52mm 輪組"
            }
        },
        "BMX": {
            "title": f"🏆 UCI BMX Freestyle 極限自由式世界巡迴賽：空中 720 空翻與連續神技解析",
            "subtitle": "極限空中美學！解析全球頂尖 BMX 選手如何以超大滯空時間鎖定分站金牌與 Hyper 戰車配置",
            "city_tag": "GOLD COAST",
            "gear_keyword": "bmx helmet gloves fox racing",
            "recommended_gear_title": "Fox Racing Proframe 全罩式輕量極限頭盔",
            "recommended_gear_reason": "DH / BMX 賽事指定標準，高透氣整合下巴防護與 MIPS 衝擊系統",
            "telegram_caption": "⚡ 各位 BMX 車迷！UCI BMX Freestyle 極限自由式戰報來襲！\n\n🚲 3大空中神技速報：\n1️⃣ 滯空時間突破 3.5 秒，垂直躍升超過 5 米！\n2️⃣ Backflip Double Tailwhip 空翻雙甩尾神級連招\n3️⃣ 360 度旋轉 Gyro 雙抽油壓剎車系統極限配置\n\n💬 邊個大招最誇張？留言話我知！",
            "website_full_content": """### 🏆 賽事精華與空中滯空極限

UCI BMX Freestyle 自由式世界盃黃金海岸站展開激烈廝殺。本站木質碗池與拋台（MegaRamp）高度超過 6 米，頂尖選手在空中能獲得超過 3.5 秒的純粹滯空時間，為複雜的多重轉體動作提供了完美的發揮空間。

### ⚡ 焦點神技分解

1. **720 Barspin to Barspin**：在空中完成兩周 720 度水平旋轉的同時，雙手連續完成兩次車把 360 度凌空轉把。
2. **Backflip Triple Tailwhip**：後空翻狀態下連續完成三次車身 360 度水平甩尾，對核心爆發力與接車精準度要求達到極致。

### ⚙️ 冠軍級戰車配置與安全建議

極限自由式戰車採用 20.4 吋短後叉鉻鉬鋼（4130 Cr-Mo）車架，搭配 360 度旋轉 Gyro 雙抽剎車系統，確保連續空中甩把甩尾線管不打結。頭部防護首選配備 MIPS 衝擊防護系統的全罩式碳纖維安全頭盔。""",
            "video_id": "E-VClAvTgSU",
            "video_title": "Best of Logan Martin | Men BMX Freestyle Paris 2024 Highlights",
            "expert_info": {
                "name": "Logan Martin",
                "country": "澳洲 (Australia)",
                "stance_or_style": "Park / 頂尖超大滯空花式 (Huge Air & Technical Flips)",
                "signature_tricks": ["Triple Tailwhip", "720 Barspin to Barspin", "Backflip Double Whip"],
                "setup_breakdown": "Hyper Wizard Jet Fuel 車架 + Snafu Maelstrom 零件組 + Maxxis Grifter 輪胎"
            }
        },
        "SURF": {
            "title": f"🏆 WSL 世界衝浪巡迴賽夏威夷 Pipeline 站：直擊致命巨浪管與王者對決",
            "subtitle": "衝浪界的終極殿堂！解析冬季北太平洋超強湧浪下的管浪深度切入與計分關鍵",
            "city_tag": "OAHU HAWAII",
            "gear_keyword": "surfing wetsuit rip curl fcs fins",
            "recommended_gear_title": "Rip Curl Flashbomb 專業保暖防寒衣與 FCS II 碳纖維衝浪尾舵",
            "recommended_gear_reason": "頂級輕量彈性氯丁橡膠，提供大浪管高速下切時完美的抓水與控板性能",
            "telegram_caption": "⚡ 各位浪人！WSL 衝浪巡迴賽夏威夷 Pipeline 站戰報直擊！\n\n🏄 3大管浪看點：\n1️⃣ 冬季北太平洋 12-18 呎巨型猛烈管浪\n2️⃣ 致命淺礁區 Drop-in 垂直下切極限考驗\n3️⃣ 6'8\" 槍板 + 碳纖維蜂巢尾舵極限軌跡控制\n\n💬 咁大個浪你敢唔敢落？留言傾下！",
            "website_full_content": """### 🏆 賽事焦點：衝浪運動的終極聖殿

夏威夷北岸的 Banzai Pipeline 被公認為全球最致命但也最具觀賞性的巨浪管點。冬季強烈的北太平洋低壓系統帶來高達 12 至 18 英尺的超重型管浪，浪壁在極淺的火山珊瑚礁上瞬間崩塌，形成完美的圓柱形水下真空巨管。

裁判評分的最高標準在於「Deep Barrel（深層鑽管）」的切入深度與在極度浪花崩塌壓迫下能否完整出浪（Make the Wave）。

### ⚡ 關鍵技術剖析

- **Late Drop-in（極限晚下切）**：在浪頭即將合攏的垂直浪壁上起乘，雙腳必須精準卡緊防滑墊，利用浪板內側邊緣（Rail）死死咬住水面。
- **Stall & Speed Control（管內控速）**：用手掌拖拽浪壁進行微幅減速以深入管心，隨後壓低重心全速衝出浪口。

### ⚙️ 浪板配置與防護選購

面對 Pipeline 級別的巨浪，選手多採用 6'6\" 至 7'2\" 的 Step-up 槍板（Gun），搭配碳纖維強化蜂巢結構尾舵（FCS II Fins）與高抗拉力大浪腳繩，確保高速切入浪壁時具備絕對的軌跡穩定性。""",
            "video_id": "OcAH2xXfVhA",
            "video_title": "Kelly Slater Monumental Road To Victory - Billabong Pro Pipeline",
            "expert_info": {
                "name": "Kelly Slater",
                "country": "美國 (USA)",
                "stance_or_style": "Regular / 史上最偉大衝浪王者 (11座世界冠軍傳奇)",
                "signature_tricks": ["Deep Barrel Ride", "Air Reverse", "Roundhouse Cutback"],
                "setup_breakdown": "Slater Designs / Firewire FRK 板型 + Endorfins KS 碳纖維尾舵"
            }
        },
        "SNOW": {
            "title": f"🏆 X Games 冬季極限單板 SuperPipe 總決賽：空中三周轉體 1440 終極震撼",
            "subtitle": "直擊 22 尺巨型 U 型槽之戰！全球頂級單板滑雪選手的極限騰空與抓板美學",
            "city_tag": "ASPEN COLORADO",
            "gear_keyword": "snowboard goggles anon burton helmet",
            "recommended_gear_title": "Anon M4 磁吸快拆防霧雪鏡 & Burton 碳纖維固定器",
            "recommended_gear_reason": "ZEISS 光學增對比鏡片，在高速 SuperPipe 陰影與強光切換時提供清晰雪道視野",
            "telegram_caption": "⚡ 各位雪友！X Games 冬季極限單板 SuperPipe 決賽焦點！\n\n🏂 3大高空震撼看點：\n1️⃣ 22 尺垂直冰切雪槽，騰空高度突破 6 米！\n2️⃣ Frontside Double Cork 1440 空中三周轉體大招\n3️⃣ Camber 正拱高硬度單板 + 碳纖維固定器極限抓雪\n\n💬 邊個動作最令你起雞皮？即刻留言！",
            "website_full_content": """### 🏆 賽事亮點：22 尺垂直巨型 U 槽巔峰之戰

美國阿斯本（Aspen）X Games 冬季極限運動會單板 SuperPipe 總決賽聚集了全世界最頂尖的 U 槽滑手。高達 22 英尺的冰切垂直牆壁中，滑手以超過 40km/h 的高速衝出槽頂，滯空高度突破 6 米，在空中展現極致轉體與優雅抓板。

### ⚡ 焦點神技拆解

1. **Frontside Double Cork 1440**：在正向起跳中完成兩次偏軸空翻與整整四周（1440度）轉體，並在落地前緊緊抓牢板刃（Mute Grab）。
2. **Switch Backside 1260**：倒滑起跳並以背向盲區完成三周半旋轉，對空間感知與空中落點預判要求極為苛刻。

### ⚙️ 頂級單板滑雪裝備配置

面對極速刻滑與高空衝擊，選手首選 Camber 正拱硬度 8/10 以上的專業競技板身，搭配碳纖維高反應固定器與 ZEISS 增對比磁吸快拆防霧雪鏡，確保在高速陰影與烈日轉換間保持清晰雪面視野。""",
            "video_id": "he03dVkhLTM",
            "video_title": "Shaun White grabs Snowboard Halfpipe Gold | PyeongChang 2018",
            "expert_info": {
                "name": "Shaun White",
                "country": "美國 (USA)",
                "stance_or_style": "Regular / 傳奇飛天番茄 (3屆奧運單板U型槽金牌)",
                "signature_tricks": ["Double McTwist 1260", "Frontside Double Cork 1440", "Tomahawk"],
                "setup_breakdown": "WHITESPACE Freestyle 156 板身 + Burton Custom X 固定器"
            }
        }
    }

    base = autonomous_db.get(cat, autonomous_db["SKATE"])
    return {
        "title": base["title"],
        "subtitle": base["subtitle"],
        "city_tag": base["city_tag"],
        "gear_keyword": base["gear_keyword"],
        "telegram_caption": base["telegram_caption"],
        "website_full_content": base["website_full_content"],
        "content": base["website_full_content"],
        "topic_type": topic_type if topic_type else "EVENT",
        "recommended_gear_title": base["recommended_gear_title"],
        "recommended_gear_reason": base["recommended_gear_reason"],
        "youtube_video_id": official_yt if official_yt else base["video_id"],
        "youtube_video_title": base["video_title"],
        "expert_info": base.get("expert_info"),
        "official_cover_image": official_img
    }

def generate_xgame_content(category_key="", topic_type="", topic_desc="", target_lang="zh-hk"):
    api_key = clean_token_or_url(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "")
    if api_key:
        masked = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "***"
        print(f"🔑 已載入 GEMINI_API_KEY ({masked}, 長度 {len(api_key)})")
    else:
        print("⚠️ 未檢測到 GEMINI_API_KEY，將啟用極限運動智慧知識庫生成深度專題！")

    if not category_key or not category_key.strip():
        category_key = random.choice(list(XGAME_CATEGORIES.keys()))
    display_category = category_key.strip().upper()

    rss_context, official_img, official_yt = fetch_latest_rss_news(display_category)

    # 內容輪播排程：五大支柱
    weekday = datetime.now().weekday()
    SCHEDULE_MAP = {
        0: {"type": "EVENT", "title": "🗓️ 未來3-12個月賽事雷達與近期戰報"},
        1: {"type": "SPOT", "title": "🛹 全球與亞洲頂級場地導覽"},
        2: {"type": "ATHLETE", "title": "🏆 焦點專家與選手檔案 (PRO PROFILE)"},
        3: {"type": "SAFETY", "title": "🛡️ 安全裝備評測與護具選購指南"},
        4: {"type": "EVENT", "title": "⚡ 賽事精華與頒獎台名次速報"},
        5: {"type": "TIPS", "title": "🎯 花式招式分解與技巧心法庫"},
        6: {"type": "RECORD", "title": "🔥 極限歷史紀錄與經典重溫"}
    }

    current_schedule = SCHEDULE_MAP.get(weekday, SCHEDULE_MAP[0])
    active_topic = topic_type if topic_type else current_schedule["type"]
    active_title = current_schedule["title"]

    # 若有 API Key，嘗試呼叫 Google Gemini API
    if api_key:
        lang_map = {
            "zh-hk": "繁體中文（廣東話/香港口語，語氣熱血且極具社群吸引力）",
            "zh-cn": "簡體中文（專業熱血的極限運動社群口吻）",
            "ja": "日文（專業且地道的極限運動風格）",
            "en": "英文（Authentic Action Sports Community Style）"
        }
        selected_lang_desc = lang_map.get(target_lang, lang_map["zh-hk"])

        prompt = f"""
你是一位專注於全球極限運動的專業主編 Una (@Una_next)。
今日專欄主題：【{active_title}】（項目類別：{display_category}，主題類型：{active_topic}）
{rss_context}

【任務要求】:
請生成一篇具備深度專業度、高社群傳播力與極限運動熱血感的文章資料，語言格式：完全使用 **{selected_lang_desc}**。
必須以嚴格的 JSON 格式回傳（請勿輸出 Markdown 區塊或多餘文字），包含以下欄位：

{{
  "title": "精煉且具震撼力的封面主標題（嚴禁【】符號，約 20-35 字）",
  "subtitle": "副標題或一句話亮點總結（約 30-50 字）",
  "city_tag": "舉辦城市英文或主題城市（例如: TOKYO, SYDNEY, CALIFORNIA, GLOBAL）",
  "gear_keyword": "純英文推薦裝備搜尋關鍵字（例如: skate shoes pro / bmx helmet / surfing wetsuit，嚴禁中文）",
  "telegram_caption": "【📱 Telegram 社群專用速報短文】：約 100-150 字，極致精練，熱血 Emoji 列點總結 3 大賽事/動作/場地核心亮點，並帶有強烈社群互動號召！",
  "website_full_content": "【🌐 官方網站長篇深度專題】：約 450-650 字，嚴格使用 Markdown 結構化排版，包含多個章節副標題（例如：### 🏆 賽況復盤與焦點直擊、### ⚡ 關鍵技術亮點與動作分解、### ⚙️ 職業裝備深度評測與選購建議），段落分明，具備極高資訊密度與專業深度！",
  "content": "保留備用字段（填入 telegram_caption）",
  "topic_type": "{active_topic}",
  "expert_info": {{
    "name": "選手或專家姓名（若為 ATHLETE 主題請填寫，否則可留空）",
    "country": "代表國家",
    "stance_or_style": "風格或站姿",
    "signature_tricks": ["招牌動作1", "招牌動作2"],
    "setup_breakdown": "專用裝備配置說明"
  }},
  "spot_info": {{
    "name": "場地名稱（若為 SPOT 主題請填寫）",
    "location": "場地地理位置",
    "difficulty": "All Levels / Beginner / Intermediate / Advanced / Pro",
    "features": ["特點1", "特點2"],
    "fee": "收費方式"
  }},
  "event_info": {{
    "event_name": "賽事名稱（若為 EVENT 主題請填寫）",
    "dates": "賽事日期（未來3-12個月或近期）",
    "event_status": "UPCOMING",
    "location": "賽事地點",
    "tier": "World Championship / X-Games Tier"
  }},
  "trick_info": {{
    "trick_name": "花式招式名稱（若為 TIPS/TRICKS 主題請填寫）",
    "difficulty_rating": 3,
    "prerequisites": ["先修基礎動作1", "先修基礎動作2"]
  }},
  "safety_gear_info": {{
    "gear_type": "裝備品類（若為 SAFETY 主題請填寫）",
    "certification": "ASTM F1492 / CPSC / CE EN1078"
  }},
  "recommended_gear_title": "Amazon 推薦商品中文標題",
  "recommended_gear_reason": "推薦理由"
}}
"""
        print(f"🤖 今日專欄: 【{active_title}】，正在呼叫 Gemini API 生成深度專題...")
        
        # 動態偵測 API Key 支援的有效 Gemini 模型
        available_models = []
        try:
            list_res = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}", timeout=10)
            if list_res.status_code == 200:
                models_data = list_res.json().get("models", [])
                for m in models_data:
                    if "generateContent" in m.get("supportedGenerationMethods", []):
                        m_name = m["name"].replace("models/", "")
                        if "gemini" in m_name:
                            available_models.append(m_name)
                print(f"📡 自動偵測到可用模型清單: {available_models[:6]}")
        except Exception as e:
            print(f"⚠️ 模型清單自動查詢跳過: {e}")

        # 若未自動取得，使用最全面之相容清單
        if not available_models:
            available_models = [
                "gemini-1.5-flash-latest",
                "gemini-1.5-flash-001",
                "gemini-1.5-flash-002",
                "gemini-1.5-pro-latest",
                "gemini-1.5-pro-001",
                "gemini-2.0-flash-exp",
                "gemini-2.5-flash",
                "gemini-1.5-flash"
            ]

        for model_name in available_models:
            for api_ver in ["v1beta", "v1"]:
                url = f"https://generativelanguage.googleapis.com/{api_ver}/models/{model_name}:generateContent?key={api_key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.4
                    }
                }
                try:
                    res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
                    if res.status_code == 200:
                        data = res.json()
                        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw_text)
                        if json_match:
                            raw_text = json_match.group(1).strip()
                        start = raw_text.find('{')
                        end = raw_text.rfind('}')
                        if start != -1 and end != -1:
                            raw_text = raw_text[start:end+1]
                        
                        parsed = json.loads(raw_text)
                        if parsed and isinstance(parsed, dict) and parsed.get("title"):
                            if official_img:
                                parsed["official_cover_image"] = official_img
                            if official_yt:
                                parsed["youtube_video_id"] = official_yt
                            print(f"✅ Google API [{model_name} / {api_ver}] 成功生成高品質深度專案: {parsed.get('title')}")
                            return parsed
                    elif res.status_code != 404:
                        print(f"⚠️ [{model_name}/{api_ver}] 回應 ({res.status_code}): {res.text[:100]}")
                except Exception as e:
                    pass

    # 若 API 離線或未設定金鑰，啟用自主深度專題生成引擎
    print(f"⚡ 啟用極限運動精選知識庫生成【{display_category}】深度專題...")
    return generate_rich_autonomous_post(display_category, active_topic, official_img, official_yt)

# ==========================================
# 4. AFFILIATE LINK BUILDER
# ==========================================
def attach_affiliate_link(content_text, gear_keyword, category_key):
    clean_kw = re.sub(r'[^a-zA-Z0-9\s]', '', gear_keyword).strip()
    if not clean_kw or len(clean_kw) < 2:
        clean_kw = DEFAULT_GEAR_KEYWORDS.get(category_key.upper(), "extreme sports gear")

    encoded_kw = quote(clean_kw)
    amazon_url = f"https://www.amazon.com/s?k={encoded_kw}&tag={AMAZON_AFFILIATE_ID}"
    display_name = clean_kw.title()

    affiliate_block = (
        f"\n\n🛒 *Una 裝備選購建議*:\n"
        f"👉 [{display_name} Amazon 直送門市]({amazon_url})\n"
        f"*(透過連結購買可支持本頻道與網站運作)*"
    )
    return content_text + affiliate_block

# ==========================================
# 5. ACTION SPORTS IMAGE REPOSITORY & PEXELS FETCHER
# ==========================================
CATEGORY_ACTION_IMAGES = {
    "SKATE": [
        "https://images.unsplash.com/photo-1516762689617-e1cffcef479d?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1547447134-cd3f5c716030?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1564769662533-4f00a87b4056?auto=format&fit=crop&w=1200&q=80"
    ],
    "BMX": [
        "https://images.unsplash.com/photo-1508780709619-79562169bc64?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1576435728678-68d0fbf94e91?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1508780709619-79562169bc64?auto=format&fit=crop&w=1200&q=80"
    ],
    "SURF": [
        "https://images.unsplash.com/photo-1502680390469-be75c86b636f?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1459749411175-04bf5292ceea?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80"
    ],
    "CLIMB": [
        "https://images.unsplash.com/photo-1522163182402-834f871fd851?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1564769662533-4f00a87b4056?auto=format&fit=crop&w=1200&q=80"
    ],
    "SNOW": [
        "https://images.unsplash.com/photo-1551698618-1dfe5d97d256?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1491553895911-0055eca6402d?auto=format&fit=crop&w=1200&q=80"
    ],
    "EVENT": [
        "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1508780709619-79562169bc64?auto=format&fit=crop&w=1200&q=80"
    ],
    "SPOT": [
        "https://images.unsplash.com/photo-1564769662533-4f00a87b4056?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1516762689617-e1cffcef479d?auto=format&fit=crop&w=1200&q=80"
    ],
    "SAFETY": [
        "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1547447134-cd3f5c716030?auto=format&fit=crop&w=1200&q=80"
    ]
}

def get_action_sports_image(keyword, category_key="SKATE"):
    """精準抓取對應運動項目的高畫質相片，徹底杜絕披薩與多肉植物等無關圖片"""
    cat = category_key.upper() if category_key else "SKATE"
    if cat not in CATEGORY_ACTION_IMAGES:
        cat = "SKATE"

    pexels_key = clean_token_or_url(os.getenv("PEXELS_API_KEY", ""))
    if pexels_key:
        try:
            headers = {"Authorization": pexels_key}
            # 確保搜尋詞強烈關聯極限運動
            search_query = f"{cat.lower()} action sports {keyword}".strip()
            clean_keyword = quote(search_query)
            url = f"https://api.pexels.com/v1/search?query={clean_keyword}&per_page=3&orientation=landscape"
            res = requests.get(url, headers=headers, timeout=10).json()
            if res.get("photos") and len(res["photos"]) > 0:
                img_url = extract_clean_url(res["photos"][0]["src"]["large2x"])
                print(f"✅ Pexels 成功抓取【{cat}】極限動作圖: {img_url}")
                return img_url
        except Exception as e:
            print(f"⚠️ Pexels 搜尋跳過: {e}")

    # 預設使用真實極限運動相片庫
    selected = random.choice(CATEGORY_ACTION_IMAGES.get(cat, CATEGORY_ACTION_IMAGES["SKATE"]))
    print(f"📸 選用【{cat}】高畫質運動相片庫: {selected}")
    return selected

# ==========================================
# 6. ASYNC PLAYWRIGHT CARD RENDERER
# ==========================================
async def render_card_image_async(title, subtitle, tag_city, bg_image_url, output_path):
    bg_base64 = url_to_base64(bg_image_url).replace("'", "%27")

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <style>
        body {{ margin: 0; padding: 0; width: 1080px; height: 1080px; display: flex; justify-content: center; align-items: center; background: #000; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
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

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1080, "height": 1080})
        await page.set_content(html_template)
        await page.screenshot(path=output_path)
        await browser.close()
    print(f"📸 1080x1080 卡片圖片生成完畢: {output_path}")

# ==========================================
# 7. CLOUDFLARE R2 STORAGE UPLOADER
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

        file_url = f"{public_domain}/{r2_object_name}" if public_domain else f"https://pub-{account_id}.r2.dev/{r2_object_name}"
        print(f"☁️ 檔案已成功上傳至 R2: {file_url}")
        return file_url
    except Exception as e:
        print(f"❌ R2 上傳失敗: {e}")
        return None

# ==========================================
# 8. MARKDOWN POST GENERATOR (ASTRO COMPATIBLE)
# ==========================================
def save_post_as_markdown(post_data, image_url, source_label="Official / Editorial"):
    timestamp = datetime.now().strftime("%Y-%m-%d")
    category_key = post_data.get("category", "SKATE").upper()
    topic_type = post_data.get("topic_type", "GENERAL").upper()
    title = post_data.get("title", "").replace('"', '\\"')
    subtitle = post_data.get("subtitle", "").replace('"', '\\"')
    gear_kw = post_data.get("gear_keyword", "extreme sports gear")
    clean_slug = re.sub(r'[^a-zA-Z0-9]', '_', post_data.get("city_tag", "global").lower())[:15]
    
    posts_dir = os.path.join("src", "content", "posts")
    os.makedirs(posts_dir, exist_ok=True)
    filename = f"{timestamp}_{category_key.lower()}_{clean_slug}.md"
    filepath = os.path.join(posts_dir, filename)

    # 組合 YAML Frontmatter
    frontmatter_dict = {
        "title": title,
        "subtitle": subtitle,
        "date": datetime.now().isoformat(),
        "category": category_key if category_key in ["SKATE", "BMX", "SURF", "CLIMB", "SNOW", "EVENT", "SPOT", "ATHLETE", "SAFETY", "TRICKS"] else "SKATE",
        "topic_type": topic_type if topic_type in ["EVENT", "SPOT", "ATHLETE", "SAFETY", "RECORD", "TIPS", "GEAR", "GENERAL"] else "GENERAL",
        "cover_image": image_url,
        "cover_image_source": source_label,
        "author": "Una (@Una_next)",
        "city_tag": post_data.get("city_tag", "GLOBAL"),
        "featured": True,
        "gear_keyword": gear_kw
    }

    if post_data.get("youtube_video_id"):
        frontmatter_dict["youtube_video_id"] = post_data["youtube_video_id"]
        frontmatter_dict["youtube_video_title"] = post_data.get("youtube_video_title", "官方精彩精華")

    if post_data.get("expert_info") and post_data["expert_info"].get("name"):
        frontmatter_dict["expert_info"] = post_data["expert_info"]

    if post_data.get("spot_info") and post_data["spot_info"].get("name"):
        frontmatter_dict["spot_info"] = post_data["spot_info"]

    if post_data.get("event_info") and post_data["event_info"].get("event_name"):
        frontmatter_dict["event_info"] = post_data["event_info"]

    if post_data.get("trick_info") and post_data["trick_info"].get("trick_name"):
        frontmatter_dict["trick_info"] = post_data["trick_info"]

    if post_data.get("safety_gear_info") and post_data["safety_gear_info"].get("gear_type"):
        frontmatter_dict["safety_gear_info"] = post_data["safety_gear_info"]

    # Affiliate Product Object
    amazon_search_url = f"https://www.amazon.com/s?k={quote(gear_kw)}&tag={AMAZON_AFFILIATE_ID}"
    frontmatter_dict["affiliate_products"] = [
        {
            "title": post_data.get("recommended_gear_title", f"{gear_kw.title()} 專業裝備"),
            "subtitle": "Amazon 官方直送・全球職業選手信賴",
            "search_term": gear_kw,
            "amazon_url": amazon_search_url,
            "recommended_for": post_data.get("recommended_gear_reason", "日常訓練與賽事高強度防護必備"),
            "badge_text": "Una 編輯推薦"
        }
    ]

    # 格式化 YAML Frontmatter
    yaml_lines = ["---"]
    for k, v in frontmatter_dict.items():
        if isinstance(v, (dict, list)):
            json_str = json.dumps(v, ensure_ascii=False)
            # 轉換為標準 YAML 物件結構
            yaml_lines.append(f"{k}: {json_str}")
        elif isinstance(v, bool):
            yaml_lines.append(f"{k}: {'true' if v else 'false'}")
        else:
            yaml_lines.append(f"{k}: \"{v}\"")
    yaml_lines.append("---")
    yaml_lines.append("")
    yaml_lines.append(f"![{title}]({image_url})")
    yaml_lines.append("")
    yaml_lines.append(post_data.get("content", ""))

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(yaml_lines))
    print(f"📝 Astro Markdown 文章已生成: {filepath}")
    return filepath

# ==========================================
# 9. TELEGRAM DISPATCHER
# ==========================================
def clean_markdown_for_telegram(text):
    parts = re.split(r'(https?://[^\s\)]+)', text)
    for i in range(0, len(parts), 2):
        parts[i] = parts[i].replace("_", " ")
        if parts[i].count("*") % 2 != 0:
            parts[i] = parts[i].replace("*", "")
    return "".join(parts)

def send_telegram_post(caption_text, image_path=None):
    bot_token = clean_token_or_url(os.getenv("TELEGRAM_BOT_TOKEN", ""))
    chat_id = clean_token_or_url(os.getenv("TELEGRAM_CHAT_ID", ""))

    if not bot_token or not chat_id:
        print("⚠️ 未設定 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID，跳過社群推播。")
        return

    clean_caption = clean_markdown_for_telegram(caption_text)

    def make_tg_request(parse_mode="Markdown"):
        if image_path and os.path.exists(image_path):
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            payload = {"chat_id": chat_id, "caption": clean_caption}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            with open(image_path, "rb") as photo:
                return requests.post(url, data=payload, files={"photo": photo}, timeout=15)
        else:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
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

        print(f"⚠️ Telegram 第一次發送失敗: {res_json.get('description', '')}，嘗試純文字模式...")
        fallback_res = make_tg_request(parse_mode=None)
        if fallback_res.json().get("ok"):
            print("✅ Telegram (純文字模式) 發送成功！")
    except Exception as e:
        print(f"❌ Telegram 發送異常: {e}")

# ==========================================
# 10. MAIN ASYNC PIPELINE
# ==========================================
async def main_async():
    print("🚀 啟動 xGame Radar Magazine 全自動化發布引擎...")
    init_db()

    category_arg = sys.argv[1] if len(sys.argv) > 1 else ""
    lang_arg = sys.argv[2] if len(sys.argv) > 2 else "zh-hk"
    topic_arg = sys.argv[3] if len(sys.argv) > 3 else ""

    category = category_arg.strip().upper() if category_arg and category_arg.upper() != "AUTO" else random.choice(list(XGAME_CATEGORIES.keys()))

    # 1. AI 內容與結構化資料生成
    post_data = generate_xgame_content(category_key=category, topic_type=topic_arg, target_lang=lang_arg)
    title = post_data.get("title", f"{category} 極限特刊")
    subtitle = post_data.get("subtitle", "")
    content = post_data.get("content", "")
    city_tag = post_data.get("city_tag", "GLOBAL")
    gear_kw = post_data.get("gear_keyword", "extreme sports gear")
    topic_type = post_data.get("topic_type", "GENERAL")

    if is_already_posted(title):
        now_time = datetime.now().strftime("%H:%M")
        print(f"ℹ️ 偵測到文章 [{title}] 今日已存在於資料庫，自動為新專題附加獨立刊號以確保發布...")
        title = f"{title} (Vol. {now_time})"
        post_data["title"] = title

    # 2. 分流處理：提取 Telegram 短訊精華與網站長篇深度內容
    tg_caption = post_data.get("telegram_caption") or post_data.get("content", "")
    web_content = post_data.get("website_full_content") or post_data.get("content", "")

    # 計算網站文章專屬 URL
    today_date_str = datetime.now().strftime("%Y-%m-%d")
    clean_slug = re.sub(r'[^a-zA-Z0-9]', '_', city_tag.lower())[:15]
    post_slug = f"{today_date_str}_{category.lower()}_{clean_slug}"
    post_web_url = f"https://unanext.fans/posts/{post_slug}/"
    amazon_search_url = f"https://www.amazon.com/s?k={quote(gear_kw)}&tag={AMAZON_AFFILIATE_ID}"

    # 網站文章內容：注入 Amazon Affiliate
    monetized_web_content = attach_affiliate_link(web_content, gear_kw, category)
    post_data["category"] = category
    post_data["content"] = monetized_web_content

    # 確保每篇文章都擁有 100% 官方可外嵌播放的 YouTube 精華
    if not post_data.get("youtube_video_id"):
        yt_id, yt_title = search_embeddable_youtube_video(title, category)
        post_data["youtube_video_id"] = yt_id
        post_data["youtube_video_title"] = yt_title

    # 3. 官方圖片或精準運動項目高解析度相片（杜絕披薩與植物）
    official_img = post_data.get("official_cover_image")
    source_label = "Official Source" if official_img else "Editorial / Action Sports"
    bg_image = official_img if official_img else get_action_sports_image(f"{category.lower()} action sports", category)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    card_filename = f"xgame_{timestamp}.png"

    # 4. Playwright 生成 1080x1080 社群卡片
    await render_card_image_async(title, subtitle, city_tag, bg_image, card_filename)

    # 5. 上傳卡片圖片至 Cloudflare R2
    r2_img_url = upload_to_r2(card_filename, f"cards/{card_filename}")
    img_link_for_record = r2_img_url if r2_img_url else bg_image

    # 6. 生成並上傳 JSON 備份至 Cloudflare R2
    json_filename = f"{timestamp}_{category}.json"
    backup_payload = {
        "id": timestamp,
        "title": title,
        "subtitle": subtitle,
        "category": category,
        "topic_type": topic_type,
        "content": monetized_web_content,
        "telegram_caption": tg_caption,
        "image_url": img_link_for_record,
        "created_at": datetime.now().isoformat(),
        "author": "Una (@Una_next)"
    }
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(backup_payload, f, ensure_ascii=False, indent=2)
    upload_to_r2(json_filename, f"posts/{json_filename}")

    # 7. 儲存至 Astro 靜態網站 (src/content/posts/) -> 存入長篇深度完整專題
    save_post_as_markdown(post_data, img_link_for_record, source_label)

    # 8. 推送至 Telegram 頻道 -> 發布簡明熱血重點 + 裝備直送 + 直達網站全文連結
    tg_message = (
        f"🏆 *{title}*\n"
        f"⚡ _{subtitle}_\n\n"
        f"{tg_caption}\n\n"
        f"🛒 *Una 裝備推薦*:\n"
        f"👉 [{gear_kw.title()} Amazon 直送門市]({amazon_search_url})\n\n"
        f"🌐 *閱讀完整深度專題與 4K 影片*:\n"
        f"👉 [點擊直達 xGame Magazine 官方專題]({post_web_url})\n\n"
        f"#xGameRadar #{category} #Una_next"
    )
    send_telegram_post(tg_message, image_path=card_filename)

    # 9. 記錄於 SQLite 並清理暫存檔
    record_posted_article(title, category, topic_type)

    if os.path.exists(card_filename):
        os.remove(card_filename)
    if os.path.exists(json_filename):
        os.remove(json_filename)

    print("🎉 xGame Radar Magazine 今日自動化發布與網站文章生成圓滿完成！")

if __name__ == "__main__":
    asyncio.run(main_async())
