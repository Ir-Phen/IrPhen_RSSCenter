import json
from bilibili_api import Credential

def load_bilibili_credential(cookies_path: str = r"userdata/bilibili-cookies.json") -> Credential:
    """
    从指定路径的JSON文件加载B站凭证
    
    Args:
        cookies_path: 存储B站Cookie的JSON文件路径
    
    Returns:
        Credential对象，包含SESSDATA、bili_jct和buvid3
    """
    try:
        with open(cookies_path, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Cookie文件不存在: {cookies_path}")
    except json.JSONDecodeError:
        raise ValueError(f"Cookie文件格式错误: {cookies_path}")
    
    def get_cookie_value(name: str) -> str:
        """从cookie列表中获取指定名称的cookie值"""
        for c in cookies:
            if c.get('name', '').lower() == name.lower():
                return c.get('value', '')
        return ''
    
    # 创建并返回Credential对象
    return Credential(
        sessdata=get_cookie_value('SESSDATA'),
        bili_jct=get_cookie_value('bili_jct'),
        buvid3=get_cookie_value('buvid3')
    )    