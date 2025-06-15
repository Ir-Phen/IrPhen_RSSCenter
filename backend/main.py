# FastAPI 应用程序的主要入口点，包括用于前端开发的 CORS 中间件
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api import posts, subscriptions
from backend.utils.logger import setup_logger
from backend.tasks.runner import setup_tasks

setup_tasks()
app = FastAPI(title="IrPhen RSS Center")

# 注册路由
app.include_router(posts.router, prefix="/api/posts")
app.include_router(subscriptions.router, prefix="/api/subscriptions")

# 启动初始化
@app.on_event("startup")
async def startup_event():
    setup_logger()
    print("Server started.")

@app.on_event("shutdown")
async def shutdown_event():
    print("Server shutting down.")

    