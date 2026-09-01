import sys
import json
import os
import boto3
import requests  # 修正：補上缺失的 requests 模組

# ==========================================
# 1. UTILS & R2 FETCHING
# ==========================================
def clean_token_or_url(val):
    return val.strip() if val else ""

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

    # 確保路徑格式正確（R2 上的路徑通常為 posts/檔名.json）
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
# 2. TELEGRAM DISPATCHER
# ==========================================
def send_to_telegram(post_data):
    token = clean_token_or_url(os.getenv("TELEGRAM_BOT_TOKEN", ""))
    chat_id = clean_token_or_url(os.getenv("TELEGRAM_CHAT_ID", ""))
    
    if not token or not chat_id:
        print("❌ 錯誤：未設定 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID")
        return

    title = post_data.get("title", "")
    subtitle = post_data.get("subtitle", "")
    content = post_data.get("content", "")
    category = post_data.get("category", "")
    image_url = post_data.get("image_url", "")

    # 組合訊息內文 (支援 HTML 格式)
    text = f"🏆 <b>{title}</b>\n<i>{subtitle}</i>\n\n{content}\n\n#xGameRadar #{category} #Una_next"

    # 如果 JSON 裡有圖片網址，優先發送帶圖訊息
    if image_url:
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": image_url,
            "caption": text,
            "parse_mode": "HTML"
        }
    else:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }

    try:
        res = requests.post(url, json=payload, timeout=15)
        res_data = res.json()
        if res.status_code == 200 and res_data.get("ok"):
            print("✅ Telegram 發送成功！")
        else:
            print(f"❌ Telegram 發送失敗！HTTP Code: {res.status_code}")
            print(f"回應內容: {res.text}")
    except Exception as e:
        print(f"❌ 發送 Telegram 訊息時發生異常: {e}")

# ==========================================
# 3. MAIN ENTRY POINT
# ==========================================
if __name__ == "__main__":
    specified_file = sys.argv[1] if len(sys.argv) > 1 else ""
    
    if specified_file and specified_file.strip():
        post = get_specific_post_from_r2(specified_file)
    else:
        print("⚠️ 未指定檔名，執行預設邏輯...")
        post = None

    if post:
        print(f"✅ 成功取得文章標題: {post.get('title')}")
        # 修正：確實呼叫發送 Telegram 函式
        send_to_telegram(post)
    else:
        print("❌ 未取得任何文章數據，放棄發送 Telegram。")
