"""
Bilibili 图文动态批量轮询与图片下载脚本
=====================================

【使用说明】
1. 配置好 data/Artist.csv，包含要轮询的 B 站用户信息（bilibili_id、bilibili_name、bilibili_url、bilibili_roll_time 等字段）。
2. 在 main() 函数中填写有效的 B 站 Cookie 信息（sessdata、bili_jct、buvid3）。
3. 运行本脚本，将自动分组轮询用户的图文动态，下载图片到 data/bilibili/downloads/，并自动更新 CSV 中的轮询时间。
4. 支持断点续传，失败信息会在终端输出。

【主要代码逻辑说明】
- Preprocessor：负责读取和分组 CSV 用户数据，处理轮询时间。
- BilibiliDynamicFetcher：异步获取指定用户的图文动态，支持分页和时间过滤。
- BilibiliContentDownloader：提取动态中的图片链接并下载，支持多种动态结构和图片字段，带并发限制。
- Postprocessor：处理轮询后用户的轮询时间更新，写回 CSV。
- process_users：串行处理每组用户，下载图片并更新轮询时间。
- main：主入口，配置认证、读取用户、分组、依次处理。

依赖：bilibili_api、pandas、requests、asyncio、logging
"""

import asyncio
import json
import os
import logging
import random
from datetime import datetime, timedelta
from bilibili_api import user, opus, Credential, article
import pandas as pd

# 配置详细日志，输出到控制台和文件
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"bili_poller_{datetime.now().strftime('%Y%m%d')}.log")

log_formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
)

file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(log_formatter)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_formatter)

logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])

