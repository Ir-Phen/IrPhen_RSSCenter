"""
Bilibili 动态采集与处理框架
=====================================

【设计特点】
1. 模块化设计：
    - 用户管理模块负责加载和管理需要采集动态的用户数据，支持从 CSV 文件加载或手动添加用户。
    - 动态获取模块通过 B 站 API 接口获取指定用户的动态信息，支持全量抓取和增量更新两种模式。
    - 动态处理模块使用工厂模式，根据动态的类型自动选择合适的处理器进行内容提取和资源下载。
    - 内容下载模块负责下载动态中的图片、视频等资源，并对下载过程进行并发控制。
    - 输出管理模块将处理结果保存到 JSON 文件，并更新 CSV 文件中的轮询时间，同时打印处理摘要。
2. 支持多种输入源：
    - 可以通过配置 data/Artist.csv 文件批量添加用户信息，也可以使用 add_user() 方法手动添加单个用户。
3. 两种抓取模式：
    - 增量更新模式：基于轮询时间，只获取自上次轮询之后更新的动态，提高采集效率。
    - 全量抓取模式：获取用户的所有动态信息。
4. 动态类型处理：
    - 使用工厂模式，根据动态的类型自动选择合适的处理器，便于扩展新的动态类型处理逻辑。
5. 可扩展性：
    - 易于添加新的动态类型处理器，只需要继承 DynamicProcessor 基类并实现相应的方法即可。

【使用说明】
1. 配置用户信息：
    - 可以选择配置 data/Artist.csv 文件，文件中应包含 bilibili_id（B站用户 ID）、bilibili_name（B站用户名）、bilibili_url（B站用户主页 URL）和 bilibili_roll_time（轮询时间，格式为 YYYY:MM:DD）等字段。
    - 也可以使用 add_user() 方法手动添加用户，该方法接受用户 ID、用户名、用户主页 URL 和轮询时间作为参数。
2. 配置凭证信息：
    - 在 main() 函数中，通过 load_bilibili_credential() 函数加载 B 站的凭证信息，凭证信息存储在 userdata/bilibili-cookies.json 文件中。
3. 选择抓取模式：
    - 在调用 run() 方法时，通过 full_fetch 参数选择抓取模式，full_fetch=True 表示全量抓取，full_fetch=False 表示增量抓取。
4. 运行脚本：
    - 在代码的最后，调用 asyncio.run(main()) 来启动采集程序。

【注意事项】
- 运行脚本前，请确保已经安装了所需的依赖库，如 pandas、bilibili_api 等。
- 请确保 userdata/bilibili-cookies.json 文件中包含有效的 B 站 Cookie 信息，否则可能无法正常获取动态数据。
- 在采集过程中，为了避免对 B 站服务器造成过大压力，程序会在请求之间添加随机延迟。
"""

import asyncio
import json
import os
import logging
import random
import pandas as pd
from datetime import datetime, time, timedelta
from abc import ABC, abstractmethod
from bilibili_api import user, Credential, dynamic
from typing import List, Dict, Any, Optional

# 配置详细日志
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"bili_harvester_{datetime.now().strftime('%Y%m%d')}.log")

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
logger = logging.getLogger(__name__)

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

