#!/usr/bin/env python3
"""
朝9時メール本文の生成 + SMTP自動送信
- 本日新着記事のみ抜粋し、HTMLメールを生成
- まとめサイトへのリンクを末尾に付与
- 環境変数:
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS,
  EMAIL_FROM, EMAIL_TO (カンマ区切り),
  SITE_URL (まとめサイトのURL)
"""
import os
import json
import smtplib
import ssl
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SOURCES_FILE = ROOT / "sources.yaml"


def load_today_articles():
    today = datetime.now().strftime("%Y%m%d")
    f = DATA_DIR / f"articles_{today}.json"
    if not f.exists():
        return []
    with open(f, encoding="utf-8") as fp:
        return json.load(fp)


def load_categories():
    with open(SOURCES_FILE, encoding="utf-8") as fp:
        return yaml.safe_load(fp).get("categories", {})


def render_email_html(articles, categories, site_url):
    today = datetime.now().strftime("%Y年%m月%d日 (%a)")
    if not articles:
        body_html = '<p style="padding:40px 0;text-align:center;color:#64748b;">本日は新着情報がありませんでした。</p>'
    else:
        # カテゴリ別にグループ化
        grouped = {}
        for a in articles:
            c = a.get("category", "general")
            grouped.setdefault(c, []).append(a)
        order = ["mext", "giga", "komuDX", "security", "case", "general"]
        sections = []
        for cat in order:
            if cat not in grouped:
                continue
            arts = grouped[cat]
            cdef = categories.get(cat, {"label": cat, "color": "#6b7280", "icon": "📰"})
            section = f"""
            <div style="margin-bottom:32px;">
              <div style="display:inline-block;padding:6px 14px;background:{cdef['color']}15;color:{cdef['color']};border-radius:999px;font-size:13px;font-weight:600;border:1px solid {cdef['color']}30;margin-bottom:12px;">
                {cdef['icon']} {cdef['label']} ({len(arts)}件)
              </div>
            """
            for a in arts:
                stars = "★" * a.get("importance", 3)
                section += f"""
              <div style="border-left:3px solid {cdef['color']};padding:10px 16px;margin:10px 0;background:#f8fafc;border-radius:0 8px 8px 0;">
                <div style="font-weight:600;font-size:15px;margin-bottom:4px;line-height:1.4;">
                  <a href="{a['url']}" style="color:#1e40af;text-decoration:none;" target="_blank">{a.get('title','')}</a>
                </div>
                <div style="color:#475569;font-size:13px;line-height:1.6;margin-bottom:6px;">{a.get('summary','')}</div>
                <div style="font-size:11px;color:#94a3b8;">
                  <span style="font-weight:600;">{a.get('source_name','')}</span>
                  <span style="margin:0 8px;">·</span>
                  <span style="color:#f59e0b;">{stars}</span>
                </div>
              </div>"""
            section += "</div>"
            sections.append(section)
        body_html = "\n".join(sections)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,'Hiragino Kaku Gothic ProN','Yu Gothic',Meiryo,sans-serif;color:#0f172a;">
<div style="max-width:680px;margin:0 auto;padding:24px 16px;">
  <div style="background:white;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,0.05);overflow:hidden;">
    <div style="background:linear-gradient(135deg,#1e40af 0%,#3b82f6 100%);color:white;padding:24px 28px;">
      <div style="font-size:20px;font-weight:700;">📚 教育自治体ビジネス インテリジェンス</div>
      <div style="opacity:0.85;font-size:13px;margin-top:4px;">{today} 朝刊 · 新着 {len(articles)}件</div>
    </div>
    <div style="padding:24px 28px;">
      <p style="margin:0 0 24px 0;color:#475569;font-size:14px;line-height:1.7;">
      おはようございます。本日収集した新着情報をお届けします。<br>
      要約は営業視点で重要なポイント (自治体名・サービス名・金額・期日) を優先しています。
      </p>
      {body_html}
      <div style="text-align:center;margin:32px 0 8px 0;">
        <a href="{site_url}" style="display:inline-block;padding:12px 24px;background:#1e40af;color:white;text-decoration:none;border-radius:8px;font-weight:600;font-size:14px;">📊 まとめサイトで全件を見る</a>
      </div>
      <p style="font-size:11px;color:#94a3b8;text-align:center;margin-top:24px;line-height:1.5;">
      このメールは自動配信されています。<br>
      検出元: 文部科学省 / 教育家庭新聞 / ICT教育ニュース / リシード / 自治体広報 等
      </p>
    </div>
  </div>
</div>
</body></html>"""
    return html


def render_email_text(articles, categories, site_url):
    today = datetime.now().strftime("%Y年%m月%d日 (%a)")
    if not articles:
        return f"{today} 朝刊\n\n本日は新着情報がありませんでした。\n\nまとめサイト: {site_url}\n"
    lines = [
        f"📚 教育自治体ビジネス インテリジェンス",
        f"{today} 朝刊 · 新着 {len(articles)}件",
        "",
        "─" * 40,
        "",
    ]
    grouped = {}
    for a in articles:
        c = a.get("category", "general")
        grouped.setdefault(c, []).append(a)
    order = ["mext", "giga", "komuDX", "security", "case", "general"]
    for cat in order:
        if cat not in grouped:
            continue
        cdef = categories.get(cat, {"label": cat, "icon": "📰"})
        lines.append(f"■ {cdef['icon']} {cdef['label']} ({len(grouped[cat])}件)")
        for a in grouped[cat]:
            lines.append(f"")
            lines.append(f"  ▸ {a.get('title','')}")
            lines.append(f"    {a.get('summary','')}")
            lines.append(f"    [{a.get('source_name','')}] {a['url']}")
        lines.append("")
    lines.extend([
        "─" * 40,
        "",
        f"📊 まとめサイトで全件を見る: {site_url}",
        "",
        "このメールは自動配信されています。",
    ])
    return "\n".join(lines)


def send_smtp(html_body, text_body, subject):
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", 587))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASS"]
    sender = os.environ.get("EMAIL_FROM", user)
    to_list = [x.strip() for x in os.environ["EMAIL_TO"].split(",") if x.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(to_list)
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx) as s:
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as s:
            s.starttls(context=ctx)
            s.login(user, password)
            s.send_message(msg)
    # 注意: 公開リポジトリのActionsログには配信先メールアドレスを出さない
    print(f"送信完了: {len(to_list)}件の宛先に配信")


def main():
    articles = load_today_articles()
    categories = load_categories()
    site_url = os.environ.get("SITE_URL", "https://example.com/edu-intel/")
    today = datetime.now().strftime("%Y/%m/%d")
    subject = f"【教育自治体インテリジェンス】{today} 朝刊 · 新着{len(articles)}件"
    html_body = render_email_html(articles, categories, site_url)
    text_body = render_email_text(articles, categories, site_url)

    # プレビュー保存
    preview_dir = ROOT / "data"
    with open(preview_dir / "email_preview.html", "w", encoding="utf-8") as f:
        f.write(html_body)
    with open(preview_dir / "email_preview.txt", "w", encoding="utf-8") as f:
        f.write(text_body)
    print(f"プレビュー: {preview_dir}/email_preview.html")

    if "--send" in sys.argv:
        if not os.environ.get("SMTP_HOST"):
            print("SMTP_HOST未設定 - 送信をスキップ")
            return
        send_smtp(html_body, text_body, subject)
    else:
        print("(--sendを付けると実際に送信)")


if __name__ == "__main__":
    main()