class Preprocessor:
    """前处理类：读取CSV文件并准备数据"""
    
    def __init__(self, csv_file=None):
        self.csv_file = csv_file
        self.users = []
    
    def read_users(self, csv_file=None):
        """使用pandas读取CSV文件，所有字段强制为字符串"""
        if csv_file is not None:
            self.csv_file = csv_file
        if not self.csv_file or not os.path.exists(self.csv_file):
            logging.error(f"CSV文件不存在: {self.csv_file}")
            return []
        df = pd.read_csv(self.csv_file, dtype=str).fillna('')
        users = []
        for _, row in df.iterrows():
            # 只处理bilibili_id不为空的行
            if not row.get('bilibili_id', '').strip():
                continue
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
        try:
            # 解析日期并减去一天
            dt = datetime.strptime(time_str, "%Y:%m:%d") - timedelta(days=1)
            # 获取前一天零点的时间戳
            return int(dt.replace(hour=0, minute=0, second=0).timestamp())
        except ValueError:
            logging.error(f"无效的时间格式: {time_str}，程序即将退出")
            exit(1)
    
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
        since_str = datetime.fromtimestamp(since_timestamp).strftime("%Y-%m-%d %H:%M:%S")
        logging.info(f"开始获取用户 {name}({uid}) 的动态，起始时间: {since_str} (timestamp: {since_timestamp})")
        
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
                    timestamp_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S") if timestamp else ""
                    # 如果动态时间早于起始时间，停止翻页
                    if timestamp <= since_timestamp:
                        logging.info(f"用户 {name} 遇到旧动态(<= {since_str})，动态时间: {timestamp_str} (timestamp: {timestamp})，停止翻页")
                        return all_dynamics
                    
                    # 只处理图文动态 (类型2)
                    if dyn_type == 2:
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
        self.failed_info = []  # 记录失败的(id, user_name)

    async def download_opus(self, opus_id, user_name=None):
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
            self.failed_info.append((opus_id, user_name or ""))
            try:
                images = await op_instance.get_images_raw_info()
                logging.error(f"原始图片数据: {images}")
            except Exception:
                pass
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
        # 5. 若仍未找到，打印card结构并正则兜底
        if not image_urls:
            card_preview = card if isinstance(card, str) else json.dumps(card, ensure_ascii=False) if card else None
            logging.warning(f"未提取到图片，card字段预览: {str(card_preview)[:500]}")
            import re
            if card_preview:
                pattern = r"https?://[^'\"\s>]+?\.(?:jpg|jpeg|png|webp|gif|bmp|svg|tif|tiff|avif|jfif|ico|apng|heic|heif)"
                found_urls = re.findall(pattern, card_preview, re.IGNORECASE)
                # 过滤掉头像、VIP标签等无关图片
                filtered_urls = [
                    url for url in found_urls
                    if not re.search(r"/(face|vip|avatar|icon|head_|logo|badge|emoticon|emotion|level|medal|rank|pendant|frame|background|cover|banner|label|watermark|stamp|gift|guard|fans|medal|card|skin|bubble|title|tag|sign|mark|corner|flag|mask|border|effect|decorate|decoration|screenshot|preview|thumb|small|mini|tiny|profile|system|default|temp|test|testimg|testpic|testimage|testphoto|testicon|testface|testavatar|testlogo|testcover|testbanner|testbadge|testmedal|testframe|testpendant|testbubble|testtitle|testtag|testsign|testmark|testcorner|testflag|testmask|testborder|testeffect|testdecorate|testdecoration|testscreenshot|testpreview|testthumb|testsmall|testmini|testtiny|testprofile|testsystem|testdefault|testtemp)/",
                        url, re.IGNORECASE)
                ]
                if filtered_urls:
                    logging.info(f"正则强制提取到内容图片链接: {filtered_urls}")
                    image_urls.extend(filtered_urls)
                if found_urls and not filtered_urls:
                    logging.info(f"正则提取到的图片均为无关图片（如头像、VIP标签等），已全部过滤: {found_urls}")
                elif found_urls and filtered_urls and len(filtered_urls) < len(found_urls):
                    filtered_out = [url for url in found_urls if url not in filtered_urls]
                    logging.info(f"部分无关图片已过滤: {filtered_out}")
        return image_urls

    # 限制同时下载图片的数量
    _download_semaphore = asyncio.Semaphore(5)  # 最多同时下载5个动态的图片

    async def download_dynamic(self, dynamic_data):
        """递归查找所有图片链接并下载，添加请求延迟和并发限制"""
        dynamic_id = dynamic_data["id"]
        user_name = dynamic_data.get("user_name", "unknown")
        raw_data = dynamic_data.get("raw_data", {})
        image_urls = self.extract_image_urls(raw_data)
        if image_urls:
            # 并发限制
            async with self._download_semaphore:
                # 随机延迟，防止高并发
                await asyncio.sleep(random.uniform(0.5, 2.0))
                loop = asyncio.get_event_loop()
                # 用线程池避免阻塞
                result = await loop.run_in_executor(
                    None, self.download_images, user_name, dynamic_id, list(set(image_urls))
                )
                return result, None
        else:
            logging.info(f"动态 {dynamic_id} 未找到图片")
            self.failed_info.append((dynamic_id, user_name))
            return None, None

class Postprocessor:
    """后处理类：更新CSV文件"""
    
    def __init__(self, csv_file=None):
        self.csv_file = csv_file
        self.updated_users = {}
    
    def add_updated_user(self, user_id, new_roll_time):
        """添加需要更新的用户"""
        self.updated_users[user_id] = new_roll_time
    
    def update_csv(self, csv_file=None):
        """使用pandas更新CSV文件中的轮询时间，所有字段强制为字符串"""
        if csv_file is not None:
            self.csv_file = csv_file
        if not self.csv_file or not os.path.exists(self.csv_file):
            logging.error(f"CSV文件不存在: {self.csv_file}")
            return
        df = pd.read_csv(self.csv_file, dtype=str).fillna('')
        for idx, row in df.iterrows():
            user_id = row.get('bilibili_id')
            if user_id and user_id.isdigit() and int(user_id) in self.updated_users:
                df.at[idx, 'bilibili_roll_time'] = str(self.updated_users[int(user_id)])
        # 强制所有列为字符串
        df = df.astype(str)
        df.to_csv(self.csv_file, index=False, encoding='utf-8')
        logging.info(f"已更新 {len(self.updated_users)} 个用户的轮询时间")

