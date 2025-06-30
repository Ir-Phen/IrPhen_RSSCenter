import csv
import re
from urllib.parse import urlparse

def is_hex_id(s):
    return bool(re.fullmatch(r'[0-9a-fA-F]+', s))

def is_id(s):
    # 允许数字、字母、下划线、连字符
    return bool(re.fullmatch(r'[\w\-]+', s))

def is_pixiv_url(s):
    return bool(re.fullmatch(r'https://www\.pixiv\.net/users/\d+', s))

def is_twitter_url(s):
    return bool(re.fullmatch(r'https://x\.com/[\w\d_]+', s))

def is_weibo_url(s):
    return bool(re.fullmatch(r'https://weibo\.com/u/\d+', s))

def is_bilibili_url(s):
    return bool(re.fullmatch(r'https://space\.bilibili\.com/\d+', s))

def is_url(s):
    if not s.startswith('http://') and not s.startswith('https://'):
        return False
    try:
        result = urlparse(s)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def split_multi(s):
    return [x.strip() for x in s.split(';')] if s else []

def check_csv_keys(file_path):
    with open(file_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        # 检查列名
        if len(fieldnames) != len(set(fieldnames)):
            print("列名有重复！")
        for name in fieldnames:
            if not name or name.strip() != name:
                print(f"列名有空值或多余空格: '{name}'")
            if re.search(r'[^\w\d_一-龥ぁ-んァ-ンー・（）()@\-.,;: ]', name):
                print(f"列名含有非法字符: '{name}'")
        id_fields = [n for n in fieldnames if n.endswith('_id') or n == 'uni_id']
        url_fields = [n for n in fieldnames if n.endswith('_url')]
        uni_ids = set()
        platforms = [
            ('pixiv', 'pixiv_name', 'pixiv_id', 'pixiv_url', is_pixiv_url),
            ('twitter', 'twitter_name', 'twitter_id', 'twitter_url', is_twitter_url),
            ('weibo', 'weibo_name', 'weibo_id', 'weibo_url', is_weibo_url),
            ('bilibili', 'bilibili_name', 'bilibili_id', 'bilibili_url', is_bilibili_url),
        ]
        for i, row in enumerate(reader, 2):
            # 检查uni_id
            uni_id = row.get('uni_id', '')
            if not uni_id:
                print(f"第{i}行 uni_id 为空")
            else:
                for idx, uid in enumerate(split_multi(uni_id), 1):
                    if not is_hex_id(uid):
                        print(f"第{i}行 uni_id 第{idx}项非16进制: {uid}")
                    if uid in uni_ids:
                        print(f"第{i}行 uni_id 第{idx}项重复: {uid}")
                    else:
                        uni_ids.add(uid)
            # 检查id类字段
            for id_field in id_fields:
                val = row.get(id_field, '')
                for idx, v in enumerate(split_multi(val), 1):
                    if v and not is_id(v):
                        print(f"第{i}行 字段'{id_field}'第{idx}项格式异常: '{v}'")
            # 检查url类字段
            for url_field in url_fields:
                val = row.get(url_field, '')
                for idx, v in enumerate(split_multi(val), 1):
                    if v and not is_url(v):
                        print(f"第{i}行 字段'{url_field}'第{idx}项不是合法URL: '{v}'")
            # 检查url主页格式和三元组缺失（多值适配）
            for plat, name_key, id_key, url_key, url_check in platforms:
                names = split_multi(row.get(name_key, ''))
                ids = split_multi(row.get(id_key, ''))
                urls = split_multi(row.get(url_key, ''))
                maxlen = max(len(names), len(ids), len(urls))
                for idx in range(maxlen):
                    name = names[idx] if idx < len(names) else ''
                    id_ = ids[idx] if idx < len(ids) else ''
                    url = urls[idx] if idx < len(urls) else ''
                    filled = [bool(name), bool(id_), bool(url)]
                    if any(filled) and not all(filled):
                        missing = []
                        if not name: missing.append(name_key)
                        if not id_: missing.append(id_key)
                        if not url: missing.append(url_key)
                        print(f"第{i}行 {plat} 第{idx+1}组字段有缺失: {', '.join(missing)}")
                    if url and not url_check(url):
                        print(f"第{i}行 {plat}_url 第{idx+1}项非主页格式: {url}")
            # 检查每个字段是否有多余空格或不可见字符
            for k, v in row.items():
                for idx, vv in enumerate(split_multi(v), 1):
                    if vv and (vv != vv.strip()):
                        print(f"第{i}行 字段'{k}'第{idx}项有多余空格: '{vv}'")
                    if vv and any(ord(c) < 32 and c not in '\t\n\r' for c in vv):
                        print(f"第{i}行 字段'{k}'第{idx}项含有不可见字符: '{vv}'")

if __name__ == "__main__":
    check_csv_keys("data/Artist.csv")