# 轮询调度
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.services.fetcher import fetch_bilibili_dynamic_async

scheduler = AsyncIOScheduler()

def setup_tasks():
	scheduler.add_job(fetch_job, 'interval', seconds=600)
	scheduler.start()

async def fetch_job():
	print("Running Bilibili fetch...")
	data = await fetch_bilibili_dynamic_async("12345678")
	print(data)
