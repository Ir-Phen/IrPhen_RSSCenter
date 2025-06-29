'''
下载需要做随机延迟，减少并发
'''

import asyncio
import json
import os
import logging
from bilibili_api import user, opus, Credential, article
import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

class BilibiliDynamicFetcher:
    """B站动态信息获取类"""
    
    def __init__(self, uid, credential=None, since_timestamp=0):
        """
        初始化
        :param uid: 用户UID
        :param credential: 认证信息
        :param since_timestamp: 起始时间戳（秒），只获取此时间之后的动态
        """
        self.uid = uid
        self.credential = credential
        self.since_timestamp = since_timestamp  # 新增时间戳参数
        self.json_file = f"data/bilibili/userdata/{uid}_dynamics.json"
    
    async def fetch_dynamics(self, max_pages=10):
        """获取用户图文动态列表，只返回since_timestamp之后的动态"""
        u = user.User(self.uid, credential=self.credential)
        all_dynamics = []
        page = 0
        offset = 0
        has_older = True  # 标记是否还有更早的动态
        
        while page < max_pages and has_older:
            page += 1
            try:
                logging.info(f"请求第 {page} 页动态，offset={offset}")
                dynamics = await u.get_dynamics(offset)
                
                # 检查返回数据是否有效
                if not dynamics or "cards" not in dynamics or not dynamics["cards"]:
                    logging.info(f"第 {page} 页无数据或格式异常")
                    break
                    
                cards = dynamics["cards"]
                logging.info(f"第 {page} 页获取到 {len(cards)} 条动态")
                
                # 筛选图文动态（类型=2或8）并过滤时间
                for card in cards:
                    try:
                        desc = card.get("desc", {})
                        dyn_type = desc.get("type")
                        timestamp = desc.get("timestamp", 0)  # 获取动态时间戳
                        
                        # 检查是否在时间范围内
                        if timestamp <= self.since_timestamp:
                            has_older = False  # 发现旧动态，停止获取
                            break
                        
                        if dyn_type in [2, 8]:  # 2: 图文动态, 8: 专栏动态
                            dynamic_id = desc.get("dynamic_id")
                            logging.info(f"发现图文动态: ID={dynamic_id}, 类型={dyn_type}, 时间={timestamp}")
                            all_dynamics.append({
                                "id": dynamic_id,
                                "type": dyn_type,
                                "timestamp": timestamp,  # 保存时间戳
                                "raw_data": card
                            })
                    except Exception as e:
                        logging.error(f"处理动态卡片出错: {str(e)}")
                
                # 如果没有更多数据或遇到旧动态，停止翻页
                if not has_older:
                    logging.info(f"遇到旧动态(<= {self.since_timestamp})，停止翻页")
                    break
                
                # 更新offset为最后一条动态的ID，防止死循环
                if cards:
                    new_offset = cards[-1].get("desc", {}).get("dynamic_id", 0)
                    if new_offset == offset:
                        logging.warning(f"offset未变化({offset})，可能到达末尾，停止翻页")
                        break
                    offset = new_offset
                
            except Exception as e:
                logging.error(f"获取动态第 {page} 页出错: {str(e)}")
                break
                
        logging.info(f"共获取到 {len(all_dynamics)} 条图文动态（时间 > {self.since_timestamp}）")
        return all_dynamics
    
    def save_to_json(self, dynamics):
        """保存动态数据到JSON文件"""
        # 确保目录存在
        os.makedirs(os.path.dirname(self.json_file), exist_ok=True)
        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump(dynamics, f, ensure_ascii=False, indent=2)
        logging.info(f"动态数据已保存到 {self.json_file}")
        return self.json_file
    
    def load_from_json(self):
        """从JSON文件加载动态数据"""
        if not os.path.exists(self.json_file):
            return None
            
        with open(self.json_file, 'r', encoding='utf-8') as f:
            return json.load(f)

