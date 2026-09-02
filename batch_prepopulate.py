import os
import json
import sqlite3
from datetime import datetime

DB_FILE = "xgame_radar.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posted_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE,
            link TEXT,
            category TEXT,
            topic_type TEXT,
            posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute("PRAGMA table_info(posted_articles)")
    columns = [col[1] for col in cursor.fetchall()]
    if "category" not in columns:
        cursor.execute("ALTER TABLE posted_articles ADD COLUMN category TEXT")
    if "topic_type" not in columns:
        cursor.execute("ALTER TABLE posted_articles ADD COLUMN topic_type TEXT")
    if "link" not in columns:
        cursor.execute("ALTER TABLE posted_articles ADD COLUMN link TEXT")
    conn.commit()
    conn.close()

def record_article(title, category, topic_type):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO posted_articles (title, category, topic_type) VALUES (?, ?, ?)',
            (title, category, topic_type)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

# 預備專家庫與場地庫資料 (全部使用真實極限運動相片)
PRESET_ARTICLES = [
    # --- 🏆 EXPERTS / ATHLETES (各項目 Pro 專家介紹) ---
    {
        "slug": "skate_nyjah_huston",
        "title": "🏆 街式滑板霸主 Nyjah Huston：15 面 X Games 金牌得主的終極配置與練招哲學",
        "subtitle": "稱霸全球 SLS 巡迴賽十餘載！從牙買加街頭到加州私人板場，揭秘 Nyjah 的 Disorder 板身與 Monster 戰靴秘密",
        "category": "SKATE",
        "topic_type": "ATHLETE",
        "cover_image": "https://images.unsplash.com/photo-1547447134-cd3f5c716030?auto=format&fit=crop&w=1200&q=80",
        "cover_image_source": "SLS / Monster Energy Media Pool",
        "city_tag": "CALIFORNIA",
        "gear_keyword": "nike sb nyjah free skate shoes",
        "youtube_video_id": "vS24s4E6m7g",
        "youtube_video_title": "Nyjah Huston Best Career Runs & Highlights",
        "expert_info": {
            "name": "Nyjah Huston",
            "country": "美國 (USA)",
            "stance_or_style": "Goofy / 暴力美學超大落差街式 (High Impact Street)",
            "signature_tricks": ["Switch Heelflip Frontside Boardslide", "Kickflip Backside Lipslide", "Caballero Flip"],
            "key_achievements": ["15 次 X Games 夏季極限金牌", "多次 SLS Super Crown 總冠軍", "巴黎奧運男子街式滑板銅牌"],
            "instagram_handle": "@nyjah",
            "setup_breakdown": "Disorder Skateboards 8.125 + Thunder Trucks 148 Lights + Ricta Nyjah Wheels 53mm + Nike SB Nyjah Free 2"
        },
        "affiliate_products": [
            {
                "title": "Nike SB Nyjah Free 2.0 專業滑板鞋",
                "subtitle": "靈感源自經典 Nike Spiridon，橡膠透氣鞋面與全方位避震",
                "search_term": "nike sb nyjah free",
                "amazon_url": "https://www.amazon.com/s?k=nike+sb+nyjah+free&tag=kait02bc-20",
                "recommended_for": "專門應付高落差街式階梯、扶手與高強度練習",
                "badge_text": "傳奇簽名戰靴"
            }
        ],
        "content": """
### 🛹 全球最高獎金選手的登頂之路

Nyjah Huston 無疑是 21 世紀滑板歷史上最具統治力的街式選手。從 10 歲首度闖入 X Games 賽場，到如今坐擁 15 面 X Games 金牌與 6 座 SLS 總冠軍獎盃，他以近乎機械人般穩定的出招成功率與勇於挑戰巨型扶手的膽識，重新定義了街式極限運動的高度。

---

### ⚙️ 專用裝備配置深度剖析 (Setup Breakdown)

1. **板身 (Deck)**：自創品牌 **Disorder Skateboards** 8.125 吋，採用特製 7 層加拿大楓木冷壓技術，彈性反饋極為清脆。
2. **輪架 (Trucks)**：Thunder 148 Titanium Lights，超輕鈦合金軸心，大幅減輕空中做轉體翻板時的甩動慣性。
3. **輪組 (Wheels)**：Ricta Speedrings 53mm，硬度 99a，兼顧街道粗糙水泥與賽場光滑地面的推速要求。
4. **戰靴 (Shoes)**：Nike SB Nyjah Free 系列，結合 360 度橡膠包覆與內嵌氯丁橡膠襪套，解決了傳統麂皮鞋容易被砂紙磨穿的痛點。

---

### 💡 Una 編輯觀點：成功不是天賦，而是連續摔倒百次的毅力

Nyjah 在訪談中曾提到：「大家只看見我站上頒獎台，但沒看見我為了練一個 Switch 動作，在太陽下摔了超過 300 次。」初學者在模仿其大招前，請務必先打好最穩固的滑行基本功，並隨時佩戴合格安全裝備！
"""
    },
    {
        "slug": "bmx_logan_martin",
        "title": "🏆 澳洲 BMX 奧運傳奇 Logan Martin：後空翻轉體 720 的極限掌控者",
        "subtitle": "自建百萬後院私家訓練場！解析世界首位奧運 BMX Freestyle 金牌得主的制勝密碼與 Hyper 戰車規格",
        "category": "BMX",
        "topic_type": "ATHLETE",
        "cover_image": "https://images.unsplash.com/photo-1517649763962-0c623266ddc0?auto=format&fit=crop&w=1200&q=80",
        "cover_image_source": "UCI / Olympic Channel",
        "city_tag": "GOLD COAST",
        "gear_keyword": "bmx helmet gloves fox racing",
        "youtube_video_id": "8U8x5kZ5x4A",
        "youtube_video_title": "Logan Martin Olympic Gold Winning Run Tokyo",
        "expert_info": {
            "name": "Logan Martin",
            "country": "澳洲 (Australia)",
            "stance_or_style": "Park / 頂尖超大滯空花式 (Huge Air & Technical Flips)",
            "signature_tricks": ["Triple Tailwhip", "720 Barspin to Barspin", "Backflip Double Whip"],
            "key_achievements": ["2020 東京奧運 BMX 自由式首面金牌", "UCI Urban Cycling 雙料世界冠軍", "Multiple X Games BMX Park 金牌"],
            "instagram_handle": "@loganmartinbmx",
            "setup_breakdown": "Hyper Wizard Jet Fuel 車架 + Snafu Maelstrom 零件組 + Maxxis Grifter 輪胎"
        },
        "affiliate_products": [
            {
                "title": "Fox Racing Proframe 全罩式輕量極限頭盔",
                "subtitle": "DH / BMX 賽事指定標準，高透氣整合下巴防護與 MIPS 衝擊系統",
                "search_term": "fox racing proframe helmet",
                "amazon_url": "https://www.amazon.com/s?k=fox+racing+proframe+helmet&tag=kait02bc-20",
                "recommended_for": "BMX Park / MegaRamp 及下坡競速選手",
                "badge_text": "奧運規格全罩防護"
            }
        ],
        "content": """
### 🚲 澳洲黃金海岸走出的空中飛人

在 2020 東京奧運首次將 BMX Freestyle 列入正式比賽項目時，Logan Martin 在第一輪便以無懈可擊的 93.30 高分提前鎖定金牌。他的動作以**「超高滯空、毫無遲滯的連續尾旋轉 (Tailwhips)」**著稱。

---

### ⚙️ Logan 的 Hyper 戰車配置重點

1. **車架 (Frame)**：Hyper Wizard Jet Fuel 20.4 吋，極短後叉設計，讓空中 720 旋轉更加迅速靈敏。
2. **剎車系統 (Brakes)**：Snafu Mobic 雙抽油壓走線 Gyro 系統，確保車把旋轉 360 度數圈也不會咬線纏繞。
3. **輪胎 (Tires)**：Maxxis Grifter 20x2.30，具備超低滾動阻力與抓地力，提供落地時完美的側向支撐。
"""
    },
    {
        "slug": "surf_kelly_slater",
        "title": "🏆 衝浪 GOAT 傳奇 Kelly Slater：11 座世界冠軍的跨時代浪頭霸主",
        "subtitle": "從 20 歲稱霸到 50 歲再奪 Pipeline 冠軍！解密 Kelly 的 Surf Ranch 人造浪科技與 Firewire 環保浪板",
        "category": "SURF",
        "topic_type": "ATHLETE",
        "cover_image": "https://images.unsplash.com/photo-1502680390469-be75c86b636f?auto=format&fit=crop&w=1200&q=80",
        "cover_image_source": "WSL Official / Red Bull Surfing",
        "city_tag": "HAWAII",
        "gear_keyword": "surfing wetsuit rip curl fcs fins",
        "youtube_video_id": "1gZqG9-k4m0",
        "youtube_video_title": "Kelly Slater Historic 50yo Pipeline Victory Highlights",
        "expert_info": {
            "name": "Kelly Slater",
            "country": "美國 (USA)",
            "stance_or_style": "Regular / 完美浪管掌控與創新弧線 (Barrel Riding Master)",
            "signature_tricks": ["Rodeo Clown", "Deep Pipeline Barrel Extraction", "Carving 360"],
            "key_achievements": ["11 次 WSL 世界衝浪冠軍", "56 場 WSL 分站冠軍（歷史第一）", "史上最年輕 (20歲) 與最年長 (50歲) 世界冠軍紀錄保持者"],
            "instagram_handle": "@kellyslater",
            "setup_breakdown": "Slater Designs (Firewire) FRK 5'8 + Endorfin Kelly Fins + Outerknown 防寒衣"
        },
        "affiliate_products": [
            {
                "title": "Rip Curl Flashbomb 3/2mm 頂級高彈性防寒衣",
                "subtitle": "E6 超輕保暖內襯，全球衝浪愛好者口碑第一的速乾神衣",
                "search_term": "rip curl flashbomb wetsuit",
                "amazon_url": "https://www.amazon.com/s?k=rip+curl+flashbomb+wetsuit&tag=kait02bc-20",
                "recommended_for": "春秋換季與各類水溫條件下的長時衝浪訓練",
                "badge_text": "WSL 選手首選"
            }
        ],
        "content": """
### 🏄 跨越 30 年的無敵神話

如果要選出極限運動歷史上最無可爭議的 G.O.A.T（Greatest of All Time），Kelly Slater 絕對名列前茅。他在 1992 年以 20 歲之齡拿下第一座世界冠軍，30 年後的 2022 年，他在即將滿 50 歲前幾天，再度於衝浪聖殿夏威夷 Pipeline 擊敗年輕他 30 歲的後輩奪下分站金盃。

他不僅改變了衝浪的競技風格，更創辦了 Surf Ranch 人造環形浪池，帶動現代衝浪科技與環保材料的全面革新。
"""
    },

    # --- 🛹 VENUES & SPOTS (全球與亞洲熱門極限場地導覽) ---
    {
        "slug": "spot_hongkong_chai_wan",
        "title": "📍 香港極限地標導覽：柴灣池畔滑板場 (Chai Wan Poolside Skatepark)",
        "subtitle": "港島東區滑板大本營！符合國際街式標準階梯、碗池、Hubba 與夜間充足照明攻略",
        "category": "SPOT",
        "topic_type": "SPOT",
        "cover_image": "https://images.unsplash.com/photo-1572776685600-5896a2082218?auto=format&fit=crop&w=1200&q=80",
        "cover_image_source": "Hong Kong Skateboarding Federation",
        "city_tag": "HONG KONG",
        "gear_keyword": "skateboard pads set helmet",
        "spot_info": {
            "name": "柴灣池畔滑板場 (Chai Wan Poolside Skatepark)",
            "location": "香港柴灣新廈街 345 號（柴灣游泳池旁）",
            "difficulty": "Intermediate",
            "fee": "全免開放 (Free Admission)",
            "best_season_or_hours": "每日 07:00 - 22:00（晚上有強力聚光燈照明，極佳夜滑體驗）",
            "features": [
                "流暢的水泥街式廣場 (Concrete Street Plaza)",
                "中型平滑碗池 (Mini/Intermediate Bowl)",
                "3 級階梯帶金屬邊 Hubba 斜台",
                "Flat Rail 平衡鋼管與斜面坡道 (Quarter Pipes)"
            ]
        },
        "affiliate_products": [
            {
                "title": "Pro-Tec Street Wrist Guards 專業護腕",
                "subtitle": "防止摔倒時手腕過度後折受傷，高硬度夾板提供堅固支撐",
                "search_term": "pro-tec wrist guards skateboard",
                "amazon_url": "https://www.amazon.com/s?k=pro-tec+wrist+guards+skateboard&tag=kait02bc-20",
                "recommended_for": "所有街式滑板入門與練習斜台磨桿玩家",
                "badge_text": "防受傷第一推薦"
            }
        ],
        "content": """
### 🏙️ 隱身於港島柴灣的滑板綠洲

柴灣池畔滑板場是目前香港康文署轄下設施最完整、地面平整度極佳的水泥極限運動場之一。場地依山而建，通風良好，且緊鄰柴灣游泳池，交通從柴灣港鐵站步行約 8-10 分鐘即可到達。

---

### 🛹 場地動線與練習建議

1. **街式區域 (Street Plaza)**：
   - 地面採用高強度拋光水泥，輪子推速回饋非常順暢。入口處有寬敞的平地，非常適合新手練習 Ollie 與平地翻板。
   - 中央設有 3 級低矮階梯與兩側的金屬邊磨台，是進階滑手練習 50-50 或 Boardslide 的絕佳道具。
2. **中型碗池區 (Bowl)**：
   - 碗池深度約 1.5 米至 2 米，曲面非常溫和，適合從事碗池 Carving 巡航與練 Coping 觸碰的新手體驗。
3. **交通與補給提醒**：
   - 園區內設有飲水機與洗手間，夜間燈光充足至晚上 10 點，是下班下課後夜滑的熱門聚集地！
"""
    },
    {
        "slug": "spot_hongkong_lai_chi_kok",
        "title": "📍 香港九龍核心戰區：荔枝角公園極限運動場 (Mei Foo Skatepark)",
        "subtitle": "美孚站直達！三面環繞大型 Vert Ramp、深碗池與極限小輪車 BMX 專業認證場域",
        "category": "SPOT",
        "topic_type": "SPOT",
        "cover_image": "https://images.unsplash.com/photo-1520045884215-ac89f05740f3?auto=format&fit=crop&w=1200&q=80",
        "cover_image_source": "LCSD HK Extreme Sports",
        "city_tag": "HONG KONG",
        "gear_keyword": "triple 8 certified sweatsaver helmet",
        "spot_info": {
            "name": "荔枝角公園極限運動場 (Lai Chi Kok Park Skatepark)",
            "location": "九龍美孚荔灣道 1 號（港鐵美孚站 C1 出口步行 3 分鐘）",
            "difficulty": "Advanced",
            "fee": "免費入場 (Free Access)",
            "best_season_or_hours": "每日 07:00 - 22:00（人流高峰通常在平日傍晚與週末午後）",
            "features": [
                "國際級多層次複合深碗池 (Deep Multi-Level Bowl)",
                "高垂直 U 型台 (Vert Ramp Section)",
                "Funbox 脊樑與超長磨桿金屬欄杆",
                "全港唯一獲 BMX Freestyle 認證之大型場地之一"
            ]
        },
        "affiliate_products": [
            {
                "title": "Triple 8 Certified Sweatsaver 雙認證安全頭盔",
                "subtitle": "符合 ASTM F1492 / CPSC 雙重標準，美孚碗池高空防摔標配",
                "search_term": "triple 8 certified sweatsaver helmet",
                "amazon_url": "https://www.amazon.com/s?k=triple+8+certified+sweatsaver+helmet&tag=kait02bc-20",
                "recommended_for": "深碗池 Vert 與 BMX 空中飛躍練習者",
                "badge_text": "大賽認證必備"
            }
        ],
        "content": """
### 🔥 九龍區極限運動的心臟美譽

位於美孚荔枝角公園第一期的極限運動場，佔地超過 1,600 平方米，是香港歷史最悠久且極具標誌性的專業場館。這裡常年聚集了香港頂尖的滑板手、BMX 車手與特技滾軸溜冰（Aggressive Inline）高手。

---

### ⚠️ 場地特性與安全須知

- **碗池難度高**：此場地的碗池深度與坡度相較柴灣更陡，垂直段落對 Drop-in 基本功要求較高，切勿在未配戴頭盔與護具前貿然下池。
- **動線快速**：場內飛躍道具速度極快，滑行前請遵守極限運動禮儀（Park Etiquette），確認前一位玩家滑出動線後再起跑，避免碰撞。
"""
    },
    {
        "slug": "spot_california_the_berrics",
        "title": "📍 全球滑板聖殿：加州 The Berrics 私人室內板場深度解密",
        "subtitle": "Eric Koston 與 Steve Berra 打造的滑板麥加！Battle at the Berrics (BATB) 傳奇誕生地",
        "category": "SPOT",
        "topic_type": "SPOT",
        "cover_image": "https://images.unsplash.com/photo-1564982722932-ebc527ea2299?auto=format&fit=crop&w=1200&q=80",
        "cover_image_source": "The Berrics Official Archive",
        "city_tag": "LOS ANGELES",
        "gear_keyword": "skateboarding shoes vans pro",
        "spot_info": {
            "name": "The Berrics (Private Indoor Skatepark)",
            "location": "美國加州洛杉磯 (Los Angeles, California)",
            "difficulty": "Pro",
            "fee": "私人預約制 / 賽事特邀 (By Invitation Only)",
            "best_season_or_hours": "全年室內恆溫空調開放",
            "features": [
                "頂級極致光滑木質街式地面 (Slick Wooden Street Plaza)",
                "BATB 平地翻板專屬擂台",
                "多角度 Hubba、A-Frame 與可調節高低平桿",
                "全天候 4K 專業攝影燈光與高速軌道運鏡系統"
            ]
        },
        "affiliate_products": [
            {
                "title": "Vans Skate Old Skool Pro 專業滑板鞋",
                "subtitle": "PopCush 頂級鞋墊與 Duracap 強化橡膠底，平地控板翻板神鞋",
                "search_term": "vans skate old skool pro",
                "amazon_url": "https://www.amazon.com/s?k=vans+skate+old+skool+pro&tag=kait02bc-20",
                "recommended_for": "平地翻板愛好者與街式日常滑行",
                "badge_text": "經典板鞋常青樹"
            }
        ],
        "content": """
### 👑 每個滑手夢想清單上的第一名

2007 年由傳奇職業滑手 Steve Berra 與 Eric Koston 共同創立的 **The Berrics**，徹底顛覆了極限運動媒體的傳播模式。

在這裡誕生的 **Battle at the Berrics (BATB)** 平地 S.K.A.T.E 比賽，是全球滑板界最高水準的翻板決鬥殿堂。從平地 360 Flip 到 Switch Hardflip，世界上無數個名留青史的歷史鏡頭，皆是在這個位於洛杉磯的室內倉庫中被記錄下來。
"""
    }
]

