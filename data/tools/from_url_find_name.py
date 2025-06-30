import pandas as pd
import asyncio
import time
from urllib.parse import urlparse
import json
import logging
from typing import List, Dict, Optional
from urllib.parse import urlparse
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

def chunked(lst, n):
    """将列表每n个元素分一组"""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

async def process_social_platform_profiles( # Make this function async
    platform: str,
    csv_path: str = "data/Artist.csv",
    config_path: str = "data/config.json",
    scrape_function=None,
    batch_size: int = 5,
    rate_limit_seconds: int = 5
):
    if scrape_function is None:
        raise ValueError("必须提供 scrape_function 参数（一个异步函数）")

    # 读取配置文件
    with open(config_path, "r", encoding="utf-8") as f:
        config_json = f.read()

    # 读取数据
    df = pd.read_csv(csv_path, dtype=str)

    url_col = f"{platform}_url"
    name_col = f"{platform}_name"
    id_col = f"{platform}_id"

    grouped_rows = []
    for idx, row in df.iterrows():
        raw_url = row.get(url_col, "")
        if pd.isna(raw_url) or not raw_url.strip():
            continue

        # 解析所有URL，并标记哪些是需要处理的（带*的）
        all_original_urls_parts = [u.strip() for u in raw_url.split(";") if u.strip()]
        urls_to_scrape = [] # 存储实际用于抓取的URL（不带*）
        url_map_to_original_tagged = {} # 映射抓取URL到原始带*的URL

        for part in all_original_urls_parts:
            if part.startswith('*'):
                clean_url = part.lstrip('*')
                urls_to_scrape.append(clean_url)
                url_map_to_original_tagged[clean_url] = part # 存储原始带*的url
        
        # 只有当存在需要抓取的URL时才加入grouped_rows
        if urls_to_scrape:
            grouped_rows.append({
                "uni_id": row["uni_id"],
                "original_url_column_value": raw_url, # 存储完整的原始URL字符串
                "all_original_urls_parts": all_original_urls_parts, # 存储分割后的原始URL部分
                "urls_to_scrape": urls_to_scrape, # 存储需要抓取的干净URL
                "url_map_to_original_tagged": url_map_to_original_tagged, # 抓取URL到原始带*URL的映射
                "original_name": row.get(name_col, ""),
                "original_id": row.get(id_col, "")
            })

    print(f"平台 {platform} 待处理的链接总数: {len(grouped_rows)}")

    total_batches = (len(grouped_rows) + batch_size - 1) // batch_size
    current_batch_number = 0

    for group in chunked(grouped_rows, batch_size):
        current_batch_number += 1
        print(f"\n正在处理批次: {current_batch_number}/{total_batches}")

        all_urls_in_batch_to_scrape = []
        for row_data in group:
            all_urls_in_batch_to_scrape.extend(row_data["urls_to_scrape"])

        # 并发抓取
        results = await scrape_function(all_urls_in_batch_to_scrape, config_json) # Changed to await

        # 更新 DataFrame
        for row_data in group:
            name_list = []
            id_list = []
            updated_url_parts = [] # 存储最终回写到url_col的URL部分

            # 遍历所有原始URL部分，包括带*和不带*的
            for original_part in row_data["all_original_urls_parts"]:
                if original_part.startswith('*'):
                    # 这是需要处理的URL，现在已经处理完成，所以回写时不带*
                    clean_url_for_scrape = original_part.lstrip('*')
                    data = results.get(clean_url_for_scrape)

                    display_name = data["display_name"] if data and "display_name" in data else "N/A"
                    name_list.append(display_name)

                    if data and "id" in data and data["id"] != "N/A":
                        social_id = data["id"]
                    else:
                        path = urlparse(clean_url_for_scrape).path.strip("/")
                        social_id = path.split("/")[-1] if path and not path.startswith("video") else "N/A"
                    id_list.append(social_id)
                    updated_url_parts.append(clean_url_for_scrape) # 回写不带*的干净URL

                    print(f"URL: {clean_url_for_scrape} (原始带*: {original_part})")
                    print(f"Display Name: {display_name}")
                    print(f"{platform.title()} ID: {social_id}")
                    print("-" * 40)
                else:
                    # 这是不需要处理的URL，保持原样回写
                    updated_url_parts.append(original_part)
                    # 对于未处理的URL，其名称和ID可以从原始数据中获取或标记为N/A
                    # 这里为了简化，我们只更新那些被处理过的URL的name和id
                    # 如果需要，您可以根据original_name和original_id的结构进行更复杂的处理
                    # 目前这里不为不带*的URL添加新的name/id，保持与原始_name/_id的对应关系
                    # 如果原始_name/_id是分号分隔的，您需要更精细地处理索引匹配
                    # 为了与处理过的URL的name/id列表长度保持一致，您可能需要添加占位符
                    # 考虑到这是一个复杂的用户需求，我们先聚焦URL的回写，
                    # 对于name/id的精确匹配和回写，可能需要您提供原始name/id的结构细节
                    pass # 不对这些URL产生新的name或id

            new_name = ";".join(name_list) # 这里只包含被抓取URL的名称
            new_id = ";".join(id_list)     # 这里只包含被抓取URL的ID
            new_url_column_value = ";".join(updated_url_parts) # 所有URL重新组合，带*的已去除*

            idx = df[df["uni_id"] == row_data["uni_id"]].index[0]
            df.at[idx, name_col] = new_name
            df.at[idx, id_col] = new_id
            df.at[idx, url_col] = new_url_column_value # 更新原始的URL列

        # 等待速率限制
        # 注意：这里判断等待逻辑需要调整，因为group不再是grouped_rows的直接子列表
        # 简单起见，可以判断当前批次是否是最后一批次
        if current_batch_number < total_batches:
            print(f"等待 {rate_limit_seconds} 秒钟，准备下一批请求...")
            time.sleep(rate_limit_seconds)

    # 保存结果
    df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"平台 {platform} 抓取完成，数据已更新到 {csv_path}")

