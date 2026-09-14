#!/usr/bin/env python3
"""
unanext.fans | Global Extreme Sports Spot Hub - ETL Data Ingestion Engine
========================================================================
Automated OpenStreetMap (Overpass API) extraction, transformation, and
Supabase PostGIS batch upsert pipeline.

Supports:
- 🛹 Skateboarding (Skateparks, Street plazas, Bowls)
- 🧗 Climbing & Bouldering (Indoor Gyms, Natural Crags, Boulders)
- 🏄 Surfing (Surf Breaks, Point Breaks, Beach Breaks)
- 🚲 BMX & Pump Tracks (BMX Tracks, Asphalt Pump Tracks)

Usage:
  python3 scripts/etl_osm_spots.py --country "Japan" --category "SKATE"
  python3 scripts/etl_osm_spots.py --bbox 22.1,113.8,22.6,114.4 --category "ALL"
  python3 scripts/etl_osm_spots.py --global --limit 500
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

AFFILIATE_AMAZON_TAG = os.getenv("AMAZON_AFFILIATE_TAG", "kait02bc-20")

def build_overpass_query(category: str, area_name: Optional[str] = None, bbox: Optional[List[float]] = None) -> str:
    """Constructs optimized Overpass QL query with timeout and center tags."""
    filters = CATEGORY_TAG_QUERIES.get(category, [])
    
    if bbox:
        # bbox format: minLat, minLng, maxLat, maxLng
        spatial_filter = f"({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]})"
        statements = "".join([f"  {f}{spatial_filter};\n" for f in filters])
        query = f"""
[out:json][timeout:90];
(
{statements});
out center tags 500;
"""
    elif area_name:
        statements = "".join([f'  {f}(area.searchArea);\n' for f in filters])
        query = f"""
[out:json][timeout:120];
area["name"="{area_name}"]->.searchArea;
(
{statements});
out center tags 500;
"""
    else:
        statements = "".join([f'  {f};\n' for f in filters])
        query = f"""
