import os, sys, re

hashtags_engine = '''def generate_chinese_hashtags(category, topic_type="NEWS", city_tag="", title=""):
    """根據文章項目、主題、城市與標題，自動生成 4-6 個精準高關聯度的中文 Hashtag"""
    cat = str(category).upper() if category else "SKATE"
    top = str(topic_type).upper() if topic_type else "NEWS"
    
    sport_map = {
        "SKATE": ["#滑板", "#極限滑板", "#街式滑板", "#板仔日常"],
        "SURF": ["#衝浪", "#極限衝浪", "#浪人日常", "#浪點推薦"],
        "SNOW": ["#單板滑雪", "#滑雪", "#極限雪上", "#雪季日常"],
        "CLIMB": ["#攀岩", "#抱石", "#極限攀爬", "#岩壁挑戰"],
        "BMX": ["#極限小輪車", "#BMX單車", "#泵道", "#特技單車"]
    }
    
    topic_map = {
        "SPOT": ["#極限探索地圖", "#場地指南", "#據點實測", "#朝聖地標"],
        "EVENT": ["#賽事雷達", "#賽事實況", "#世界盃直擊"],
        "NEWS": ["#最新戰報", "#極限速報", "#即時焦點"],
        "FORECAST": ["#賽事預報", "#賽程時間表", "#日程雷達"],
        "ATHLETE": ["#頂尖選手", "#職業選手"],
        "SAFETY": ["#裝備評測", "#護具指南"],
        "TRICKS": ["#動作分解", "#花式技巧"]
    }

    city_map = {
        "GLOBAL": "#全球極限",
        "HONG KONG": "#香港",
        "TOKYO": "#東京",
        "LOS ANGELES": "#洛杉磯",
        "CALIFORNIA": "#加州",
        "PARIS": "#巴黎",
        "INNSBRUCK": "#因斯布魯克",
        "CHUR": "#瑞士庫爾",
        "YANGYANG": "#韓國襄陽",
        "KOREA": "#韓國",
        "WOLFURT": "#奧地利"
    }

    tags = ["#xGameRadar"]
    tags.extend(sport_map.get(cat, ["#極限運動", f"#{cat}"])[:2])
    tags.extend(topic_map.get(top, ["#極限專題"])[:1])
    
    if city_tag:
        c_clean = str(city_tag).strip().upper()
        if c_clean in city_map:
            tags.append(city_map[c_clean])
        elif len(c_clean) <= 12 and c_clean != "GLOBAL":
            tags.append(f"#{c_clean.title()}")
            
    t_upper = str(title).upper()
    if "X GAMES" in t_upper or "XGAMES" in t_upper:
        tags.append("#XGames")
    elif "WSL" in t_upper:
        tags.append("#WSL衝浪世界盃")
    elif "SLS" in t_upper:
        tags.append("#SLS街式滑板")
    elif "IFSC" in t_upper:
        tags.append("#IFSC攀岩世界盃")
    elif "FIS" in t_upper:
        tags.append("#FIS滑雪世界盃")

    tags.append("#極限運動")
    
    seen = set()
    res = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            res.append(t)
    return " ".join(res[:7])

'''

# ========================================================
# 1. 升級 spot_publisher.py
# ========================================================
if os.path.exists("spot_publisher.py"):
    with open("spot_publisher.py", "r", encoding="utf-8") as f:
        code = f.read()

    if "def generate_chinese_hashtags(" not in code:
        code = hashtags_engine + code

    # (A) 提前計算 ch_tags，避免 f-string 括號內語法衝突
    if 'ch_tags = generate_chinese_hashtags(category, "SPOT", city_tag, title)' not in code:
        code = code.replace(
            '    tg_message = (',
            '    ch_tags = generate_chinese_hashtags(category, "SPOT", city_tag, title)\n    tg_message = (',
            1
        )
    # (B) 替換 Telegram 末尾英文字串
    code = re.sub(
        r'f"#xGameRadar\s*#\{category\}\s*#SpotsMap\s*#Una_next"',
        'f"{ch_tags}"',
        code
    )

    # (C) Markdown 文章末尾自動注入中文標籤列
    bottom_tag = '''
    # 自動在文章末尾附加精準中文標籤列（強化 SEO 長尾詞檢索）
    if "🏷️ **熱門標籤**:" not in post_data.get("content", ""):
        ch_tags = generate_chinese_hashtags(category_key, "SPOT", city_tag, title)
        post_data["content"] = post_data.get("content", "").rstrip() + f"\\n\\n---\\n\\n🏷️ **熱門標籤**: {ch_tags}\\n"
'''
    def_anchor = 'def save_post_as_markdown(post_data, image_url, source_label="Official / Editorial"):'
    if def_anchor in code and "🏷️ **熱門標籤**:" not in code:
        code = code.replace(def_anchor, def_anchor + bottom_tag, 1)

    compile(code, "spot_publisher.py", "exec")
    with open("spot_publisher.py", "w", encoding="utf-8") as f:
        f.write(code)
    print("✅ 1. 成功為 spot_publisher.py 升級中文關聯 Hashtag 引擎！")


# ========================================================
# 2. 升級 xgame_publisher.py
# ========================================================
if os.path.exists("xgame_publisher.py"):
    with open("xgame_publisher.py", "r", encoding="utf-8") as f:
        code = f.read()

    if "def generate_chinese_hashtags(" not in code:
        code = hashtags_engine + code

    # (A) 提前計算 ch_tags
    if 'ch_tags = generate_chinese_hashtags(category, topic_type, city_tag, title)' not in code:
        code = code.replace(
            '    tg_message = f"🔥 *{title}*',
            '    ch_tags = generate_chinese_hashtags(category, topic_type, city_tag, title)\n    tg_message = f"🔥 *{title}*',
            1
        )
    # (B) 替換 Telegram 末尾標籤
    code = re.sub(
        r'tg_message \+= f"\\n#xGameRadar #\{category\.upper\(\)\} #極限運動 #ActionSports"',
        'tg_message += f"\\n{ch_tags}"',
        code
    )

    # (C) Markdown 文章末尾自動注入中文標籤列
    bottom_tag = '''
    # 自動在文章末尾附加精準中文標籤列（強化 SEO 長尾詞檢索）
    if "🏷️ **熱門標籤**:" not in post_data.get("content", ""):
        ch_tags = generate_chinese_hashtags(category_key, topic_type, city_tag, title)
        post_data["content"] = post_data.get("content", "").rstrip() + f"\\n\\n---\\n\\n🏷️ **熱門標籤**: {ch_tags}\\n"
'''
    def_anchor = 'def save_post_as_markdown(post_data, image_url, source_label="Official / Editorial"):'
    if def_anchor in code and "🏷️ **熱門標籤**:" not in code:
        code = code.replace(def_anchor, def_anchor + bottom_tag, 1)

    compile(code, "xgame_publisher.py", "exec")
    with open("xgame_publisher.py", "w", encoding="utf-8") as f:
        f.write(code)
    print("✅ 2. 成功為 xgame_publisher.py 升級中文關聯 Hashtag 引擎！")

print("🎯 兩個腳本均已通過 Python 語法驗證！")
