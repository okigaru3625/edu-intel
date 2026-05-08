#!/usr/bin/env python3
"""
教育自治体ビジネス情報収集スクリプト
- RSS / HTMLスクレイピング / 検索ベースで新着記事を収集
- 重複排除 (state.json)
- Anthropic APIで要約 + カテゴリ自動分類
- 成果物: data/articles_YYYYMMDD.json (本日新着), data/all_articles.json (全履歴)
"""
import os
import sys
import json
import hashlib
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml
import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

# ---- 設定 ----
ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "sources.yaml"
STATE_FILE = ROOT / "state" / "seen.json"
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
(ROOT / "state").mkdir(exist_ok=True)

USER_AGENT = "Mozilla/5.0 (compatible; EduIntelBot/1.0; +https://example.com)"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "ja"}
REQ_TIMEOUT = 20
MAX_PER_SOURCE = 30  # 1ソースから取る上限
RECENT_DAYS = 7      # この日数以内の記事のみ対象


def load_sources():
    with open(SOURCES_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"seen_ids": [], "last_run": None}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def article_id(url):
    """URLからユニークID生成"""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def parse_date(s):
    """日付文字列を datetime に変換 (失敗したらNone)"""
    if not s:
        return None
    try:
        return date_parser.parse(s)
    except Exception:
        return None


def is_recent(dt, days=RECENT_DAYS):
    if not dt:
        return True  # 日付不明は採用
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=None)
    else:
        dt = dt.astimezone().replace(tzinfo=None)
    return (datetime.now() - dt) <= timedelta(days=days)


# ---- RSS収集 ----
def fetch_rss(source):
    print(f"[RSS] {source['name']}: {source['url']}")
    try:
        feed = feedparser.parse(source["url"], request_headers=HEADERS)
    except Exception as e:
        print(f"  ERROR: {e}")
        return []
    out = []
    for entry in feed.entries[:MAX_PER_SOURCE]:
        url = entry.get("link", "")
        if not url:
            continue
        title = entry.get("title", "").strip()
        published = entry.get("published") or entry.get("updated") or ""
        dt = parse_date(published)
        if dt and not is_recent(dt):
            continue
        summary = re.sub(r"<[^>]+>", "", entry.get("summary", ""))[:500]
        out.append({
            "id": article_id(url),
            "url": url,
            "title": title,
            "raw_summary": summary,
            "published_at": dt.isoformat() if dt else None,
            "source_id": source["id"],
            "source_name": source["name"],
            "default_category": source.get("default_category", "general"),
        })
    return out


# ---- HTMLスクレイピング ----
def fetch_html_listing(source):
    print(f"[HTML] {source['name']}: {source['url']}")
    try:
        r = requests.get(source["url"], headers=HEADERS, timeout=REQ_TIMEOUT)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
    except Exception as e:
        print(f"  ERROR: {e}")
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    selector = source.get("selector", "a")
    base_filter = source.get("base_filter")
    base_url = source["url"]
    out = []
    seen_urls = set()
    for a in soup.select(selector):
        href = a.get("href", "").strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        full_url = urljoin(base_url, href)
        if base_filter and base_filter not in full_url:
            continue
        # PDFやアーカイブ系は教育情報なのでOKだが、内部の上下ナビは除外
        title = a.get_text(strip=True)
        if not title or len(title) < 5:
            continue
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)
        out.append({
            "id": article_id(full_url),
            "url": full_url,
            "title": title,
            "raw_summary": "",
            "published_at": None,  # 後で取得試行
            "source_id": source["id"],
            "source_name": source["name"],
            "default_category": source.get("default_category", "general"),
        })
        if len(out) >= MAX_PER_SOURCE:
            break
    return out