class UserManager:
    """用户管理类：负责加载和管理用户数据"""
    
    def __init__(self):
        self.users = []
    
    def load_from_csv(self, csv_file: str):
        """从CSV文件加载用户数据"""
        if not os.path.exists(csv_file):
            logger.error(f"CSV文件不存在: {csv_file}")
            return
        
        df = pd.read_csv(csv_file, dtype=str).fillna('')
        for _, row in df.iterrows():
            if not row.get('bilibili_id', '').strip():
                continue
            
            # 转换轮询时间
            roll_time = self._convert_roll_time(row.get('bilibili_roll_time', ''))
            self.users.append({
                'name': row.get('bilibili_name', ''),
                'id': int(row['bilibili_id']),
                'url': row.get('bilibili_url', ''),
                'roll_time': roll_time,
                'original_roll_time': row.get('bilibili_roll_time', ''),
                'source': 'csv'  # 添加来源标记
            })
        logger.info(f"从CSV加载 {len(self.users)} 个用户")
    
    def add_user(self, user_id: int, name: str = "", url: str = "", roll_time: str = ""):
        """手动添加用户"""
        roll_timestamp = self._convert_roll_time(roll_time) if roll_time else 0
        self.users.append({
            'name': name,
            'id': user_id,
            'url': url,
            'roll_time': roll_timestamp,
            'original_roll_time': roll_time,
            'source': 'manual'  # 添加来源标记
        })
        logger.info(f"添加用户: ID={user_id}, 名称={name}")
    
    def get_users(self, group_size: int = 5) -> List[List[Dict]]:
        """将用户分组"""
        groups = []
        for i in range(0, len(self.users), group_size):
            groups.append(self.users[i:i+group_size])
        logger.info(f"将用户分成 {len(groups)} 组，每组最多 {group_size} 人")
        return groups
    
    def _convert_roll_time(self, time_str: str) -> int:
        """将YYYY:MM:DD格式转换为当日的零点时间戳"""
        try:
            if not time_str:
                return 0
            dt = datetime.strptime(time_str, "%Y:%m:%d")
            return int(dt.replace(hour=0, minute=0, second=0).timestamp())
        except ValueError:
            logger.error(f"无效的时间格式: {time_str}")
            return 0

class DynamicFetcher:
    """动态获取类：负责获取用户动态"""
    
    def __init__(self, credential: Credential):
        self.credential = credential
    
    async def fetch_user_dynamics(
        self, 
        user_info: Dict, 
        full_fetch: bool = False,
    ) -> List[Dict]:
        """
        获取用户动态
        :param full_fetch: True=获取全部动态, False=仅获取更新
        """
        uid = user_info['id']
        name = user_info['name']
        since_timestamp = 0 if full_fetch else user_info['roll_time']
        
        since_str = datetime.fromtimestamp(since_timestamp).strftime("%Y-%m-%d %H:%M:%S") if since_timestamp else "起始"
        logger.info(f"开始获取用户 {name}({uid}) 的动态，模式: {'全量' if full_fetch else '增量'}, 起始时间: {since_str}")
        
        u = user.User(uid, credential=self.credential)
        all_dynamics = []
        offset = ""
        page = 0
        has_more = True
        
        try:
            while has_more:
                page += 1
                await asyncio.sleep(random.uniform(1, 3))  # 随机延迟
                
                logger.debug(f"请求用户 {name} 第 {page} 页动态，offset={offset}")
                dynamics = await u.get_dynamics_new(offset)
                
                if not dynamics or "items" not in dynamics or not dynamics["items"]:
                    logger.info(f"用户 {name} 第 {page} 页无数据，停止翻页")
                    break
                
                items = dynamics["items"]
                logger.info(f"用户 {name} 第 {page} 页获取到 {len(items)} 条动态")
                
                for item in items:
                    try:
                        timestamp = item["modules"]["module_author"]["pub_ts"]
                    except KeyError:
                        logger.warning(f"动态缺少pub_ts，使用当前时间")
                        timestamp = int(datetime.now().timestamp())
                    
                    # 增量模式且动态时间早于起始时间，停止翻页
                    if not full_fetch and timestamp <= since_timestamp:
                        timestamp_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                        logger.info(f"用户 {name} 遇到旧动态(<= {since_str})，停止翻页")
                        has_more = False
                        break
                    
                    if not has_more:
                        break

                    dynamic_id = item.get("id_str", str(item.get("id", "")))
                    all_dynamics.append({
                        "user_id": uid,
                        "user_name": name,
                        "id": dynamic_id,
                        "type": item.get("type", "UNKNOWN"),
                        "type_name": DYNAMIC_TYPE_MAP.get(item.get("type", ""), "未知类型"),
                        "timestamp": timestamp,
                        "raw_data": item
                    })
                
                # 检查是否还有更多
                if has_more:
                    has_more = dynamics.get("has_more", 0) == 1
                    if has_more:
                        offset = dynamics.get("offset", "")
        
        except Exception as e:
            logger.error(f"获取用户 {name} 动态失败: {str(e)}")
        
        logger.info(f"用户 {name} 共获取到 {len(all_dynamics)} 条动态，共翻了 {page} 页")
        return all_dynamics    

