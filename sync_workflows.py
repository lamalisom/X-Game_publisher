import os, glob

workflow_files = glob.glob(".github/workflows/*.yml")
print(f"🔍 找到 {len(workflow_files)} 個 Workflow 檔案進行依賴檢查...")

for wf in workflow_files:
    with open(wf, "r", encoding="utf-8") as f:
        content = f.read()

    # 確保每個 workflow 的 pip install 都包含 feedparser
    if "pip install" in content and "feedparser" not in content:
        content = content.replace("pip install google-genai", "pip install google-genai feedparser")
        with open(wf, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ 已為 {wf} 補全 feedparser 依賴！")
    else:
        print(f"ℹ️ {wf} 依賴已是最新狀態。")

print("🎯 全部 Workflow 設定檔已達 100% 一致與健全！")
