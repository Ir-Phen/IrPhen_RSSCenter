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
            browser = await p.chromium.launch(headless=True)
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

    df = pd.read_csv("data/Artist.csv", dtype=str)
    profile_urls = []
    # 修改为读取bilibili_url列
    for url in df["bili_url"].dropna():
        if ";" in url:
            profile_urls.extend([u.strip() for u in url.split(";") if u.strip()])
        else:
            profile_urls.append(url.strip())

    print(f"待处理的链接: {len(profile_urls)}")
    
    # Bilibili反爬较严格，降低频率
    RATE_LIMIT_SECONDS = 8  # 每组之间等待8秒
    BATCH_SIZE = 2  # 每次只处理2个URL

    def chunked(lst, n):
        """将列表每n个元素分一组"""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    # 修改输出文件名和字段名
    with open("bilibili_profiles.csv", "w", newline='', encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["bili_name", "bili_id", "bili_url"])
        writer.writeheader()

        for group in chunked(profile_urls, BATCH_SIZE):
            results = asyncio.run(scrape_multiple_profiles(group, config_json))
            for url, data in results.items():
                # 从URL中提取ID（B站ID是数字）
                path = urlparse(url).path.strip("/")
                # 处理多种URL格式：space.bilibili.com/123456 或 www.bilibili.com/video/BV...
                bilibili_id = path.split('/')[-1] if not path.startswith('video') else "N/A"
                
                # 一边获取一边写入csv
                writer.writerow({
                    "bili_name": data["display_name"] if data else "N/A",
                    "bili_id": bilibili_id,
                    "bili_url": url
                })
                csvfile.flush()

                print(f"URL: {url}")
                print(f"Display Name: {data['display_name'] if data else 'N/A'}")
                print(f"Bilibili ID: {bilibili_id}")
                print("-" * 40)
            
            if len(profile_urls) > BATCH_SIZE:  # 如果有多组才需要等待
                print(f"等待 {RATE_LIMIT_SECONDS} 秒钟，准备下一批请求...")
                time.sleep(RATE_LIMIT_SECONDS)

    print("抓取完成，数据已写入 bilibili_profiles.csv")