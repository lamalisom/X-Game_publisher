# 🛹 xGame Radar Magazine & Automated Publisher

> 全球極限運動前線雷達與極限運動 Una (@Una_next) 主編維護現代極速雜誌網站與 Telegram 自動化推播系統。


📁 專案目錄結構

```
├── .github/
│   └── workflows/
│       ├── daily_publisher.yml      # 每日排程自動發布與網站建置
│       ├── repost.yml               # R2 指定文章重發 Telegram
│       └── xgame_publisher.yml      # 原有發布工作流 (相容)
├── src/
│   ├── components/
│   │   ├── Header.astro             # 導航列 (分類、搜尋、Telegram 捷徑)
│   │   ├── Footer.astro             # 頁尾免責聲明、Amazon Affiliate 聲明、RSS
│   │   ├── AffiliateCard.astro      # Amazon 聯盟推薦卡片
│   │   ├── YouTubeEmbed.astro       # 官方 YouTube 16:9 內嵌播放器
│   │   ├── AdSense.astro            # Google AdSense 響應式廣告容器
│   │   ├── EventBadge.astro         # 賽事倒數與狀態標籤
│   │   └── TrickBadge.astro         # 技巧難度星級標籤
│   ├── content/
│   │   ├── config.ts                # Zod 文章結構 Schema
│   │   └── posts/                   # 自動生成 Markdown 文章存放處
│   ├── layouts/
│   │   └── Layout.astro             # 黑潮主題樣板 + SEO Meta
│   └── pages/
│       ├── index.astro              # 雜誌首頁
│       ├── today.astro              # IG Link in Bio 手機落地頁
│       ├── [category].astro         # 分類彙整頁面
│       ├── rss.xml.ts               # RSS 2.0 Feed
│       └── posts/
│           └── [slug].astro         # 深度文章內頁
├── package.json
├── astro.config.mjs
├── tailwind.config.mjs
├── tsconfig.json
├── xgame_publisher.py               # 升級版 Python 發布核心
├── repost_from_r2.py                # R2 重發腳本
└── requirements.txt
```

---
© 2026 xGame Radar Magazine. All rights reserved.
