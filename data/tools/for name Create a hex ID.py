import pandas as pd
import numpy as np

def fill_uni_id(filename, output_filename):
    """
    填充 CSV 文件中 'uni_id' 列为空的项，优先复用被跳过的六位十六进制唯一标识。
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

    # 3. 收集所有已用的六位十六进制id
    used_hex_ids = set()
    for uid in df['uni_id'].dropna():
        if isinstance(uid, str) and len(uid) == 6 and all(c in '0123456789abcdefABCDEF' for c in uid):
            used_hex_ids.add(uid.lower())

    # 找到已用id中的最大值
    existing_hex_ints = [int(uid, 16) for uid in used_hex_ids]
    max_id = max(existing_hex_ints) if existing_hex_ints else -1

    # 检查跳过的id（即0~max_id之间未被使用的id）
    skipped_ids = []
    for i in range(max_id + 1):
        hex_id = format(i, '06x')
        if hex_id not in used_hex_ids:
            skipped_ids.append(hex_id)

    num_to_generate = len(empty_uni_id_indices)
    new_ids = []
    # 优先复用跳过的id
    for i in range(min(len(skipped_ids), num_to_generate)):
        new_ids.append(skipped_ids[i])
    # 不够则继续生成新id
    current_counter = max_id + 1
    while len(new_ids) < num_to_generate:
        hex_id = format(current_counter, '06x')
        if hex_id not in used_hex_ids and hex_id not in new_ids:
            new_ids.append(hex_id)
        current_counter += 1

    # 4. 填充空值
    df.loc[empty_uni_id_indices, 'uni_id'] = new_ids

    # 5. 保存 CSV 文件
    df.to_csv(output_filename, index=False)
    print(f"已成功填充 'uni_id' 空值，文件已保存到 '{output_filename}'。")

# 运行函数来填充 uni_id
fill_uni_id("data/Artist.csv", "data/Artist.csv")