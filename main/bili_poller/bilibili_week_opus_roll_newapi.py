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
- BilibiliDynamicFetcher：异步获取指定用户的图文动态，支持分页和时间过滤（使用新API）。
- BilibiliContentDownloader：提取动态中的图片链接并下载，支持多种动态结构和图片字段，带并发限制。
- DynamicProcessor：动态处理类的基类。
- DrawDynamicProcessor：图文动态处理类（部分实现）。
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
from datetime import datetime, time, timedelta
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

# 动态类型映射表
DYNAMIC_TYPE_MAP = {
    "DYNAMIC_TYPE_WORD": "纯文字",
    "DYNAMIC_TYPE_DRAW": "图文",
    "DYNAMIC_TYPE_AV": "视频",
    "DYNAMIC_TYPE_FORWARD": "转发",
    "DYNAMIC_TYPE_ARTICLE": "专栏",
    "DYNAMIC_TYPE_MUSIC": "音频",
    "DYNAMIC_TYPE_COMMON_SQUARE": "通用卡",
    "DYNAMIC_TYPE_LIVE_RCMD": "直播推荐",
    "DYNAMIC_TYPE_AD": "广告",
    "DYNAMIC_TYPE_LIVE": "直播",
    "DYNAMIC_TYPE_BANNER": "横幅",
    "DYNAMIC_TYPE_PGC": "番剧",
    "DYNAMIC_TYPE_UGC_SEASON": "合集更新",
    "DYNAMIC_TYPE_OGV_SEASON": "OGV更新"
}

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

class DynamicProcessor:
    """动态处理基类"""
    async def process(self, dynamic_data, downloader):
        """处理动态数据，子类实现具体逻辑"""
        raise NotImplementedError("子类必须实现process方法")

class DrawDynamicProcessor(DynamicProcessor):
    """图文动态处理器（部分实现）"""
    async def process(self, dynamic_data, downloader):
        """处理图文动态"""
        # 这里可以添加图文动态特有的处理逻辑
        # 目前只是调用通用的下载方法
        return await downloader.download_dynamic(dynamic_data)

