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

if __name__ == "__main__":
    with open("data/config.json") as f:
        config_json = f.read()

    df = pd.read_csv("data/Artist.csv", dtype=str)
    profile_urls = []
    # 修改为读取twitter_url列
    for url in df["twitter_url"].dropna():
        if ";" in url:
            profile_urls.extend([u.strip() for u in url.split(";") if u.strip()])
        else:
            profile_urls.append(url.strip())

    print(f"待处理的链接: {len(profile_urls)}")

    # 访问速率限制，每组之间等待5秒
    RATE_LIMIT_SECONDS = 5
    BATCH_SIZE = 2  # 每次只处理2个URL


    def chunked(lst, n):
        """将列表每n个元素分一组"""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    with open("twitter_profiles.csv", "w", newline='', encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["twitter_name", "twitter_id", "twitter_url"])
        writer.writeheader()

        for group in chunked(profile_urls, BATCH_SIZE):
            results = asyncio.run(scrape_multiple_profiles(group, config_json))
            for url, data in results.items():
                twitter_id = urlparse(url).path.strip("/")
                # 一边获取一边写入csv
                writer.writerow({
                    "twitter_name": data["display_name"] if data else "N/A",
                    "twitter_id": twitter_id,
                    "twitter_url": url
                })
                csvfile.flush()

                print(f"URL: {url}")
                print(f"Display Name: {data['display_name'] if data else 'N/A'}")
                print("-" * 40)
            
            if len(profile_urls) > BATCH_SIZE:  # 如果有多组才需要等待
                print(f"等待 {RATE_LIMIT_SECONDS} 秒钟，准备下一批请求...")
                time.sleep(RATE_LIMIT_SECONDS)
                
    print("抓取完成，数据已写入 twitter_profiles.csv")