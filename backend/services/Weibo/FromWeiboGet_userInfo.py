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

async def scrape_weibo_profile_async(url: str, config_json: str) -> Optional[Dict[str, Optional[str]]]:
    """
    异步抓取微博用户主页信息（使用 Playwright）

    Args:
        url: 用户主页URL（如 https://weibo.com/username）
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
            # 移除代理设置
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=user_agent)
            page = await context.new_page()

            logger.info(f"正在访问 {url} ...")
            response = await page.goto(url, timeout=30000)

            if not response or not response.ok:
                logger.error(f"页面加载失败: {response.status if response else 'No Response'}")
                return None

            # 修改为微博的选择器
            await page.wait_for_selector('div.ProfileHeader_name_1KbBs', timeout=30000)
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
                "display_name": safe_text('div.ProfileHeader_name_1KbBs'),
            }

    except Exception as e:
        logger.error(f"抓取异常: {e}")
        return None
    
def scrape_weibo_profile(url: str, config_json: str) -> Optional[Dict[str, Optional[str]]]:
    return asyncio.run(scrape_weibo_profile_async(url, config_json))

async def scrape_multiple_profiles(urls: List[str], config_json: str):
    tasks = [scrape_weibo_profile_async(url, config_json) for url in urls]
    results = await asyncio.gather(*tasks)
    return dict(zip(urls, results))

if __name__ == "__main__":
    with open("data/config.json") as f:
        config_json = f.read()

    df = pd.read_csv("data/Artist.csv", dtype=str)
    profile_urls = []
    for url in df["weibo_url"].dropna():
        if ";" in url:
            profile_urls.extend([u.strip() for u in url.split(";") if u.strip()])
        else:
            profile_urls.append(url.strip())

    print(f"待处理的链接{len(profile_urls)}")
    # 降低访问频率，每组之间等待10秒
    RATE_LIMIT_SECONDS = 5
    BATCH_SIZE = 3  # 每次只处理1个URL

    def chunked(lst, n):
        """将列表每n个元素分一组"""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    # 修改输出文件名和字段名
    with open("weibo_profiles.csv", "w", newline='', encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["weibo_name", "weibo_id", "weibo_url"])
        writer.writeheader()

        for group in chunked(profile_urls, BATCH_SIZE):
            results = asyncio.run(scrape_multiple_profiles(group, config_json))
            for url, data in results.items():
                # 从URL中提取ID（最后路径部分）
                weibo_id = urlparse(url).path.strip("/").split('/')[-1]
                # 一边获取一边写入csv
                writer.writerow({
                    "weibo_name": data["display_name"] if data else "N/A",
                    "weibo_id": weibo_id,
                    "weibo_url": url
                })
                csvfile.flush()

                print(f"URL: {url}")
                print(f"Display Name: {data['display_name'] if data else 'N/A'}")
                print("-" * 40)
            
            if len(profile_urls) > BATCH_SIZE:  # 如果有多组才需要等待
                print(f"等待 {RATE_LIMIT_SECONDS} 秒钟，准备下一批请求...")
                time.sleep(RATE_LIMIT_SECONDS)

    print("抓取完成，数据已写入 weibo_profiles.csv")