import os, sys, re

# ========================================================
# 1. 升級 spot_publisher.py：杜絕純數字編號據點與贅詞自介
# ========================================================
pub_path = "spot_publisher.py"
if os.path.exists(pub_path):
    with open(pub_path, "r", encoding="utf-8") as f:
        code = f.read()

    # (A) 增加嚴格的場地校驗函式
    validator = '''def is_real_named_spot(s):
    """嚴格校驗場地名稱，徹底排除無意義純數字編號 (如 Spot #727290408) 與無城市據點"""
    name = str(s.get("name", "")).strip()
    if not name or re.search(r"Spot\\s*#\\d+", name, re.IGNORECASE):
        return False
    if name.lower() in ["unnamed", "skatepark", "skate park", "spot", "global"]:
        return False
    city = str(s.get("city", "")).strip()
    country = str(s.get("country", "")).strip()
    if (not city or city.lower() in ["global", ""]) and (not country or country.lower() in ["global", ""]):
        return False
    return True

'''
    if "def is_real_named_spot(" not in code:
        code = code.replace("def get_daily_featured_spot(", validator + "def get_daily_featured_spot(", 1)

    # (B) 在據點篩選時套用校驗
    code = code.replace(
        'if s.get("category", "").upper() == cat and s.get("name"):',
        'if s.get("category", "").upper() == cat and is_real_named_spot(s):'
    )

    # (C) 注入第一人稱自介口頭禪清潔器（注入於 save_post_as_markdown 函式內部）
    def_anchor = 'def save_post_as_markdown(post_data, image_url, source_label="Official / Editorial"):'
    sanitizer = '''def save_post_as_markdown(post_data, image_url, source_label="Official / Editorial"):
    # 徹底清除第一人稱自介口頭禪與贅詞
    for field in ["content", "website_full_content", "telegram_caption"]:
        if field in post_data and isinstance(post_data[field], str):
            val = post_data[field]
            val = re.sub(r"我是\\s*Una\\s*(?:\\(@Una_next\\)|@Una_next)?[，。、\\s]*", "", val, flags=re.IGNORECASE)
            val = re.sub(r"Una\\s*\\(@Una_next\\)\\s*今日帶嚟嘅", "今日帶大家探索嘅", val, flags=re.IGNORECASE)
            val = re.sub(r"Una\\s*\\(@Una_next\\)\\s*", "", val, flags=re.IGNORECASE)
            post_data[field] = val'''

    if def_anchor in code and "我是\\s*Una" not in code:
        code = code.replace(def_anchor, sanitizer, 1)

    # (D) 在 Prompt 加入嚴格禁令
    old_req = "【任務要求】:"
    new_req = """【任務核心禁令】:
1. 嚴禁在標題或內文中輸出無意義的純數字編號（如 Spot #727290408）。場地必須具備真實名稱與明確所在城市。
2. 嚴禁在內文中出現「我是 Una (@Una_next)」、「Una (@Una_next) 今日帶嚟嘅」等第一人稱自我介紹贅詞，直接以專業極限運動專欄角度切入！

【任務要求】:"""
    if old_req in code and "【任務核心禁令】" not in code:
        code = code.replace(old_req, new_req, 1)

    # 語法校驗並寫入
    compile(code, pub_path, "exec")
    with open(pub_path, "w", encoding="utf-8") as f:
        f.write(code)
    print("✅ 成功升級 spot_publisher.py（過濾純數字據點、清除贅詞自介、強化真實場地檢驗）！")

print("🎯 全部修復與語法驗證通過！")
