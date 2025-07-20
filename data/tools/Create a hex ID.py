import pandas as pd
import numpy as np

def fill_uni_id(filename, output_filename):
    """
    填充 CSV 文件中 'uni_id' 列为空的项，生成六位长度的十进制唯一标识（前面补零）。
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
    df['uni_id'] = df['uni_id'].replace({np.nan: ''})
    empty_uni_id_indices = df[df['uni_id'].astype(str).str.strip() == ''].index

    if empty_uni_id_indices.empty:
        print("所有 'uni_id' 字段都已填充，无需操作。")
        df.to_csv(output_filename, index=False)
        return

    # 3. 收集所有已用的六位十进制id（转换为整数处理）
    used_ids = set()
    invalid_ids = []
    
    for uid in df['uni_id'].dropna():
        if isinstance(uid, str) and len(uid) == 6 and uid.isdigit():
            used_ids.add(int(uid))
        else:
            invalid_ids.append(uid)
    
    if invalid_ids:
        print(f"警告：发现 {len(invalid_ids)} 个不符合六位十进制格式的ID，这些将被忽略")

    # 找到已用id中的最大值
    max_id = max(used_ids) if used_ids else -1

    # 检查0~999999范围内被跳过的id
    all_possible_ids = set(range(1000000))  # 000000~999999
    available_ids = sorted(all_possible_ids - used_ids)

    num_to_generate = len(empty_uni_id_indices)
    if len(available_ids) < num_to_generate:
        print(f"错误：无法生成足够的唯一ID。需要 {num_to_generate} 个，但只有 {len(available_ids)} 个可用")
        return

    # 4. 生成新ID（六位十进制，前面补零）
    new_ids = [f"{available_ids[i]:06d}" for i in range(num_to_generate)]

    # 5. 填充空值
    df.loc[empty_uni_id_indices, 'uni_id'] = new_ids
    
    # 重置索引并保存
    df = df.reset_index(drop=True)
    df.to_csv(output_filename, index=False)
    print(f"已成功填充 {len(new_ids)} 个 'uni_id' 空值，文件已保存到 '{output_filename}'")

# 运行函数来填充 uni_id
fill_uni_id("data/Artist.csv", "data/Artist.csv")