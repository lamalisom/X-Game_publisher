import sys
import json
import boto3
import os

# 清理環境變數工具（保持專案既有規範）
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
    object_key = f"posts/{target_filename}" if not target_filename.startswith("posts/") else target_filename
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
# 主執行入口
# ==========================================
if __name__ == "__main__":
    # 檢查是否有從命令列傳入檔名參數
    if len(sys.argv) > 1:
        specified_file = sys.argv[1]
        post = get_specific_post_from_r2(specified_file)
    else:
        print("⚠️ 未指定檔名，執行預設邏輯（如：抓取最新文章）...")
        # 這裡放入你原本抓取最新/隨機文章的函式
        post = None 

    if post:
        print(f"✅ 成功取得文章標題: {post.get('title')}")
        # 接下來執行發布至 Telegram 或其他平台的邏輯...
