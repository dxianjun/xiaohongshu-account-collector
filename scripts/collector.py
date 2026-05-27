#!/usr/bin/env python3
"""
小红书行业账号ID采集工具 — 核心采集引擎
通过 Playwright 浏览器自动化采集小红书用户 ID 和主页链接

用法:
  python collector.py --keywords "健身,瑜伽" --output result.csv
  python collector.py --keywords-file keywords.txt --format json
  python collector.py --keywords "健身" --format md --output result.md
"""

import argparse
import asyncio
import csv
import json
import os
import random
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional

from playwright.async_api import async_playwright, Browser, Page

# ============================================================
# 配置
# ============================================================

@dataclass
class Config:
    keywords: List[str] = field(default_factory=list)
    max_scroll: int = 20          # 每个关键词最大翻页次数
    min_delay: float = 2.0        # 操作最小延迟(秒)
    max_delay: float = 5.0        # 操作最大延迟(秒)
    headless: bool = True         # 无头模式
    output_format: str = "csv"    # csv 或 json
    output_path: str = "result.csv"
    cookie_file: str = "cookies.json"


# ============================================================
# 采集引擎
# ============================================================

class XiaoHongShuCollector:
    """小红书账号采集器"""

    def __init__(self, config: Config):
        self.config = config
        self.browser: Optional[Browser] = None
        self.results: List[dict] = []
        self.seen_ids: set = set()  # 去重

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def launch(self):
        p = await async_playwright().start()
        self.browser = await p.chromium.launch(
            headless=self.config.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
        )

    async def close(self):
        if self.browser:
            await self.browser.close()

    async def random_delay(self, min_s=None, max_s=None):
        delay = random.uniform(
            min_s or self.config.min_delay,
            max_s or self.config.max_delay
        )
        await asyncio.sleep(delay)

    async def create_page(self) -> Page:
        context = await self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ])
        )

        # 加载cookies（如果存在）
        if os.path.exists(self.config.cookie_file):
            with open(self.config.cookie_file, "r") as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)

        page = await context.new_page()
        return page

    async def search_users(self, page: Page, keyword: str):
        """搜索用户并采集"""
        print(f"[搜索] 关键词: {keyword}")

        # 访问小红书搜索页
        search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_notes&type=user"
        await page.goto(search_url, wait_until="networkidle", timeout=30000)
        await self.random_delay(3, 6)

        # 等待搜索结果加载
        try:
            await page.wait_for_selector(".user-item, .user-card, [class*='user']", timeout=10000)
        except:
            print(f"  [警告] 关键词 '{keyword}' 未找到用户结果，尝试滚动...")

        collected = 0
        for scroll_round in range(self.config.max_scroll):
            # 提取当前页用户信息
            users = await self._extract_users(page)
            new_count = 0
            for user in users:
                uid = user.get("user_id", "")
                if uid and uid not in self.seen_ids:
                    self.seen_ids.add(uid)
                    self.results.append(user)
                    new_count += 1

            collected += new_count
            if new_count > 0:
                print(f"  [采集] 第{scroll_round+1}轮: +{new_count} 位用户 (总计: {collected})")

            # 滚动加载更多
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self.random_delay(1.5, 3.5)

            # 检查是否到底了
            prev_height = await page.evaluate("document.body.scrollHeight")
            await asyncio.sleep(2)
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == prev_height and scroll_round > 3:
                print(f"  [结束] 已滚动到底，停止")
                break

        print(f"  [完成] 关键词 '{keyword}' 共采集 {collected} 位用户")
        return collected

    async def _extract_users(self, page: Page) -> List[dict]:
        """从页面提取用户信息"""
        users = []

        # 尝试多种选择器提取
        try:
            # 方法1: 搜索用户卡片
            cards = await page.query_selector_all("[class*='user-item'], [class*='user-card'], [class*='user']")
            for card in cards:
                try:
                    # 提取用户ID（从链接中）
                    link_el = await card.query_selector("a[href*='xhslink'], a[href*='xiaohongshu'], a")
                    if link_el:
                        href = await link_el.get_attribute("href") or ""
                    else:
                        href = ""

                    # 提取昵称
                    name_el = await card.query_selector("[class*='name'], [class*='title'], h3, h4")
                    nickname = await name_el.inner_text() if name_el else ""
                    nickname = nickname.strip()

                    # 从 href 提取用户ID
                    user_id = self._extract_user_id(href)

                    if user_id:
                        users.append({
                            "user_id": user_id,
                            "nickname": nickname,
                            "profile_url": f"https://www.xiaohongshu.com/user/profile/{user_id}",
                            "source_keyword": "",
                        })
                except:
                    continue

            # 方法2: 直接解析整个页面链接
            if not users:
                links = await page.evaluate("""
                    () => {
                        const items = [];
                        document.querySelectorAll('a[href*="/user/profile/"]').forEach(a => {
                            const href = a.href;
                            const match = href.match(/\\/user\\/profile\\/([^/?&]+)/);
                            if (match) {
                                const card = a.closest('[class*="user"]') || a.parentElement;
                                const name = card?.querySelector('[class*="name"], [class*="title"]');
                                items.push({
                                    user_id: match[1],
                                    nickname: name ? name.innerText.trim() : '',
                                    profile_url: href.split('?')[0]
                                });
                            }
                        });
                        return items;
                    }
                """)
                for item in links:
                    if item.get("user_id") and item["user_id"] not in self.seen_ids:
                        users.append({
                            "user_id": item["user_id"],
                            "nickname": item.get("nickname", ""),
                            "profile_url": item.get("profile_url", f"https://www.xiaohongshu.com/user/profile/{item['user_id']}"),
                            "source_keyword": "",
                        })

        except Exception as e:
            print(f"  [解析错误] {e}")

        return users

    def _extract_user_id(self, url: str) -> str:
        """从URL中提取用户ID"""
        import re
        if not url or not isinstance(url, str):
            return ""
        # xiaohongshu.com/user/profile/{id}
        match = re.search(r"/user/profile/([^/?&]+)", url)
        if match:
            return match.group(1)
        # xhslink.com/{id}
        match = re.search(r"xhslink\.com/([^/?&]+)", url)
        if match:
            return match.group(1)
        return ""

    def _save_markdown(self):
        """保存为Markdown格式"""
        lines = [
            "# 小红书账号采集结果\n",
            f"> 采集时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"> 关键词: {', '.join(self.config.keywords)}",
            f"> 共采集: {len(self.results)} 位用户\n",
            "| 序号 | 用户ID | 昵称 | 主页链接 | 来源关键词 |",
            "|:----:|:------:|:----:|:--------:|:----------:|",
        ]

        for i, r in enumerate(self.results, 1):
            user_id = r.get("user_id", "")
            nickname = r.get("nickname", "")
            profile_url = r.get("profile_url", "")
            keyword = r.get("source_keyword", "")
            lines.append(
                f"| {i} | `{user_id}` | {nickname} | [{profile_url}]({profile_url}) | {keyword} |"
            )

        with open(self.config.output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"   Markdown输出: {self.config.output_path}")

    async def collect(self):
        """执行采集任务"""
        print(f"🎯 开始小红书账号采集")
        print(f"   关键词: {', '.join(self.config.keywords)}")
        print(f"   最大翻页: {self.config.max_scroll}")
        print()

        await self.launch()

        for keyword in self.config.keywords:
            page = await self.create_page()
            try:
                await self.search_users(page, keyword)
            except Exception as e:
                print(f"  [错误] 关键词 '{keyword}' 采集失败: {e}")
            finally:
                await page.close()
            await self.random_delay(3, 6)

        print(f"\n✅ 采集完成! 共采集 {len(self.results)} 位用户")
        self._save_results()

    def _save_results(self):
        """保存结果"""
        # 补全 source_keyword
        for r in self.results:
            if not r.get("source_keyword"):
                r["source_keyword"] = ""

        if self.config.output_format == "csv":
            with open(self.config.output_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=["user_id", "nickname", "profile_url", "source_keyword"])
                writer.writeheader()
                writer.writerows(self.results)
            print(f"   CSV输出: {self.config.output_path}")

        elif self.config.output_format == "json":
            with open(self.config.output_path, "w", encoding="utf-8") as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
            print(f"   JSON输出: {self.config.output_path}")

        elif self.config.output_format == "md":
            self._save_markdown()

        # 也打印前5条预览
        print(f"\n   预览（前5条）:")
        for r in self.results[:5]:
            print(f"     {r['user_id']} | {r['nickname']} | {r['profile_url']}")


