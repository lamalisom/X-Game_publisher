#!/usr/bin/env python3
"""
unanext.fans | Global Extreme Sports Spot Hub - Enhanced Multi-Region ETL Engine
================================================================================
Automated OpenStreetMap (Overpass API) extraction, transformation, and
Supabase PostGIS batch upsert pipeline with robust BBox & Country alias matching.
"""

import os
import sys
import json
import time
import urllib.parse
import argparse
import requests
from typing import List, Dict, Any, Optional

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
]

CATEGORY_TAG_QUERIES = {
    "SKATE": [
        'node["leisure"="skatepark"]',
        'way["leisure"="skatepark"]',
        'node["sport"="skateboard"]',
        'way["sport"="skateboard"]'
    ],
    "CLIMB": [
        'node["sport"="climbing"]',
        'way["sport"="climbing"]',
        'node["climbing"="crag"]',
        'node["climbing"="boulder"]',
        'node["climbing"="gym"]'
    ],
    "SURF": [
        'node["sport"="surfing"]',
        'way["sport"="surfing"]',
        'node["natural"="beach"]["surf"="yes"]',
        'node["leisure"="surf_spot"]'
    ],
    "BMX": [
        'node["sport"="bmx"]',
        'way["sport"="bmx"]',
        'node["leisure"="pumptrack"]',
        'way["leisure"="pumptrack"]'
    ]
}

# 預定義熱門地區 BBox 坐標 (minLat, minLng, maxLat, maxLng) 提升查詢命中率與速度
KNOWN_REGION_BBOX = {
    "hong kong": [22.15, 113.83, 22.58, 114.45],
    "hk": [22.15, 113.83, 22.58, 114.45],
    "香港": [22.15, 113.83, 22.58, 114.45],
    "tokyo": [35.50, 139.50, 35.85, 139.95],
    "東京": [35.50, 139.50, 35.85, 139.95],
    "japan": [31.0, 129.5, 45.5, 145.8],
    "日本": [31.0, 129.5, 45.5, 145.8],
    "taiwan": [21.8, 119.8, 25.4, 122.1],
    "台灣": [21.8, 119.8, 25.4, 122.1],
    "sydney": [-34.15, 150.60, -33.55, 151.35],
    "los angeles": [33.70, -118.67, 34.34, -118.15],
    "california": [32.5, -124.5, 42.0, -114.1],
    "paris": [48.75, 2.15, 48.95, 2.45],
    "france": [42.3, -4.8, 51.1, 8.2]
}

AFFILIATE_AMAZON_TAG = os.getenv("AMAZON_AFFILIATE_TAG", "kait02bc-20")

def build_overpass_query(category: str, area_name: Optional[str] = None, bbox: Optional[List[float]] = None) -> str:
    """Constructs optimized Overpass QL query with timeout and center tags."""
    filters = CATEGORY_TAG_QUERIES.get(category, [])
    
    # 優先使用精確 BBox 範圍
    target_bbox = bbox
    if not target_bbox and area_name:
        clean_area = area_name.strip().lower()
        if clean_area in KNOWN_REGION_BBOX:
            target_bbox = KNOWN_REGION_BBOX[clean_area]
            print(f"🗺️ 自動套用【{area_name}】專屬地理 BBox 坐標加速查詢: {target_bbox}")

    if target_bbox:
        spatial_filter = f"({target_bbox[0]},{target_bbox[1]},{target_bbox[2]},{target_bbox[3]})"
        statements = "".join([f"  {f}{spatial_filter};\n" for f in filters])
        query = f"""
[out:json][timeout:90];
(
{statements});
out center tags 500;
"""
    elif area_name:
        # 多語系 Area 匹配
        query = f"""
[out:json][timeout:90];
(
  area["name:en"="{area_name}"];
  area["name"="{area_name}"];
  area["ISO3166-1"="{area_name.upper()}"];
)->.searchArea;
(
""" + "".join([f'  {f}(area.searchArea);\n' for f in filters]) + f"""
);
out center tags 500;
"""
    else:
        statements = "".join([f'  {f};\n' for f in filters])
        query = f"""
[out:json][timeout:90];
(
{statements});
out center tags 300;
"""
    return query

