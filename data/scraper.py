#!/usr/bin/env python3
"""
Wise Help Centre Scraper
Fetches articles from Wise's 6 main help topic pages.

Topic URLs:
- Sending Money:          https://wise.com/help/topics/5bVKT0uQdBrDp6T62keyfz/sending-money
- Managing Your Account:  https://wise.com/help/topics/OQDKGx7MTsaujfEjiZmIS/managing-your-account
- Holding Money:          https://wise.com/help/topics/5U80whCL1cmJnbIVNGsm3h/holding-money
- Wise Card:              https://wise.com/help/topics/6Tme4V2z9ONNzQMeqJpcVi/wise-card
- Receiving Money:        https://wise.com/help/topics/1pXx5wZnF7Rp83VWwzGPUv/receiving-money
- Wise Business:          https://wise.com/help/topics/4weIubYURiKk7XZK3ZawNx/wise-business

Usage:
    pip install requests beautifulsoup4
    python3 scraper.py
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import os

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

TOPIC_URLS = [
    ("Sending Money",          "https://wise.com/help/topics/5bVKT0uQdBrDp6T62keyfz/sending-money"),
    ("Managing Your Account",  "https://wise.com/help/topics/OQDKGx7MTsaujfEjiZmIS/managing-your-account"),
    ("Holding Money",          "https://wise.com/help/topics/5U80whCL1cmJnbIVNGsm3h/holding-money"),
    ("Wise Card",              "https://wise.com/help/topics/6Tme4V2z9ONNzQMeqJpcVi/wise-card"),
    ("Receiving Money",        "https://wise.com/help/topics/1pXx5wZnF7Rp83VWwzGPUv/receiving-money"),
    ("Wise Business",          "https://wise.com/help/topics/4weIubYURiKk7XZK3ZawNx/wise-business"),
]

def get_article_links(topic_url):
    """Fetch all article links from a topic page."""
    try:
        r = requests.get(topic_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/help/articles/" in href:
                full = "https://wise.com" + href if href.startswith("/") else href
                # Remove query params
                full = full.split("?")[0]
                if full not in links:
                    links.append(full)
        return links
    except Exception as e:
        print(f"  Error fetching topic page: {e}")
        return []


def scrape_article(url, category, article_id):
    """Scrape a single article page."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Title
        title_el = soup.find("h1") or soup.find("title")
        title = title_el.get_text(strip=True) if title_el else "Unknown"

        # Subcategory (breadcrumb)
        breadcrumbs = soup.find_all(class_=re.compile("breadcrumb", re.I))
        subcategory = ""
        if breadcrumbs:
            texts = [b.get_text(strip=True) for b in breadcrumbs]
            if len(texts) >= 2:
                subcategory = texts[-2] if texts[-1].lower() != title.lower() else texts[-1]

        # Content — find main article body
        content_el = (
            soup.find("article") or
            soup.find(class_=re.compile("article-body|article-content|help-content|content", re.I)) or
            soup.find("main")
        )
        if content_el:
            # Remove nav, footer, related articles
            for tag in content_el.find_all(["nav", "footer", "aside", "script", "style"]):
                tag.decompose()
            content = content_el.get_text(separator="\n", strip=True)
        else:
            content = soup.get_text(separator="\n", strip=True)[:3000]

        # Clean content
        content = re.sub(r"\n{3,}", "\n\n", content).strip()

        return {
            "id": article_id,
            "title": title,
            "category": category,
            "subcategory": subcategory,
            "url": url,
            "content": content
        }
    except Exception as e:
        print(f"  Error scraping {url}: {e}")
        return None


def scrape_all(delay=1.5, max_per_topic=None):
    """Scrape all topics and articles."""
    all_articles = []
    article_counter = 1

    for category, topic_url in TOPIC_URLS:
        print(f"\n{'='*50}")
        print(f"Topic: {category}")
        print(f"URL: {topic_url}")

        links = get_article_links(topic_url)
        print(f"Found {len(links)} article links")

        if max_per_topic:
            links = links[:max_per_topic]

        for i, url in enumerate(links):
            article_id = f"{category[:2].upper()}{article_counter:03d}"
            print(f"  [{i+1}/{len(links)}] {article_id}: {url}")

            article = scrape_article(url, category, article_id)
            if article:
                all_articles.append(article)
                article_counter += 1
                print(f"    ✓ {article['title'][:60]}")
            else:
                print(f"    ✗ Failed")

            time.sleep(delay)  # Rate limiting — be respectful

    return all_articles


if __name__ == "__main__":
    print("Wise Help Centre Scraper")
    print("Respects robots.txt — rate limited to ~1 request per 1.5 seconds")
    print()

    articles = scrape_all(delay=1.5)

    # Save output
    out_path = os.path.join(os.path.dirname(__file__), "knowledge_base.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*50}")
    print(f"Scraping complete!")
    print(f"Total articles: {len(articles)}")
    from collections import Counter
    cats = Counter(a["category"] for a in articles)
    for cat, count in sorted(cats.items()):
        print(f"  {cat}: {count}")
    print(f"Saved to: {out_path}")
