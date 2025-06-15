import json
from bilibili_api import dynamic
from bilibili_api import Credential

async def get_user_dynamics_and_export_json():
    # 替换为实际的凭据信息
    credential = Credential(sessdata="88000d5c%2C1765404109%2Cd6199%2A62CjD09cVXp23EtRgCPOA48AE4sf6XBXYYBzYAcdDztRyyfqQXnW47ED_rBAdzeYORv7wSVlJ0bDg2aHdLeXd6Q2xuTVJ4cGRCWGZ5NFdGVDdEQVB4YXZyTUhVS2FZbjh0cEhfdUQyMjZvbWFZTGlfcFkwZWRUN25BUFFCYm55WnFkZWRLcUQzbVhBIIEC", bili_jct="f0c1edb4d5f44cfa6d55842c8df308c5", dedeuserid="67727345-8BA8-E479-5FD1-64450BB5A1A485280infoc")
    # 替换为目标用户的host_mid（UP主ID）
    host_mid = 23306371
    try:
        # 获取动态列表信息
        dynamics = await dynamic.get_dynamic_page_info(credential=credential, host_mid=host_mid)
        # 将动态列表转换为JSON格式的字符串
        dynamics_json = json.dumps(dynamics, ensure_ascii=False, indent=4)
        # 导出为JSON文件
        with open("user_dynamics.json", "w", encoding="utf-8") as f:
            f.write(dynamics_json)
        print("用户动态列表已成功导出为user_dynamics.json文件")
    except Exception as e:
        print(f"获取用户动态列表并导出JSON时出错：{e}")

# 如果你在Jupyter notebook或其他异步支持环境中，可直接运行
# get_user_dynamics_and_export_json()

# 如果你在普通脚本中，可以这样运行：
import asyncio
asyncio.run(get_user_dynamics_and_export_json())