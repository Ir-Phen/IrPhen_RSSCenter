import time
import pandas as pd
import json
from datetime import datetime
from pywinauto.application import Application, timings
from pywinauto.findwindows import ElementNotFoundError

# 设置全局超时时间，防止因窗口未及时响应而报错
timings.Timings.window_find_timeout = 15

# 定义一个简单的日志函数，用于统一输出格式
def log(level: str, message: str, indent: int = 0):
    """
    一个简单的日志函数，用于格式化和输出信息。
    
    参数:
    level (str): 日志级别，例如 'INFO', 'SUCCESS', 'ERROR'。
    message (str): 要打印的日志信息。
    indent (int): 缩进级别，用于更清晰地展示层级关系。
    """
    level_map = {
        "INFO": "➡️",
        "SUCCESS": "✅",
        "ERROR": "❌",
        "DEBUG": "🔍",
        "WARNING": "⚠️",
    }
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefix = level_map.get(level, " ")
    indent_str = "  " * indent
    print(f"[{timestamp}] {prefix} {indent_str}{message}")

def read_twitter_csv(file_path: str, encoding: str = 'utf-8') -> tuple[list[dict], list[str]]:
    """
    从CSV文件中读取Twitter ID和时间数据。
    
    参数:
    file_path (str): CSV文件路径。
    encoding (str): 文件编码，默认为'utf-8'。
    
    返回:
    tuple[list[dict], list[str]]: 
        第一个元素: 包含twitter_id和twitter_roll_time的字典列表 (有效数据)。
        第二个元素: 包含';'的Twitter ID列表 (被跳过的数据)。
    
    抛出:
    FileNotFoundError: 如果文件未找到。
    KeyError: 如果CSV文件缺少必要列。
    Exception: 读取过程中发生其他错误。
    """
    try:
        log("INFO", f"正在尝试从 '{file_path}' 读取数据...")
        # 1. 读取CSV文件（仅加载目标列，提升效率）
        df = pd.read_csv(
            file_path,
            usecols=['twitter_id', 'twitter_roll_time'],
            encoding=encoding,
            dtype=str
        )
        
        # 2. 检查是否存在空值
        null_count = df.isnull().sum().sum()
        if null_count > 0:
            log("WARNING", f"CSV文件中存在 {null_count} 个空值，已自动过滤空行。")
            df = df.dropna(subset=['twitter_id', 'twitter_roll_time'])
        
        # 定义过滤条件：不包含';'的ID为有效ID
        valid_condition = ~df['twitter_id'].str.contains(';', na=False)
        # 收集被跳过的含';'的ID（取反条件）
        skipped_ids = df[~valid_condition]['twitter_id'].tolist()
        # 应用过滤条件，只保留有效ID
        filtered_df = df[valid_condition].copy()

        # 3. 转换为列表套字典格式
        twitter_list = filtered_df.to_dict('records')
        
        log("SUCCESS", f"成功读取！共获取 {len(twitter_list)} 条有效Twitter数据。")
        if skipped_ids:
            log("WARNING", f"已跳过 {len(skipped_ids)} 个包含';'的Twitter ID：", indent=1)
            for idx, skipped_id in enumerate(skipped_ids, 1):
                log("WARNING", f"{idx}. {skipped_id}", indent=2)
        else:
            log("INFO", "无包含';'的Twitter ID需要跳过。", indent=1)
        
        return twitter_list, skipped_ids

    except FileNotFoundError:
        log("ERROR", f"未找到文件，请检查路径是否正确 -> {file_path}")
        raise FileNotFoundError(f"未找到文件 -> {file_path}")
    except KeyError as e:
        # 更好地处理缺少列的错误信息
        missing_cols = [col for col in ['twitter_id', 'twitter_roll_time'] if col not in df.columns]
        log("ERROR", f"CSV文件缺少必要列。缺失列：{missing_cols}")
        raise KeyError(f"CSV文件缺少必要列 -> 缺失列：{missing_cols}")
    except Exception as e:
        log("ERROR", f"读取文件失败，原因：{str(e)}")
        raise Exception(f"读取文件失败，原因：{str(e)}")


