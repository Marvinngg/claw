#!/usr/bin/env python3
"""RSS 采集器 — Stage 1：纯 Python，不用 LLM

职责：
  1. 读取 feeds.json
  2. 并发拉取全部 RSS 源
  3. URL 去重 + 7 天回看窗口
  4. 输出新文章列表

用法:
  python3 feed_fetcher.py              # 采集全部源
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import feedparser

CLAW_DIR = Path(__file__).parent
FEEDS_JSON = CLAW_DIR / "feeds.json"
LAST_CHECK_FILE = CLAW_DIR / ".feeds-last-check"
READ_URLS_FILE = CLAW_DIR / ".feeds-read-urls"
NEW_ARTICLES_FILE = CLAW_DIR / ".feeds-new-articles.json"

LOOKBACK_DAYS = 7
FAIL_FILE = CLAW_DIR / ".feeds-fail-counts"
MAX_CONSECUTIVE_FAILS = 3  # 连续失败 3 次自动跳过

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[fetcher {ts}] {msg}")


def load_fail_counts() -> dict[str, int]:
    if FAIL_FILE.exists():
        try:
            return json.loads(FAIL_FILE.read_text())
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def save_fail_counts(counts: dict[str, int]):
    # 只保留有失败记录的
    active = {k: v for k, v in counts.items() if v > 0}
    FAIL_FILE.write_text(json.dumps(active))


def load_feeds_config() -> dict:
    with open(FEEDS_JSON, encoding="utf-8") as f:
        return json.load(f)


def load_last_check() -> float:
    if LAST_CHECK_FILE.exists():
        try:
            return float(LAST_CHECK_FILE.read_text().strip())
        except ValueError:
            return 0
    return 0


def save_last_check():
    LAST_CHECK_FILE.write_text(str(time.time()))


def load_read_urls() -> set[str]:
    if READ_URLS_FILE.exists():
        return set(READ_URLS_FILE.read_text().splitlines())
    return set()


def save_read_urls(urls: set[str]):
    recent = sorted(urls)[-5000:]
    READ_URLS_FILE.write_text("\n".join(recent))


async def fetch_feed(session: aiohttp.ClientSession, feed_info: dict) -> tuple[str, list[dict]]:
    """异步获取单个 RSS feed 并解析，返回 (name, articles)"""
    url = feed_info["url"]
    name = feed_info["name"]
    tags = feed_info.get("tags", [])

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                log(f"  {name}: HTTP {resp.status}")
                return name, []
            text = await resp.text()
    except Exception as e:
        log(f"  {name}: 获取失败 ({type(e).__name__})")
        return name, []

    feed = feedparser.parse(text)
    articles = []

    for entry in feed.entries[:10]:
        article = {
            "title": entry.get("title", "").strip(),
            "url": entry.get("link", "").strip(),
            "summary": _clean_summary(entry.get("summary", "")),
            "source": name,
            "tags": tags,
            "date": _parse_date(entry),
        }
        if article["title"] and article["url"]:
            articles.append(article)

    return name, articles


def _clean_summary(raw: str) -> str:
    import html
    from bs4 import BeautifulSoup
    text = BeautifulSoup(raw, "html.parser").get_text(separator=" ")
    text = html.unescape(text)
    text = " ".join(text.split())
    return text[:300]


def _parse_date(entry) -> str:
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                dt = datetime(*parsed[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                pass
    return ""


async def fetch_all(feeds: list[dict], read_urls: set[str]) -> list[dict]:
    """并发获取全部 feeds，URL 去重 + 7 天窗口 + 失败跟踪"""
    fail_counts = load_fail_counts()

    # 跳过连续失败的源
    active_feeds = []
    skipped = 0
    for f in feeds:
        if fail_counts.get(f["name"], 0) >= MAX_CONSECUTIVE_FAILS:
            skipped += 1
            continue
        active_feeds.append(f)
    if skipped:
        log(f"  跳过 {skipped} 个连续失败源")

    new_articles = []
    cutoff_ts = time.time() - LOOKBACK_DAYS * 86400

    # 用系统线程 DNS 解析器，兼容 Tailscale 等 DNS 代理环境
    connector = aiohttp.TCPConnector(resolver=aiohttp.resolver.ThreadedResolver())
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_feed(session, f) for f in active_feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            continue
        name, articles = result
        if not articles:
            fail_counts[name] = fail_counts.get(name, 0) + 1
            continue
        # 成功：重置失败计数
        fail_counts[name] = 0
        for article in articles:
            if article["url"] in read_urls:
                continue
            if article["date"]:
                try:
                    article_ts = datetime.fromisoformat(article["date"]).timestamp()
                    if article_ts < cutoff_ts:
                        continue
                except Exception:
                    pass
            new_articles.append(article)

    save_fail_counts(fail_counts)

    # 按时间倒序（最新的在前），无日期的排最后
    new_articles.sort(key=lambda a: a["date"] or "", reverse=True)
    return new_articles


async def run() -> list[dict]:
    """采集全部源，返回新文章列表"""
    config = load_feeds_config()
    feeds = config["feeds"]
    read_urls = load_read_urls()

    last_ts = load_last_check()
    if last_ts > 0:
        hours_ago = (time.time() - last_ts) / 3600
        log(f"上次采集: {hours_ago:.1f} 小时前")
    else:
        log("首次采集")

    log(f"并发拉取 {len(feeds)} 个源...")

    new_articles = await fetch_all(feeds, read_urls)
    log(f"获取到 {len(new_articles)} 篇新文章")

    # 保存结果
    NEW_ARTICLES_FILE.write_text(
        json.dumps(new_articles, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 只更新采集时间戳（供 heartbeat needs_feed_check 判断间隔）
    # 不标记已读——由调用方在学习完成后调用 mark_as_read()
    save_last_check()

    return new_articles


def mark_as_read(articles: list[dict]):
    """学习完成后标记文章为已读"""
    read_urls = load_read_urls()
    for a in articles:
        read_urls.add(a["url"])
    save_read_urls(read_urls)


async def main():
    articles = await run()
    for a in articles[:10]:
        print(f"  [{a['source']}] {a['title'][:60]}")
    if len(articles) > 10:
        print(f"  ... 共 {len(articles)} 篇")


if __name__ == "__main__":
    asyncio.run(main())
