import pandas as pd

# 定义表头
columns = [
    'name', 'name_used', 'uni_id', 'pixiv_name', 'pixiv_id', 'pixiv_url',
    'twitter_name', 'twitter_id', 'twitter_url', 'twitter_roll_time',
    'weibo_name', 'weibo_id', 'weibo_url', 'weibo_roll_time',
    'bilibili_name', 'bilibili_id', 'bilibili_url', 'bilibili_roll_time',
    'tags', 'tips'
]

# 创建空的DataFrame
df = pd.DataFrame(columns=columns)


# 读取CSV文件
df = pd.read_csv('data/Artist copy.csv', dtype=str)

# 处理twitter_id
for index, row in df.iterrows():
    twitter_id = row.get('twitter_id', '')
    val_twitter = str(twitter_id)
    # 自动跳过twitter_id为空或NaN
    if not val_twitter or val_twitter == 'nan':
        pass  # 可选择continue或不处理
    else:
        if val_twitter.startswith('*'):
            df.at[index, 'twitter_id'] = row['twitter_id'][1:]
            df.at[index, 'twitter_url'] = row['twitter_url'][1:]
            df.at[index, 'twitter_roll_time'] = '2100:01:01'
        else:
            df.at[index, 'twitter_roll_time'] = '2025:08:01'

# 处理weibo_id
for index, row in df.iterrows():
    weibo_id = row.get('weibo_id', '')
    val_weibo = str(weibo_id)
    # 自动跳过weibo_id为空或NaN
    if not val_weibo or val_weibo == 'nan':
        continue  # 跳过本行
    if val_weibo.startswith('*'):
        df.at[index, 'weibo_id'] = row['weibo_id'][1:]
        df.at[index, 'weibo_url'] = row['weibo_url'][1:]
        df.at[index, 'weibo_roll_time'] = '2100:01:01'
    else:
        df.at[index, 'weibo_roll_time'] = '2025:08:01'

# 写入到CSV文件
df.to_csv('data/Artist copy.csv', index=False, encoding='utf-8-sig')