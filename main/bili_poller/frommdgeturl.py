import os
import re
import sys
from pathlib import Path

def extract_links_from_md(content):
    """从Markdown内容中提取一级标题后的所有链接"""
    # 找到一级标题的位置
    title_match = re.search(r'^#\s.+$', content, re.MULTILINE)
    if not title_match:
        return []
    
    start_pos = title_match.start()
    
    # 提取一级标题之后的内容
    content_after_title = content[start_pos:]
    
    # 匹配所有Markdown格式的链接
    links = re.findall(r'!?\[.*?\]\((.+?)\)', content_after_title)
    return links

def process_directory(directory, output_file):
    """处理目录中的所有Markdown文件"""
    if not os.path.exists(directory):
        print(f"错误: 目录 '{directory}' 不存在")
        return
    
    md_files = list(Path(directory).rglob('*.md'))
    all_links = []
    
    if not md_files:
        print(f"警告: 在目录 '{directory}' 中没有找到任何Markdown文件")
        return
    
    for file_path in md_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                links = extract_links_from_md(content)
                if links:
                    all_links.extend(links)
                    print(f"在 {file_path} 中找到 {len(links)} 个链接")
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
    
    # 去重并保存到文件
    unique_links = set(all_links)
    with open(output_file, 'w', encoding='utf-8') as f:
        for link in unique_links:
            f.write(link + '\n')
    
    print(f"\n提取完成! 共找到 {len(unique_links)} 个唯一链接")
    print(f"结果已保存到: {output_file}")

if __name__ == "__main__":
    process_directory(r'data\bilibili\userdata\downloads\32200784', r'data\bilibili\userdata')