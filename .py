import pandas as pd
from datetime import datetime

# 读取CSV文件，所有列都当做字符串

df = pd.read_csv(r'data\Artist.csv', dtype=str)

# 指定要写入的时间戳
timestamp = '2025:05:31'

# 检查bilibili_id列非空的行，并写入bilibili_roll_time列
df.loc[df['bilibili_id'].notna() & (df['bilibili_id'] != ''), 'bilibili_roll_time'] = timestamp

# 保存修改后的CSV，所有数据都为字符串
df.to_csv(r'data\Artist.csv', index=False)