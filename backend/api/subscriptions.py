# 后端数据库接口
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_subscriptions():
    # TODO: 返回所有订阅信息
    return {"subs": []}