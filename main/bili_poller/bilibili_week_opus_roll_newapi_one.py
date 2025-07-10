import asyncio
from datetime import datetime
from bilibili_week_opus_roll_newapi import run_bili_poller, Credential

async def query_single_user(user_id, since_timestamp):
    """
    完全复用原模块的认证和核心逻辑查询单个用户
    （通过构造单用户组模拟原流程）
    """
    # 1. 构造用户组（与原CSV结构兼容）
    user_group = [{
        'name': f'用户{user_id}',
        'id': user_id,
        'roll_time': since_timestamp,
        'original_roll_time': datetime.fromtimestamp(since_timestamp).strftime("%Y:%m:%d")
    }]

    # 2. 直接调用原模块入口函数（自动复用其认证逻辑）
    await run_bili_poller(
        user_groups=[user_group],  # 传入单用户组
        csv_file=None,  # 禁用CSV读取
        group_size=1    # 组大小为1确保独立处理
    )

# 使用示例
async def main():
    await query_single_user(
        user_id=190024262,  # 替换为目标UID
        since_timestamp=int(datetime(2000, 1, 1).timestamp())
    )

if __name__ == "__main__":
    asyncio.run(main())