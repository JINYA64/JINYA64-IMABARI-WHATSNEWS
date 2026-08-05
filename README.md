# 今治市 更新情報ボード（自動更新版）

今治市公式サイトの [更新情報ページ](https://www.city.imabari.ehime.jp/whatsnew.html) を毎日自動で巡回し、
過去7日分のお知らせと簡易要約を `docs/news.json` に書き出して、
`docs/index.html`（電子掲示板）がそれを読み込んで表示する仕組みです。

Claude（このチャット）はブラウザ上のファイルとしてしか動けず、
サイトを定期的に見に行く「常駐処理」を自分では持てません。
そこで、無料で使える **GitHub Actions の定時実行（cron）** に
「毎日サイトを見に行く係」をやってもらう構成にしています。

```
[GitHub Actions（毎朝7:30 JST）]
      │  scrape_imabari_news.py を実行
      ▼
[docs/news.json を自動コミット]
      │
      ▼
[GitHub Pages で公開された docs/index.html]
      │  ブラウザが起動時＋5分おきに news.json を再取得
      ▼
[電子掲示板が最新のお知らせを表示]
```

## セットアップ手順

1. **GitHubにリポジトリを作成**し、このフォルダの中身一式（`scrape_imabari_news.py` /
   `.github/workflows/update-news.yml` / `docs/` フォルダ）をアップロードする。

2. **GitHub Pages を有効化**
   リポジトリの `Settings → Pages` で、公開元を `main` ブランチの `/docs` フォルダに設定する。
   数分後に `https://<ユーザー名>.github.io/<リポジトリ名>/` で掲示板が見られるようになる。

3. **Actions の実行を確認**
   `Actions` タブを開き、`今治市お知らせを毎日更新` ワークフローを一度「Run workflow」で手動実行してみる。
   成功すると `docs/news.json` が最新のお知らせに書き換えられてコミットされる。

4. あとは毎日 JST 7:30 に自動実行され、`docs/news.json` → 掲示板の表示が自動更新され続ける。

## 実行タイミングを変えたい場合

`.github/workflows/update-news.yml` の `cron` の値を変更する（UTC基準）。
例：JST 12:00 に実行したい場合 → `"0 3 * * *"`

## ローカルで試す場合

```bash
pip install requests beautifulsoup4
python scrape_imabari_news.py
# docs/news.json が更新されるので、docs/index.html をブラウザで開いて確認
```

## 要約をよりわかりやすくする（Claudeによる言い換え・任意）

デフォルトのままでも、詳細ページの「タイトル直後の説明文」を狙って抜き出すようになっているので
ある程度読みやすい要約になります。もう一段階、専門用語を避けたやさしい日本語に自動で
書き換えたい場合は、Anthropic APIキーを設定してください。

1. [console.anthropic.com](https://console.anthropic.com/) でAPIキーを発行する
2. GitHubのリポジトリで `Settings → Secrets and variables → Actions → New repository secret`
3. Name に `ANTHROPIC_API_KEY`、Secret にキーの値を貼り付けて保存
4. 次回のActions実行から、Claude（claude-haiku-4-5）が本文を読んで
   「2文以内・120字程度・やさしい日本語」の要約を自動生成するようになる

APIキーを設定しない場合は、①の抽出結果がそのまま使われます（費用もかかりません）。
コードにキーを直接書き込む必要はなく、GitHubのSecretsに保存したものが
実行時だけ安全に読み込まれます。

## サイト構造が変わったら

`parse_whatsnew()` は、更新情報ページの「日付テキストの直後に出てくるリンク」という
シンプルなルールで項目を拾っています。今治市サイトのHTML構造が変わると
うまく拾えなくなることがあるため、その際はこの関数を見直してください。
