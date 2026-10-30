import os
import json
import time
import requests
from datetime import datetime

# ========================================================
# Google Suggest 免費長尾關鍵字挖掘引擎
# ========================================================

CATEGORIES = {
    "SKATE": ["滑板", "skateboard", "長板", "陸衝 surfskate"],
    "SURF": ["衝浪", "surfing", "浪點", "防寒衣"],
    "SNOW": ["單板滑雪", "snowboard", "雙板滑雪", "滑雪裝備"],
    "CLIMB": ["抱石", "攀岩", "climbing", "攀岩鞋"],
    "BMX": ["BMX 單車", "極限單車", "pumptrack 泵道"]
}

# 針對痛點、比較、選購與入門的長尾修飾詞（低競爭度金礦）
MODIFIERS = [
    "新手",
    "怎麼選",
    "推薦",
    "初學者",
    "入門技巧",
    "難度",
    "價格",
    "差別",
    "注意事項"
]

def get_google_suggestions(query, hl="zh-TW", gl="TW"):
    """調用 Google Suggest API 獲取即時熱門長尾搜尋詞"""
    url = f"https://suggestqueries.google.com/complete/search?client=chrome&hl={hl}&gl={gl}&q={query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            return data[1] if len(data) > 1 else []
    except Exception as e:
        print(f"⚠️ 查詢 [{query}] 失敗: {e}")
    return []

def harvest_low_competition_keywords():
    print(f"🚀 開始挖掘 Google 低競爭度長尾關鍵字庫（時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）...\n")
    
    os.makedirs("data", exist_ok=True)
    output_file = os.path.join("data", "seo_keyword_ideas.json")
    
    all_results = {}
    total_found = 0

    for cat, base_terms in CATEGORIES.items():
        all_results[cat] = []
        seen = set()
        print(f"🔍 正在挖掘項目：【{cat}】...")
        
        for term in base_terms:
            for mod in MODIFIERS:
                query = f"{term} {mod}"
                suggestions = get_google_suggestions(query)
                for s in suggestions:
                    s_clean = s.strip()
                    if s_clean and s_clean not in seen and s_clean != query:
                        seen.add(s_clean)
                        all_results[cat].append({
                            "keyword": s_clean,
                            "seed_query": query,
                            "discovered_at": datetime.now().isoformat()
                        })
                        total_found += 1
                time.sleep(0.3)  # 禮貌性間隔，防止被限流
        
        print(f"   👉 【{cat}】成功獲取 {len(all_results[cat])} 個高價值長尾詞！")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 挖掘完成！共獲取 {total_found} 個低競爭長尾關鍵字。")
    print(f"📁 已完整儲存至: {output_file}")

if __name__ == "__main__":
    harvest_low_competition_keywords()
