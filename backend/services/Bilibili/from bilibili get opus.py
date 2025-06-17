# 从bilibili获取图文内容
import asyncio
from bilibili_api import opus

# 设置最大并发数
semaphore = asyncio.Semaphore(5)

Data_FILE = "23306371.json"
# 抓取单个 opus 的 Markdown 内容
async def fetch_opus_md(opus_id: str):
    # 初始化 opus 实例
    op = opus.Opus(opus_id=opus_id)
    # 获取 opus 元信息
    info = await op.get_info()
    # 获取 Markdown 格式文本内容
    text = await op.markdown()
    # 拉取图片元信息
    images = await op.get_images_raw_info()

    md_lines = [f"# Opus {opus_id}", "", text, ""]
    for img in images:
        url = img.get("url") or img.get("image_url")
        alt = img.get("desc", "")
        md_lines.append(f"![{alt}]({url})")
    return "\n".join(md_lines)

# 批量抓取
async def fetch_all_opus(opus_ids):
    tasks = [fetch_opus_md(oid) for oid in opus_ids]
    return await asyncio.gather(*tasks)
    

if __name__ == "__main__":
    # 这里填写你要抓取的 Opus ID 列表
    opus_id_list = []

    # 运行并输出
    results = asyncio.run(fetch_all_opus(opus_id_list))
    for md in results:
        print(md)
        print("\n---\n")