# ============================================================
# CLI 入口
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(description="小红书行业账号ID采集工具")
    parser.add_argument("--keywords", "-k", type=str, help="关键词，逗号分隔，如: 健身,瑜伽")
    parser.add_argument("--keywords-file", type=str, help="关键词文件，每行一个")
    parser.add_argument("--output", "-o", type=str, default="result.csv", help="输出文件路径")
    parser.add_argument("--format", "-f", type=str, choices=["csv", "json", "md"], default="csv", help="输出格式 (csv/json/md)")
    parser.add_argument("--max-scroll", type=int, default=20, help="每个关键词最大翻页次数")
    parser.add_argument("--headless", action="store_true", default=True, help="无头模式")
    parser.add_argument("--no-headless", action="store_false", dest="headless", help="显示浏览器")
    parser.add_argument("--cookie-file", type=str, default="cookies.json", help="Cookie文件路径")
    return parser.parse_args()


def load_keywords(args) -> List[str]:
    keywords = []
    if args.keywords:
        keywords.extend([k.strip() for k in args.keywords.split(",") if k.strip()])
    if args.keywords_file:
        with open(args.keywords_file, "r", encoding="utf-8") as f:
            keywords.extend([line.strip() for line in f if line.strip()])
    return keywords


async def main():
    args = parse_args()
    keywords = load_keywords(args)

    if not keywords:
        print("❌ 请提供关键词: --keywords 或 --keywords-file")
        sys.exit(1)

    config = Config(
        keywords=keywords,
        max_scroll=args.max_scroll,
        headless=args.headless,
        output_format=args.format,
        output_path=args.output,
        cookie_file=args.cookie_file,
    )

    # 检查 Playwright 是否已安装
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ 请先安装 playwright: pip install playwright && playwright install chromium")
        sys.exit(1)

    async with XiaoHongShuCollector(config) as collector:
        await collector.collect()


if __name__ == "__main__":
    asyncio.run(main())