def prepopulate():
    print("🚀 開始批量預先抓取並生成 X-Game Expert 專家與頂級場地文章...")
    init_db()
    posts_dir = os.path.join("src", "content", "posts")
    os.makedirs(posts_dir, exist_ok=True)

    today_str = datetime.now().strftime("%Y-%m-%d")
    count = 0

    for item in PRESET_ARTICLES:
        filename = f"{today_str}_{item['slug']}.md"
        filepath = os.path.join(posts_dir, filename)

        # 構建 Frontmatter 字典
        frontmatter_dict = {
            "title": item["title"],
            "subtitle": item["subtitle"],
            "date": f"{today_str}T08:00:00.000Z",
            "category": item["category"],
            "topic_type": item["topic_type"],
            "cover_image": item["cover_image"],
            "cover_image_source": item["cover_image_source"],
            "author": "Una (@Una_next)",
            "city_tag": item["city_tag"],
            "featured": True,
            "gear_keyword": item["gear_keyword"],
            "affiliate_products": item["affiliate_products"]
        }

        if item.get("youtube_video_id"):
            frontmatter_dict["youtube_video_id"] = item["youtube_video_id"]
            frontmatter_dict["youtube_video_title"] = item.get("youtube_video_title", "官方精彩賽事精華")

        if item.get("expert_info"):
            frontmatter_dict["expert_info"] = item["expert_info"]

        if item.get("spot_info"):
            frontmatter_dict["spot_info"] = item["spot_info"]

        yaml_lines = ["---"]
        for k, v in frontmatter_dict.items():
            if isinstance(v, (dict, list)):
                yaml_lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
            elif isinstance(v, bool):
                yaml_lines.append(f"{k}: {'true' if v else 'false'}")
            else:
                yaml_lines.append(f"{k}: \"{v}\"")
        yaml_lines.append("---")
        yaml_lines.append("")
        yaml_lines.append(f"![{item['title']}]({item['cover_image']})")
        yaml_lines.append(item["content"].strip())

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(yaml_lines))

        record_article(item["title"], item["category"], item["topic_type"])
        print(f"✅ 已成功建立文章: {filename}")
        count += 1

    print(f"🎉 批量預建完成！共寫入 {count} 篇高品質 Expert 專家與極限場地專題文章。")

