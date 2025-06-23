import time
import json
import pandas as pd
from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By

def wait_for_clear_state(driver):
    while True:
        handles = driver.window_handles
        if len(handles) == 1:
            driver.switch_to.window(handles[0])
            current_url = driver.current_url
            # 新建一个空白标签页并切换过去
            driver.execute_script("window.open('about:blank', '_blank');")
            driver.switch_to.window(driver.window_handles[-1])
            print("✅ 已新建空白标签页，准备处理下一条记录")
            # 关闭除当前空白页外的所有标签页
            blank_handle = driver.current_window_handle
            for handle in driver.window_handles:
                if handle != blank_handle:
                    driver.switch_to.window(handle)
                    driver.close()
            driver.switch_to.window(blank_handle)
            break
        # print("⚠️ 请关闭多余标签页，确保只剩一个空白页面。等待中...")
        time.sleep(1)

def build_driver(config):
    options = Options()
    options.use_chromium = True
    options.add_argument("--start-maximized")

    # 添加本地 Edge 用户数据目录参数（示例路径，按你本机实际路径调整）
    user_data_dir = config.get("user_data_dir", r"C:\Users\Ryimi\AppData\Local\Microsoft\Edge\User Data")
    options.add_argument(f'--user-data-dir={user_data_dir}')

    # 可选指定具体的Profile目录，通常为 "Default"
    profile_dir = config.get("profile_dir", "Default")
    options.add_argument(f'--profile-directory={profile_dir}')

    # user-agent 和 proxy 仍保留原逻辑（如果有）
    user_agents = config.get("user_agents", [])
    if user_agents:
        options.add_argument(f"user-agent={user_agents[0]}")

    proxy_pool = config.get("proxy_pool", [])
    if proxy_pool:
        proxy = proxy_pool[0]
        proxy_address = proxy.get("http") or proxy.get("https")
        if proxy_address:
            options.add_argument(f'--proxy-server={proxy_address}')

    webdriver_path = config.get("webdriver_path", "./backend/tools/edgedriver_win64/msedgedriver.exe")
    service = EdgeService(executable_path=webdriver_path)

    driver = webdriver.Edge(service=service, options=options)
    return driver

def search_missing_platforms(driver, name, missing_platforms):
    platform_urls = {
        "pixiv": f"https://www.pixiv.net/search/users?nick={name}&s_mode=s_usr",
        "twitter": f"https://x.com/search?q={name}&src=typed_query&f=user",
        "weibo": f"https://s.weibo.com/weibo?q={name}&Refer=weibo_user",
        "bilibili": f"https://search.bilibili.com/upuser?keyword={name}&search_source=1"
    }

    for platform in missing_platforms:
        url = platform_urls.get(platform)
        if url:
            driver.execute_script(f"window.open('{url}', '_blank');")
            print(f"🔍 已打开 {platform} 搜索页面: {url}")

    wait_for_clear_state(driver)

    wait_for_clear_state(driver)

    main_handle = driver.window_handles[0]
    for handle in driver.window_handles[1:]:
        driver.switch_to.window(handle)
        driver.close()
    driver.switch_to.window(main_handle)

    time.sleep(0)

def main():
    df = pd.read_csv("data/Artist.csv", dtype=str).fillna("")
    with open("data/config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    driver = build_driver(config)

    # 设置起点
    start_uni_id = "000021"  # 替换为你想恢复的位置
    start_processing = False

    try:
        driver.get("about:blank")

        for idx, row in df.iterrows():
            uni_id = row.get("uni_id", "").lower()

            # 跳过起始点之前的行
            if not start_processing:
                if uni_id == start_uni_id.lower():
                    start_processing = True
                else:
                    continue

            name = row.get("name", "")

            missing_platforms = []
            if not row.get("pixiv_url"): missing_platforms.append("pixiv")
            if not row.get("twitter_url"): missing_platforms.append("twitter")
            if not row.get("weibo_url"): missing_platforms.append("weibo")
            if not row.get("bilibili_url"): missing_platforms.append("bilibili")

            if not missing_platforms:
                continue

            print(f"\n====== 🔍 正在处理 {name} ({uni_id})，缺失平台: {missing_platforms} ======")
            search_missing_platforms(driver, name, missing_platforms)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
