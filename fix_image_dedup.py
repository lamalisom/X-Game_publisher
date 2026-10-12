with open('xgame_publisher.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 升級 init_db 加入 used_photos 資料表
new_init_db = '''def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posted_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE,
            category TEXT,
            topic_type TEXT,
            posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS used_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id TEXT UNIQUE,
            photo_url TEXT,
            category TEXT,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
'''

s_init = content.find('def init_db():')
e_init = content.find('def is_already_posted(')
if s_init != -1 and e_init != -1:
    content = content[:s_init] + new_init_db + '\n' + content[e_init:]

# 2. 升級 get_action_sports_image 支援多候選池與歷史去重過濾
new_img_fetcher = '''def get_used_photos_set():
    """從資料庫與 Markdown 檔案中收集所有已使用過的照片 URL / ID"""
    used = set()
    # 1. 從 SQLite 讀取
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT photo_id, photo_url FROM used_photos")
        for pid, purl in cursor.fetchall():
            if pid: used.add(str(pid))
            if purl: used.add(purl)
        conn.close()
    except Exception as e:
        print(f"⚠️ 讀取 used_photos 失敗: {e}")

    # 2. 從 posts 目錄掃描
    import glob
    for md_file in glob.glob("src/content/posts/*.md"):
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                txt = f.read()
                for line in txt.splitlines():
                    if line.startswith("cover_image:"):
                        val = line.split("cover_image:", 1)[1].strip().strip('\"').strip("\'")
                        if val: used.add(val)
                    elif "![" in line and "](<" in line:
                        m_url = line.split("](", 1>)[1].split(")", 1)[0].strip()
                        if m_url.startswith("http"): used.add(m_url)
        except Exception:
            pass
    return used

def record_used_photo(photo_id, photo_url, category):
    """記錄已使用的照片"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO used_photos (photo_id, photo_url, category) VALUES (?, ?, ?)", (str(photo_id), photo_url, category))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ 記錄照片失敗: {e}")

def get_action_sports_image(keyword, category_key="SKATE"):
    cat = category_key.upper() if category_key else "SKATE"
    used_photos = get_used_photos_set()
    print(f"🛡️ 目前已使用過的照片資料庫：共 {len(used_photos)} 張，將自動排除重複。")

    pexels_key = clean_token_or_url(os.getenv("PEXELS_API_KEY", ""))
    if pexels_key:
        try:
            headers = {"Authorization": pexels_key}
            search_queries = [
                f"{cat.lower()} action sports {keyword}".strip(),
                f"{cat.lower()} extreme sports professional",
                f"{cat.lower()} competition athlete",
                f"{cat.lower()} trick outdoor",
            ]
            
            for query in search_queries:
                clean_keyword = quote(query)
                # 抓取 20 張候選照片以供去重篩選
                url = f"https://api.pexels.com/v1/search?query={clean_keyword}&per_page=20&orientation=landscape"
                res = requests.get(url, headers=headers, timeout=10).json()
                
                if res.get("photos"):
                    for photo in res["photos"]:
                        pid = str(photo.get("id"))
                        img_url = extract_clean_url(photo["src"]["large2x"])
                        
                        # 檢查照片 ID 與 URL 是否曾被使用
                        if pid not in used_photos and img_url not in used_photos:
                            record_used_photo(pid, img_url, cat)
                            print(f"✅ Pexels 成功選中【{cat}】全新未重複相片 (ID: {pid}): {img_url}")
                            return img_url
                        else:
                            print(f"⏩ 略過已重複相片 (ID: {pid})")
        except Exception as e:
            print(f"⚠️ Pexels 搜尋異常: {e}")

    # 備用高品質動態相片庫
    fallback_pool = CATEGORY_ACTION_IMAGES.get(cat, CATEGORY_ACTION_IMAGES.get("SKATE", []))
    for fb_url in fallback_pool:
        if fb_url not in used_photos:
            record_used_photo(fb_url, fb_url, cat)
            print(f"📸 選用【{cat}】未重複備用相片: {fb_url}")
            return fb_url

    # 若備用庫全部用過，使用動態亂數種子生成唯一定製圖
    random_seed = int(time.time())
    dynamic_url = f"https://images.unsplash.com/photo-1516762689617-e1cffcef479d?auto=format&fit=crop&w=1200&q=80&sig={random_seed}"
    record_used_photo(str(random_seed), dynamic_url, cat)
    return dynamic_url
'''

s_img = content.find('def get_action_sports_image(')
e_img = content.find('async def render_card_image_async(')
if s_img != -1 and e_img != -1:
    content = content[:s_img] + new_img_fetcher + '\n' + content[e_img:]

with open('xgame_publisher.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ 成功升級 xgame_publisher.py 照片防重複機制！")
