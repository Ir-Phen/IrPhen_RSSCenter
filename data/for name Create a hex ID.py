import pandas as pd
import numpy as np

def fill_uni_id(filename, output_filename):
    """
    填充 CSV 文件中 'uni_id' 列为空的项，使用从零开始正序增加的六位十六进制唯一标识。

    Args:
        filename (str): 输入 CSV 文件的路径。
        output_filename (str): 输出 CSV 文件的路径。
    """
    try:
        # 1. 读取 CSV 文件
        df = pd.read_csv(filename, dtype=str)
    except FileNotFoundError:
        print(f"错误：文件 '{filename}' 未找到。请确保文件存在。")
        return
    except Exception as e:
        print(f"读取 CSV 文件时发生错误：{e}")
        return

    # 2. 识别 'uni_id' 列中为空的项
    # 考虑 None, NaN, 和空字符串作为空值
    # 使用 .fillna('') 将 NaN 转换为空字符串，以便更容易地识别空值
    df['uni_id'] = df['uni_id'].replace({np.nan: ''})
    empty_uni_id_indices = df[df['uni_id'].astype(str).str.strip() == ''].index

    # 如果没有空的 uni_id，则直接保存并退出
    if empty_uni_id_indices.empty:
        print("所有 'uni_id' 字段都已填充，无需操作。")
        df.to_csv(output_filename, index=False)
        print(f"文件已保存到 '{output_filename}' (未修改)。")
        return

    # 3. 生成唯一 ID
    # 获取当前 uni_id 中已有的最大数字（如果它们是十六进制数字）
    # 过滤掉非十六进制格式的 uni_id，以避免转换错误
    existing_hex_ids = []
    for uid in df['uni_id'].dropna():
        try:
            # 尝试将现有 uni_id 转换为整数，如果它们是有效的六位十六进制
            if isinstance(uid, str) and len(uid) == 6 and all(c in '0123456789abcdefABCDEF' for c in uid):
                existing_hex_ids.append(int(uid, 16))
        except ValueError:
            # 忽略非十六进制格式的 uni_id
            pass

    # 确定起始计数器：如果存在现有十六进制ID，则从最大值 + 1 开始，否则从 0 开始
    start_counter = max(existing_hex_ids) + 1 if existing_hex_ids else 0

    # 生成足够数量的唯一十六进制 ID
    num_to_generate = len(empty_uni_id_indices)
    new_ids = []
    current_counter = start_counter

    for _ in range(num_to_generate):
        while True:
            hex_id = format(current_counter, '06x') # 格式化为六位十六进制
            # 确保生成的 ID 在现有 uni_id 中是唯一的
            if hex_id not in df['uni_id'].values:
                new_ids.append(hex_id)
                current_counter += 1
                break
            current_counter += 1 # 如果重复则继续增加计数器

    # 4. 填充空值
    df.loc[empty_uni_id_indices, 'uni_id'] = new_ids

    # 5. 保存 CSV 文件
    df.to_csv(output_filename, index=False)
    print(f"已成功填充 'uni_id' 空值，文件已保存到 '{output_filename}'。")

# 运行函数来填充 uni_id
fill_uni_id("data/Artist.csv", "data/Artist.csv")