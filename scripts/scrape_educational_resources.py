#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scrape_educational_resources.py
整合 Scrapling 高效網頁擷取、調適性結構解析與 Markdown 轉換模組
1. 支援純 HTTP Fetcher 與真人擬真 StealthyFetcher（遵守安全紅線，不破解 CAPTCHA）。
2. 提供自適應選擇器與 AI-targeted 內文抽取，過濾教育網站之頁尾、側欄與選單雜訊。
3. 無縫串接 check_curriculum.py，抓取後可直接進入三階漏斗審查並輸出檢核報告。
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import Optional, Dict

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

def fetch_web_curriculum(url: str, output_path: Optional[Path] = None, use_stealth: bool = False, css_selector: Optional[str] = None) -> str:
    """
    使用 Scrapling 擷取教育網站資源並轉換為乾淨的 Markdown 格式
    """
    try:
        from scrapling.fetchers import Fetcher, StealthyFetcher
    except ImportError:
        # 若未全域安裝，透過 uv 或提示執行
        raise ImportError("請使用 uv run 執行此程式，或安裝 scrapling: uv pip install 'scrapling[all]'")

    print(f"🌐 正在擷取教育資源：{url}")
    if use_stealth:
        print("🕵️ 啟用 Scrapling StealthyFetcher (抗阻斷/擬真瀏覽器模式)...")
        # 嚴格遵循 Guidelines：不繞過 CAPTCHA/Turnstile，純粹用於擬真 headers 與防反爬阻擋
        page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
    else:
        print("⚡ 啟用 Scrapling 高速 HTTP Fetcher (Chrome TLS 擬真)...")
        page = Fetcher.get(url, stealthy_headers=True)

    # 抽取目標區域或主體內文
    if css_selector:
        elements = page.css(css_selector)
        if elements:
            # 整合所有選中的節點
            raw_html = "".join([el.get() for el in elements])
        else:
            print(f"⚠️ 指定的 CSS Selector '{css_selector}' 未找到元素，回退至全局 body。")
            raw_html = page.body or ""
    else:
        # 優先尋找題庫或文章主體 container
        candidate_selectors = ["article", "main", ".exam-content", ".question-box", "#content", "body"]
        raw_html = ""
        for sel in candidate_selectors:
            el = page.css(sel)
            if el:
                raw_html = el[0].get()
                break
        if not raw_html:
            raw_html = page.body or ""

    # 使用 Scrapling 或 markdown 轉換器將 HTML 轉為精簡結構化 Markdown
    clean_markdown = html_to_curriculum_markdown(raw_html, page_title=page.css("title::text").get() or "擷取教材")

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(clean_markdown)
        print(f"💾 已儲存擷取之結構化教材 Markdown：{output_path}")

    return clean_markdown

def html_to_curriculum_markdown(html_content: str, page_title: str = "") -> str:
    """
    去除廣告與無關導覽列，轉換為專供三階審查之教育試題/教材 Markdown
    """
    # 移除 script, style, nav, footer, iframe
    clean = re.sub(r"<(script|style|nav|footer|header|aside|iframe)[^>]*>.*?</\1>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
    
    # 標籤轉換
    clean = re.sub(r"<h1[^>]*>(.*?)</h1>", r"# \1\n\n", clean, flags=re.IGNORECASE)
    clean = re.sub(r"<h2[^>]*>(.*?)</h2>", r"## \1\n\n", clean, flags=re.IGNORECASE)
    clean = re.sub(r"<h3[^>]*>(.*?)</h3>", r"### \1\n\n", clean, flags=re.IGNORECASE)
    clean = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", clean, flags=re.IGNORECASE)
    clean = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1\n", clean, flags=re.IGNORECASE)
    clean = re.sub(r"<br\s*/?>", r"\n", clean, flags=re.IGNORECASE)
    
    # 清理剩餘標籤
    clean = re.sub(r"<[^>]+>", "", clean)
    # 還原 HTML entities
    clean = clean.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    
    # 移除多餘空白行
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    body_text = "\n\n".join(lines)

    header = f"# 🌐 線上擷取教材資源：{page_title.strip()}\n\n"
    meta = "> [!NOTE] 來源說明\n> 此教材由 Scrapling 爬蟲引擎自動擷取自線上教育題庫/資源網，已去除雜訊並轉換為標準審查結構。\n\n"
    
    return header + meta + body_text

def run_pipeline(url: str, output_name: str, auto_review: bool = True):
    """
    端到端管線：Scrapling 擷取 -> 轉 Markdown -> 自動進入 check_curriculum.py 三階審查
    """
    raw_dir = WORKSPACE_ROOT / "scraped"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_file = raw_dir / f"{output_name}.md"

    md_content = fetch_web_curriculum(url, output_path=out_file)

    if auto_review:
        print("\n🚀 正在自動將擷取之教材送入三階漏斗審查機制...")
        from check_curriculum import process_file, load_or_build_corpus
        reviewed_dir = WORKSPACE_ROOT / "reviewed"
        corpus = load_or_build_corpus()
        process_file(out_file, reviewed_dir, corpus)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrapling 教育資源擷取與結構化轉換工具")
    parser.add_argument("url", help="目標網址（例如題庫網、線上教材資源頁）")
    parser.add_argument("--output", "-o", default="scraped_material", help="輸出檔名（不含副檔名，預設 scraped_material）")
    parser.add_argument("--stealth", action="store_true", help="啟用 StealthyFetcher 抗阻斷擬真模式")
    parser.add_argument("--selector", "-s", help="指定擷取之 CSS Selector")
    parser.add_argument("--no-review", action="store_true", help="僅擷取而不自動執行三階審查")
    args = parser.parse_args()

    run_pipeline(args.url, args.output, auto_review=not args.no_review)
