import pandas as pd

# 读取两个CSV文件
artist_df = pd.read_csv('data/Artist.csv', dtype=str)
namecheck_df = pd.read_csv('data/namecheck.csv', dtype=str)

# 创建一个字典，以name为键，存储namecheck中的URL信息
namecheck_dict = {}
for _, row in namecheck_df.iterrows():
    name = row['name']
    namecheck_dict[name] = {
        'pixiv_url': row['pixiv_url'],
        'twitter_url': row['twitter_url'],
        'weibo_url': row['weibo_url'],
        'bilibili_url': row['bilibili_url']
    }

# 更新Artist.csv中的URL信息
for index, row in artist_df.iterrows():
    name = row['name']
    if name in namecheck_dict:
        # 获取namecheck中的URL信息
        nc_data = namecheck_dict[name]
        
        # 更新pixiv_url（添加*前缀）
        if pd.isna(row['pixiv_url']) and nc_data['pixiv_url'] and not pd.isna(nc_data['pixiv_url']):
            artist_df.at[index, 'pixiv_url'] = f"*{nc_data['pixiv_url']}" if not nc_data['pixiv_url'].startswith('*') else nc_data['pixiv_url']
        
        # 更新twitter_url（添加*前缀）
        if pd.isna(row['twitter_url']) and nc_data['twitter_url'] and not pd.isna(nc_data['twitter_url']):
            artist_df.at[index, 'twitter_url'] = f"*{nc_data['twitter_url']}" if not nc_data['twitter_url'].startswith('*') else nc_data['twitter_url']
        
        # 更新weibo_url（添加*前缀）
        if pd.isna(row['weibo_url']) and nc_data['weibo_url'] and not pd.isna(nc_data['weibo_url']):
            artist_df.at[index, 'weibo_url'] = f"*{nc_data['weibo_url']}" if not nc_data['weibo_url'].startswith('*') else nc_data['weibo_url']
        
        # 更新bilibili_url（添加*前缀）
        if pd.isna(row['bilibili_url']) and nc_data['bilibili_url'] and not pd.isna(nc_data['bilibili_url']):
            artist_df.at[index, 'bilibili_url'] = f"*{nc_data['bilibili_url']}" if not nc_data['bilibili_url'].startswith('*') else nc_data['bilibili_url']

# 保存合并后的结果
artist_df.to_csv('data/Artist.csv', index=False)