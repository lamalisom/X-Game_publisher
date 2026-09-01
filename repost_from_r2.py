import sys
import json
import os
import re
import boto3
import requests
from urllib.parse import quote

# ==========================================
# 1. UTILS & SANITIZERS
# ==========================================
def clean_token_or_url(val):
    if not val:
        return ""
    return re.sub(r'[\[\]\(\)\'"]', '', str(val)).strip()

def extract_clean_url(url_str):
    if not url_str:
        return ""
    match = re.search(r'https?://[^\s\)]+', str(url_str))
    if match:
        clean_u = match.group(0).rstrip(']')
        return re.sub(r'[\[\]\'"]', '', clean_u).strip()
    return clean_token_or_url(url_str)

AMAZON_AFFILIATE_ID = clean_token_or_url(os.getenv("AMAZON_AFFILIATE_ID", "kait02bc-20"))

# ==========================================
# 2. R2 FETCHING MODULE
# ==========================================
def get_specific_post_from_r2(target_filename):
    """從 Cloudflare R2 指定抓取某一篇文章的 JSON 檔案"""
    account_id = clean_token_or_url(os.getenv("R2_ACCOUNT_ID", ""))
    access_key = clean_token_or_url(os.getenv("R2_ACCESS_KEY_ID", ""))
    secret_key = clean_token_or_url(os.getenv("R2_SECRET_ACCESS_KEY", ""))
    bucket_name = clean_token_or_url(os.getenv("R2_BUCKET_NAME", "xgame-radar-media"))

    s3 = boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto"
    )

    clean_name = target_filename.strip()
    object_key = f"posts/{clean_name}" if not clean_name.startswith("posts/") else clean_name
    if not object_key.endswith(".json"):
        object_key += ".json"

    try:
        print(f"🔍 正在從 R2 讀取指定文章: {object_key}...")
        response = s3.get_object(Bucket=bucket_name, Key=object_key)
        post_data = json.loads(response['Body'].read().decode('utf-8'))
        return post_data
    except Exception as e:
        print(f"❌ 抓取指定文章失敗 ({object_key}): {e}")
        return None

# ==========================================
# 3. TELEGRAM SMART DISPATCHER (WITH R2 IMAGE)
# ==========================================
def send_to_telegram(post_data):
    token = clean_token_or_url(os.getenv("TELEGRAM_BOT_TOKEN", ""))
    chat_id = clean_token_or_url(os.getenv("TELEGRAM_CHAT_ID", ""))
    
    if not token or not chat_id:
        print("❌ 錯誤：未設定 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID")
        return

    title = post_data.get("title", "").replace("封面主標題", "").strip()
    subtitle = post_data.get("subtitle", "").replace("封面副標題", "").strip()
    content = post_data.get("content", "")
    category = post_data.get("category", "XGAME")
    image_url = extract_clean_url(post_data.get("image_url", ""))

    # 組合 Telegram 訊息文字 (HTML 格式)
    caption_text = f"🏆 <b>{title}</b>\n<i>{subtitle}</i>\n\n{content}\n\n#xGameRadar #{category} #Una_next"

    # 如果 Telegram HTML 標籤過長，做簡單安全處理
    if len(caption_text) > 1024 and image_url:
        # Telegram 圖片附帶文字上限為 1024 字元
        caption_text = caption_text[:1000] + "..."

    # 1. 嘗試發送帶 R2 圖片的訊息
    if image_url:
        print(f"🖼️ 嘗試從 R2 載入圖片發送至 Telegram: {image_url}")
        url_photo = f"https://api.telegram.org/bot{token}/sendPhoto"
        payload_photo = {
            "chat_id": chat_id,
            "photo": image_url,
            "caption": caption_text,
            "parse_mode": "HTML"
        }
        try:
            res = requests.post(url_photo, json=payload_photo, timeout=15)
            res_json = res.json()
            if res.status_code == 200 and res_json.get("ok"):
                print("✅ Telegram 成功發送 (含 R2 圖片卡片)！")
                return
            else:
                print(f"⚠️ 帶圖發送失敗 ({res_json.get('description')})，轉為純文字發送...")
        except Exception as e:
            print(f"⚠️ 圖片請求發生例外 ({e})，轉為純文字發送...")

    # 2. 降級備案：純文字發送
    url_msg = f"https://api.telegram.org/bot{token}/sendMessage"
    payload_msg = {
        "chat_id": chat_id,
        "text": caption_text,
        "parse_mode": "HTML"
    }
    try:
        res = requests.post(url_msg, json=payload_msg, timeout=15)
        res_json = res.json()
        if res.status_code == 200 and res_json.get("ok"):
            print("✅ Telegram 純文字訊息發送成功！")
        else:
            print(f"❌ Telegram 發送失敗！錯誤: {res_json.get('description')}")
    except Exception as e:
        print(f"❌ 發送 Telegram 時發生異常: {e}")

# ==========================================
# 4. MAIN ENTRY POINT
# ==========================================
if __name__ == "__main__":
    specified_file = sys.argv[1] if len(sys.argv) > 1 else ""
    
    if specified_file and specified_file.strip():
        post = get_specific_post_from_r2(specified_file)
    else:
        print("⚠️ 未指定檔名，請提供 R2 JSON 檔名 (例如: 20260831_162709_BMX.json)")
        post = None

    if post:
        print(f"✅ 成功讀取文章，標題: {post.get('title')}")
        send_to_telegram(post)
    else:
        print("❌ 未取得任何文章數據，程序終止。")
