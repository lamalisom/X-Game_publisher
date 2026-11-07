import os, sys, re

# ========================================================
# Google E-E-A-T 與 People-First 內容標準規範 (用於注入 Prompt)
# ========================================================
eeat_guidelines = """【Google E-E-A-T 與「以使用者為優先 (People-First)」內容品質核心標準】：
1. 原創深度與實質價值（Substantial & Practical）：
   - 拒絕空泛公關套話！必須提供讀者真正需要的「實用乾貨」（如新手避坑指南、裝備挑選具體參數、動作發力要領、浪型潮汐、雪場纜車與雪道特性）。
   - 讀者讀完後能獲得完整解答與實戰指引，無需再返回 Google 重新搜尋。
2. 事實準確性與專業度（Expertise & Trustworthiness）：
   - 賽事戰報必須具備 5W1H（官方大賽正式全名、舉辦城市、關鍵選手全名與官方成績、決勝動作招式名稱）。
   - 據點介紹必須詳實描述真實地形、設施規格（如混凝土平整度、拋台規格、浪型特點），嚴禁跨項目術語混淆。
3. 內容透明度（Who, How, Why）：
   - 由 xGame Radar 專業編輯團隊整理，旨在提供客觀、詳實的全球極限賽事實況與器材專業評測。

【任務要求】:"""

# 正確的 save_post_as_markdown 函式頭部（確保變數先賦值，再呼叫標籤函式）
correct_save_func_top = '''def save_post_as_markdown(post_data, image_url, source_label="Official / Editorial"):
    timestamp = datetime.now().strftime("%Y-%m-%d")
    category_key = str(post_data.get("category", "SKATE")).upper()
    topic_type = str(post_data.get("topic_type", "GENERAL")).upper()

    title = sanitize_single_line_text(post_data.get("title", f"{category_key} 特刊"))
    subtitle = sanitize_single_line_text(post_data.get("subtitle", ""))
    city_tag = sanitize_single_line_text(post_data.get("city_tag", "GLOBAL"))

    # 自動在文章末尾附加精準中文標籤列（強化 SEO 長尾詞檢索）
    if "🏷️ **熱門標籤**:" not in post_data.get("content", ""):
        ch_tags = generate_chinese_hashtags(category_key, topic_type, city_tag, title)
        post_data["content"] = post_data.get("content", "").rstrip() + "\\n\\n---\\n\\n🏷️ **熱門標籤**: " + str(ch_tags) + "\\n"
'''

for target_file in ["spot_publisher.py", "xgame_publisher.py"]:
    if not os.path.exists(target_file):
        continue

    with open(target_file, "r", encoding="utf-8") as f:
        code = f.read()

    # 1. 修復 save_post_as_markdown 的變數賦值順序
    start_idx = code.find('def save_post_as_markdown(')
    if start_idx != -1:
        end_idx = code.find('clean_slug =', start_idx)
        if end_idx != -1:
            code = code[:start_idx] + correct_save_func_top + '    ' + code[end_idx:]

    # 2. 修復 feedparser NoneType 異常
    if "spot_publisher" in target_file:
        code = code.replace(
            "entries = feedparser.parse(",
            "if not feedparser: return []\n    entries = feedparser.parse("
        )

    # 3. 注入 Google 官方 E-E-A-T 與 People-First 指引至 Prompt
    if "【Google E-E-A-T 與「以使用者為優先" not in code and "【任務要求】:" in code:
        code = code.replace("【任務要求】:", eeat_guidelines, 1)

    compile(code, target_file, "exec")
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"✅ 成功修復 {target_file}（解決 UnboundLocalError、RSS 異常並注入 Google E-E-A-T 規範）！")

print("🎯 全部修正與語法校驗 100% 通過！")