class BilibiliContentDownloader:
    """B站内容抓取类"""
    
    def __init__(self, credential=None, output_dir="downloads", max_concurrent=5):
        self.credential = credential
        self.output_dir = output_dir
        self.max_concurrent = max_concurrent
        os.makedirs(output_dir, exist_ok=True)
    
    async def download_opus(self, opus_id):
        """下载单个opus的Markdown内容"""
        try:
            # 初始化opus实例
            op = opus.Opus(opus_id=opus_id, credential=self.credential)
            
            # 获取opus元信息
            info = await op.get_info()
            
            # 获取Markdown格式文本内容
            text = await op.markdown()
            
            # 拉取图片元信息
            images = await op.get_images_raw_info()
            
            # 构建Markdown内容
            md_lines = [f"# {info.get('title', f'Opus {opus_id}')}", "", text, ""]
            for img in images:
                url = img.get("url") or img.get("image_url")
                alt = img.get("desc", "")
                md_lines.append(f"![{alt}]({url})")
            
            return "\n".join(md_lines), info
        except Exception as e:
            logging.error(f"下载Opus {opus_id} 失败: {str(e)}")
            return None, None
    
    async def download_article(self, cv_id):
        """下载专栏文章内容"""
        try:
            # 初始化专栏实例
            art = article.Article(cvid=cv_id, credential=self.credential)
            
            # 获取专栏详细信息
            info = await art.get_info()
            
            # 获取专栏内容
            content = await art.get_content()
            
            # 构建Markdown内容
            md_lines = [
                f"# {info.get('title', f'专栏 {cv_id}')}",
                "",
                f"**作者**: {info.get('author', {}).get('name', '未知')}",
                f"**发布时间**: {datetime.fromtimestamp(info.get('publish_time', 0)).strftime('%Y-%m-%d %H:%M:%S')}",
                f"**阅读量**: {info.get('stats', {}).get('view', 0)}",
                "",
                "## 正文",
                ""
            ]
            
            # 处理正文内容
            for item in content:
                if item["type"] == 0:  # 文本段落
                    text = item["content"]
                    # 处理B站的特殊换行格式
                    text = text.replace("\u2028", "\n")
                    md_lines.append(text)
                elif item["type"] == 1:  # 图片
                    img_url = item["url"]
                    img_alt = item["alt"] or "图片"
                    md_lines.append(f"![{img_alt}]({img_url})")
                elif item["type"] == 2:  # 视频
                    bvid = item["bvid"]
                    md_lines.append(f"[视频 BV{bvid}](https://www.bilibili.com/video/{bvid})")
                elif item["type"] == 3:  # 链接卡片
                    link_url = item["link_url"]
                    link_title = item["title"] or "链接"
                    md_lines.append(f"[{link_title}]({link_url})")
                elif item["type"] == 4:  # 引用
                    quote_content = item["content"]
                    md_lines.append(f"> {quote_content}")
                elif item["type"] == 5:  # 代码块
                    code_content = item["content"]
                    md_lines.append("```")
                    md_lines.append(code_content)
                    md_lines.append("```")
            
            return "\n".join(md_lines), info
        except Exception as e:
            logging.error(f"下载专栏 cv{cv_id} 失败: {str(e)}")
            return None, None
    
    async def download_dynamic(self, dynamic_data):
        """根据动态类型下载内容"""
        dynamic_id = dynamic_data["id"]
        dynamic_type = dynamic_data["type"]
        
        if dynamic_type == 2:  # 图文动态
            return await self.download_opus(dynamic_id)
        elif dynamic_type == 8:  # 专栏文章
            # 从原始数据中提取cv号
            raw_data = dynamic_data.get("raw_data", {})
            card_data = raw_data.get("card", {})
            
            # 处理卡片数据可能是字符串的情况
            if isinstance(card_data, str):
                try:
                    card_data = json.loads(card_data)
                except json.JSONDecodeError:
                    logging.error(f"无法解析专栏动态卡片数据: {card_data}")
                    return None, None
            
            # 提取专栏ID
            cv_id = card_data.get("id") or card_data.get("article", {}).get("id")
            
            if not cv_id:
                logging.error(f"无法从动态 {dynamic_id} 提取专栏ID")
                return None, None
            
            return await self.download_article(cv_id)
        else:
            logging.warning(f"未知的动态类型: {dynamic_type} (ID: {dynamic_id})")
            return None, None
    
    def save_content(self, dynamic_id, content, info):
        """保存内容到文件"""
        if not content:
            return False
            
        try:
            # 创建动态专属目录
            dynamic_dir = os.path.join(self.output_dir, str(dynamic_id))
            os.makedirs(dynamic_dir, exist_ok=True)
            
            # 保存Markdown内容
            md_file = os.path.join(dynamic_dir, f"{dynamic_id}.md")
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logging.info(f"动态 {dynamic_id} 内容已保存到 {md_file}")
            return True
        except Exception as e:
            logging.error(f"保存动态 {dynamic_id} 内容失败: {str(e)}")
            return False
    
    async def download_all(self, dynamics):
        """批量下载所有动态内容"""
        if not dynamics:
            logging.warning("没有可下载的动态")
            return
        
        logging.info(f"开始下载 {len(dynamics)} 条动态内容...")
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def download_with_semaphore(dynamic_data):
            async with semaphore:
                content, info = await self.download_dynamic(dynamic_data)
                if content:
                    return self.save_content(dynamic_data["id"], content, info)
                return False
        
        tasks = [download_with_semaphore(data) for data in dynamics]
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r)
        logging.info(f"\n下载完成! 成功: {success_count}, 失败: {len(results) - success_count}")


async def main():
    # 配置认证信息（根据需要）
    credential = Credential(
        sessdata="3a84a2b9%2C1766711892%2C9714b%2A62CjDRA09DniT-5vxbwV64m-Z-Os7ZufCYw7gAHHJO1i0uIhJUHOOA63cmdFACuVUGil0SVkxrc21JZE9MZWJoak9ubkYxTjBYWkQ2TXFKemoyYldXcU1hVy01SC1Tb2Rub2JScU5qM1ZzZFI2NERnLUl1OGVocnRzYTdCbjdnRmVxaW9Wc3BtM0lnIIEC",
        bili_jct="32b3aafa92e44eee2a5dfe5785561e6d",
        buvid3="67727345-8BA8-E479-5FD1-64450BB5A1A485280infocs"
    )
    
    # 目标用户UID和时间戳（例如：获取2023年1月1日之后的数据）
    target_uid = 431436293
    since_ts = 0000000000
    
    # 创建Fetcher并传入时间戳
    fetcher = BilibiliDynamicFetcher(target_uid, credential, since_timestamp=since_ts)
    
    # 获取动态（只会获取指定时间之后的）
    logging.info(f"开始获取用户 {target_uid} 的图文动态...")
    dynamics = await fetcher.fetch_dynamics(max_pages=10)
    if dynamics:
        # 有数据就保存
        fetcher.save_to_json(dynamics)
    else:
        logging.warning("没有获取到任何图文动态")
        return
    
    # 2. 下载动态内容
    downloader = BilibiliContentDownloader(credential, output_dir=f"data/bilibili/userdata/downloads/{target_uid}")
    await downloader.download_all(dynamics)


if __name__ == "__main__":
    asyncio.run(main())