class XSpiderAutomation:
    """
    用于自动化X-Spider应用程序的类。
    优化了元素查找逻辑，避免每次都重新查找。
    """
    def __init__(self, window_title="X-Spider"):
        self.window_title = window_title
        self.app = None
        self.main_window = None
        # 添加实例属性来存储找到的控件，初始化为None
        self.search_box = None
        self.load_button = None
        self.download_button = None
        self.is_connected = False

    def connect_app(self):
        """
        连接到指定的应用程序窗口，并在连接成功后立即查找并存储常用控件。
        """
        log("INFO", f"正在尝试连接到 '{self.window_title}' 程序...")
        try:
            self.app = Application(backend="uia").connect(title=self.window_title)
            log("SUCCESS", f"成功连接到 '{self.window_title}' 程序。")
            self.main_window = self.app.window(title=self.window_title)
            log("INFO", "正在查找并缓存常用控件...")
            
            # 在连接时一次性找到并缓存控件
            parent_group = self.main_window.child_window(title="搜索用户", control_type="Group")
            self.search_box = parent_group.child_window(control_type="Edit")
            self.load_button = parent_group.child_window(title="加载", control_type="Button")
            self.download_button = self.main_window.child_window(title="开始下载", control_type="Button")
            
            # 检查所有控件是否都已找到并可用
            if not all([self.search_box.exists(), self.load_button.exists(), self.download_button.exists()]):
                log("ERROR", "核心控件未能全部找到，请检查程序界面布局是否与脚本预期一致。")
                self.is_connected = False
                return
            
            log("SUCCESS", "常用控件已成功找到并缓存。")
            self.is_connected = True
            
        except Exception as e:
            log("ERROR", f"连接到 '{self.window_title}' 程序失败，请确保程序已打开。")
            log("DEBUG", f"详细错误信息: {e}")
            self.is_connected = False

    def enter_text_and_click_load(self, text_to_enter: str):
        """
        在搜索框中输入文本，然后点击“加载”按钮。
        此方法现在直接使用已缓存的控件，不再重复查找。
        """
        log("INFO", "----------- 正在执行子任务: 输入和加载 -----------")
        try:
            # 直接使用缓存的 search_box 对象
            log("INFO", f"正在输入文本: '{text_to_enter}' 到搜索框...", indent=1)
            # 使用 set_text() 方法清空并设置文本，避免内容追加
            self.search_box.set_text(text_to_enter)
            log("SUCCESS", "文本输入完成。", indent=1)
            
        except Exception as e:
            log("ERROR", f"输入文本到搜索框失败。")
            log("DEBUG", f"详细错误信息: {e}")
            raise Exception("文本输入失败")
            
        # 直接使用缓存的 load_button 对象
        if self.load_button.is_enabled():
            log("INFO", "'加载' 按钮可用，准备点击。", indent=1)
            self.click_button_with_wait(self.load_button, wait_seconds=5)
        else:
            log("ERROR", "'加载' 按钮不可用或不可见。", indent=1)
            raise Exception("'加载' 按钮不可用")

    def click_button_with_wait(self, button, wait_seconds=5):
        """
        点击一个按钮，并在点击后等待指定秒数。
        """
        try:
            button_name = button.element_info.name
            log("INFO", f"正在模拟点击 '{button_name}' 按钮...", indent=1)
            button.click_input()
            log("SUCCESS", f"'{button_name}' 按钮点击成功！", indent=1)
            
            if wait_seconds > 0:
                log("INFO", f"开始等待 {wait_seconds} 秒以确保程序响应...", indent=1)
                for i in range(wait_seconds):
                    time.sleep(1)
                    # 动态更新进度条
                    print(f"\r等待中... {i + 1}/{wait_seconds} 秒 ", end="", flush=True)
                print("\r") # 换行以清除进度条
        except Exception as e:
            button_name = "未知按钮"
            try:
                button_name = button.element_info.name
            except:
                pass
            log("ERROR", f"点击 '{button_name}' 按钮或等待过程失败。")
            log("DEBUG", f"详细错误信息: {e}")
            raise Exception(f"点击 '{button_name}' 按钮失败")
    
    def run_full_process(self, user_id: str) -> bool:
        """
        执行完整的自动化流程，包括输入ID、加载和下载。
        此方法不再重复查找下载按钮。
        
        参数:
        user_id (str): 要处理的Twitter ID。
        
        返回:
        bool: 如果流程成功则返回True，否则返回False。
        """
        log("INFO", "✨ 开始执行自动化流程...")
        log("INFO", "------------------------------------------")
        
        try:
            # 1. 输入ID并点击加载 (使用已缓存的控件)
            self.enter_text_and_click_load(user_id)
            
            # 2. 点击下载按钮 (直接使用已缓存的控件)
            log("INFO", "----------- 正在执行子任务: 下载 -----------")
            if self.download_button.is_enabled():
                log("INFO", "'开始下载' 按钮可用，准备点击。", indent=1)
                self.click_button_with_wait(self.download_button, wait_seconds=5)
            else:
                log("ERROR", "'开始下载' 按钮不可用或不可见。", indent=1)
                raise Exception("'开始下载' 按钮不可用")
                
            log("INFO", "------------------------------------------")
            log("SUCCESS", "🏁 自动化流程执行完毕。")
            return True
        
        except Exception as e:
            log("ERROR", f"处理账号 '{user_id}' 失败，原因: {e}")
            log("WARNING", "将跳过此账号并继续处理下一个。")
            return False

