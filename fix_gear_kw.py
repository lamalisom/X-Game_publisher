import os, sys, re

correct_top = '''def save_post_as_markdown(post_data, image_url, source_label="Official / Editorial"):
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
        post_data["content"] = post_data.get("content", "").rstrip() + "\\n\\n---\\n\\n🏷️ **熱門標籤**: " + str(ch_tags) + "\\n"
'''

for target_file in ["spot_publisher.py", "xgame_publisher.py"]:
    if not os.path.exists(target_file):
        continue

    with open(target_file, "r", encoding="utf-8") as f:
        code = f.read()

    start_idx = code.find('def save_post_as_markdown(')
    if start_idx != -1:
        end_idx = code.find('clean_slug =', start_idx)
        if end_idx != -1:
            code = code[:start_idx] + correct_top + '    ' + code[end_idx:]

    compile(code, target_file, "exec")
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"✅ 成功修復 {target_file}（補齊 gear_kw 變數，語法編譯 100% 通過）！")

print("🎯 全部檔案修復與語法校驗完成！")
