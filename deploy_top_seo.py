import os, re

# ========================================================
# 1. 建立頂級標準的 public/robots.txt
# ========================================================
os.makedirs("public", exist_ok=True)
robots_content = """User-agent: *
Allow: /

# 禁止爬取後台或內部檔案
Disallow: /api/
Disallow: /admin/
Disallow: /scratch/

# Google 與各大搜尋引擎 Sitemap 索引入口
Sitemap: https://unanext.fans/sitemap-index.xml
Sitemap: https://unanext.fans/sitemap-0.xml
"""

with open("public/robots.txt", "w", encoding="utf-8") as f:
    f.write(robots_content.strip() + "\n")
print("✅ 1. 成功部署 public/robots.txt（已配置權限與 Sitemap 錨點）！")

# ========================================================
# 2. 在 src/layouts/Layout.astro 注入 Google 官方 Schema.org 結構化資料
# ========================================================
layout_path = "src/layouts/Layout.astro"
if os.path.exists(layout_path):
    with open(layout_path, "r", encoding="utf-8") as f:
        content = f.read()

    schema_ld = """
    <!-- 🚀 Google Schema.org 結構化資料 (Rich Snippets & Topical Authority) -->
    <script type="application/ld+json" is:inline>
    {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "WebSite",
          "@id": "https://unanext.fans/#website",
          "url": "https://unanext.fans/",
          "name": "xGame Radar Magazine",
          "description": "全球極限運動雷達、賽事戰報、裝備指南與 3,400+ 熱點地圖",
          "publisher": {
            "@id": "https://unanext.fans/#organization"
          },
          "inLanguage": "zh-HK"
        },
        {
          "@type": "Organization",
          "@id": "https://unanext.fans/#organization",
          "name": "xGame Radar Magazine 專業編輯部",
          "url": "https://unanext.fans/",
          "logo": {
            "@type": "ImageObject",
            "url": "https://unanext.fans/favicon.svg"
          }
        }
      ]
    }
    </script>
"""

    if "@type\": \"WebSite\"" not in content:
        # 插入在 </head> 結束標籤前
        content = content.replace("</head>", schema_ld.strip() + "\n  </head>", 1)
        with open(layout_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("✅ 2. 成功在全站 Layout 注入 Google Schema.org 結構化標籤！")
    else:
        print("ℹ️ 2. Schema.org 結構化資料已存在。")

print("🎯 優良 SEO 核心架構部署完成！")