# ---- 検索ベース収集 (Tavily / Brave / 代替) ----
def fetch_search(source):
    """
    Tavily APIまたはBrave Search APIを使った検索ベースの新着発見。
    環境変数 TAVILY_API_KEY または BRAVE_API_KEY が必要。
    """
    print(f"[SEARCH] {source['name']}")
    out = []
    tavily_key = os.environ.get("TAVILY_API_KEY")
    brave_key = os.environ.get("BRAVE_API_KEY")
    if not (tavily_key or brave_key):
        print("  検索APIキー未設定 - スキップ")
        return out
    for q in source.get("queries", []):
        try:
            if tavily_key:
                results = tavily_search(q, tavily_key)
            else:
                results = brave_search(q, brave_key)
        except Exception as e:
            print(f"  search error: {e}")
            continue
        for r in results[:5]:
            url = r.get("url", "")
            if not url:
                continue
            out.append({
                "id": article_id(url),
                "url": url,
                "title": r.get("title", "")[:200],
                "raw_summary": (r.get("content") or r.get("description") or "")[:500],
                "published_at": r.get("published") or None,
                "source_id": source["id"],
                "source_name": source["name"],
                "default_category": source.get("default_category", "general"),
            })
    return out


def tavily_search(query, key):
    r = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": key,
            "query": query,
            "search_depth": "basic",
            "topic": "general",
            "max_results": 5,
            "days": RECENT_DAYS,
            "include_domains": [],
        },
        timeout=REQ_TIMEOUT,
    )
    r.raise_for_status()
    return r.json().get("results", [])


def brave_search(query, key):
    r = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers={"X-Subscription-Token": key, "Accept": "application/json"},
        params={"q": query, "freshness": f"pd{RECENT_DAYS}d", "count": 5, "country": "JP"},
        timeout=REQ_TIMEOUT,
    )
    r.raise_for_status()
    return [
        {"url": x["url"], "title": x.get("title"), "content": x.get("description")}
        for x in r.json().get("web", {}).get("results", [])
    ]


# ---- 本文取得 (要約用) ----
def fetch_article_body(url, max_chars=4000):
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQ_TIMEOUT)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
    except Exception:
        return ""
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    # 本文抽出 (article, main, または #main)
    main = soup.find("article") or soup.find("main") or soup.find(id="main") or soup.body
    if not main:
        return ""
    text = re.sub(r"\s+", " ", main.get_text(" ", strip=True))
    return text[:max_chars]


# ---- Claude APIによる要約 + カテゴリ分類 ----
def summarize_with_claude(article, body):
    """
    Anthropic API経由で2-3行要約とカテゴリ判定を取得
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # APIキー未設定時はrule-basedのみ
        article["summary"] = (article.get("raw_summary") or article["title"])[:200]
        article["category"] = classify_by_keyword(article, body)
        article["importance"] = score_importance(article, body)
        return article

    prompt = f"""以下は教育向け自治体ビジネスのリサーチ情報です。営業担当者向けに重要なポイントを抽出してください。

タイトル: {article['title']}
ソース: {article['source_name']}
本文 (抜粋): {body[:3000]}