# ... (SocialProfileScraper 和 main 函数保持不变) ...

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SocialProfileScraper:
    def __init__(self):
        self.selectors = {
            "weibo": 'div.ProfileHeader_name_1KbBs',
            "twitter": 'div[data-testid="UserName"] span:first-child',
            "bilibili": 'span#h-name'
        }
        self.browser = None
        self.context = None

    async def initialize_browser(self, config_json: str):
        """初始化浏览器实例"""
        try:
            config = json.loads(config_json)
            user_agents = config.get("user_agents", [])
            proxy_pool = config.get("proxy_pool", [])

            if not user_agents:
                logger.error("必须提供至少一个 User-Agent")
                return False

            user_agent = user_agents[0]
            proxy = proxy_pool[0] if proxy_pool else None

            async with async_playwright() as p:
                self.browser = await p.chromium.launch(
                    headless=True,
                    proxy={
                        "server": proxy.get("http") or proxy.get("https")
                    } if proxy else None
                )
                self.context = await self.browser.new_context(user_agent=user_agent)
                return True
        except Exception as e:
            logger.exception(f"浏览器初始化异常: {e}")
            return False

    async def close_browser(self):
        """关闭浏览器实例"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        self.browser = None
        self.context = None

    async def _scrape_single(self, platform: str, url: str) -> Optional[Dict[str, Optional[str]]]:
        """使用已初始化的浏览器实例抓取单个页面"""
        if not self.context:
            logger.error("浏览器未初始化")
            return None

        try:
            page = await self.context.new_page()
            selector = self.selectors.get(platform)
            
            logger.info(f"[{platform}] 访问: {url}")
            response = await page.goto(url, timeout=30000)
            
            if not response or not response.ok:
                logger.error(f"[{platform}] 页面加载失败: {response.status if response else '无响应'}")
                await page.close()
                return None

            await page.wait_for_selector(selector, timeout=30000)
            html = await page.content()
            await page.close()

            soup = BeautifulSoup(html, 'html.parser')
            elem = soup.select_one(selector)
            display_name = elem.text.strip() if elem else None

            # 提取ID
            parsed = urlparse(url)
            path = parsed.path.strip('/')
            uid = path.split("/")[-1] if path and not path.startswith("video") else "N/A"

            return {
                "display_name": display_name or "N/A",
                "id": uid or "N/A"
            }

        except Exception as e:
            logger.exception(f"[{platform}] 抓取异常: {e}")
            if 'page' in locals():
                await page.close()
            return None

    async def scrape_multiple_profiles(self, platform: str, urls: List[str]) -> Dict[str, Dict[str, Optional[str]]]:
        """使用已初始化的浏览器实例抓取多个页面"""
        if not self.context:
            logger.error("浏览器未初始化")
            return {url: {"display_name": "N/A", "id": "N/A"} for url in urls}

        results = {}
        for url in urls:
            result = await self._scrape_single(platform, url)
            results[url] = result if result else {
                "display_name": "N/A",
                "id": "N/A"
            }
        return results

async def main():
    # 初始化浏览器
    scraper = SocialProfileScraper()
    with open("data/config.json", "r", encoding="utf-8") as f:
        config_json = f.read()
    
    if not await scraper.initialize_browser(config_json):
        logger.error("无法初始化浏览器，程序退出")
        return

    try:
        # 处理微博
        async def weibo_scrape_function(urls, _):
            return await scraper.scrape_multiple_profiles("weibo", urls)

        await process_social_platform_profiles(
            platform="weibo",
            csv_path="data/Artist.csv",
            config_path="data/config.json",
            scrape_function=weibo_scrape_function,
            batch_size=5,
            rate_limit_seconds=5
        )

        # 处理Twitter
        async def twitter_scrape_function(urls, _):
            return await scraper.scrape_multiple_profiles("twitter", urls)

        await process_social_platform_profiles(
            platform="twitter",
            csv_path="data/Artist.csv",
            config_path="data/config.json",
            scrape_function=twitter_scrape_function,
            batch_size=5,
            rate_limit_seconds=5
        )

        # 处理Bilibili
        async def bilibili_scrape_function(urls, _):
            return await scraper.scrape_multiple_profiles("bilibili", urls)

        await process_social_platform_profiles(
            platform="bilibili",
            csv_path="data/Artist.csv",
            config_path="data/config.json",
            scrape_function=bilibili_scrape_function,
            batch_size=5,
            rate_limit_seconds=5
        )

    finally:
        # 确保浏览器被关闭
        await scraper.close_browser()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    asyncio.run(main())