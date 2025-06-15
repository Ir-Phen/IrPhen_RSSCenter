# 后端数据库接口
from fastapi import APIRouter
from backend.models.post import Post

router = APIRouter()

@router.get("/", response_model=list[Post])
async def list_posts():
    # TODO: 从数据库读取
    return []
