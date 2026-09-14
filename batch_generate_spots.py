#!/usr/bin/env python3
"""
xGame Spot Batch Generator & Uploader
一次過生成全球與亞洲頂級極限運動場地（滑板場、浪點、岩館/岩場、BMX公園、雪場）完整深度資料
並直接存入 src/content/posts/ 與 SQLite 資料庫
"""

import os
import json
import sqlite3

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

TOP_XGAME_SPOTS = [
    {
        "slug": "spot_hongkong_chai_wan",
        "title": "📍 香港柴灣池畔滑板場：港島東頂級街式斜台與水泥碗池全攻略",
        "subtitle": "港島滑手必朝聖！配備標準金字塔台、雙層大理石 Hubba 與深淺雙碗池設施指南",
        "category": "SKATE",
        "city_tag": "HONG KONG",
        "cover_image": "/images/chai_wan_skatepark.jpg",
        "cover_image_source": "xGame Radar Editorial HK",
        "youtube_video_id": "4YYTNkAdDD8",
        "youtube_video_title": "Hong Kong Chai Wan Skatepark Street & Bowl Session",
        "gear_keyword": "pro-tec wrist guards skateboard",
        "spot_info": {
            "name": "柴灣池畔滑板場 (Chai Wan Skatepark)",
            "location": "香港柴灣新廈街柴灣游泳池旁",
            "difficulty": "All Levels / Intermediate",
            "features": ["深淺雙水泥碗池", "標準街式斜台 (Quarterpipe)", "不銹鋼磨桿與大理石 Hubba", "全場夜間照明夜滑支援"],
            "fee": "免費入場 (公眾康文署場地)"
        },
        "affiliate_products": [{
            "title": "Pro-Tec Street Wrist Guards 專業防摔護腕",
            "subtitle": "防止摔倒時手腕過度後折受傷，高硬度夾板提供堅固支撐",
            "search_term": "pro-tec wrist guards skateboard",
            "amazon_url": "https://www.amazon.com/s?k=pro-tec+wrist+guards+skateboard&tag=kait02bc-20",
            "recommended_for": "所有街式斜台與金屬桿練習滑手",
            "badge_text": "防骨折第一推薦"
        }],
        "content": """### 📍 場地概述與地理優勢

柴灣池畔滑板場座落於港島東柴灣游泳池旁，鄰近柴灣港鐵站，是香港島設施最完整、動線最流暢的公眾水泥極限運動場之一。場地鋪設平整的水泥地面，分為「街式街區（Street Plaza）」與「雙聯碗池區（Coping Bowl）」兩大核心區域。

### 🛹 核心設施與玩法亮點

1. **街式區（Street Plaza）**：設有不同傾角的三面斜台（Quarterpipes）、中型金字塔跳台（Pyramid）、不銹鋼圓磨桿（Round Rail）以及兩側包邊的大理石 Hubba 階梯滑台，適合練習 Ollie、Kickflip 上台及 Boardslide 磨桿動作。
2. **水泥碗池（Concrete Bowl）**：由淺水區（約 1.5 米）與深水區（約 2.2 米）連通組成，邊緣鑲嵌金屬鋼管（Steel Coping），是練習 Carving 刷池、Drop-in 及 50-50 Grind 弧面技巧的絕佳場所。

### 💡 實戰小貼士與交通指引
- **交通方式**：港鐵柴灣站 B 出口步行約 6 分鐘即可直達。
- **最佳時段**：平日上午人流較少；夜間設有強力泛光燈照明，開放至晚上 10 點。"""
    },
    {
        "slug": "spot_hongkong_lai_chi_kok",
        "title": "📍 香港美孚荔枝角公園滑板場：全港最大極限運動場與極速巨型碗池指南",
        "subtitle": "美孚極限聖地！符合國際賽事標準的 Vert 垂直深碗池與極速泵道全解析",
        "category": "SKATE",
        "city_tag": "HONG KONG",
        "cover_image": "/images/lai_chi_kok_park.jpg",
        "cover_image_source": "LCSD HK / Action Sports",
        "youtube_video_id": "bPFuh1AKS-s",
        "youtube_video_title": "Lai Chi Kok Skatepark Vert Bowl Session",
        "gear_keyword": "triple 8 certified sweatsaver helmet",
        "spot_info": {
            "name": "荔枝角公園滑板場 (Mei Foo Skatepark)",
            "location": "香港九龍荔枝角荔灣道1號 (美孚站旁)",
            "difficulty": "Intermediate / Advanced / Pro",
            "features": ["全港最深 Vert 巨型碗池 (2.8米)", "國際賽規格街式大階梯", "Pump Track 連續泵道", "滑板、BMX 及特技滾軸溜冰通用"],
            "fee": "免費入場"
        },
        "affiliate_products": [{
            "title": "Triple 8 Certified Sweatsaver 雙認證安全頭盔",
            "subtitle": "符合 ASTM F1492 / CPSC 雙重標準，美孚深碗池高空防摔標配",
            "search_term": "triple 8 certified sweatsaver helmet",
            "amazon_url": "https://www.amazon.com/s?k=triple+8+certified+sweatsaver+helmet&tag=kait02bc-20",
            "recommended_for": "深碗池 Vert 與高空飛躍練習者",
            "badge_text": "大賽認證必備"
        }],
        "content": """### 📍 場地概述

位於美孚荔枝角公園三期的極限運動場，佔地約 1,600 平方米，是九龍區乃至全香港規模最大、挑戰難度最高的極限運動場地。場地經過國際標準認證，曾多次舉辦全港滑板公開賽與國際極限運動交流賽。

### 🛹 核心設施

1. **Vert 巨型深碗池**：深度達 2.8 米，落差巨大，底部過渡弧度完美，可提供極高加速度，是練習 High Air、Invert 與 540 轉體的終極考驗。
2. **多級街式挑戰台**：包含 4 階與 6 階大落差樓梯、斜向下切磨桿（Handrail）、波浪過渡坡道與 A-Frame 金字塔台。

### 💡 裝備與安全須知
深碗池具備極高速度與高空墜落風險，進入碗池前務必佩戴經 ASTM/CPSC 認證的安全頭盔、護膝及護肘。"""
    },
    {
        "slug": "spot_california_the_berrics",
        "title": "📍 美國加州 The Berrics：全球街式滑板最高殿堂私密室內滑板場探索",
        "subtitle": "Eric Koston 與 Steve Berra 打造的滑板聖地！BATB 傳奇對決誕生地深度導覽",
        "category": "SKATE",
        "city_tag": "CALIFORNIA",
        "cover_image": "/images/the_berrics.jpg",
        "cover_image_source": "The Berrics Media Official",
        "youtube_video_id": "-Lra51BUgEs",
        "youtube_video_title": "Inside The Berrics - Battle at the Berrics Final",
        "gear_keyword": "vans skate old skool pro shoes",
        "spot_info": {
            "name": "The Berrics",
            "location": "洛杉磯 (Los Angeles, California, USA)",
            "difficulty": "Pro / Invitation & Events",
            "features": ["頂級木質平地賽道", "全天候溫控室內極限場", "專業 4K 高速攝影燈光陣列", "經典 BATB 平地翻板對決台"],
            "fee": "特定活動 / 邀請制 / 預約體驗"
        },
        "affiliate_products": [{
            "title": "Vans Skate Old Skool Pro 專業滑板鞋",
            "subtitle": "PopCush 頂級緩震鞋墊與 Duracap 耐磨橡膠底，平地控板翻板神鞋",
            "search_term": "vans skate old skool pro",
            "amazon_url": "https://www.amazon.com/s?k=vans+skate+old+skool+pro&tag=kait02bc-20",
            "recommended_for": "平地翻板愛好者與街式日常滑行",
            "badge_text": "經典板鞋常青樹"
        }],
        "content": """### 📍 傳奇誕生背景

The Berrics 由職業滑板傳奇 Steve Berra 與 Eric Koston 於 2007 年在加州洛杉磯創立。這裡不僅是全球滑板文化的發源地，更誕生了風靡全球的「Battle at the Berrics (BATB)」平地遊戲對決賽事。

### 🛹 場地設計特色
全場採用精密切割的頂級樺木板材鋪設，提供毫釐不差的起跳回彈反饋。場內所有道具（扶手、Hubba、斜坡）均為可微調模組化結構，專為拍攝最極限的滑板影片零件與大賽定制。"""
    },
    {
        "slug": "spot_bondi_bowl_sydney",
        "title": "📍 澳洲悉尼 Bondi Skatepark：南太平洋最美海景碗池與碗池狂歡節聖地",
        "subtitle": "座落於 Bondi Beach 金色沙灘邊的傳奇水泥巨碗！直擊 Bowl-A-Rama 經典賽場",
        "category": "SKATE",
        "city_tag": "SYDNEY",
        "cover_image": "/images/bondi_bowl.jpg",
        "cover_image_source": "Waverley Council / Bondi Skate Media",
        "youtube_video_id": "4YYTNkAdDD8",
        "youtube_video_title": "Bondi Bowl-A-Rama Legend Sessions Tony Hawk & Steve Caballero",
        "gear_keyword": "187 killer pads pro knee pads",
        "spot_info": {
            "name": "Bondi Skatepark (邦代滑板場)",
            "location": "Queen Elizabeth Dr, Bondi Beach, NSW Australia",
            "difficulty": "Intermediate / Advanced / Pro",
            "features": ["10 呎專業大賽級水泥深碗池", "全開放太平洋海景視野", "平滑金屬 Coping 磨切邊", "海邊全天候免費開放"],
            "fee": "完全免費"
        },
        "affiliate_products": [{
            "title": "187 Killer Pads Pro 頂級重裝護膝",
            "subtitle": "全球碗池與 U 槽選手唯一指定護膝，超厚高密度 V-22 雙層海綿",
            "search_term": "187 killer pads pro knee",
            "amazon_url": "https://www.amazon.com/s?k=187+killer+pads+pro+knee&tag=kait02bc-20",
            "recommended_for": "深碗池 Knee Slide 跪滑救命必備",
            "badge_text": "碗池防護天花板"
        }],
        "content": """### 📍 場地概述

座落於全球知名的悉尼邦代海灘（Bondi Beach）旁，Bondi Bowl 是全世界拍照打卡率最高、風景最震撼的極限運動碗池。每年 2 月舉辦的「Bowl-A-Rama」賽事吸引包括 Tony Hawk、Pedro Barros 在內的全球頂級碗池大師齊聚於此。

### 🛹 碗池結構指南
碗池主體分為 5 呎淺水區與 10 呎深水區，半圓形擴展槽設計提供了極速泵速（Pumping）路徑，能夠在連續轉彎中積蓄強大離心力並飛出槽頂。"""
    },
    {
        "slug": "spot_marseille_bowl_france",
        "title": "📍 法國馬賽 Prado Bowl：歐洲街式碗池發源地與地中海滑板塗鴉文化聖地",
        "subtitle": "90 年代傳奇碗池！無 Coping 金屬邊的純水泥流線，直擊 Red Bull Bowl Rippers 賽場",
        "category": "SKATE",
        "city_tag": "MARSEILLE",
        "cover_image": "/images/marseille_bowl.jpg",
        "cover_image_source": "Red Bull Content Pool / Marseille Skate",
        "youtube_video_id": "4YYTNkAdDD8",
        "youtube_video_title": "Red Bull Bowl Rippers Marseille Highlights",
        "gear_keyword": "bones spf skateboard wheels 58mm",
        "spot_info": {
            "name": "Prado Bowl (馬賽碗池)",
            "location": "Plage du Prado, Marseille, France",
            "difficulty": "All Levels / Intermediate",
            "features": ["無金屬邊緣純水泥脊線 (Spines)", "滿版街頭藝術與塗鴉文化", "地中海日落景觀", "歐洲最古老傳奇碗池之一"],
            "fee": "完全免費"
        },
        "affiliate_products": [{
            "title": "Bones SPF 58mm 104A 頂級碗池專用滑板輪",
            "subtitle": "Skatepark Formula 專利配方，抗平點 (Flatspot) 水平全球第一",
            "search_term": "bones spf skateboard wheels 58mm",
            "amazon_url": "https://www.amazon.com/s?k=bones+spf+skateboard+wheels+58mm&tag=kait02bc-20",
            "recommended_for": "水泥碗池、金屬 Coping 磨切與高速滑行",
            "badge_text": "碗池刷池神器"
        }],
        "content": """### 📍 傳奇歷史

建於 1991 年的馬賽 Prado 碗池被譽為歐洲滑板的「西斯廷教堂」。其最具特色的設計在於多個碗池交界處採用了純水泥平滑過渡（Spines），而非傳統的金屬鋼管，讓滑手可以在不同碗池間進行極限飛越與無縫滑接。"""
    },
    {
        "slug": "spot_tahiti_teahupoo_barrel",
        "title": "📍 法國大溪地 Teahupo'o (提阿胡普)：全球最危險也是最美麗的重力厚浪管",
        "subtitle": "2024 巴黎奧運衝浪賽場！水下重力斷崖與厚重巨浪深度指南",
        "category": "SURF",
        "city_tag": "TAHITI",
        "cover_image": "/images/teahupoo_barrel.jpg",
        "cover_image_source": "WSL / Olympic Surfing Pool",
        "youtube_video_id": "OcAH2xXfVhA",
        "youtube_video_title": "Teahupoo Heaviest Wave in the World Highlights",
        "gear_keyword": "dakine kainui team surf leash",
        "spot_info": {
            "name": "Teahupo'o (提阿胡普)",
            "location": "大溪地西南部 (Tahiti Iti, French Polynesia)",
            "difficulty": "Expert / Pro Only",
            "features": ["全球最厚重的半圓形重力管浪", "水下 0.5 米銳利珊瑚斷崖", "需乘船抵達離岸礁石區", "奧運與 WSL 標竿賽事地"],
            "fee": "需乘船出海 ($30-50 USD)"
        },
        "affiliate_products": [{
            "title": "DAKINE Kainui Team 6' 頂級大浪防斷腳繩",
            "subtitle": "高強聚氨酯繩體，雙不銹鋼旋轉扣，重浪拉扯不易斷裂",
            "search_term": "dakine kainui team surf leash",
            "amazon_url": "https://www.amazon.com/s?k=dakine+kainui+team+surf+leash&tag=kait02bc-20",
            "recommended_for": "礁石浪點、中大浪與進階管浪練習",
            "badge_text": "大浪保命配備"
        }],
        "content": """### 📍 浪點介紹

Teahupo'o 位於法屬波利尼西亞大溪地島西南角，以其「厚度大於高度」的超重重力管浪聞名於世。湧浪從深海直接衝上幾乎露出水面的珊瑚礁平台，使得整個海面呈現不可思議的凹陷折疊。

2024 年巴黎奧運會衝浪比賽即在此成功舉辦，見證了人類征服海洋極限的最高榮耀。"""
    }
]

