# 🛹 xGame Radar Magazine & Automated Publisher

> 全球極限運動前線雷達！由 AI 引擎與極限運動主編 Una (@Una_next) 共同維護的現代極速雜誌網站與 Telegram 自動化推播系統。

---

## 🌟 核心功能特色 (Features)

1. **🚀 極速現代雜誌網站 (Astro 4.x + Tailwind CSS)**:
   - **`index.astro` 雜誌風格首頁**：Hero 大圖輪播、未來 3-12 個月賽事雷達倒數、焦點人物、全球場地導覽、花式技巧庫與精選裝備。
   - **`today.astro` IG Link in Bio 落地頁**：手機端極致優化，發光動態按鈕一鍵加入 Telegram 頻道與今日特選推薦。
   - **`[category].astro` 分類專題頁**：`/skate`, `/bmx`, `/surf`, `/climb`, `/snow`, `/events`, `/spots`, `/athletes`, `/tricks`, `/safety`。
   - **`posts/[slug].astro` 深度文章內頁**：含賽事頒獎台、場地規格、選手專用裝備、技巧難度星級、官方 16:9 YouTube 影片內嵌、Amazon 聯盟模組與 Google AdSense 廣告容器。
   - **`rss.xml.ts`**：全站 RSS 2.0 Feed 自動輸出。

2. **📸 官方媒體與影片抓取 (Official Media & Video Embeds)**:
   - 爬蟲自動從官方 RSS 與大會官網解析 `<meta property="og:image">` 高清大圖與 YouTube 官方賽事精華影片 ID。
   - 自動備份至 Cloudflare R2，防止防盜鏈 (403 Hotlink Protection) 破圖。

3. **🤖 每日自動化發布核心 (`xgame_publisher.py`)**:
   - **五大支柱專題輪播**（未來賽事、場地導覽、焦點人物、安全裝備評測、賽果戰報、技巧教學）。
   - **Playwright 自動渲染 1080x1080 社群卡片**。
   - **Cloudflare R2 雲端儲存**（圖片卡片 + JSON 備份）。
   - **Telegram 頻道圖文極速推播**（`@Una_next`）。
   - **SQLite 資料庫防重複發布** (`xgame_radar.db`)。
   - **自動產生 Astro Markdown** 儲存至 `src/content/posts/`。

4. **⚙️ GitHub Actions 每日自動化工作流 (`.github/workflows/daily_publisher.yml`)**:
   - 每日定時自動執行新聞抓取、AI 生成、Telegram 發布、靜態網站建置並自動 Commit & Push 回儲存庫。

---

## 🛠️ 本機快速啟動 (Local Quick Start)

### 1. 安裝前端依賴並啟動網站
```bash
# 安裝 Node.js 依賴
npm install

# 啟動本機開發伺服器
npm run dev

# 進行靜態網站打包建置 (SSG)
npm run build
```

### 2. 本機執行 Python 自動發布腳本
```bash
# 安裝 Python 依賴
pip install -r requirements.txt
playwright install chromium

# 執行自動發布
python xgame_publisher.py AUTO zh-hk
```

---

## 🔑 環境變數設定 (Environment Variables / GitHub Secrets)

請在 GitHub Repository 的 `Settings > Secrets and variables > Actions` 或本地 `.env` 中設定：

| 環境變數名稱 | 說明 | 範例 / 預設值 |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Google Gemini AI API 金鑰 | `AIzaSy...` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | `123456:ABC-DEF...` |
| `TELEGRAM_CHAT_ID` | Telegram 頻道或群組 ID | `@Una_next` 或 `-100xxxxxx` |
| `AMAZON_AFFILIATE_ID`| Amazon 聯盟行銷代碼 | `kait02bc-20` |
| `PEXELS_API_KEY` | Pexels 高清圖庫 API 金鑰 (選填) | `...` |
| `R2_ACCOUNT_ID` | Cloudflare R2 Account ID (選填) | `...` |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 Access Key ID (選填) | `...` |
| `R2_SECRET_ACCESS_KEY`| Cloudflare R2 Secret Access Key (選填) | `...` |
| `R2_BUCKET_NAME` | Cloudflare R2 Bucket 名稱 | `xgame-radar-media` |
| `R2_PUBLIC_DOMAIN` | Cloudflare R2 自訂公開域名 (選填) | `https://cdn.example.com` |

---

## 📁 專案目錄結構

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