class BilibiliDynamicFetcher:
    """B站动态获取类（使用新API）"""
    
    def __init__(self, credential=None):
        self.credential = credential
        # 初始化动态处理器映射
        self.processors = {
            "DYNAMIC_TYPE_DRAW": DrawDynamicProcessor(),
            # 其他动态类型的处理器可以在这里添加
        }
    
    async def fetch_user_dynamics(self, user_info):
        """获取单个用户的动态（使用新API）"""
        uid = user_info['id']
        since_timestamp = user_info['roll_time']
        name = user_info['name']
        since_str = datetime.fromtimestamp(since_timestamp).strftime("%Y-%m-%d %H:%M:%S")
        logging.info(f"开始获取用户 {name}({uid}) 的动态，起始时间: {since_str} (timestamp: {since_timestamp})")
        
        u = user.User(uid, credential=self.credential)
        all_dynamics = []
        offset = ""  # 新API使用字符串offset
        page = 0
        has_more = True
        
        try:
            while has_more:
                page += 1
                # 随机延迟减少并发压力
                await asyncio.sleep(random.uniform(1, 3))
                
                logging.info(f"请求用户 {name} 第 {page} 页动态，offset={offset}")
                dynamics = await u.get_dynamics_new(offset)
                
                if not dynamics or "items" not in dynamics or not dynamics["items"]:
                    logging.info(f"用户 {name} 第 {page} 页无数据，停止翻页")
                    break
                
                items = dynamics["items"]
                logging.info(f"用户 {name} 第 {page} 页获取到 {len(items)} 条动态")
                
                for item in items:
                    # 获取动态类型和时间戳
                    dyn_type = item.get("type")
                    try:
                        timestamp = item["modules"]["module_author"]["pub_ts"]
                    except KeyError:
                        logging.warning(f"动态缺少pub_ts，使用当前时间")
                        timestamp = int(time.time())
                    
                    timestamp_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S") if timestamp else ""
                    # 如果动态时间早于起始时间，停止翻页
                    if timestamp <= since_timestamp:
                        logging.info(f"用户 {name} 遇到旧动态(<= {since_str})，动态时间: {timestamp_str} (timestamp: {timestamp})，停止翻页")
                        has_more = False
                        break
                    
                    # 只处理图文动态 (类型为DYNAMIC_TYPE_DRAW)
                    if dyn_type == "DYNAMIC_TYPE_DRAW":
                        dynamic_id = item.get("id_str", str(item.get("id", "")))
                        all_dynamics.append({
                            "user_id": uid,
                            "user_name": name,
                            "id": dynamic_id,
                            "type": dyn_type,
                            "timestamp": timestamp,
                            "raw_data": item
                        })
                
                # 更新offset和has_more状态
                has_more = dynamics.get("has_more", 0) == 1
                if has_more:
                    new_offset = dynamics.get("offset", "")
                    if not new_offset:
                        logging.warning(f"用户 {name} offset为空，停止翻页")
                        has_more = False
                    else:
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

    def extract_image_urls(self, item):
        """
        针对新API的动态结构提取图片URL
        """
        image_urls = []
        
        # 尝试从动态内容模块提取图片
        try:
            modules = item.get("modules", {})
            module_dynamic = modules.get("module_dynamic", {})
            
            # 主要图片区域
            if "major" in module_dynamic and module_dynamic["major"].get("type") == "MAJOR_TYPE_DRAW":
                draw = module_dynamic["major"].get("draw", {})
                items = draw.get("items", [])
                for img in items:
                    url = img.get("src", "")
                    if url:
                        image_urls.append(url)
            
            # 附加图片区域
            if "additional" in module_dynamic and module_dynamic["additional"].get("type") == "ADDITIONAL_TYPE_DRAW":
                draw = module_dynamic["additional"].get("draw", {})
                items = draw.get("items", [])
                for img in items:
                    url = img.get("src", "")
                    if url:
                        image_urls.append(url)
            
            # 转发动态中的图片
            if "origin" in item:
                origin = item["origin"]
                origin_modules = origin.get("modules", {})
                origin_dynamic = origin_modules.get("module_dynamic", {})
                
                if "major" in origin_dynamic and origin_dynamic["major"].get("type") == "MAJOR_TYPE_DRAW":
                    draw = origin_dynamic["major"].get("draw", {})
                    items = draw.get("items", [])
                    for img in items:
                        url = img.get("src", "")
                        if url:
                            image_urls.append(url)
        except Exception as e:
            logging.error(f"提取图片URL失败: {str(e)}")
        
        # 去重
        return list(set(image_urls))

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

    # 限制同时下载图片的数量
    _download_semaphore = asyncio.Semaphore(5)  # 最多同时下载5个动态的图片

    async def download_dynamic(self, dynamic_data):
        """下载动态中的图片"""
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
                return result
        else:
            logging.info(f"动态 {dynamic_id} 未找到图片")
            self.failed_info.append((dynamic_id, user_name))
            return False

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
    for user_info in user_group:
        dynamics = await fetcher.fetch_user_dynamics(user_info)
        if not dynamics:
            continue
        total += len(dynamics)
        has_new_content = False  # 标记本用户是否有新动态且有图片下载成功
        for dynamic in dynamics:
            # 获取对应动态类型的处理器
            processor = fetcher.processors.get(dynamic['type'], None)
            if processor:
                result = await processor.process(dynamic, downloader)
            else:
                # 没有特定处理器时使用默认下载
                result = await downloader.download_dynamic(dynamic)
            
            # 回调处理
            if callback:
                try:
                    callback(dynamic, result)
                except Exception as e:
                    logging.warning(f"回调函数异常: {e}")
            
            if result:
                has_new_content = True
        if has_new_content:
            postprocessor.add_updated_user(user_info['id'], new_roll_time)
    postprocessor.update_csv()
    failed = downloader.failed_info
    if failed:
        print(f"下载失败 {len(failed)}/{total} ：{failed}")
    else:
        print(f"全部下载成功，共{total}条")

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