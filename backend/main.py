# FastAPI 应用程序的主要入口点，包括用于前端开发的 CORS 中间件
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api import posts, subscriptions

app = FastAPI(title="IrPhen_RSSCenter Backend")

# CORS（跨域资源共享）配置
origins = [
    "http://localhost",
    "http://localhost:8000",  # Default for Vue/Vite dev server
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(posts.router)
app.include_router(subscriptions.router)

@app.get("/")
async def read_root():
    return {"message": "已进入IrPhen_RSSCenter后端！"}

# 稍后将包括来自api的路由器