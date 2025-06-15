import pandas as pd

# 读取CSV文件
df = pd.read_csv('data/Artist.csv', dtype=str)

# 删除所有项都为空值的行
df_cleaned = df.dropna(how='all')

# 可选：保存清理后的数据
df_cleaned.to_csv('data/Artist.csv', index=False)