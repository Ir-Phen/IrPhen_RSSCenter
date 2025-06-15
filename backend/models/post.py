# 数据结构（Pydantic / ORM）
from pydantic import BaseModel
from datetime import datetime

class Post(BaseModel):
	id: str
	title: str
	author: str
	published_at: datetime
	content: str
	source: str # 如 bilibili / pixiv 等
