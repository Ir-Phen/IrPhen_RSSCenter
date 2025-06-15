# 服务器配置
from pydantic import BaseSettings

class Config(BaseSettings):
    FETCH_INTERVAL_SECONDS: int = 600
    DATABASE_URL: str = "sqlite:///./data/rss.db"
    ENABLE_LOGGING: bool = True

config = Config()