[out:json][timeout:120];
(
{statements});
out center tags 300;
"""
    return query

def fetch_overpass_data(query: str) -> List[Dict[str, Any]]:
    """Executes query with server rotation and retry backoff."""
    for server in OVERPASS_SERVERS:
        try:
            print(f"📡 Querying Overpass API [{server}]...")
            resp = requests.post(server, data={"data": query}, timeout=95)
            if resp.status_code == 200:
                data = resp.json()
                elements = data.get("elements", [])
                print(f"✅ Retrieved {len(elements)} raw spatial elements.")
                return elements
            elif resp.status_code == 429:
                print("⏳ Rate limited (429), switching server...")
                time.sleep(2)
        except Exception as e:
            print(f"⚠️ Server error on {server}: {e}, switching...")
            time.sleep(1)
    return []

def generate_slug(name: str, osm_id: int) -> str:
    clean_name = "".join(c if c.isalnum() else "_" for c in name.lower())
    clean_name = "_".join(filter(None, clean_name.split("_")))[:40]
    return f"{clean_name}_{osm_id}"

def build_affiliate_links(name: str, city: str, country: str, category: str, lat: float, lng: float) -> Dict[str, str]:
    """Generates localized Agoda, Klook, and Amazon affiliate funnel URLs."""
    location_query = urllib.parse.quote(f"{name} {city}".strip())
    
    # 1. Agoda / Booking Hotel Search Link
    hotel_url = f"https://www.agoda.com/search?text={location_query}&latitude={lat}&longitude={lng}"
    
    # 2. Klook / KKday Experience Search Link
    ticket_query = urllib.parse.quote(f"{city or country} {category.lower()} experience")
    ticket_url = f"https://www.klook.com/zh-HK/search/result/?query={ticket_query}"
    
    # 3. Amazon Equipment with Affiliate Tag
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
    
    # Coordinates extraction (supports node lat/lon and way center lat/lon)
    lat = element.get("lat") or element.get("center", {}).get("lat")
    lng = element.get("lon") or element.get("center", {}).get("lon")
    
    if not lat or not lng or not osm_id:
        return None
    
    # Name extraction with multilingual fallback
    name = (
        tags.get("name:zh-hk") or 
        tags.get("name:zh") or 
        tags.get("name:en") or 
        tags.get("name") or 
        f"{default_category} Spot #{osm_id}"
    )
    
    # Sub-category classification
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
    
    # Features extraction
    features = []
    if tags.get("lit") == "yes":
        features.append("夜間照明 (Night Lighting)")
    if tags.get("fee") == "no":
        features.append("免費開放 (Free Access)")
    if tags.get("surface"):
        features.append(f"地面材質: {tags.get('surface')}")
    if tags.get("skatepark:material"):
        features.append(f"結構: {tags.get('skatepark:material')}")

    # Affiliate URLs
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
    
    # Batch in chunks of 50
    chunk_size = 50
    total_inserted = 0
    
    for i in range(0, len(records), chunk_size):
        chunk = records[i:i + chunk_size]
        try:
            resp = requests.post(endpoint, json=chunk, headers=headers, timeout=20)
            if resp.status_code in [200, 201, 204]:
                total_inserted += len(chunk)
                print(f"  ⚡ Upserted {len(chunk)} spots (Batch {i // chunk_size + 1})...")
            else:
                print(f"  ❌ Failed chunk ({resp.status_code}): {resp.text[:120]}")
        except Exception as e:
            print(f"  ❌ Error during batch upsert: {e}")
            
    return total_inserted

def main():
    parser = argparse.ArgumentParser(description="unanext.fans Global Spots ETL Engine")
    parser.add_argument("--category", choices=["SKATE", "CLIMB", "SURF", "BMX", "ALL"], default="ALL")
    parser.add_argument("--country", type=str, help="Target country (e.g., 'Japan', 'Hong Kong')")
    parser.add_argument("--bbox", type=str, help="Bounding box minLat,minLng,maxLat,maxLng")
    parser.add_argument("--export-json", type=str, default="public/data/global_spots.json", help="Export to local JSON file")
    
    args = parser.parse_args()
    
    categories = ["SKATE", "CLIMB", "SURF", "BMX"] if args.category == "ALL" else [args.category]
    bbox_coords = [float(x.strip()) for x in args.bbox.split(",")] if args.bbox else None
    
    all_transformed = []
    
    for cat in categories:
        print(f"\n🚀 Running ETL Pipeline for Category: 【{cat}】")
        query = build_overpass_query(cat, area_name=args.country, bbox=bbox_coords)
        raw_elements = fetch_overpass_data(query)
        
        cat_transformed = []
        for elem in raw_elements:
            transformed = transform_element(elem, cat)
            if transformed:
                cat_transformed.append(transformed)
                
        print(f"🎯 Successfully processed {len(cat_transformed)} valid spots for {cat}.")
        all_transformed.extend(cat_transformed)
        time.sleep(1)

    # Save to local JSON fallback
    os.makedirs(os.path.dirname(args.export_json), exist_ok=True)
    with open(args.export_json, "w", encoding="utf-8") as f:
        json.dump(all_transformed, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Saved {len(all_transformed)} total spots to local fallback: {args.export_json}")
    
    # Supabase Ingestion
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    
    if supabase_url and supabase_key:
        print(f"\n☁️ Syncing {len(all_transformed)} spots with Supabase PostGIS...")
        upserted_count = upsert_to_supabase(all_transformed, supabase_url, supabase_key)
        print(f"✨ Supabase Sync Complete! Upserted {upserted_count} records.")
    else:
        print("\n💡 NOTE: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not configured in env.")
        print("  Local static JSON dataset generated successfully for immediate Astro frontend use!")

if __name__ == "__main__":
    main()