def fetch_overpass_data(query: str) -> List[Dict[str, Any]]:
    """Executes query with server rotation and retry backoff."""
    for server in OVERPASS_SERVERS:
        try:
            print(f"📡 查詢 Overpass API 伺服器 [{server}]...")
            resp = requests.post(server, data={"data": query}, timeout=45)
            if resp.status_code == 200:
                data = resp.json()
                elements = data.get("elements", [])
                print(f"✅ 成功抓取 {len(elements)} 筆原始空間點位數據！")
                return elements
            elif resp.status_code == 429:
                print("⏳ 遭遇請求頻率限制 (429)，自動切換備用伺服器...")
                time.sleep(2)
        except Exception as e:
            print(f"⚠️ 伺服器連線略過 ({server}): {e}")
            time.sleep(1)
    return []

def generate_slug(name: str, osm_id: int) -> str:
    clean_name = "".join(c if c.isalnum() else "_" for c in name.lower())
    clean_name = "_".join(filter(None, clean_name.split("_")))[:40]
    return f"{clean_name}_{osm_id}"

def build_affiliate_links(name: str, city: str, country: str, category: str, lat: float, lng: float) -> Dict[str, str]:
    """Generates localized Agoda, Klook, and Amazon affiliate funnel URLs."""
    location_query = urllib.parse.quote(f"{name} {city}".strip())
    
    # 1. Agoda 附近住宿
    hotel_url = f"https://www.agoda.com/search?text={location_query}&latitude={lat}&longitude={lng}"
    
    # 2. Klook 體驗預約
    ticket_query = urllib.parse.quote(f"{city or country} {category.lower()} experience")
    ticket_url = f"https://www.klook.com/zh-HK/search/result/?query={ticket_query}"
    
    # 3. Amazon 專屬防護裝備 (帶 Tag)
    gear_keywords = {
        "SKATE": "skateboard helmet pads bones bearings",
        "CLIMB": "climbing shoes chalk bag harness",
        "SURF": "surfboard leash wetsuit traction pad",
        "BMX": "bmx helmet gloves knee guards",
        "SNOW": "snowboard goggles helmet gloves"
    }
    search_keyword = urllib.parse.quote(gear_keywords.get(category, "extreme sports gear"))
    gear_url = f"https://www.amazon.com/s?k={search_keyword}&tag={AFFILIATE_AMAZON_TAG}"
    
    return {
        "affiliate_hotel_url": hotel_url,
        "affiliate_ticket_url": ticket_url,
        "affiliate_gear_url": gear_url
    }

def transform_element(element: Dict[str, Any], default_category: str) -> Optional[Dict[str, Any]]:
    """Transforms raw OSM node/way into unanext.fans spot record."""
    tags = element.get("tags", {})
    osm_id = element.get("id")
    
    lat = element.get("lat") or element.get("center", {}).get("lat")
    lng = element.get("lon") or element.get("center", {}).get("lon")
    
    if not lat or not lng or not osm_id:
        return None
    
    name = (
        tags.get("name:zh-hk") or 
        tags.get("name:zh") or 
        tags.get("name:en") or 
        tags.get("name") or 
        f"{default_category} Spot #{osm_id}"
    )
    
    sub_category = "general"
    if default_category == "SKATE":
        if "bowl" in name.lower() or tags.get("skatepark:bowl") == "yes":
            sub_category = "bowl"
        elif "street" in name.lower() or tags.get("skatepark:street") == "yes":
            sub_category = "street_plaza"
        else:
            sub_category = "skatepark"
    elif default_category == "CLIMB":
        if tags.get("climbing") == "boulder" or "boulder" in name.lower():
            sub_category = "bouldering"
        elif tags.get("climbing") == "crag" or "crag" in name.lower():
            sub_category = "outdoor_crag"
        else:
            sub_category = "climbing_gym"
    elif default_category == "SURF":
        sub_category = "surf_break"
    elif default_category == "BMX":
        sub_category = "pumptrack" if "pumptrack" in tags.get("leisure", "") else "bmx_track"
    
    city = tags.get("addr:city") or tags.get("city") or tags.get("is_in:city") or ""
    country = tags.get("addr:country") or tags.get("country") or ""
    address = tags.get("addr:full") or tags.get("addr:street") or ""
    
    features = []
    if tags.get("lit") == "yes":
        features.append("夜間照明 (Night Lighting)")
    if tags.get("fee") == "no":
        features.append("免費開放 (Free Access)")
    if tags.get("surface"):
        features.append(f"地面材質: {tags.get('surface')}")
    if tags.get("skatepark:material"):
        features.append(f"結構: {tags.get('skatepark:material')}")

    affiliates = build_affiliate_links(name, city, country, default_category, lat, lng)
    
    return {
        "osm_id": osm_id,
        "name": name,
        "slug": generate_slug(name, osm_id),
        "category": default_category,
        "sub_category": sub_category,
        "latitude": round(lat, 6),
        "longitude": round(lng, 6),
        "city": city,
        "country": country,
        "formatted_address": address,
        "difficulty": tags.get("difficulty", "All Levels"),
        "fee_type": "FREE" if tags.get("fee") == "no" else ("PAID" if tags.get("fee") == "yes" else "OPEN"),
        "fee_details": tags.get("charge", ""),
        "opening_hours": tags.get("opening_hours", "依現場公告"),
        "surface_type": tags.get("surface", "Standard"),
        "features": features,
        "photos": [],
        "tags": tags,
        **affiliates
    }

