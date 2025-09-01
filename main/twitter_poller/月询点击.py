# import pandas as pd

# class TwitterCSVReader:
#     def __init__(self, csv_path):
#         self.csv_path = csv_path
#         self.data = []
#         self._read_csv()

#     def _read_csv(self):
#         df = pd.read_csv(self.csv_path, encoding='utf-8')
#         filtered = df[df['twitter_roll_time'] != '3000:01:01']
#         self.data = filtered[['twitter_id', 'twitter_roll_time']].values.tolist()

#     @property
#     def search_id(self):
#         if self.data:
#             return self.data[0][0]
#         return None
    
from pywinauto import Application
from pywinauto.findwindows import ElementNotFoundError
from pywinauto.timings import TimeoutError
import time
import configparser

def automate_app(app_path, ini_path="window_identifiers.ini"):
    try:
        # 尝试连接到应用程序
        try:
            app = Application(backend="uia").connect(path=app_path)
        except Exception:
            app = Application(backend="uia").start(app_path)
            time.sleep(5)  # 等待应用程序启动
        
        # 获取主窗口
        main_window = app.window(title="X-Spider")  # 替换为实际窗口标题

        # 获取窗口控件标识符    
        identifiers = main_window.print_control_identifiers()
        # print_control_identifiers() 默认打印到stdout, 需要捕获输出
        import io
        import sys
        buffer = io.StringIO()
        sys_stdout = sys.stdout
        sys.stdout = buffer
        main_window.print_control_identifiers()
        sys.stdout = sys_stdout
        identifiers_text = buffer.getvalue()

        # 保存到ini文件
        config = configparser.ConfigParser()
        config['WindowIdentifiers'] = {'identifiers': identifiers_text}
        with open(ini_path, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        print(f"窗口标识符已保存到 {ini_path}")
    except ElementNotFoundError:
        print("未找到应用程序窗口，请检查应用程序是否已启动以及路径是否正确。")
        return

if __name__ == "__main__":
    application_path = r"C:\App Files\Xspider\X-Spider.exe"
    automate_app(application_path)