import os, re

NEW_PUB_ID = "9936045917768902"
NEW_CLIENT = f"ca-pub-{NEW_PUB_ID}"

# ========================================================
# 1. 更新 src/layouts/Layout.astro (Code Snippet + Meta Tag)
# ========================================================
layout_path = "src/layouts/Layout.astro"
if os.path.exists(layout_path):
    with open(layout_path, "r", encoding="utf-8") as f:
        content = f.read()

    # (A) 替換或補上 Meta Tag
    meta_tag = f'<meta name="google-adsense-account" content="{NEW_CLIENT}">'
    if "google-adsense-account" in content:
        content = re.sub(r'<meta name="google-adsense-account" content="[^"]*">', meta_tag, content)
    else:
        content = content.replace("<!-- 📢 Google AdSense", f"{meta_tag}\n    <!-- 📢 Google AdSense", 1)

    # (B) 替換 AdSense Script Code
    content = re.sub(
        r'https://pagead2\.googlesyndication\.com/pagead/js/adsbygoogle\.js\?client=ca-pub-\d+',
        f'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={NEW_CLIENT}',
        content
    )

    with open(layout_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("✅ 1. 成功更新 Layout.astro（AdSense Script 代碼 + Meta Tag 均已更換為新帳號）！")

# ========================================================
# 2. 更新 public/ads.txt
# ========================================================
os.makedirs("public", exist_ok=True)
ads_txt_path = "public/ads.txt"
new_ads_txt = f"google.com, pub-{NEW_PUB_ID}, DIRECT, f08c47fec0942fa0\n"

with open(ads_txt_path, "w", encoding="utf-8") as f:
    f.write(new_ads_txt)
print(f"✅ 2. 成功更新 public/ads.txt -> {new_ads_txt.strip()}")

print("🎯 全部 AdSense 驗證配置已 100% 更新為新帳號！")
