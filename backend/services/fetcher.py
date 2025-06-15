from curl_cffi import requests
import asyncio

BILI_HEADERS = {
	"user-agent": "Mozilla/5.0",
	"referer": "https://space.bilibili.com",
	"cookie": "SESSDATA=your_cookie_here;", # 建议从登录模块注入
}

def fetch_bilibili_dynamic_async(uid: str):
	url = f"https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space?host_mid={uid}"
	resp = requests.get(url, headers=BILI_HEADERS, impersonate="chrome110")
	return resp.json()
