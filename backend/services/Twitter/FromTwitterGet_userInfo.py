import asyncio
import json
import logging
from typing import List, Optional, Dict
from bs4 import BeautifulSoup
import pandas as pd
from playwright.async_api import async_playwright
import csv
from urllib.parse import urlparse
import time

# 日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def scrape_twitter_profile_async(url: str, config_json: str) -> Optional[Dict[str, Optional[str]]]:
    """
    异步抓取 Twitter/X 用户主页信息（使用 Playwright）

    Args:
        url: 用户主页URL（如 https://x.com/username）
        config_json: 包含 webdriver_path（无用）、user_agents、proxy_pool 的JSON配置

    Returns:
        字典，包含 display_name 和 bio，失败则返回 None
    """
    try:
        config = json.loads(config_json)
        user_agents = config.get("user_agents", [])
        proxy_pool = config.get("proxy_pool", [])

        if not user_agents:
            logger.error("必须提供至少一个 User-Agent")
            return None

        user_agent = user_agents[0]  # 可随机选择
        proxy = proxy_pool[0] if proxy_pool else None

        logger.info(f"使用User-Agent: {user_agent}")
        logger.info(f"使用代理: {proxy}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, proxy={
                "server": proxy.get("http") or proxy.get("https")
            } if proxy else None)

            context = await browser.new_context(user_agent=user_agent)
            page = await context.new_page()

            logger.info(f"正在访问 {url} ...")
            response = await page.goto(url, timeout=30000)

            if not response or not response.ok:
                logger.error(f"页面加载失败: {response.status if response else 'No Response'}")
                return None

            await page.wait_for_selector('div[data-testid="UserName"]', timeout=30000)
            html = await page.content()

            soup = BeautifulSoup(html, 'html.parser')

            def safe_text(selector: str) -> Optional[str]:
                try:
                    elem = soup.select_one(selector)
                    return elem.text.strip() if elem else None
                except Exception as e:
                    logger.warning(f"解析元素失败: {selector} - {str(e)}")
                    return None

            return {
                "display_name": safe_text('div[data-testid="UserName"] span:first-child'),
            }

    except Exception as e:
        logger.error(f"抓取异常: {e}")
        return None
    
def scrape_twitter_profile(url: str, config_json: str) -> Optional[Dict[str, Optional[str]]]:
    return asyncio.run(scrape_twitter_profile_async(url, config_json))

async def scrape_multiple_profiles(urls: List[str], config_json: str):
    tasks = [scrape_twitter_profile_async(url, config_json) for url in urls]
    results = await asyncio.gather(*tasks)
    return dict(zip(urls, results))

async def scrape_multiple_profiles(urls, config):
    results = {}
    for url in urls:
        await asyncio.sleep(0.1) # Simulate network delay
        # Dummy data based on URL
        if "weibo.com/u/" in url:
            dummy_id = url.split("u/")[-1].split("/")[0]
            dummy_name = f"User_{dummy_id}"
        elif "weibo.com/" in url:
            dummy_id = url.split("/")[-1]
            dummy_name = f"Page_{dummy_id}"
        else:
            dummy_id = "N/A"
            dummy_name = "Unknown"
        results[url] = {"display_name": dummy_name, "id": dummy_id}
    return results

if __name__ == "__main__":
    with open("data/config.json") as f:
        config_json = f.read()

    # 读取原始数据
    df = pd.read_csv("data/Artist.csv", dtype=str)

    grouped_rows = []

    for idx, row in df.iterrows():
        raw_url = row.get("weibo_url", "")
        if pd.isna(raw_url) or not raw_url.strip():
            continue

        urls = [u.strip() for u in raw_url.split(";") if u.strip() and u.strip().startswith('*')]
        if urls:
            grouped_rows.append({
                "uni_id": row["uni_id"],
                "original_url_column_value": raw_url,
                "split_urls": urls,
                "original_weibo_name": row.get("weibo_name", ""),
                "original_weibo_id": row.get("weibo_id", "")
            })

    print(f"待处理的链接: {len(grouped_rows)}")

    # 访问速率限制，每组之间等待5秒
    RATE_LIMIT_SECONDS = 5
    BATCH_SIZE = 5

    def chunked(lst, n):
        """将列表每n个元素分一组"""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    # Add these variables to track progress
    total_batches = (len(grouped_rows) + BATCH_SIZE - 1) // BATCH_SIZE
    current_batch_number = 0

    # 修改为更新原始DataFrame
    for group in chunked(grouped_rows, BATCH_SIZE):
        current_batch_number += 1
        print(f"\n正在处理批次: {current_batch_number}/{total_batches}")

        # 1. 合并本组所有url
        all_urls = []
        row_url_map = []
        for row_data in group:
            all_urls.extend(row_data["split_urls"])
            row_url_map.append((row_data, list(row_data["split_urls"])))

        # 2. 并发抓取
        results = asyncio.run(scrape_multiple_profiles(all_urls, config_json))

        # 3. 更新DataFrame
        for row_data, urls_for_this_row in row_url_map:
            name_list = []
            id_list = []
            for url in urls_for_this_row:
                data = results.get(url)
                display_name = data["display_name"] if data and "display_name" in data else "N/A"
                name_list.append(display_name)

                if data and "id" in data and data["id"] != "N/A":
                    weibo_id = data["id"]
                else:
                    path = urlparse(url).path.strip