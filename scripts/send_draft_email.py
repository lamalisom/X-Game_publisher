#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unanext.fans | Draft Review Email Notification Dispatcher
"""
import os
import sys
import glob
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_draft_notification():
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    to_email = os.getenv("REVIEW_EMAIL")
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))

    if not smtp_user or not smtp_pass or not to_email:
        print("ℹ️ [Email] 未配置 SMTP_USER / SMTP_PASS / REVIEW_EMAIL Secrets，略過電郵發送。")
        return

    # 尋找最新產生的草稿 .md 檔案
    post_files = sorted(glob.glob("src/content/posts/*.md"), key=os.path.getmtime, reverse=True)
    if not post_files:
        print("⚠️ 未找到任何文章檔案")
        return

    latest_file = post_files[0]
    with open(latest_file, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # 提取標題
    title = os.path.basename(latest_file)
    for line in raw_text.splitlines():
        if line.startswith("title:"):
            title = line.replace("title:", "").strip().strip('"').strip("'")
            break

    rel_path = latest_file.replace("\\", "/")
    review_url = f"https://github.com/lamalisom/X-Game_publisher/edit/main/{rel_path}"

    html_content = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:680px;margin:0 auto;padding:24px;border:1px solid #e1e4e8;border-radius:12px;background:#ffffff;">
        <div style="background:#ff4d00;color:#fff;display:inline-block;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:bold;margin-bottom:12px;">xGame 待審核草稿</div>
        <h2 style="margin-top:0;color:#111;font-size:22px;line-height:1.3;">{title}</h2>
        <p style="color:#555;font-size:14px;">系統已為您生成最新草稿，目前處於 <b>draft: true</b> 狀態（正式網站已自動隱藏，訪客與 Google 看不到）。</p>
        
        <div style="margin:24px 0;text-align:center;">
            <a href="{review_url}" style="background:#ff4d00;color:#ffffff;text-decoration:none;padding:14px 28px;border-radius:8px;font-size:16px;font-weight:bold;display:inline-block;box-shadow:0 4px 12px rgba(255,77,0,0.3);">
                👉 點此前往 GitHub 審核並一鍵發布 (Publish)
            </a>
        </div>
        
        <div style="background:#f6f8fa;padding:16px;border-radius:8px;font-size:13px;color:#333;margin-bottom:20px;">
            <b>💡 發布步驟：</b><br>
            1. 點擊上方按鈕進入 GitHub 編輯畫面。<br>
            2. 檢查內文無誤後，將最上方的 <code>draft: true</code> 改為 <code>draft: false</code>。<br>
            3. 點擊右上角綠色按鈕 <b>Commit changes</b>，文章即刻在 unanext.fans 正式上線！
        </div>

        <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
        <h3 style="color:#444;font-size:16px;">📄 完整內文預覽：</h3>
        <pre style="white-space:pre-wrap;word-break:break-word;background:#fafbfc;padding:15px;border-radius:6px;font-size:12px;color:#444;line-height:1.5;">{raw_text}</pre>
    </div>
    """

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"📝【xGame 草稿待審】{title}"
    msg['From'] = f"xGame Draft Robot <{smtp_user}>"
    msg['To'] = to_email
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))

    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [to_email], msg.as_string())
        print(f"📧 審核電郵已成功寄出至: {to_email}")
    except Exception as e:
        print(f"⚠️ 電郵發送失敗: {e}")

if __name__ == "__main__":
    send_draft_notification()
