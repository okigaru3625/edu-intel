# 本番セットアップ手順書

このドキュメントの通りに進めれば、平日朝9時に**自動で**メールが届き、御社ドメインのまとめサイトが更新される運用になります。所要時間: 約60-90分。

## 0. 全体像

```
[GitHub Actions cron] → [Python収集スクリプト] → [Claude APIで要約]
                              ↓
                    [data/all_articles.json 更新]
                              ↓
              ┌─────────────┴──────────────┐
              ↓                              ↓
    [HTMLサイト生成]                  [メールHTML生成]
              ↓                              ↓
    [GitHub Pages → 御社ドメイン]    [SMTP自動送信]
```

## 1. 事前に用意するもの

| # | アイテム | 取得方法 | 用途 |
|---|---|---|---|
| 1 | GitHubアカウント | github.com で無料登録 | スクリプト・自動実行基盤 |
| 2 | Anthropic APIキー | console.anthropic.com → API Keys | 記事要約・カテゴリ分類 (Claude Haiku使用、月額~$5想定) |
| 3 | SMTP情報 | Gmail (アプリパスワード) または SendGrid/Resend (推奨) | メール自動送信 |
| 4 | 御社ドメイン管理画面 | お名前.com / Cloudflare 等 | カスタムドメイン紐付け |
| 5 | (任意) Tavily APIキー | tavily.com — 無料枠1000検索/月 | 自治体導入事例の検索ベース発見 |

## 2. GitHubリポジトリ作成

1. github.com にログイン → 右上「+」→ New repository
2. リポジトリ名: `edu-intel` (任意)
3. **Private** を選択 (営業情報のため非公開推奨)
4. 「Create repository」

ローカルでこのフォルダ全体をリポジトリへpush:

```bash
cd /Users/munemitsu/Documents/Claude/Projects/営業必要情報の取得/edu_intel
git init
git add .
git commit -m "initial: 教育自治体インテリジェンス基盤"
git branch -M main
git remote add origin https://github.com/<あなたのユーザー名>/edu-intel.git
git push -u origin main
```

## 3. GitHub Secrets 設定

リポジトリ → Settings → Secrets and variables → Actions → New repository secret で以下を登録:

| Secret名 | 値 | 説明 |
|---|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-api03-...` | console.anthropic.com で取得 |
| `SMTP_HOST` | `smtp.gmail.com` 等 | (Gmail例: `smtp.gmail.com`) |
| `SMTP_PORT` | `587` | TLS。Gmailは587 |
| `SMTP_USER` | `myamanaka@okigaru.club` | 送信元アドレス |
| `SMTP_PASS` | アプリパスワード16桁 | Gmail2段階認証 → アプリパスワード生成 |
| `EMAIL_FROM` | `myamanaka@okigaru.club` | 送信元 |
| `EMAIL_TO` | `you@a.com,sales1@a.com,sales2@a.com` | カンマ区切りで複数指定 |
| `SITE_URL` | `https://intel.okigaru.club/` 等 | 後で決定 (まとめサイトURL) |
| `TAVILY_API_KEY` | (任意) | 自治体検索発見のため |

### Gmailアプリパスワードの取得方法

1. myaccount.google.com → セキュリティ
2. 2段階認証プロセスをON (済み済の場合スキップ)
3. 「アプリパスワード」を生成 → 16桁をコピー

> **代替案 (推奨)**: 業務利用なら **Resend** や **SendGrid** の方がGmailより配信レピュテーションが安定します。Resendは無料枠100通/日。

## 4. GitHub Pagesでサイト公開

1. リポジトリ → Settings → Pages
2. Source: **GitHub Actions**
3. 一度 Actions タブから `daily` ワークフローを手動実行 (workflow_dispatch)
4. 完了後、`https://<ユーザー名>.github.io/edu-intel/` でサイト表示確認

## 5. 御社ドメインへの紐付け

例: `intel.okigaru.club` をまとめサイトに使う場合

### ドメインDNSに以下を追加 (お名前.comやCloudflareの管理画面)

| Type | Name | Value |
|---|---|---|
| CNAME | intel | `<ユーザー名>.github.io` |

### GitHub側設定

1. リポジトリ → Settings → Pages → Custom domain → `intel.okigaru.club` 入力
2. DNS伝搬まで待つ (5分〜24時間)
3. 「Enforce HTTPS」にチェック
4. リポジトリのルートに `CNAME` ファイルが自動生成され、これがGitHub Pagesに使用される

設定が完了したら GitHub Secrets の `SITE_URL` を `https://intel.okigaru.club/` に更新。

## 6. 動作確認

1. Actions タブ → `daily` → Run workflow をクリック
2. ログを確認 (5-10分で完了)
3. 朝9時メールが指定アドレス宛に届くか確認
4. まとめサイトが更新されているか確認

## 7. 平日朝9時の自動実行

`.github/workflows/daily.yml` の `cron: '0 0 * * 1-5'` で **JST 9:00 月-金** に自動実行されます。

> ⚠️ GitHub Actions cronは数分の遅延があります (公式仕様)。9時5分頃届くこともあります。

## 8. 運用上のチューニング

### ノイズが多い場合
- `sources.yaml` で `enabled: false` にして問題ソースを停止
- `classification_keywords` を追加してフィルタを強化
- `collect.py` の `RECENT_DAYS` を変更 (現在7日)

### 重要記事の見逃しがある場合
- `sources.yaml` の `search` セクションにキーワードを追加
- 特定自治体を監視したい場合: `自治体名 教育委員会 site:都道府県名.lg.jp` のような検索クエリを追加

### 配信先を増やす場合
- GitHub Secrets `EMAIL_TO` をカンマ区切りで追加更新

## 9. コスト見積もり

| 項目 | 月額目安 |
|---|---|
| GitHub (Pages + Actions) | **無料** (Public/Private同等) |
| Anthropic API (Claude Haiku) | $3-10 (記事30件/日 × 22営業日) |
| Tavily Search | 無料枠 (1000検索/月) |
| ドメイン | 既存利用 |
| **合計** | **月額 約$5-10 (≒800-1500円)** |

## 10. トラブルシューティング

### メールが届かない
- GitHub Actions ログで SMTP エラー確認
- 受信側のスパムフォルダ確認
- Gmail アプリパスワード再生成

### サイトが更新されない
- Actions ログで `git push` エラー確認
- リポジトリ Settings → Actions → Workflow permissions が "Read and write" になっているか

### 記事が収集されない
- 各サイトのRSSが落ちている可能性 → `sources.yaml` の URL 確認
- ANTHROPIC_API_KEY がexpired/無効