async def process_users(user_group, credential, csv_file, callback=None):
    """处理一组用户，支持回调"""
    fetcher = BilibiliDynamicFetcher(credential)
    downloader = BilibiliContentDownloader(credential)
    postprocessor = Postprocessor(csv_file)
    
    now = datetime.now()
    today_zero = datetime(now.year, now.month, now.day)
    new_roll_time = today_zero.strftime("%Y:%m:%d")
    total = 0
    filtered_count = 0  # 新增：被完全过滤的动态数
    filtered_failed = []  # 新增：被完全过滤的动态id和用户名
    for user_info in user_group:
        dynamics = await fetcher.fetch_user_dynamics(user_info)
        if not dynamics:
            continue
        total += len(dynamics)
        has_new_content = False  # 标记本用户是否有新动态且有图片下载成功
        for dynamic in dynamics:
            content, info = await downloader.download_dynamic(dynamic)
            # 回调处理
            if callback:
                try:
                    callback(dynamic, content, info)
                except Exception as e:
                    logging.warning(f"回调函数异常: {e}")
            # 检查是否因过滤无关图片导致无图片
            if not content:
                raw = dynamic.get('raw_data', {})
                card = raw.get('card')
                card_obj = None
                if card:
                    try:
                        card_obj = json.loads(card) if isinstance(card, str) else card
                    except Exception:
                        pass
                filtered = False
                if card_obj:
                    item = card_obj.get('item')
                    if item and (item.get('pictures') is None or item.get('pictures_count', 0) == 0):
                        filtered = True
                if filtered:
                    filtered_count += 1
                    filtered_failed.append((dynamic['id'], dynamic.get('user_name', '')))
            else:
                has_new_content = True  # 有图片下载成功
        if has_new_content:
            postprocessor.add_updated_user(user_info['id'], new_roll_time)
    postprocessor.update_csv()
    failed = downloader.failed_info
    failed_count = len(failed)
    real_failed = failed_count - filtered_count
    if real_failed > 0:
        print(f"下载失败 {real_failed}/{total-filtered_count} ：{failed if real_failed>0 else ''}")
    print(f"全部下载成功，共{total-filtered_count}条")
    if filtered_count > 0:
        print(f"已完全过滤无关图片的动态 {filtered_count} 条：{filtered_failed}")

async def run_bili_poller(user_groups=None, callback=None, csv_file="data/Artist.csv", credential=None, group_size=5):
    """
    统一入口：可传入用户组、回调、csv路径、认证等参数。
    user_groups: List[List[user_info]]，如为None则自动读取并分组。
    callback: 处理每个动态的回调(dynamic, content, info)
    csv_file: CSV路径
    credential: B站认证对象
    group_size: 自动分组时每组人数
    """
    # 自动获取credential
    if credential is None:
        cookies_path = r"userdata/bilibili-cookies.json"
        with open(cookies_path, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        def get_cookie_value(name):
            for c in cookies:
                if c.get('name', '').lower() == name.lower():
                    return c.get('value', '')
            return ''
        credential = Credential(
            sessdata=get_cookie_value('SESSDATA'),
            bili_jct=get_cookie_value('bili_jct'),
            buvid3=get_cookie_value('buvid3')
        )
    # 自动获取用户组
    if user_groups is None:
        preprocessor = Preprocessor()
        users = preprocessor.read_users(csv_file)
        if not users:
            logging.warning("未找到有效用户")
            return
        user_groups = preprocessor.get_user_groups(group_size)
        logging.info(f"将 {len(users)} 个用户分成 {len(user_groups)} 组进行处理")
    # 处理每组
    for group in user_groups:
        await process_users(group, credential, csv_file, callback=callback)
        await asyncio.sleep(random.uniform(5, 10))

async def main():
    # 兼容原有main流程
    await run_bili_poller()

if __name__ == "__main__":
    asyncio.run(main())