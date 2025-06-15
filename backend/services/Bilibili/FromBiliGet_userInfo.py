import asyncio
import json
import logging
from typing import List, Optional, Dict
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import csv
from urllib.parse import urlparse
import time
import pandas as pd

# 日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def scrape_bilibili_profile_async(url: str, config_json: str) -> Optional[Dict[str, Optional[str]]]:
    """
    异步抓取Bilibili用户主页信息（使用 Playwright）

    Args:
        url: 用户主页URL（如 https://space.bilibili.com/123456）
        config_json: 包含 user_agents 的JSON配置

    Returns:
        字典，包含 display_name，失败则返回 None
    """
    try:
        config = json.loads(config_json)
        user_agents = config.get("user_agents", [])

        if not user_agents:
            logger.error("必须提供至少一个 User-Agent")
            return None

        user_agent = user_agents[0]  # 可随机选择

        logger.info(f"使用User-Agent: {user_agent}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(user_agent=user_agent)
            page = await context.new_page()

            logger.info(f"正在访问 {url} ...")
            response = await page.goto(url, timeout=30000)

            if not response or not response.ok:
                logger.error(f"页面加载失败: {response.status if response else 'No Response'}")
                return None

            # 修改为Bilibili的选择器
            await page.wait_for_selector('span#h-name', timeout=30000)
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
                "display_name": safe_text('span#h-name'),
            }

    except Exception as e:
        logger.error(f"抓取异常: {e}")
        return None
    
def scrape_bilibili_profile(url: str, config_json: str) -> Optional[Dict[str, Optional[str]]]:
    return asyncio.run(scrape_bilibili_profile_async(url, config_json))

async def scrape_multiple_profiles(urls: List[str], config_json: str):
    tasks = [scrape_bilibili_profile_async(url, config_json) for url in urls]
    results = await asyncio.gather(*tasks)
    return dict(zip(urls, results))

if __name__ == "__main__":
    with open("data/config.json") as f:
        config_json = f.read()

    df = pd.read_csv("data/Artist.csv", dtype=str)  # 请确保文件路径和文件名正确
    
    grouped_rows = []

    for idx, raw_url in df["bili_url"].dropna().items():
        urls = [u.strip() for u in raw_url.split(";") if u.strip()]
        grouped_rows.append({
            "original_url": raw_url,
            "split_urls": urls
        })

    print(f"待处理的链接: {len(grouped_rows)}")

    # Bilibili反爬较严格，降低频率
    RATE_LIMIT_SECONDS = 8  # 每组之间等待8秒
    BATCH_SIZE = 3  # 每次只处理2个URL

    def chunked(lst, n):
        """将列表每n个元素分一组"""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    # 修改输出文件名和字段名
    with open("bilibili_profiles.csv", "w", newline='', encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["bili_name", "bili_id", "bili_url"])
        writer.writeheader()

        for group in chunked(grouped_rows, BATCH_SIZE):
            # 1. 合并本组所有url
            all_urls = []
            row_url_map = []
            for row in group:
                all_urls.extend(row["split_urls"])
                row_url_map.append((row, list(row["split_urls"])))  # 保留每行的url列表

            # 2. 并发抓取
            results = asyncio.run(scrape_multiple_profiles(all_urls, config_json))

            # 3. 按原始行写入
            for row, urls in row_url_map:
                name_list = []
                id_list = []
                for url in urls:
                    data = results.get(url)
                    display_name = data["display_name"] if data else "N/A"
                    name_list.append(display_name)
                    path = urlparse(url).path.strip("/")
                    bilibili_id = path.split('/')[-1] if not path.startswith('video') else "N/A"
                    id_list.append(bilibili_id)
                    print(f"URL: {url}")
                    print(f"Display Name: {display_name}")
                    print(f"Bilibili ID: {bilibili_id}")
                    print("-" * 40)
                writer.writerow({
                    "bili_name": ";".join(name_list),
                    "bili_id": ";".join(id_list),
                    "bili_url": row["original_url"]
                })
                csvfile.flush()

            if len(grouped_rows) > 1:
                print(f"等待 {RATE_LIMIT_SECONDS} 秒钟，准备下一批请求...")
                time.sleep(RATE_LIMIT_SECONDS)

print("抓取完成，数据已写入 bilibili_profiles.csv")