class DynamicProcessor(ABC):
    """动态处理器基类"""
    
    def __init__(self, dynamic_data: Dict):
        self.data = dynamic_data
    
    @abstractmethod
    def extract_content(self) -> Dict:
        """提取动态主要内容"""
        pass
    
    @abstractmethod
    async def download_resources(self, downloader: Any) -> bool:
        """下载资源"""
        pass

class DrawProcessor(DynamicProcessor):
    """图文动态处理器"""
    
    def extract_content(self) -> Dict:
        """提取图文动态内容"""
        item = self.data["raw_data"]
        content = {
            "text": "",
            "image_urls": []
        }

        try:
            # 提取文本内容
            modules = item.get("modules", {})
            module_dynamic = modules.get("module_dynamic", {})
            desc = module_dynamic.get("desc", {}) or {}
            content["text"] = desc.get("text", "")
            
            # 提取图片URL
            content["image_urls"] = self._extract_image_urls(item)
        
        except Exception as e:
            # 添加更详细的错误日志
            logger.error(f"提取图文内容失败: {str(e)}")
        
        return content
    
    async def download_resources(self, downloader: Any) -> bool:
        """下载图片资源"""
        content = self.extract_content()
        if not content["image_urls"]:
            return False
        
        user_name = self.data["user_name"]
        dynamic_id = self.data["id"]
        return await downloader.download_images(user_name, dynamic_id, content["image_urls"], "draw")
    
    def _extract_image_urls(self, item: Dict) -> List[str]:
        """提取图片URL"""
        image_urls = []
        
        try:
            modules = item.get("modules", {})
            module_dynamic = modules.get("module_dynamic", {})
            
            # 主要图片区域
            major = module_dynamic.get("major")
            if major and major.get("type") == "MAJOR_TYPE_OPUS":
                pics = major.get("opus", {}).get("pics", [])
                for pic in pics:
                    if url := pic.get("url"):
                        image_urls.append(url)
            
            # 转发动态中的图片
            origin = item.get("origin")
            if origin:
                origin_modules = origin.get("modules", {})
                origin_dynamic = origin_modules.get("module_dynamic", {})
                origin_major = origin_dynamic.get("major")
                if origin_major and origin_major.get("type") == "MAJOR_TYPE_DRAW":
                    items = origin_major.get("draw", {}).get("items", [])
                    for img in items:
                        if url := img.get("src"):
                            image_urls.append(url)
        
        except Exception as e:
            logger.error(f"提取图片URL失败: {str(e)}")
        
        return list(set(image_urls))

class VideoProcessor(DynamicProcessor):
    """视频动态处理器"""
    
    def extract_content(self) -> Dict:
        """提取视频动态内容"""
        return {
            "type": "video",
            "title": "",
            "cover_url": "",
            "video_url": ""
        }
    
    async def download_resources(self, downloader: Any) -> bool:
        """下载视频封面"""
        print("视频下载功能未实现，跳过处理。")
        # 待实现
        return False

class ArticleProcessor(DynamicProcessor):
    """专栏动态处理器"""
    
    def extract_content(self) -> Dict:
        """提取专栏内容"""
        return {
            "type": "article",
            "title": "",
            "content": "",
            "image_urls": []
        }
    
    async def download_resources(self, downloader: Any) -> bool:
        """下载专栏图片"""
        print("专栏下载功能未实现，跳过处理。")
        # 待实现
        return False

class ForwardProcessor(DynamicProcessor):
    """转发动态处理器"""
    
    def extract_content(self) -> Dict:
        """提取转发内容"""
        return {
            "type": "forward",
            "text": "",
            "origin": {}
        }
    
    async def download_resources(self, downloader: Any) -> bool:
        """处理转发内容中的资源"""
        print("转发下载功能未实现，跳过处理。")
        # 待实现
        return False

class DefaultProcessor(DynamicProcessor):
    """默认动态处理器"""
    
    def extract_content(self) -> Dict:
        """提取基础内容"""
        return {
            "type": self.data["type_name"],
            "raw_type": self.data["type"],
            "timestamp": self.data["timestamp"]
        }
    
    async def download_resources(self, downloader: Any) -> bool:
        """默认不下载资源"""
        print("默认下载功能未实现，跳过处理。")
        return False