def save_progress(current_index: int, total_count: int, file_path: str = r'main\twitter_poller\data\progress.json'):
    """将当前处理进度保存到 JSON 文件中。"""
    progress = {
        "current_index": current_index,
        "total_count": total_count
    }
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=4)
    log("INFO", f"进度已保存: {current_index}/{total_count}")

def load_progress(file_path: str = r'main\twitter_poller\data\progress.json') -> int:
    """从 JSON 文件中加载上次保存的进度。"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            progress = json.load(f)
            start_index = progress.get("current_index", 0)
            log("INFO", f"从上次进度恢复，将从第 {start_index + 1} 个账号开始处理。")
            return start_index
    except FileNotFoundError:
        log("INFO", "未找到上次的进度文件，将从头开始运行。")
        return 0
    except json.JSONDecodeError:
        log("WARNING", "进度文件已损坏，将从头开始运行。")
        return 0

def main():
    """主函数，负责 orchestrate 整个自动化流程。"""
    skipped_ids = []
    failed_ids = []
    
    # 1. 读取CSV数据
    csv_path = r"data/Artist.csv"
    try:
        twitter_data, skipped_ids = read_twitter_csv(csv_path)
    except Exception as e:
        log("ERROR", "无法读取CSV文件，脚本无法继续执行。")
        return
        
    total_count = len(twitter_data)
    
    # 2. 加载上次的进度
    start_index = load_progress()

    # 3. 初始化自动化实例并连接程序
    automation = XSpiderAutomation(window_title="X-Spider")
    automation.connect_app()
    
    if not automation.is_connected:
        log("ERROR", "无法连接到程序，脚本无法继续执行。")
        return
        
    # 4. 遍历CSV中的每个search_id，传入自动化程序
    for idx in range(start_index, total_count):
        item = twitter_data[idx]
        search_id = item['twitter_id']
        search_time = item['twitter_roll_time']
        
        log("INFO", f"--- 开始处理第 {idx + 1} 个ID，共 {total_count} 个 ---")
        log("INFO", f"待处理ID: {search_id}，对应时间: {search_time}")

        if search_time == "3000:01:01":
            log("WARNING", f"ID: {search_id} 标识为非下载，跳过此条目。")
            log("INFO", "------------------------------------------")
            continue

        # 核心：将search_id传入自动化流程
        process_success = automation.run_full_process(user_id=search_id)
        if not process_success:
            failed_ids.append(search_id)

        # 保存进度 (如果成功处理)
        if process_success:
            save_progress(idx + 1, total_count)

        # 可选：处理完1个ID后，等待程序恢复
        wait_after_process = 5
        log("INFO", f"等待 {wait_after_process} 秒，准备处理下一个ID...")
        time.sleep(wait_after_process)
        
        # 添加进度总结信息
        progress_percent = ((idx + 1) / total_count) * 100
        log("SUCCESS", f"✅ 第 {idx + 1} 个任务完成。总进度: {progress_percent:.0f}%")
        log("INFO", "------------------------------------------\n")
    
    # 最终处理，如果所有任务都完成，则删除进度文件
    try:
        if idx + 1 == total_count:
            import os
            os.remove(r'main\twitter_poller\data\progress.json')
            log("SUCCESS", "所有任务已完成，进度文件已清除。")
    except NameError:
        # 如果循环从未开始，idx将不存在
        pass
    except Exception as e:
        log("ERROR", f"清除进度文件失败: {e}")

    finally:
        log("INFO", "自动化脚本执行结束。")
        
        print("\n" + "="*80)
        print("📊 自动化流程最终报告")
        print("="*80)
        
        print("\n--- 失败的账号列表 (自动化流程中出现异常的账号) ---")
        if failed_ids:
            print(f"总计失败 {len(failed_ids)} 个账号，详情如下：")
            for i, failed_id in enumerate(failed_ids, 1):
                print(f"{i:3d}. {failed_id}")
        else:
            print("✅ 自动化流程中无账号失败。")

        print("\n--- 被跳过的ID列表 (包含';'的ID) ---")
        if skipped_ids:
            print(f"总计跳过 {len(skipped_ids)} 个ID，详情如下：")
            for i, skipped_id in enumerate(skipped_ids, 1):
                print(f"{i:3d}. {skipped_id}")
        else:
            print("✅ 无任何包含';'的ID被跳过。")
            
        print("="*80)
        
if __name__ == "__main__":
    main()
    