def generate_spot_markdown(spot):
    date_str = "2026-09-08"
    posts_dir = os.path.join("src", "content", "posts")
    os.makedirs(posts_dir, exist_ok=True)
    
    filename = f"{date_str}_{spot['slug']}.md"
    filepath = os.path.join(posts_dir, filename)

    frontmatter_dict = {
        "title": spot["title"],
        "subtitle": spot["subtitle"],
        "date": f"{date_str}T00:00:00.000Z",
        "category": spot["category"],
        "topic_type": "SPOT",
        "cover_image": spot["cover_image"],
        "cover_image_source": spot.get("cover_image_source", "xGame Radar Editorial"),
        "author": "Una (@Una_next)",
        "city_tag": spot.get("city_tag", "GLOBAL"),
        "featured": True,
        "gear_keyword": spot.get("gear_keyword", "extreme sports gear"),
        "youtube_video_id": spot.get("youtube_video_id"),
        "youtube_video_title": spot.get("youtube_video_title", "官方精彩精華"),
        "spot_info": spot.get("spot_info"),
        "affiliate_products": spot.get("affiliate_products", [])
    }

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
    yaml_lines.append(f"![{spot['title']}]({spot['cover_image']})")
    yaml_lines.append("")
    yaml_lines.append(spot.get("content", ""))

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(yaml_lines))
    
    record_article(spot["title"], spot["category"], "SPOT")
    print(f"✅ 已生成場地攻略: {spot['title']} -> {filepath}")
    return filepath

def main():
    print("🚀 啟動 xGame Spot 全球與亞洲頂級場地庫批量生成引擎...")
    init_db()
    
    count = 0
    for spot in TOP_XGAME_SPOTS:
        generate_spot_markdown(spot)
        count += 1
        
    print(f"\n🎉 批量場地資料生成完畢！共新增 {count} 個頂級場地專題檔案。")
    print("💡 檔案已存入 src/content/posts/ 並已同步登記至 SQLite 資料庫。")

if __name__ == "__main__":
    main()
