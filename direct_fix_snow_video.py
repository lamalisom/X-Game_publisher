import os, glob

# 找到目標文章
target_file = "src/content/posts/2026-11-02_snow_snow_news.md"

if not os.path.exists(target_file):
    # 若檔名有微小差異，自動搜尋 2026-11-02 的 snow 文章
    matches = glob.glob("src/content/posts/2026-11-02*snow*.md")
    if matches:
        target_file = matches[0]

print(f"🔍 鎖定文章檔案: {target_file}")

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

# 官方 100% 驗證的 FIS 單板滑雪大跳台世界盃決賽精華
new_vid = "z1diZ6aemag"
new_title = "FIS Snowboard World Cup Big Air Season Opener Official Highlights"

# 1. 直接替換錯誤的影片 ID
if "_b-KoFvWuvc" in content:
    content = content.replace("_b-KoFvWuvc", new_vid)
    print("✅ 成功將錯誤的 ID [_b-KoFvWuvc] 替換為 [z1diZ6aemag]！")
else:
    # 若有其他不相關 ID，直接確保 iframe 和 frontmatter 使用正確的官方影片
    import re
    content = re.sub(r'youtube_video_id:\s*["\'][^"\']*["\']', f'youtube_video_id: "{new_vid}"', content)
    content = re.sub(r'youtube_video_title:\s*["\'][^"\']*["\']', f'youtube_video_title: "{new_title}"', content)
    content = re.sub(
        r'<iframe[^>]*src="https://www.youtube.com/embed/[^"]*"[^>]*></iframe>',
        f'<iframe width="100%" height="450" src="https://www.youtube.com/embed/{new_vid}" frameborder="0" allowfullscreen></iframe>',
        content
    )
    print("✅ 已強制更新 iframe 與 frontmatter 為 FIS 官方世界盃影片！")

# 2. 寫回檔案
with open(target_file, "w", encoding="utf-8") as f:
    f.write(content)

# 3. 雙重驗證
with open(target_file, "r", encoding="utf-8") as f:
    check_text = f.read()
    if new_vid in check_text:
        print(f"🎯 驗證成功！檔案中已確認包含官方影片 ID: {new_vid}")
    else:
        print("⚠️ 警告：替換未生效，請檢查檔案權限。")
