# 未做异步!!!!!!!!
# 未做异步!!!!!!!!
# 未做异步!!!!!!!!
# 未做异步!!!!!!!!

import asyncio
import os
import logging
from bilibili_api import opus, Credential

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

class OpusToArticleConverter:
    """将图文动态转换为专栏并下载内容"""
    
    def __init__(self, credential=None, output_dir="downloads/opus_to_article"):
        """
        初始化转换器
        :param credential: 认证信息
        :param output_dir: 输出目录
        """
        self.credential = credential
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    async def convert_and_download(self, opus_id):
        """
        转换图文动态为专栏并下载内容
        :param opus_id: 图文动态ID
        :return: 专栏ID (cv_id) 或 None
        """
        try:
            logging.info(f"开始处理图文动态: {opus_id}")
            
            # 1. 创建图文动态对象
            op = opus.Opus(opus_id=opus_id, credential=self.credential)
            
            # 2. 获取图文动态的Markdown内容
            opus_md = await op.markdown()
            self._save_content(opus_id, "opus", opus_md, None)
            
            # 3. 转换为专栏
            ar = await op.turn_to_article()
            
            # 4. 获取专栏信息
            await ar.fetch_content()
            article_md = ar.markdown()
            
            # 5. 获取专栏ID
            cv_id = ar.get_cvid()
            
            # 6. 保存专栏内容
            self._save_content(opus_id, "article", article_md, cv_id)
            
            logging.info(f"成功将图文动态 {opus_id} 转换为专栏 cv{cv_id}")
            return cv_id
            
        except Exception as e:
            logging.error(f"处理图文动态 {opus_id} 失败: {str(e)}")
            return None
    
    def _save_content(self, opus_id, content_type, content, cv_id):
        """保存内容到文件"""
        try:
            # 创建目录
            dir_path = os.path.join(self.output_dir, str(opus_id))
            os.makedirs(dir_path, exist_ok=True)
            
            # 设置文件名
            if content_type == "opus":
                filename = f"opus_{opus_id}.md"
            else:
                filename = f"article_{cv_id}.md"
            
            # 保存文件
            file_path = os.path.join(dir_path, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logging.info(f"已保存 {content_type} 内容到 {file_path}")
            return True
        except Exception as e:
            logging.error(f"保存 {content_type} 内容失败: {str(e)}")
            return False


async def main():
    # 配置认证信息（可选）
    credential = Credential(
        sessdata="4dc2b669%2C1765665307%2Cad643%2A62CjCBAnpKFve4UwGUXpGEWYUNTCgROqnVUW8Ii8CFzlvPsQnBA85Nwyz_H3wkme8yiLQSVnVLNkZ1U1F6Q21zUE9XR21ENXNPbFNWU3oyNDVWdU94dHdXZmttTU5PM0VTYy1JOTJadDI4T2VQOER0ZVlvMnRfcjVoN1JlNk1rYVJiNlVjWlhQMzZ3IIEC",
        bili_jct="d0436276e559a5da35f7a0ee7a0aaeca",
        buvid3="your_bu67727345-8BA8-E479-5FD1-64450BB5A1A485280infocid3"
    )
    
    # 要转换的图文动态ID列表
    opus_ids = []
    
    # 创建转换器
    converter = OpusToArticleConverter(
        credential=credential,
        output_dir="opus_converted"
    )
    
    # 批量处理所有图文动态
    results = []
    for opus_id in opus_ids:
        cv_id = await converter.convert_and_download(opus_id)
        results.append((opus_id, cv_id))
    
    # 打印结果摘要
    print("\n===== 转换结果摘要 =====")
    success_count = 0
    for opus_id, cv_id in results:
        if cv_id:
            print(f"图文动态 {opus_id} → 专栏 cv{cv_id}")
            success_count += 1
        else:
            print(f"图文动态 {opus_id} → 转换失败")
    
    print(f"\n成功: {success_count}/{len(opus_ids)}")


if __name__ == "__main__":
    asyncio.run(main())