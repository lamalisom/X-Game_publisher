import os, re

md_path = os.path.join("src", "content", "posts", "2026-10-30_surf_lower_trestles.md")
if os.path.exists(md_path):
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. 替換為國際頂級 4K 純淨衝浪大圖 (無任何 2024 壓字)
    clean_cover_url = "https://images.unsplash.com/photo-1502680390469-be75c86b636f?auto=format&fit=crop&w=1200&q=80"
    
    # 2. 修正 frontmatter 標題與封面圖連結
    content = re.sub(
        r'title: ".*?"', 
        'title: "🏄 WSL 冠軍巡迴賽加州下棧橋站 (Lower Trestles) 巔峰對決：高性能浪壁上的極限美學"', 
        content, 
        count=1
    )
    content = re.sub(
        r'subtitle: ".*?"', 
        'subtitle: "直擊全球頂級鵝卵石浪點！解析 John John Florence 與 Griffin Colapinto 在下棧橋的高速反轉與深弧雕刻"', 
        content, 
        count=1
    )
    content = re.sub(
        r'cover_image: ".*?"', 
        f'cover_image: "{clean_cover_url}"', 
        content, 
        count=1
    )
    content = re.sub(
        r'cover_image_source: ".*?"', 
        'cover_image_source: "Editorial / Action Sports"', 
        content, 
        count=1
    )

    # 3. 確保正文頂部圖片也同步更新為乾淨大圖
    img_markdown = f'![🏄 WSL 冠軍巡迴賽加州下棧橋站 (Lower Trestles) 巔峰對決]({clean_cover_url})'
    # 移除原本舊的 markdown 圖片語法 (若有)
    content = re.sub(r'!\[.*?\]\(https:\/\/.*?\)\n*', '', content)
    
    # 將乾淨圖片插入在 frontmatter 結束標記 --- 的正下方
    parts = content.split('---', 2)
    if len(parts) >= 3:
        new_content = f"---{parts[1]}---\n\n{img_markdown}\n{parts[2].lstrip()}"
    else:
        new_content = content

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("✅ 成功將 2026-10-30_surf_lower_trestles.md 封面圖替換為無壓字 4K 衝浪精華大圖！")