def upsert_to_supabase(records: List[Dict[str, Any]], supabase_url: str, supabase_key: str) -> int:
    """Performs batch upsert directly via Supabase REST PostgREST endpoint."""
    if not records or not supabase_url or not supabase_key:
        return 0
    
    endpoint = f"{supabase_url.rstrip('/')}/rest/v1/spots"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    
    chunk_size = 50
    total_inserted = 0
    
    for i in range(0, len(records), chunk_size):
        chunk = records[i:i + chunk_size]
        try:
            resp = requests.post(endpoint, json=chunk, headers=headers, timeout=20)
            if resp.status_code in [200, 201, 204]:
                total_inserted += len(chunk)
                print(f"  ⚡ 成功寫入 {len(chunk)} 個點位 (批次 {i // chunk_size + 1})...")
            else:
                print(f"  ❌ 批次寫入回應 ({resp.status_code}): {resp.text[:120]}")
        except Exception as e:
            print(f"  ❌ Supabase 連線寫入異常: {e}")
            
    return total_inserted

def merge_with_existing_dataset(new_records: List[Dict[str, Any]], json_path: str) -> List[Dict[str, Any]]:
    """以 osm_id 為主鍵進行增量合併，確保舊點位不遺失"""
    existing_map = {}
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                old_list = json.load(f)
                for item in old_list:
                    if "osm_id" in item:
                        existing_map[item["osm_id"]] = item
        except Exception as e:
            print(f"⚠️ 讀取現有資料集略過: {e}")

    for item in new_records:
        existing_map[item["osm_id"]] = item

    return list(existing_map.values())

def main():
    parser = argparse.ArgumentParser(description="unanext.fans Global Spots ETL Engine")
    parser.add_argument("--category", choices=["SKATE", "CLIMB", "SURF", "BMX", "ALL"], default="ALL")
    parser.add_argument("--country", type=str, help="Target country or city (e.g., 'Hong Kong', 'Tokyo', 'Japan')")
    parser.add_argument("--bbox", type=str, help="Bounding box minLat,minLng,maxLat,maxLng")
    parser.add_argument("--export-json", type=str, default="public/data/global_spots.json", help="Export path")
    
    args = parser.parse_args()
    
    categories = ["SKATE", "CLIMB", "SURF", "BMX"] if args.category == "ALL" else [args.category]
    bbox_coords = [float(x.strip()) for x in args.bbox.split(",")] if args.bbox else None
    
    all_transformed = []
    
    for cat in categories:
        print(f"\n🚀 啟動【{cat}】運動項目 ETL 管道...")
        query = build_overpass_query(cat, area_name=args.country, bbox=bbox_coords)
        raw_elements = fetch_overpass_data(query)
        
        cat_transformed = []
        for elem in raw_elements:
            transformed = transform_element(elem, cat)
            if transformed:
                cat_transformed.append(transformed)
                
        print(f"🎯 成功解析 {len(cat_transformed)} 個合規的【{cat}】極限運動場地。")
        all_transformed.extend(cat_transformed)
        time.sleep(1)

    # 進行增量合併，保證歷史與手動維護點位永遠保留
    merged_data = merge_with_existing_dataset(all_transformed, args.export_json)
    
    os.makedirs(os.path.dirname(args.export_json), exist_ok=True)
    with open(args.export_json, "w", encoding="utf-8") as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=2)
    print(f"\n💾 成功累積儲存 {len(merged_data)} 個場地點位至全域資料集: {args.export_json}")
    
    # 寫入 Supabase PostGIS
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    
    if supabase_url and supabase_key:
        print(f"\n☁️ 正在與 Supabase PostGIS 空間資料庫同步...")
        upserted_count = upsert_to_supabase(all_transformed, supabase_url, supabase_key)
        print(f"✨ Supabase 同步完成！本次寫入/更新了 {upserted_count} 筆記錄。")
    else:
        print("\n💡 提示：目前使用靜態 JSON 資料集模式，前端地圖已即時生效！")

if __name__ == "__main__":
    main()