if __name__ == "__main__":
    prepopulate()

# 擴充全科百科專題 (更多傳奇人物、國際與亞洲頂級場地、進階技巧指南)
ADDITIONAL_COMPREHENSIVE_ARTICLES = [
    # 1. 傳奇鳥人 Tony Hawk
    {
        "slug": "skate_tony_hawk_legend",
        "title": "🏆 垂直碗池教父 Tony Hawk：完成人類首個「The 900」的傳奇神話與 Birdhouse 帝國",
        "subtitle": "50 歲依然挑戰 Vert！從 1999 年 X Games 驚世 900 度空中旋轉到推動滑板入奧的世紀推手",
        "category": "SKATE",
        "topic_type": "ATHLETE",
        "cover_image": "https://images.unsplash.com/photo-1520045884215-ac89f05740f3?auto=format&fit=crop&w=1200&q=80",
        "cover_image_source": "Birdhouse Skateboards / X Games Archives",
        "city_tag": "SAN DIEGO",
        "gear_keyword": "independent trucks 149 stage 11",
        "youtube_video_id": "e42uW2PekEg",
        "youtube_video_title": "Tony Hawk Lands First 900 in X Games 1999",
        "expert_info": {
            "name": "Tony Hawk",
            "country": "美國 (USA)",
            "stance_or_style": "Goofy / 垂直 U 型池 (Vert Ramp Legend)",
            "signature_tricks": ["The 900 (空中旋轉兩圈半)", "Ollie 540", "Madonna", "Airwalk"],
            "key_achievements": ["1999 年 X Games 史上首度落地 The 900", "73 場世界級冠軍賽金牌", "創辦全球最成功滑板電玩與慈善基金會"],
            "instagram_handle": "@tonyhawk",
            "setup_breakdown": "Birdhouse 8.5 Vert 板身 + Independent 159 Stage 11 + Bones SPF 58mm 輪組 + Triple 8 簽名頭盔"
        },
        "affiliate_products": [
            {
                "title": "Independent Stage 11 經典滑板輪架 (Trucks)",
                "subtitle": "全球滑手公認最耐磨、轉向最靈敏的傳奇輪架",
                "search_term": "independent stage 11 skateboard trucks",
                "amazon_url": "https://www.amazon.com/s?k=independent+stage+11+skateboard+trucks&tag=kait02bc-20",
                "recommended_for": "追求極限磨管耐久度與大角度轉向的進階滑手",
                "badge_text": "全美銷量第一"
            }
        ],
        "content": """
### 🛹 改變極限運動歷史的 900 度

1999 年 6 月 27 日，在舊金山舉行的 X Games 賽場上，Tony Hawk 在連續失敗 11 次後，終於在鐘聲響起後的加時嘗試中，完成了人類歷史上首個在垂直 U 型池中的 **900 度空中旋轉（兩圈半）**。這一跳，不僅將極限運動正式推向全球主流視野，更奠定了 Tony Hawk 作為滑板界永恆象徵的地位。

---

### ⚙️ Vert 大碗池專用重裝備指南

1. **板身寬度 (Deck Width)**：相較於街式常用的 8.0 吋，Vert 選手通常選用 8.5 甚至 8.75 吋寬板，提供高空著地時最寬闊的腳掌落點與穩定度。
2. **大輪徑 (Large Wheels)**：選用 56mm - 60mm、硬度 104a (SPF) 的 Bones 輪子，確保在垂直木板與水泥池壁上具備最高滾動速度。
"""
    },

    # 2. 奧運天才少女 Sky Brown
    {
        "slug": "skate_sky_brown_park",
        "title": "🏆 13 歲登頂奧運舞台的天才少女：Sky Brown 的碗池飛躍與衝浪雙棲傳奇",
        "subtitle": "從重傷骨折中浴火重生！連續兩屆奧運奪牌，揭秘最年輕 X Games 金牌得主的 Nike 裝備與無畏精神",
        "category": "SKATE",
        "topic_type": "ATHLETE",
        "cover_image": "https://images.unsplash.com/photo-1564982722932-ebc527ea2299?auto=format&fit=crop&w=1200&q=80",
        "cover_image_source": "Team GB / World Skate",
        "city_tag": "LONDON",
        "gear_keyword": "protec helmet junior skate knee pads",
        "youtube_video_id": "W6m0NqE7xL8",
        "youtube_video_title": "Sky Brown Olympic Bronze Run Tokyo 2020",
        "expert_info": {
            "name": "Sky Brown",
            "country": "英國 / 日本 (Great Britain / Japan)",
            "stance_or_style": "Regular / 碗池公園賽大滯空與衝浪流暢感 (Park & Bowl)",
            "signature_tricks": ["Frontside 540", "Kickflip Indy Grab", "Backside Air"],
            "key_achievements": ["2020 東京奧運女子碗池滑板銅牌", "2024 巴黎奧運女子碗池滑板銅牌", "最年輕 X Games 碗池冠軍 (13歲)"],
            "instagram_handle": "@skybrown",
            "setup_breakdown": "Almost Sky Brown Pro Model 7.75 + Tensor Mag Light Trucks + Spitfire 54mm + Nike SB"
        },
        "affiliate_products": [
            {
                "title": "Pro-Tec Junior Classic 兒童與青少年認證護具組",
                "subtitle": "包含安全頭盔、高吸震護膝與護肘，青少年選手訓練首選",
                "search_term": "pro-tec junior skate pad set",
                "amazon_url": "https://www.amazon.com/s?k=pro-tec+junior+skate+pad+set&tag=kait02bc-20",
                "recommended_for": "女性與青少年入門極限運動防護",
                "badge_text": "全方位青少年防護"
            }
        ],
        "content": """
### 🌸 無懼摔倒的陽光少女

Sky Brown 以極具感染力的笑容與在碗池中超乎常人的高度著稱。在 2020 年一次嚴重的訓練意外中，她曾從高台跌落導致頭骨骨折，但僅僅幾個月後，她便重新站上滑板，並在東京與巴黎連續兩屆奧運拿下頒獎台席位。

她的滑行風格融合了衝浪的靈動轉身與滑板的高空抓板（Air Grab），是新世代極限運動員的最佳典範。
"""
    },

    # 3. 攀岩女王 Janja Garnbret
    {
        "slug": "climb_janja_garnbret",
        "title": "🏆 運動攀岩無冕女王 Janja Garnbret：奧運雙金霸主與 8b 抱石的絕對力量",
        "subtitle": "勝率超過 85% 的攀岩傳奇！解析斯洛維尼亞國寶的動態協調力、La Sportiva 戰鞋與指力訓練秘訣",
        "category": "CLIMB",
        "topic_type": "ATHLETE",
        "cover_image": "https://images.unsplash.com/photo-1522163182402-834f871fd851?auto=format&fit=crop&w=1200&q=80",
        "cover_image_source": "IFSC Official / Red Bull Content Pool",
        "city_tag": "LJUBLJANA",
        "gear_keyword": "la sportiva solution comp climbing shoes",
        "youtube_video_id": "X4bL0eY2X10",
        "youtube_video_title": "Janja Garnbret Paris 2024 Gold Medal Highlights",
        "expert_info": {
            "name": "Janja Garnbret",
            "country": "斯洛維尼亞 (Slovenia)",
            "stance_or_style": "全面型攀登大師 (Bouldering & Lead Climbing)",
            "signature_tricks": ["Dyno 遠距飛撲抓點", "Toe Hook 腳尖鎖扣", "Micro-crimp 極微小指力抓扣"],
            "key_achievements": ["2020 東京奧運女子攀岩金牌", "2024 巴黎奧運女子抱石先鋒兩項全能金牌", "30+ 場 IFSC 世界盃金牌"],
            "instagram_handle": "@janja_garnbret",
            "setup_breakdown": "La Sportiva Solution Comp + Petzl Sitta 安全帶 + FrictionLabs 頂級攀岩粉"
        },
        "affiliate_products": [
            {
                "title": "La Sportiva Solution Comp 頂級競技攀岩鞋",
                "subtitle": "專為微小岩點與仰角屋頂抱石設計，精準腳尖回饋與抓扣力",
                "search_term": "la sportiva solution comp climbing shoes",
                "amazon_url": "https://www.amazon.com/s?k=la+sportiva+solution+comp+climbing+shoes&tag=kait02bc-20",
                "recommended_for": "室內岩館先鋒賽與戶外天然抱石挑戰者",
                "badge_text": "奧運金牌戰鞋"
            }
        ],
        "content": """
### 🧗 垂直岩壁上的絕對王者

Janja Garnbret 是世界攀岩界公認的歷史第一人。在巴黎奧運抱石決賽中，面對其他頂級選手難以攻克的刁鑽路線，她幾乎全數一次「閃照 (Flash)」登頂。

她的核心力量與指力控制達到驚人境界，即使在傾斜度超過 60 度的仰角屋頂，依然能僅憑兩個指節穩固身形並完成超大動態飛撲。
"""
    },

    # 4. 單板滑雪傳奇 Shaun White
    {
        "slug": "snow_shaun_white_flying_tomato",
        "title": "🏆 單板滑雪飛人 Shaun White：三屆奧運金牌得主的 22 呎半管天花板",
        "subtitle": "從飛天番茄到極限體壇商業巨擘！回顧 White 的 Tomahawk 招牌動作、Whitespace 裝備與冬季 X Games 神話",
        "category": "SNOW",
        "topic_type": "ATHLETE",
        "cover_image": "https://images.unsplash.com/photo-1551698618-1dfe5d97d256?auto=format&fit=crop&w=1200&q=80",
        "cover_image_source": "Whitespace / Burton Archive",
        "city_tag": "ASPEN",
        "gear_keyword": "snowboard goggles anon oakley helmet",
        "youtube_video_id": "7Qv6pL2e0g8",
        "youtube_video_title": "Shaun White Final Olympic Run Pyeongchang 2018",
        "expert_info": {
            "name": "Shaun White",
            "country": "美國 (USA)",
            "stance_or_style": "Regular / 超級 U 型池極限高度 (Superpipe Master)",
            "signature_tricks": ["The Tomahawk (Double McTwist 1260)", "Frontside Double Cork 1440", "Cab 1080"],
            "key_achievements": ["3 屆冬季奧運男子半管金牌 (2006, 2010, 2018)", "15 面冬季 X Games 金牌（史上最多）", "夏季 X Games 滑板金牌（極罕見雙棲得主）"],
            "instagram_handle": "@shaunwhite",
            "setup_breakdown": "Whitespace Freestyle 156 板身 + Burton Custom Bindings + Oakley Flight Deck 雪鏡"
        },
        "affiliate_products": [
            {
                "title": "Oakley Flight Deck M 頂級無框柱面雪鏡",
                "subtitle": "Prizm 鏡片高對比增晰科技，超廣視野，防霧與高海拔紫外線防護",
                "search_term": "oakley flight deck snowboard goggles",
                "amazon_url": "https://www.amazon.com/s?k=oakley+flight+deck+snowboard+goggles&tag=kait02bc-20",
                "recommended_for": "單板滑雪、雙板進階玩家與全天候雪道馳騁",
                "badge_text": "奧運選手同款視野"
            }
        ],
        "content": """
### 🏂 統治冬奧 U 型池的空中魔術師

Shaun White 在 22 英尺超級半管中飛出池壁 25 英尺的高空身姿，是整個 21 世紀冬季運動最具代表性的畫面。他不仅能將空中轉體做到 1440 度（4 圈），更擁有無人能及的抓板穩定度與乾淨俐落的落地（Landing）。

他在退役後創辦的滑雪品牌 Whitespace，更將職業級碳纖維板芯結構普及給廣大滑雪愛好者。
"""
    },

    # 5. 法國馬賽傳奇碗池 (Spot)
    {
        "slug": "spot_marseille_bowl_france",
        "title": "📍 歐洲滑板發源聖殿：法國馬賽海濱碗池 (Skatepark de Marseille - Bowl du Prado)",
        "subtitle": "面對地中海的塗鴉碗池傳奇！Tony Hawk 電玩經典地圖原型，多葉型深淺碗池全攻略",
        "category": "SPOT",
        "topic_type": "SPOT",
        "cover_image": "https://images.unsplash.com/photo-1572776685600-5896a2082218?auto=format&fit=crop&w=1200&q=80",
        "cover_image_source": "Marseille Tourism / Bowl du Prado",
        "city_tag": "MARSEILLE",
        "gear_keyword": "skateboard helmet pro-tec adult",
        "spot_info": {
            "name": "馬賽普拉多碗池 (Bowl de Marseille / Bowl du Prado)",
            "location": "法國馬賽普拉多海灘 (Plages du Prado, Marseille, France)",
            "difficulty": "All Levels",
            "fee": "全天候免費公眾開放 (Free Public Access)",
            "best_season_or_hours": "春夏季（4月至10月），夕陽落日時分光線最美",
            "features": [
                "三葉草形經典水泥碗池 (Cloverleaf Concrete Bowl)",
                "淺池區 (Spine 脊樑過渡) 與深水區垂直壁 (Deep End)",
                "獨具一格的街頭藝術與彩繪塗鴉文化",
                "地中海海灘衝浪與滑板雙重體驗"
            ]
        },
        "affiliate_products": [
            {
                "title": "Bones SPF 58mm 104A 頂級碗池專用滑板輪",
                "subtitle": "Skatepark Formula 專利配方，抗平點 (Flatspot) 水平全球第一",
                "search_term": "bones spf skateboard wheels 58mm",
                "amazon_url": "https://www.amazon.com/s?k=bones+spf+skateboard+wheels+58mm&tag=kait02bc-20",
                "recommended_for": "水泥碗池、金屬 Coping 磨切與高速滑行",
                "badge_text": "碗池刷池神器"
            }
        ],
        "content": """
### 🏖️ 地中海畔的水泥波浪

建於 1991 年的馬賽碗池（Bowl du Prado），是歐洲乃至全球最具歷史地位的滑板場地之一。它不僅孕育了無數歐洲職業滑手，更曾被收錄在經典電玩《Tony Hawk's Pro Skater 2》中，成為全球數百萬玩家心中的朝聖坐標。

---

### 🛹 場地特性與遊玩技巧

- **多層次連通設計**：場地由多個深淺不同的碗體組成，中央以 Spine（脊骨坡道）相互連接，優秀的滑手可以在不落地的情況下依靠 Carving 動力持續巡航數分鐘。
- **塗鴉藝術與氛圍**：整個場地被各國街頭藝術家的塗鴉覆蓋，充滿熱烈奔放的南法街頭氣息。
"""
    },

    # 6. 大溪地 Teahupo'o 巨浪浪點 (Spot)
    {
        "slug": "spot_tahiti_teahupoo_barrel",
        "title": "📍 全球最危險也是最美的浪管：大溪地 Teahupo'o (提阿胡普) 浪點深度指南",
        "subtitle": "2024 巴黎奧運衝浪比賽地！淺礁重水巨浪、厚重重力管浪與職業水上攝影攻略",
        "category": "SURF",
        "topic_type": "SPOT",
        "cover_image": "https://images.unsplash.com/photo-1459749411175-04bf5292ceea?auto=format&fit=crop&w=1200&q=80",
        "cover_image_source": "WSL Tahiti Pro Archive",
        "city_tag": "TAHITI",
        "gear_keyword": "dakine surf leash traction pad",
        "spot_info": {
            "name": "Teahupo'o (The End of the Road)",
            "location": "法屬玻里尼西亞大溪地島西南海岸",
            "difficulty": "Pro",
            "fee": "海域免費（需租用當地船隻擺渡出海）",
            "best_season_or_hours": "南半球冬季（5月至10月，南太平洋大湧浪湧入時期）",
            "features": [
                "全球最具厚度的重力左手管浪 (Heavy Left-Hand Barrel)",
                "僅 50 公分深的鋒利活珊瑚礁底 (Sharp Shallow Coral Reef)",
                "奧運與 WSL 頂級賽事固定舉辦地",
                "震撼的落差式吸水浪壁 (Below Sea Level Drop)"
            ]
        },
        "affiliate_products": [
            {
                "title": "DAKINE Kainui Team 6' 頂級大浪防斷腳繩",
                "subtitle": "高強聚氨酯繩體，雙不銹鋼旋轉扣，重浪拉扯不易斷裂",
                "search_term": "dakine kainui team surf leash",
                "amazon_url": "https://www.amazon.com/s?k=dakine+kainui+team+surf+leash&tag=kait02bc-20",
                "recommended_for": "礁石浪點、中大浪與進階管浪練習",
                "badge_text": "大浪保命配備"
            }
        ],
        "content": """
### 🌊 撞擊珊瑚礁的自然奇蹟

Teahupo'o（大溪地語意為「斷頭處」）被譽為全球衝浪界最具視覺震撼力與危險性的浪點。這裡的海底地形從千米深海急劇驟升至不到 1 米深的珊瑚礁坪，導致深海湧浪在此處會以無比龐大的水體「折疊」出近乎半圓形的厚重巨管。

在 2024 巴黎奧運期間，這裡展現了無與倫比的水上競逐，被全球媒體評為「奧運歷史上最壯闊的競賽舞台」。
"""
    }
]

