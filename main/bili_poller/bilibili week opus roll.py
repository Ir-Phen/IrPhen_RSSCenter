import asyncio
import json
import os
import logging
import csv
import time
import random
from datetime import datetime, timedelta
from bilibili_api import user, opus, Credential, article

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

class Preprocessor:
    """前处理类：读取CSV文件并准备数据"""
    
    def __init__(self, csv_file="data/Artist.csv"):
        self.csv_file = csv_file
        self.users = []
    
    def read_users(self):
        """读取CSV文件中的用户信息"""
        if not os.path.exists(self.csv_file):
            logging.error(f"CSV文件不存在: {self.csv_file}")
            return []
        
        users = []
        with open(self.csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('bilibili_id') and row['bilibili_id'].isdigit():
                    # 转换轮询时间
                    roll_time = self.convert_roll_time(row.get('bilibili_roll_time', ''))
                    
                    users.append({
                        'name': row.get('bilibili_name', ''),
                        'id': int(row['bilibili_id']),
                        'url': row.get('bilibili_url', ''),
                        'roll_time': roll_time,
                        'original_roll_time': row.get('bilibili_roll_time', '')
                    })
        
        logging.info(f"从CSV读取到 {len(users)} 个有效B站用户")
        self.users = users
        return users
    
    def convert_roll_time(self, time_str):
        """将YYYY:MM:DD格式转换为前一日的零点时间戳"""
        if not time_str:
            return 0
        
        try:
            # 解析日期并减去一天
            dt = datetime.strptime(time_str, "%Y:%m:%d") - timedelta(days=1)
            # 获取前一天零点的时间戳
            return int(dt.replace(hour=0, minute=0, second=0).timestamp())
        except ValueError:
            logging.warning(f"无效的时间格式: {time_str}, 使用默认值0")
            return 0
    
    def get_user_groups(self, group_size=5):
        """将用户分组，每组最多5个"""
        groups = []
        for i in range(0, len(self.users), group_size):
            groups.append(self.users[i:i+group_size])
        return groups

class BilibiliDynamicFetcher:
    """B站动态获取类"""
    
    def __init__(self, credential=None):
        self.credential = credential
    
    async def fetch_user_dynamics(self, user_info):
        """获取单个用户的动态"""
        uid = user_info['id']
        since_timestamp = user_info['roll_time']
        name = user_info['name']
        
        logging.info(f"开始获取用户 {name}({uid}) 的动态，起始时间: {since_timestamp}")
        
        u = user.User(uid, credential=self.credential)
        all_dynamics = []
        offset = 0
        page = 0
        max_pages = 10
        
        try:
            while page < max_pages:
                page += 1
                # 随机延迟减少并发压力
                await asyncio.sleep(random.uniform(1, 3))
                
                logging.info(f"请求用户 {name} 第 {page} 页动态，offset={offset}")
                dynamics = await u.get_dynamics(offset)
                
                if not dynamics or "cards" not in dynamics or not dynamics["cards"]:
                    logging.info(f"用户 {name} 第 {page} 页无数据，停止翻页")
                    break
                
                cards = dynamics["cards"]
                logging.info(f"用户 {name} 第 {page} 页获取到 {len(cards)} 条动态")
                
                for card in cards:
                    desc = card.get("desc", {})
                    dyn_type = desc.get("type")
                    timestamp = desc.get("timestamp", 0)
                    
                    # 如果动态时间早于起始时间，停止翻页
                    if timestamp <= since_timestamp:
                        logging.info(f"用户 {name} 遇到旧动态(<= {since_timestamp})，停止翻页")
                        return all_dynamics
                    
                    # 只处理图文动态 (类型2) 和专栏动态 (类型8)
                    if dyn_type in [2, 8]:
                        dynamic_id = desc.get("dynamic_id")
                        all_dynamics.append({
                            "user_id": uid,
                            "user_name": name,
                            "id": dynamic_id,
                            "type": dyn_type,
                            "timestamp": timestamp,
                            "raw_data": card
                        })
                
                # 更新offset
                if cards:
                    new_offset = cards[-1].get("desc", {}).get("dynamic_id", 0)
                    if new_offset == offset:
                        logging.warning(f"用户 {name} offset未变化({offset})，停止翻页")
                        break
                    offset = new_offset
        
        except Exception as e:
            logging.error(f"获取用户 {name} 动态失败: {str(e)}")
        
        logging.info(f"用户 {name} 共获取到 {len(all_dynamics)} 条新动态")
        return all_dynamics

class BilibiliContentDownloader:
    """B站内容下载类"""
    
    def __init__(self, credential=None, base_dir="data/bilibili/downloads"):
        self.credential = credential
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    async def download_opus(self, opus_id):
        """下载图文动态内容，仅下载图片，不处理md内容"""
        try:
            # 随机延迟
            await asyncio.sleep(random.uniform(0.5, 1.5))
            op_instance = opus.Opus(opus_id=opus_id, credential=self.credential)
            # 只处理图片下载
            try:
                images = await op_instance.get_images_raw_info()
            except Exception as e:
                logging.error(f"获取图文动态 {opus_id} 图片信息失败: {str(e)}")
                images = []
            image_urls = []
            for img in images:
                url = img.get("url") or img.get("image_url")
                if url:
                    image_urls.append(url)
            if image_urls:
                # 这里无法获取user_name和dynamic_id，调用方需传递
                return image_urls, None
            return None, None
        except Exception as e:
            logging.error(f"下载图文动态 {opus_id} 失败: {str(e)}")
            try:
                images = await op_instance.get_images_raw_info()
                logging.error(f"原始图片数据: {images}")
            except Exception:
                pass
            return None, None

    async def download_article(self, cv_id):
        """下载专栏内容，仅保留图片下载功能，不处理md内容"""
        try:
            await asyncio.sleep(random.uniform(0.5, 1.5))
            art = article.Article(cvid=cv_id, credential=self.credential)
            content = await art.get_content()
            image_urls = []
            for item in content:
                if item["type"] == 1:  # 图片
                    image_urls.append(item["url"])
            if image_urls:
                return image_urls, None
            return None, None
        except Exception as e:
            logging.error(f"下载专栏 cv{cv_id} 失败: {str(e)}")
            return None, None

    def download_images(self, user_name, dynamic_id, image_urls):
        """下载图片到指定目录，命名为name_动态id_序号"""
        if not image_urls:
            return False
        try:
            import requests
            user_dir = os.path.join(self.base_dir, user_name)
            os.makedirs(user_dir, exist_ok=True)
            dynamic_dir = os.path.join(user_dir, str(dynamic_id))
            os.makedirs(dynamic_dir, exist_ok=True)
            for idx, url in enumerate(image_urls, 1):
                ext = os.path.splitext(url)[1].split('?')[0] or '.jpg'
                safe_name = user_name.replace('/', '_').replace('\\', '_')
                img_path = os.path.join(dynamic_dir, f"{safe_name}_{dynamic_id}_{idx}{ext}")
                try:
                    resp = requests.get(url, timeout=10)
                    if resp.status_code == 200:
                        with open(img_path, 'wb') as f:
                            f.write(resp.content)
                        logging.info(f"图片已保存: {img_path}")
                    else:
                        logging.warning(f"下载图片失败: {url} 状态码: {resp.status_code}")
                except Exception as e:
                    logging.error(f"下载图片异常: {url} 错误: {str(e)}")
            return True
        except Exception as e:
            logging.error(f"保存图片失败: {str(e)}")
            return False

    def extract_image_urls(self, obj, path=None):
        """
        针对B站动态结构，优先解析card字段（如为字符串则json.loads），
        查找常见图片字段（如item.pictures、item.pictures[].img_src、pictures、image_urls等），
        兼容display字段下的图片。
        若未找到，打印card字段结构。
        """
        image_urls = []
        # 1. 解析card字段
        card = obj.get("card")
        card_obj = None
        if card:
            if isinstance(card, str):
                try:
                    card_obj = json.loads(card)
                except Exception as e:
                    logging.warning(f"card字段json解析失败: {e}")
            elif isinstance(card, dict):
                card_obj = card
        # 2. 常见图片字段提取
        if card_obj:
            # 动态图文
            item = card_obj.get("item")
            if item:
                # 图文图片
                if "pictures" in item and isinstance(item["pictures"], list):
                    for pic in item["pictures"]:
                        url = pic.get("img_src") or pic.get("imgUrl") or pic.get("url")
                        if url:
                            image_urls.append(url)
                # 单图
                if "pictures" not in item and "picture" in item:
                    url = item.get("picture")
                    if url:
                        image_urls.append(url)
            # 专栏图片
            if "image_urls" in card_obj and isinstance(card_obj["image_urls"], list):
                image_urls.extend(card_obj["image_urls"])
            # 其他常见字段
            if "pictures" in card_obj and isinstance(card_obj["pictures"], list):
                for pic in card_obj["pictures"]:
                    url = pic.get("img_src") or pic.get("imgUrl") or pic.get("url")
                    if url:
                        image_urls.append(url)
        # 3. display字段兼容
        display = obj.get("display")
        if display and isinstance(display, dict):
            if "origin" in display and isinstance(display["origin"], dict):
                origin = display["origin"]
                if "pictures" in origin and isinstance(origin["pictures"], list):
                    for pic in origin["pictures"]:
                        url = pic.get("img_src") or pic.get("imgUrl") or pic.get("url")
                        if url:
                            image_urls.append(url)
        # 4. 若未找到，尝试first_frame字段（视频首帧）
        if card_obj and "first_frame" in card_obj:
            url = card_obj["first_frame"]
            if isinstance(url, str) and url.startswith("http"):
                image_urls.append(url)
        # 5. 若仍未找到，打印card结构
        if not image_urls:
            card_preview = card if isinstance(card, str) else json.dumps(card, ensure_ascii=False) if card else None
            logging.warning(f"未提取到图片，card字段预览: {str(card_preview)[:500]}")
        return image_urls

    async def download_dynamic(self, dynamic_data):
        """递归查找所有图片链接并下载"""
        dynamic_id = dynamic_data["id"]
        user_name = dynamic_data.get("user_name", "unknown")
        raw_data = dynamic_data.get("raw_data", {})
        image_urls = self.extract_image_urls(raw_data)
        if image_urls:
            return self.download_images(user_name, dynamic_id, list(set(image_urls))), None
        else:
            logging.info(f"动态 {dynamic_id} 未找到图片")
            return None, None

class Postprocessor:
    """后处理类：更新CSV文件"""
    
    def __init__(self, csv_file="data/Artist.csv"):
        self.csv_file = csv_file
        self.updated_users = {}
    
    def add_updated_user(self, user_id, new_roll_time):
        """添加需要更新的用户"""
        self.updated_users[user_id] = new_roll_time
    
    def update_csv(self):
        """更新CSV文件中的轮询时间"""
        if not os.path.exists(self.csv_file):
            logging.error(f"CSV文件不存在: {self.csv_file}")
            return
        
        # 读取CSV数据
        rows = []
        with open(self.csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                user_id = row.get('bilibili_id')
                if user_id and user_id.isdigit() and int(user_id) in self.updated_users:
                    row['bilibili_roll_time'] = self.updated_users[int(user_id)]
                rows.append(row)
        
        # 写回CSV文件
        with open(self.csv_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        logging.info(f"已更新 {len(self.updated_users)} 个用户的轮询时间")

async def process_users(user_group, credential):
    """处理一组用户"""
    fetcher = BilibiliDynamicFetcher(credential)
    downloader = BilibiliContentDownloader(credential)
    postprocessor = Postprocessor()
    
    # 获取当前日期的零点时间戳（用于更新轮询时间）
    now = datetime.now()
    today_zero = datetime(now.year, now.month, now.day)
    new_roll_time = today_zero.strftime("%Y:%m:%d")
    
    for user_info in user_group:
        # 获取用户动态
        dynamics = await fetcher.fetch_user_dynamics(user_info)
        if not dynamics:
            continue
        
        # 下载动态内容
        for dynamic in dynamics:
            content, info = await downloader.download_dynamic(dynamic)
            if content:
                downloader.save_content(
                    user_info['name'], 
                    dynamic['id'], 
                    content
                )
        
        # 记录需要更新的用户
        postprocessor.add_updated_user(user_info['id'], new_roll_time)
    
    # 更新CSV文件
    postprocessor.update_csv()

async def main():
    # 配置认证信息
    credential = Credential(
        sessdata="3a84a2b9%2C1766711892%2C9714b%2A62CjDRA09DniT-5vxbwV64m-Z-Os7ZufCYw7gAHHJO1i0uIhJUHOOA63cmdFACuVUGil0SVkxrc21JZE9MZWJoak9ubkYxTjBYWkQ2TXFKemoyYldXcU1hVy01SC1Tb2Rub2JScU5qM1ZzZFI2NERnLUl1OGVocnRzYTdCbjdnRmVxaW9Wc3BtM0lnIIEC",
        bili_jct="32b3aafa92e44eee2a5dfe5785561e6d",
        buvid3="67727345-8BA8-E479-5FD1-64450BB5A1A485280infocs"
    )
    
    # 1. 前处理
    preprocessor = Preprocessor()
    users = preprocessor.read_users()
    if not users:
        return
    
    # 2. 分组处理用户
    user_groups = preprocessor.get_user_groups(5)
    logging.info(f"将 {len(users)} 个用户分成 {len(user_groups)} 组进行处理")
    
    # 3. 处理每组用户
    for group in user_groups:
        await process_users(group, credential)
        # 组间延迟
        await asyncio.sleep(random.uniform(5, 10))

if __name__ == "__main__":
    asyncio.run(main())