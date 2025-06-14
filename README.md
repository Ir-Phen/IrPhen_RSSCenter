# IrPhen_RSSCenter

适用于个人艺术创作者的资源订阅，适配前期设计流程，无痛化日常琐事。

# 代码框架

```
rss_hub_local/
├── backend/                   # Python 后端（FastAPI）
│   ├── main.py               # 启动入口
│   ├── config.py             # 配置项（抓取间隔、限流规则）
│   ├── login                 # 软件后端登录与平台cookie管理
│   ├── models/               # 数据结构（Pydantic / ORM）
│   │   └── post.py
│   ├── api/                  # API 路由模块
│   │   ├── posts.py
│   │   └── subscriptions.py
│   ├── services/             # 业务逻辑（抓取、过滤、调度）
│   │   ├── fetcher.py
│   │   ├── scheduler.py
│   │   └── filter.py
│   ├── storage/              # 数据持久层（SQLite / JSON）
│   │   ├── db.py
│   │   └── interface.py
│   ├── utils/                # 工具模块（日志、限速器、缓存）
│   │   ├── limiter.py
│   │   └── logger.py
│   └── tasks/                # 定时任务调度（APScheduler）
│       └── runner.py
│
├── frontend/                  # Vue 或 React 前端项目
│   ├── public/
│   ├── src/
│   │   ├── views/            # 页面：订阅管理 / 内容浏览 / 设置
│   │   ├── components/       # 复用组件
│   │   ├── api/              # 与后端通信封装
│   │   └── store/            # 状态管理
│   ├── vite.config.js
│   └── index.html
│
├── data/                      # 本地数据（如 JSON 数据存档）
│   └── bilibili.json
├── requirements.txt
└── README.md
```

## 模块职责简要说明

| 模块                      | 职责说明                        |
| ----------------------- | --------------------------- |
| `api/`                  | FastAPI 接口定义，供前端调用          |
| `services/fetcher.py`   | 抓取平台数据（含限流处理）               |
| `services/scheduler.py` | 动态调度订阅抓取任务                  |
| `services/filter.py`    | 对动态做关键词过滤、转发识别等             |
| `storage/`              | 数据存储抽象层（支持切换 SQLite 或 JSON） |
| `tasks/`                | 定时任务与轮询调度主逻辑                |
| `frontend/src/views`    | 包括订阅管理页、浏览页、设置页等            |