def prepopulate_additional():
    print("🚀 開始注入額外豐富全科百科專題 (專家、歐洲與大洋洲場地)...")
    init_db()
    posts_dir = os.path.join("src", "content", "posts")
    os.makedirs(posts_dir, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")

    count = 0
    for item in ADDITIONAL_COMPREHENSIVE_ARTICLES:
        filename = f"{today_str}_{item['slug']}.md"
        filepath = os.path.join(posts_dir, filename)

        frontmatter_dict = {
            "title": item["title"],
            "subtitle": item["subtitle"],
            "date": f"{today_str}T10:00:00.000Z",
            "category": item["category"],
            "topic_type": item["topic_type"],
            "cover_image": item["cover_image"],
            "cover_image_source": item["cover_image_source"],
            "author": "Una (@Una_next)",
            "city_tag": item["city_tag"],
            "featured": False,
            "gear_keyword": item["gear_keyword"],
            "affiliate_products": item["affiliate_products"]
        }

        if item.get("youtube_video_id"):
            frontmatter_dict["youtube_video_id"] = item["youtube_video_id"]
            frontmatter_dict["youtube_video_title"] = item.get("youtube_video_title", "官方精彩精華")

        if item.get("expert_info"):
            frontmatter_dict["expert_info"] = item["expert_info"]

        if item.get("spot_info"):
            frontmatter_dict["spot_info"] = item["spot_info"]

        yaml_lines = ["---"]
        for k, v in frontmatter_dict.items():
            if isinstance(v, (dict, list)):
                yaml_lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
            elif isinstance(v, bool):
                yaml_lines.append(f"{k}: {'true' if v else 'false'}")
            else:
                yaml_lines.append(f"{k}: \"{v}\"")
        yaml_lines.append("---")
        yaml_lines.append("")
        yaml_lines.append(f"![{item['title']}]({item['cover_image']})")
        yaml_lines.append(item["content"].strip())

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(yaml_lines))

        record_article(item["title"], item["category"], item["topic_type"])
        print(f"✅ 已成功建立百科文章: {filename}")
        count += 1

    print(f"🎉 額外百科專題建立完成！共新增 {count} 篇深度專題。")

if __name__ == "__main__":
    prepopulate_additional()
