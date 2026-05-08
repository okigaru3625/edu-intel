#!/usr/bin/env python3
"""
まとめサイト (静的HTML) 生成
- data/all_articles.json から index.html を生成
- カテゴリ別フィルタ、検索、新着ハイライト
- 御社ドメインで配信できる単一HTML (依存なし)
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "all_articles.json"
SOURCES_FILE = ROOT / "sources.yaml"
SITE_DIR = ROOT / "site"
SITE_DIR.mkdir(exist_ok=True)


def load_articles():
    if not DATA_FILE.exists():
        return []
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_categories():
    with open(SOURCES_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f).get("categories", {})


def render(articles, categories, brand="教育自治体ビジネス インテリジェンス"):
    today = datetime.now().strftime("%Y年%m月%d日 (%a)")
    today_iso = datetime.now().strftime("%Y-%m-%d")

    # 本日の新着件数
    new_count = sum(
        1 for a in articles
        if a.get("fetched_at", "").startswith(datetime.now().strftime("%Y-%m-%d"))
    )

    # 過去7日間の件数
    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    week_count = sum(
        1 for a in articles
        if a.get("fetched_at", "") >= cutoff
    )

    # カテゴリ別件数 (週次)
    cat_counts = {}
    for a in articles:
        if a.get("fetched_at", "") >= cutoff:
            c = a.get("category", "general")
            cat_counts[c] = cat_counts.get(c, 0) + 1

    # 記事カードHTML生成
    cards_html = []
    for a in articles[:300]:  # 直近300件
        cat = a.get("category", "general")
        cat_def = categories.get(cat, {"label": cat, "color": "#6b7280", "icon": "📰"})
        is_new = a.get("fetched_at", "").startswith(datetime.now().strftime("%Y-%m-%d"))
        published = a.get("published_at") or a.get("fetched_at") or ""
        try:
            pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            pub_str = pub_dt.strftime("%Y-%m-%d")
        except Exception:
            pub_str = ""
        importance = a.get("importance", 3)
        stars = "★" * importance + "☆" * (5 - importance)
        tags_html = "".join(f'<span class="tag">{t}</span>' for t in a.get("tags", [])[:5])
        new_badge = '<span class="new-badge">NEW</span>' if is_new else ""
        cards_html.append(f"""
        <article class="card" data-category="{cat}" data-importance="{importance}" data-search="{(a.get('title','') + ' ' + a.get('summary','') + ' ' + a.get('source_name','')).lower()}">
          <div class="card-header">
            <span class="cat-badge" style="background:{cat_def['color']}20;color:{cat_def['color']};border-color:{cat_def['color']}40;">{cat_def['icon']} {cat_def['label']}</span>
            {new_badge}
            <span class="importance" title="重要度">{stars}</span>
          </div>
          <h3 class="card-title"><a href="{a['url']}" target="_blank" rel="noopener">{a.get('title','(タイトル不明)')}</a></h3>
          <p class="card-summary">{a.get('summary','')}</p>
          <div class="card-meta">
            <span class="source">{a.get('source_name','')}</span>
            <span class="date">{pub_str}</span>
          </div>
          <div class="tags">{tags_html}</div>
        </article>
        """)

    # カテゴリフィルタボタン
    cat_buttons = ['<button class="filter-btn active" data-filter="all">すべて</button>']
    for cid, cdef in categories.items():
        count = cat_counts.get(cid, 0)
        cat_buttons.append(
            f'<button class="filter-btn" data-filter="{cid}" style="--cat-color:{cdef["color"]}">'
            f'{cdef["icon"]} {cdef["label"]} <span class="count">{count}</span></button>'
        )

    html = HTML_TEMPLATE.format(
        brand=brand,
        today=today,
        today_iso=today_iso,
        new_count=new_count,
        week_count=week_count,
        total_count=len(articles),
        filter_buttons="\n".join(cat_buttons),
        cards="\n".join(cards_html),
        gen_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    out = SITE_DIR / "index.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"サイト生成: {out}")
    return out


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{brand}</title>
<meta name="description" content="自治体教育向けビジネスのための情報収集ダッシュボード">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📚</text></svg>">
<style>
:root {{
  --bg: #f8fafc;
  --surface: #ffffff;
  --border: #e2e8f0;
  --text: #0f172a;
  --text-muted: #64748b;
  --primary: #1e40af;
  --primary-light: #dbeafe;
  --shadow: 0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.03);
  --radius: 12px;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, "Hiragino Kaku Gothic ProN", "Yu Gothic", Meiryo, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
  font-size: 15px;
}}
header {{
  background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
  color: white;
  padding: 28px 32px;
  box-shadow: var(--shadow);
}}
header h1 {{ font-size: 22px; font-weight: 700; }}
header .subtitle {{
  font-size: 13px;
  opacity: 0.85;
  margin-top: 4px;
}}
.container {{ max-width: 1280px; margin: 0 auto; padding: 24px 32px; }}
.stats {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}}
.stat-card {{
  background: var(--surface);
  padding: 20px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
}}
.stat-label {{
  font-size: 12px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}}
.stat-value {{
  font-size: 32px;
  font-weight: 700;
  color: var(--primary);
  margin-top: 4px;
}}
.stat-value.accent {{ color: #ef4444; }}

.controls {{
  background: var(--surface);
  padding: 20px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  margin-bottom: 24px;
}}
.search-box {{
  width: 100%;
  padding: 12px 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 15px;
  margin-bottom: 16px;
  font-family: inherit;
}}
.search-box:focus {{
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-light);
}}
.filter-row {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}}
.filter-btn {{
  padding: 8px 14px;
  border: 1px solid var(--border);
  background: var(--surface);
  border-radius: 999px;
  cursor: pointer;
  font-size: 13px;
  font-family: inherit;
  transition: all 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}}
.filter-btn:hover {{ border-color: var(--primary); }}
.filter-btn.active {{
  background: var(--primary);
  color: white;
  border-color: var(--primary);
}}
.filter-btn .count {{
  background: rgba(0,0,0,0.08);
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}}
.filter-btn.active .count {{ background: rgba(255,255,255,0.25); }}

.cards {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}}
.card {{
  background: var(--surface);
  border-radius: var(--radius);
  border: 1px solid var(--border);
  padding: 20px;
  box-shadow: var(--shadow);
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
}}
.card:hover {{
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  border-color: var(--primary);
}}
.card.hidden {{ display: none; }}
.card-header {{
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}}
.cat-badge {{
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid;
}}
.new-badge {{
  background: #ef4444;
  color: white;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  animation: pulse 2s infinite;
}}
@keyframes pulse {{
  0%, 100% {{ opacity: 1; }}
  50% {{ opacity: 0.7; }}
}}
.importance {{
  font-size: 11px;
  color: #f59e0b;
  margin-left: auto;
  letter-spacing: 1px;
}}
.card-title {{
  font-size: 16px;
  font-weight: 600;
  line-height: 1.4;
  margin-bottom: 10px;
}}
.card-title a {{ color: var(--text); text-decoration: none; }}
.card-title a:hover {{ color: var(--primary); }}
.card-summary {{
  color: var(--text-muted);
  font-size: 14px;
  flex-grow: 1;
  margin-bottom: 12px;
}}
.card-meta {{
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-muted);
  border-top: 1px solid var(--border);
  padding-top: 10px;
  margin-bottom: 8px;
}}
.source {{ font-weight: 600; }}
.tags {{
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}}
.tag {{
  font-size: 11px;
  padding: 2px 8px;
  background: var(--bg);
  color: var(--text-muted);
  border-radius: 4px;
  border: 1px solid var(--border);
}}
.empty-state {{
  grid-column: 1 / -1;
  text-align: center;
  padding: 80px 20px;
  color: var(--text-muted);
}}
footer {{
  text-align: center;
  padding: 32px 16px;
  color: var(--text-muted);
  font-size: 12px;
}}
@media (max-width: 640px) {{
  .container {{ padding: 16px; }}
  header {{ padding: 20px 16px; }}
  .cards {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<header>
  <div style="max-width:1280px;margin:0 auto;">
    <h1>📚 {brand}</h1>
    <div class="subtitle">{today} 更新 · 文部科学省 · 教育家庭新聞 · 自治体導入事例 · ゼロトラスト・校務DX動向を毎営業日朝9時に集約</div>
  </div>
</header>

<div class="container">
  <div class="stats">
    <div class="stat-card">
      <div class="stat-label">本日の新着</div>
      <div class="stat-value accent">{new_count}<span style="font-size:16px;color:var(--text-muted);font-weight:400;">件</span></div>
    </div>
    <div class="stat-card">
      <div class="stat-label">直近7日間</div>
      <div class="stat-value">{week_count}<span style="font-size:16px;color:var(--text-muted);font-weight:400;">件</span></div>
    </div>
    <div class="stat-card">
      <div class="stat-label">アーカイブ総数</div>
      <div class="stat-value">{total_count}<span style="font-size:16px;color:var(--text-muted);font-weight:400;">件</span></div>
    </div>
  </div>

  <div class="controls">
    <input type="text" class="search-box" id="searchBox" placeholder="🔍 自治体名・サービス名・キーワードで検索 (例: ゼロトラスト、坂出市、Qubena)">
    <div class="filter-row">
      {filter_buttons}
    </div>
  </div>

  <div class="cards" id="cards">
    {cards}
  </div>
</div>

<footer>
  生成日時: {gen_at} · 教育自治体ビジネス情報収集システム
</footer>

<script>
const cards = document.querySelectorAll('.card');
const searchBox = document.getElementById('searchBox');
const filterBtns = document.querySelectorAll('.filter-btn');
let currentFilter = 'all';
let currentSearch = '';

function applyFilters() {{
  cards.forEach(card => {{
    const cat = card.dataset.category;
    const text = card.dataset.search;
    const matchCat = currentFilter === 'all' || cat === currentFilter;
    const matchSearch = !currentSearch || text.includes(currentSearch);
    card.classList.toggle('hidden', !(matchCat && matchSearch));
  }});
}}

filterBtns.forEach(btn => {{
  btn.addEventListener('click', () => {{
    filterBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentFilter = btn.dataset.filter;
    applyFilters();
  }});
}});

searchBox.addEventListener('input', e => {{
  currentSearch = e.target.value.toLowerCase();
  applyFilters();
}});
</script>
</body>
</html>
"""


def main():
    articles = load_articles()
    categories = load_categories()
    print(f"記事数: {len(articles)}")
    render(articles, categories)


if __name__ == "__main__":
    main()
