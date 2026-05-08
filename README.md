# 教育自治体ビジネス インテリジェンス

平日朝9時に自動で稼働し、教育向け自治体ビジネスに関する新着情報をメールとまとめサイトで配信するシステム。

## 監視対象

- **文部科学省** GIGAスクール / 校務DX / 教育情報セキュリティ通知・概算要求等
- **教育家庭新聞** (kknews.co.jp) 全記事
- **ICT教育ニュース** / **リシード** / **こどもとIT** / **日本教育新聞**
- **自治体導入事例** (検索ベースで全国の教育委員会の採用情報を発見)
- **ゼロトラスト・セキュリティ** ベンダー導入事例

## 出力

1. **平日朝9時のHTMLメール** (営業チーム宛)
   - 本日の新着件数
   - カテゴリ別に整理 (文科省 → GIGA → 校務DX → セキュリティ → 自治体事例)
   - 1記事につきタイトル + 2-3行要約 + ソース + 重要度
   - まとめサイトへのリンク

2. **まとめサイト** (御社ドメインで公開)
   - 過去90日分の全記事を蓄積
   - カテゴリフィルタ + 全文検索
   - 重要度ソート、自治体名/サービス名でドリルダウン
   - 本日の新着強調

## システム構成

```
.
├── sources.yaml              # 監視対象サイト・カテゴリルール
├── scripts/
│   ├── collect.py            # 収集・要約・カテゴリ判定
│   ├── render_site.py        # まとめサイトHTML生成
│   └── send_email.py         # メール本文生成・SMTP送信
├── data/                     # 記事JSON (履歴90日)
├── state/                    # 重複検知のシード
├── site/                     # 生成された静的HTML (GitHub Pagesにデプロイ)
├── .github/workflows/daily.yml  # 平日朝9時の自動実行 (JST)
└── docs/SETUP.md             # 本番デプロイ手順書
```

## クイックスタート

ローカル動作確認:

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python scripts/collect.py        # データ収集
python scripts/render_site.py    # サイト生成 → site/index.html
python scripts/send_email.py     # メールプレビュー → data/email_preview.html
```

本番デプロイ手順は [docs/SETUP.md](docs/SETUP.md) を参照。

## カスタマイズ

- 新しい情報源を追加: `sources.yaml` の `sources:` 配列に追加
- カテゴリ追加: `sources.yaml` の `categories:` に色とラベルを追加
- 検索クエリ調整: `sources.yaml` の `type: search` セクションを編集

## ライセンス

社内利用限定 - 第三者への配布禁止
