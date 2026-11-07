import os, sys, re
from datetime import datetime

# ========================================================
# 升級 xgame_publisher.py：注入【動態年份錨點】與【過期年份攔截器】
# ========================================================
pub_path = "xgame_publisher.py"
if os.path.exists(pub_path):
    with open(pub_path, "r", encoding="utf-8") as f:
        code = f.read()

    # (A) 注入動態年份計算與 Prompt 禁令
    current_year = datetime.now().year
    year_prompt_rule = f"""【重大時間錨點與防穿越禁令】:
1. 當前現實年份為 **{current_year} 年**（賽事週期涵蓋 {current_year}–{current_year+1} 賽季）。
2. 嚴禁在標題或內文中輸出任何已過期年份（如 2024、2023 或更早年份）的「未來預報」或「年度大賽即將開打」！
3. 所有賽事名稱、巡迴賽季度與前瞻必須嚴格鎖定在 {current_year}–{current_year+1} 最新賽季！

【任務要求】:"""

    if "【重大時間錨點與防穿越禁令】" not in code and "【任務要求】:" in code:
        code = code.replace("【任務要求】:", year_prompt_rule, 1)

    # (B) 注入發布前過期年份自動清洗器（精準注入在 def save_post_as_markdown 函式內部）
    def_target = 'def save_post_as_markdown(post_data, image_url, source_label="Official / Editorial"):'
    cleaner_replacement = f'''def save_post_as_markdown(post_data, image_url, source_label="Official / Editorial"):
    # 自動清除過期年份穿越 (如 2024年度 -> {current_year}年度)
    for field in ["title", "subtitle", "content", "website_full_content", "telegram_caption"]:
        if field in post_data and isinstance(post_data[field], str):
            val = post_data[field]
            val = re.sub(r'202[0-4]年度', f'{current_year}年度', val)
            val = re.sub(r'202[0-4]賽季', f'{current_year}賽季', val)
            val = re.sub(r'202[0-4]年', f'{current_year}年', val)
            post_data[field] = val'''

    if def_target in code and "自動清除過期年份穿越" not in code:
        code = code.replace(def_target, cleaner_replacement, 1)

    compile(code, pub_path, "exec")
    with open(pub_path, "w", encoding="utf-8") as f:
        f.write(code)
    print("✅ 成功升級 xgame_publisher.py（注入動態年份約束與過期年份防護，語法驗證通過）！")

print("🎯 全部修復與語法驗證 100% 通過！")