class ProcessorFactory:
    """动态处理器工厂"""
    
    @staticmethod
    def create_processor(dynamic_data: Dict) -> DynamicProcessor:
        """根据动态类型创建处理器"""
        dyn_type = dynamic_data.get("type", "UNKNOWN")
        
        if dyn_type == "DYNAMIC_TYPE_DRAW":
            return DrawProcessor(dynamic_data)
        elif dyn_type == "DYNAMIC_TYPE_AV":
            return VideoProcessor(dynamic_data)
        elif dyn_type == "DYNAMIC_TYPE_ARTICLE":
            return ArticleProcessor(dynamic_data)
        elif dyn_type == "DYNAMIC_TYPE_FORWARD":
            return ForwardProcessor(dynamic_data)
        else:
            return DefaultProcessor(dynamic_data)

class ContentDownloader:
    """内容下载类"""
    
    def __init__(self, base_dir: str = "C:/Users/Ryimi/Downloads/bilibili"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        self.failed_downloads = []
        self.semaphore = asyncio.Semaphore(5)  # 并发控制
    
    async def download_images(self, user_name: str, dynamic_id: str, image_urls: List[str], dynamic_type: str = "draw") -> bool:
        """下载图片"""
        if not image_urls:
            return False
        
        async with self.semaphore:
            # 随机延迟防止高并发
            await asyncio.sleep(random.uniform(0.5, 2.0))
            return await asyncio.get_event_loop().run_in_executor(
                None, self._download_images_sync, user_name, dynamic_id, image_urls, dynamic_type
            )
    
    def _download_images_sync(self, user_name: str, dynamic_id: str, image_urls: List[str], dynamic_type: str) -> bool:
        """同步下载图片"""
        try:
            import requests

            # 创建用户目录
            user_dir = os.path.join(self.base_dir, user_name.replace('/', '_').replace('\\', '_'))
            os.makedirs(user_dir, exist_ok=True)
            # 创建类型-id 目录
            type_id_dir = os.path.join(user_dir, f"{dynamic_type}-{dynamic_id}")
            os.makedirs(type_id_dir, exist_ok=True)
            
            success = False
            for idx, url in enumerate(image_urls, 1):
                ext = os.path.splitext(url)[1].split('?')[0] or '.jpg'
                safe_name = user_name.replace('/', '_').replace('\\', '_')
                img_path = os.path.join(type_id_dir, f"{safe_name}_{dynamic_id}_{idx}{ext}")
                
                try:
                    resp = requests.get(url, timeout=10)
                    if resp.status_code == 200:
                        with open(img_path, 'wb') as f:
                            f.write(resp.content)
                        logger.info(f"图片已保存: {img_path}")
                        success = True
                    else:
                        logger.warning(f"下载图片失败: {url} 状态码: {resp.status_code}")
                        self.failed_downloads.append((dynamic_id, user_name, url))
                except Exception as e:
                    logger.error(f"下载图片异常: {url} 错误: {str(e)}")
                    self.failed_downloads.append((dynamic_id, user_name, url))
            
            return success
        except Exception as e:
            logger.error(f"保存图片失败: {str(e)}")
            return False

class OutputManager:
    """输出管理类"""
    
    def __init__(self, csv_file: Optional[str] = None, user_manager: Optional[UserManager] = None):
        self.csv_file = csv_file
        self.user_manager = user_manager  # 添加 UserManager 引用
        self.results = []
        self.updated_users = {}
    
    def add_result(self, result: Dict):
        """添加处理结果"""
        self.results.append(result)
        
        # 记录需要更新轮询时间的用户
        # 只更新从 CSV 加载的用户
        user_id = result["user_id"]
        if self.user_manager:
            user_info = next((u for u in self.user_manager.users if u["id"] == user_id), None)
            if user_info and user_info.get("source") == "csv":
                now = datetime.now()
                today_zero = datetime(now.year, now.month, now.day)
                self.updated_users[user_id] = today_zero.strftime("%Y:%m:%d")
    
    def save_to_json(self, file_path: str):
        """保存结果到JSON文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
            logger.info(f"结果已保存到: {file_path}")
        except Exception as e:
            logger.error(f"保存JSON失败: {str(e)}")
    
    def update_csv(self):
        """更新CSV文件中的轮询时间"""
        if not self.csv_file or not os.path.exists(self.csv_file):
            logger.warning(f"CSV文件不存在: {self.csv_file}")
            return
        
        try:
            df = pd.read_csv(self.csv_file, dtype=str).fillna('')
            updated_count = 0
            
            for idx, row in df.iterrows():
                user_id = row.get('bilibili_id')
                if user_id and user_id.isdigit() and int(user_id) in self.updated_users:
                    df.at[idx, 'bilibili_roll_time'] = self.updated_users[int(user_id)]
                    updated_count += 1
            
            df = df.astype(str)
            df.to_csv(self.csv_file, index=False, encoding='utf-8')
            logger.info(f"已更新 {updated_count} 个用户的轮询时间")
        except Exception as e:
            logger.error(f"更新CSV失败: {str(e)}")
    
    def print_summary(self):
        """打印处理摘要"""
        success = 0
        failed = 0
        types_count = {}
        
        for result in self.results:
            if result["download_success"]:
                success += 1
            else:
                failed += 1
            
            dyn_type = result["type_name"]
            types_count[dyn_type] = types_count.get(dyn_type, 0) + 1
        
        print("\n" + "="*50)
        print(f"处理完成! 总计: {len(self.results)} 条动态")
        print(f"成功下载: {success} 条, 失败: {failed} 条")
        print("\n动态类型分布:")
        for dyn_type, count in types_count.items():
            print(f"  {dyn_type}: {count} 条")
        
        if failed > 0:
            print("\n失败详情请查看日志")
        print("="*50)

class BiliDynamicHarvester:
    """B站动态采集主控制器"""
    
    def __init__(self):
        self.user_manager = UserManager()
        self.downloader = ContentDownloader()
        self.output_manager = None
    
    async def process_user(self, user_info: Dict, credential: Credential, full_fetch: bool = False):
        """处理单个用户的所有动态"""
        fetcher = DynamicFetcher(credential)
        dynamics = await fetcher.fetch_user_dynamics(user_info, full_fetch)
        
        for dynamic in dynamics:
            processor = ProcessorFactory.create_processor(dynamic)
            
            # 提取内容
            content = processor.extract_content()
            
            # 下载资源
            download_success = await processor.download_resources(self.downloader)
            
            # 记录结果
            result = {
                "user_id": user_info["id"],
                "user_name": user_info["name"],
                "dynamic_id": dynamic["id"],
                "type": dynamic["type"],
                "type_name": dynamic["type_name"],
                "timestamp": dynamic["timestamp"],
                "content": content,
                "download_success": download_success
            }
            
            self.output_manager.add_result(result)
            
            # 日志记录
            logger.info(f"处理动态: 用户={user_info['name']}, ID={dynamic['id']}, "
                       f"类型={dynamic['type_name']}, 下载={'成功' if download_success else '失败'}")
    
    async def run(
        self, 
        credential: Credential,
        csv_file: Optional[str] = None,
        full_fetch: bool = False,
        group_size: int = 5
    ):
        """运行采集器"""
        # 初始化输出管理器
        self.output_manager = OutputManager(csv_file, self.user_manager)
        
        if not self.user_manager.users:
            logger.warning("没有可处理的用户")
            return
        
        # 分组处理用户
        user_groups = self.user_manager.get_users(group_size)
        
        for group in user_groups:
            tasks = [self.process_user(user, credential, full_fetch) for user in group]
            await asyncio.gather(*tasks)
            
            # 组间延迟
            await asyncio.sleep(random.uniform(5, 10))
        
        # 后处理
        if csv_file:
            self.output_manager.update_csv()
        
        self.output_manager.save_to_json("C:/Users/Ryimi/Downloads/bilibili/results.json")
        self.output_manager.print_summary()
        
        # 打印下载失败详情
        if self.downloader.failed_downloads:
            print("\n下载失败详情:")
            for fail in self.downloader.failed_downloads:
                print(f"动态ID: {fail[0]}, 用户: {fail[1]}, URL: {fail[2]}")

def load_bilibili_credential(cookies_path: str = "userdata/bilibili-cookies.json") -> Credential:
    """加载B站凭证"""
    try:
        with open(cookies_path, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
    except Exception as e:
        logger.error(f"加载Cookie失败: {str(e)}")
        raise
    
    def get_cookie_value(name: str) -> str:
        for c in cookies:
            if c.get('name', '').lower() == name.lower():
                return c.get('value', '')
        return ''
    
    return Credential(
        sessdata=get_cookie_value('SESSDATA'),
        bili_jct=get_cookie_value('bili_jct'),
        buvid3=get_cookie_value('buvid3')
    )

async def main():
    """主函数"""
    # 初始化采集器
    harvester = BiliDynamicHarvester()
    
    # 加载凭证
    try:
        credential = load_bilibili_credential()
    except Exception as e:
        logger.error(f"凭证加载失败: {str(e)}")
        return
    
    # 从 CSV 加载用户（会更新轮询时间）
    # csv_path = "data/Artist.csv"
    # harvester.user_manager.load_from_csv(csv_path)

    # 手动添加用户（不会更新轮询时间）
    harvester.user_manager.add_user(12376109, "七赫兹_SevenHz")

    # 运行采集
    await harvester.run(
        credential=credential,
        # csv_file=csv_path,  # CSV文件路径
        csv_file=None,  # CSV文件路径
        full_fetch=False,           # True=全量抓取, False=增量抓取
        group_size=3                 # 每组用户数量
    )


async def fetch_single_dynamic(credential: Credential, user_id: int, dynamic_id: str):
    """
    获取指定动态的原始数据
    :param credential: B站凭证
    :param user_id: 用户ID
    :param dynamic_id: 动态ID
    :return: 动态的原始数据
    """
    u = user.User(user_id, credential=credential)
    offset = ""
    has_more = True
    try:
        while has_more:
            # 获取用户的动态数据
            dynamics = await u.get_dynamics_new(offset)
            if not dynamics or "items" not in dynamics or not dynamics["items"]:
                break
            items = dynamics["items"]
            for item in items:
                item_dynamic_id = item.get("id_str", str(item.get("id", "")))
                if item_dynamic_id == dynamic_id:
                    return item
            # 检查是否还有更多
            has_more = dynamics.get("has_more", 0) == 1
            if has_more:
                offset = dynamics.get("offset", "")
    except Exception as e:
        logger.error(f"获取动态 {dynamic_id} 失败: {str(e)}")
    return None

async def testoneopus():
    """主函数"""
    
    # 加载凭证
    try:
        credential = load_bilibili_credential()
    except Exception as e:
        logger.error(f"凭证加载失败: {str(e)}")
        return

    # 获取指定动态的原始数据
    user_id = 23306371  # 替换为实际的用户ID
    dynamic_id = "992701134074281988"  # 替换为实际的动态ID
    single_dynamic = await fetch_single_dynamic(credential, user_id, dynamic_id)
    if single_dynamic:
        print(f"动态 {dynamic_id} 的原始数据:")
        print(json.dumps(single_dynamic, ensure_ascii=False, indent=2))
        # 构建动态数据字典
        dynamic_data = {
            "user_id": user_id,
            "user_name": "手动用户",  # 这里可以根据实际情况修改
            "id": dynamic_id,
            "type": single_dynamic.get("type", "UNKNOWN"),
            "type_name": DYNAMIC_TYPE_MAP.get(single_dynamic.get("type", ""), "未知类型"),
            "timestamp": single_dynamic["modules"]["module_author"]["pub_ts"],
            "raw_data": single_dynamic
        }

        # 创建下载器和处理器
        downloader = ContentDownloader()
        processor = DrawProcessor(dynamic_data)

        # 提取内容
        content = processor.extract_content()

        # 下载资源
        download_success = await processor.download_resources(downloader)

        if download_success:
            print(f"动态 {dynamic_id} 的图片下载成功")
        else:
            print(f"动态 {dynamic_id} 的图片下载失败")
    else:
        print(f"未找到动态 {dynamic_id} 的原始数据")


if __name__ == "__main__":
    # asyncio.run(testoneopus())
    asyncio.run(main())