以下のJSON形式で出力してください (他の文章は不要):
{{
  "summary": "営業担当者向けに2-3行 (合計150文字以内) で要約。具体的な自治体名・サービス名・金額など事実情報を優先",
  "category": "giga | komuDX | security | case | mext | general のうち最も適切なもの",
  "importance": 1-5 の整数 (5が最重要),
  "tags": ["関連キーワードを3-5個", "..."]
}}"""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 400,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        r.raise_for_status()
        text = r.json()["content"][0]["text"].strip()
        # JSONブロック抽出
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            article["summary"] = data.get("summary", "").strip()
            article["category"] = data.get("category", article["default_category"])
            article["importance"] = int(data.get("importance", 3))
            article["tags"] = data.get("tags", [])
        else:
            article["summary"] = text[:200]
            article["category"] = article["default_category"]
            article["importance"] = 3
            article["tags"] = []
    except Exception as e:
        print(f"  Claude API error: {e}")
        article["summary"] = (article.get("raw_summary") or article["title"])[:200]
        article["category"] = classify_by_keyword(article, body)
        article["importance"] = score_importance(article, body)
        article["tags"] = []
    return article


def classify_by_keyword(article, body):
    """フォールバック分類: キーワードマッチでカテゴリ決定"""
    text = (article.get("title", "") + " " + body[:1000])
    sources = load_sources()
    rules = sources.get("classification_keywords", {})
    scores = {cat: 0 for cat in rules.keys()}
    for cat, kws in rules.items():
        for kw in kws:
            if kw in text:
                scores[cat] += 1
    best = max(scores.items(), key=lambda x: x[1])
    if best[1] > 0:
        return best[0]
    return article.get("default_category", "general")


def score_importance(article, body):
    """ヒューリスティック重要度スコア"""
    score = 3
    text = article.get("title", "") + body[:1000]
    if any(kw in text for kw in ["文部科学省", "文科省", "通知", "ガイドライン"]):
        score += 1
    if any(kw in text for kw in ["導入", "採用", "共同調達", "落札", "入札"]):
        score += 1
    if any(kw in text for kw in ["都道府県", "市", "区", "町", "教育委員会"]):
        score += 1
    return min(5, score)


# ---- メイン ----
def run():
    print(f"=== 教育自治体情報収集 開始 {datetime.now().isoformat()} ===")
    sources = load_sources()
    state = load_state()
    seen_ids = set(state.get("seen_ids", []))

    candidates = []
    for src in sources["sources"]:
        if not src.get("enabled", True):
            continue
        try:
            if src["type"] == "rss":
                items = fetch_rss(src)
            elif src["type"] == "html":
                items = fetch_html_listing(src)
            elif src["type"] == "search":
                items = fetch_search(src)
            else:
                continue
            print(f"  -> {len(items)} items")
            candidates.extend(items)
        except Exception as e:
            print(f"  source error: {e}")

    # URL重複排除
    by_id = {}
    for item in candidates:
        if item["id"] in seen_ids:
            continue
        if item["id"] not in by_id:
            by_id[item["id"]] = item
    new_articles = list(by_id.values())
    print(f"\n本日の新着: {len(new_articles)}件 (重複排除後)")

    # 各記事の本文取得 + 要約 + カテゴリ分類
    enriched = []
    for i, art in enumerate(new_articles, 1):
        print(f"[{i}/{len(new_articles)}] enriching: {art['title'][:50]}")
        body = fetch_article_body(art["url"])
        art = summarize_with_claude(art, body)
        art["fetched_at"] = datetime.now().isoformat()
        enriched.append(art)
        time.sleep(0.5)  # レート制限対策

    # 重要度でソート
    enriched.sort(key=lambda x: (-x.get("importance", 3), x.get("published_at") or ""))

    # 保存
    today = datetime.now().strftime("%Y%m%d")
    today_file = DATA_DIR / f"articles_{today}.json"
    with open(today_file, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)
    print(f"本日分: {today_file}")

    # 全履歴更新
    all_file = DATA_DIR / "all_articles.json"
    if all_file.exists():
        with open(all_file, encoding="utf-8") as f:
            all_articles = json.load(f)
    else:
        all_articles = []
    all_articles = enriched + all_articles
    # 90日分のみ保持
    cutoff = datetime.now() - timedelta(days=90)
    all_articles = [
        a for a in all_articles
        if not a.get("fetched_at") or parse_date(a["fetched_at"]) > cutoff.replace(tzinfo=None) if parse_date(a["fetched_at"]) else True
    ]
    with open(all_file, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)
    print(f"全履歴: {all_file} ({len(all_articles)}件)")

    # state更新
    seen_ids.update(a["id"] for a in enriched)
    # 90日以上前のIDは消す (sizeが大きくなりすぎないように)
    state["seen_ids"] = list(seen_ids)[-5000:]
    state["last_run"] = datetime.now().isoformat()
    save_state(state)
    print("=== 完了 ===")
    return enriched


if __name__ == "__main__":
    run()
