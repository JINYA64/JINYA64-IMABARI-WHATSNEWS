#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scrape_imabari_news.py

今治市公式サイトの更新情報ページ（whatsnew.html）を巡回し、
過去7日分のお知らせを抽出。各お知らせの詳細ページも取得して
簡易な要約（冒頭の本文を短くまとめたもの）を作り、
docs/news.json として書き出す。

GitHub Actions などから毎日1回実行することを想定している。
実行のたびに全件を作り直すので、当日分・翌日分の反映も自動で行われる。

依存: requests, beautifulsoup4
    pip install requests beautifulsoup4
"""

import json
import re
import time
import datetime
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.city.imabari.ehime.jp/whatsnew.html"
SITE_ROOT = "https://www.city.imabari.ehime.jp/"
OUTPUT_PATH = Path(__file__).parent / "docs" / "news.json"

# 今治市サイトへの負荷を抑えるための最低限のマナー設定
REQUEST_DELAY_SEC = 1.5
REQUEST_TIMEOUT = 15
HEADERS = {
    "User-Agent": "ImabariNewsBoardBot/1.0 (+personal project; contact: set-your-contact-here)"
}

DAYS_TO_KEEP = 7
MAX_SUMMARY_CHARS = 140

CATEGORY_RULES = [
    ("交通・航路", ["航路", "運航", "交通規制", "運休", "フェリー", "渡船"]),
    ("募集・イベント", ["募集", "開催", "講座", "研修", "説明会", "ワークショップ", "コンテスト", "フェスティバル"]),
    ("補助金・支援", ["補助", "助成", "応援金", "支援金", "給付"]),
    ("入札・プロポーザル", ["プロポーザル", "入札", "公募"]),
]


def guess_category(title: str) -> str:
    for cat, keywords in CATEGORY_RULES:
        if any(k in title for k in keywords):
            return cat
    return "お知らせ"


def fetch(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    return BeautifulSoup(resp.text, "html.parser")


def parse_whatsnew(soup: BeautifulSoup):
    """
    更新情報ページから (date, title, url, note) のリストを抽出する。
    サイト構造が変わった場合はここを直す。
    """
    items = []
    main = soup.find(id="main_container") or soup

    # 日付見出しの直後にリンク(または直後のテキスト)が続く構造をたどる
    date_pattern = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")

    for node in main.find_all(string=date_pattern):
        m = date_pattern.search(node)
        if not m:
            continue
        y, mo, d = map(int, m.groups())
        try:
            date = datetime.date(y, mo, d)
        except ValueError:
            continue

        # 日付の次に現れるリンクを本文として扱う
        container = node.parent
        link_el = None
        sib = container
        for _ in range(6):
            sib = sib.find_next(["a"]) if sib else None
            if sib is None:
                break
            link_el = sib
            break

        if link_el is None:
            continue

        title = link_el.get_text(strip=True)
        href = link_el.get("href", "")
        if not title or not href:
            continue
        url = urljoin(SITE_ROOT, href)
        items.append({"date": date.isoformat(), "title": title, "url": url})

    return items


def summarize_detail_page(url: str) -> str:
    """
    詳細ページ本文の冒頭を短く要約もどきにして返す。
    PDFや外部サイトは本文取得をスキップする。
    """
    if url.lower().endswith(".pdf"):
        return "（PDF資料）詳細は今治市サイトのPDFをご確認ください。"
    if "city.imabari.ehime.jp" not in url:
        return "（外部サイトの情報です）詳細はリンク先をご確認ください。"

    try:
        soup = fetch(url)
    except Exception as e:  # noqa: BLE001
        return f"（本文の取得に失敗しました: {e}）"

    main = soup.find(id="main_container") or soup
    # 見出しの次に来る最初のまとまった段落を本文とみなす
    paragraphs = [
        p.get_text(strip=True)
        for p in main.find_all(["p", "li"])
        if len(p.get_text(strip=True)) > 15
    ]
    text = " ".join(paragraphs[:2])
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "本文の要約を作成できませんでした。詳細はリンク先をご確認ください。"
    if len(text) > MAX_SUMMARY_CHARS:
        text = text[:MAX_SUMMARY_CHARS] + "…"
    return text


def main():
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=DAYS_TO_KEEP - 1)

    print(f"[INFO] fetching {BASE_URL}", file=sys.stderr)
    soup = fetch(BASE_URL)
    all_items = parse_whatsnew(soup)
    print(f"[INFO] parsed {len(all_items)} items total", file=sys.stderr)

    recent = [it for it in all_items if datetime.date.fromisoformat(it["date"]) >= cutoff]
    print(f"[INFO] {len(recent)} items within last {DAYS_TO_KEEP} days", file=sys.stderr)

    results = []
    for it in recent:
        print(f"[INFO] summarizing: {it['title'][:40]}", file=sys.stderr)
        summary = summarize_detail_page(it["url"])
        results.append({
            "date": it["date"],
            "category": guess_category(it["title"]),
            "title": it["title"],
            "summary": summary,
            "url": it["url"],
        })
        time.sleep(REQUEST_DELAY_SEC)

    payload = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "source": BASE_URL,
        "items": results,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[INFO] wrote {len(results)} items to {OUTPUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
