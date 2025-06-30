import tkinter as tk
from tkinter import ttk, scrolledtext
import asyncio
import threading
import time

class BilibiliRollingUI:
    def __init__(self, root):
        self.root = root
        self.root.title("B站图文轮询工具")
        self.root.geometry("800x600")
        
        # 状态变量
        self.waiting_users = []
        self.processing_users = []
        self.completed_users = []
        self.stats = {
            "total_users": 0,
            "processed_users": 0,
            "downloaded_images": 0,
            "failed_tasks": 0
        }
        
        self.create_widgets()
        
    def create_widgets(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 用户池区域
        user_pools_frame = ttk.LabelFrame(main_frame, text="用户池状态", padding=10)
        user_pools_frame.pack(fill=tk.X, pady=5)
        
        # 三列布局
        col1 = ttk.Frame(user_pools_frame)
        col1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        col2 = ttk.Frame(user_pools_frame)
        col2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        col3 = ttk.Frame(user_pools_frame)
        col3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        # 等待用户池
        ttk.Label(col1, text="等待用户池").pack(anchor=tk.W)
        self.waiting_listbox = tk.Listbox(col1, height=8)
        self.waiting_listbox.pack(fill=tk.BOTH, expand=True)
        
        # 正在处理的用户
        ttk.Label(col2, text="正在处理").pack(anchor=tk.W)
        self.processing_frame = ttk.Frame(col2)
        self.processing_frame.pack(fill=tk.BOTH, expand=True)
        
        self.current_user_label = ttk.Label(self.processing_frame, text="用户: -")
        self.current_user_label.pack(anchor=tk.W)
        
        self.dynamics_label = ttk.Label(self.processing_frame, text="动态: -/-")
        self.dynamics_label.pack(anchor=tk.W)
        
        self.images_label = ttk.Label(self.processing_frame, text="图片: -/-")
        self.images_label.pack(anchor=tk.W)
        
        # 已完成用户池
        ttk.Label(col3, text="已完成用户池").pack(anchor=tk.W)
        self.completed_listbox = tk.Listbox(col3, height=8)
        self.completed_listbox.pack(fill=tk.BOTH, expand=True)
        
        # 统计信息区域
        stats_frame = ttk.LabelFrame(main_frame, text="统计信息", padding=10)
        stats_frame.pack(fill=tk.X, pady=5)
        
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X)
        
        ttk.Label(stats_grid, text="总用户:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.total_users_var = tk.StringVar(value="0")
        ttk.Label(stats_grid, textvariable=self.total_users_var).grid(row=0, column=1, sticky=tk.W)
        
        ttk.Label(stats_grid, text="已处理:").grid(row=0, column=2, sticky=tk.W, padx=10)
        self.processed_users_var = tk.StringVar(value="0")
        ttk.Label(stats_grid, textvariable=self.processed_users_var).grid(row=0, column=3, sticky=tk.W)
        
        ttk.Label(stats_grid, text="图片下载:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.downloaded_images_var = tk.StringVar(value="0")
        ttk.Label(stats_grid, textvariable=self.downloaded_images_var).grid(row=1, column=1, sticky=tk.W)
        
        ttk.Label(stats_grid, text="失败任务:").grid(row=1, column=2, sticky=tk.W, padx=10)
        self.failed_tasks_var = tk.StringVar(value="0")
        ttk.Label(stats_grid, textvariable=self.failed_tasks_var).grid(row=1, column=3, sticky=tk.W)
        
        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="执行日志", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_area = scrolledtext.ScrolledText(
            log_frame, 
            wrap=tk.WORD, 
            height=10,
            state='normal'
        )
        self.log_area.pack(fill=tk.BOTH, expand=True)
        self.log_area.configure(font=("Consolas", 10))
        
        # 控制按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="开始轮询", command=self.start_rolling).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="暂停", command=self.pause_rolling).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="导出日志", command=self.export_log).pack(side=tk.RIGHT, padx=5)
    
    def update_ui(self):
        """更新UI显示"""
        # 更新用户池
        self.waiting_listbox.delete(0, tk.END)
        for user in self.waiting_users:
            self.waiting_listbox.insert(tk.END, f"{user['name']} (ID:{user['id']})")
        
        self.completed_listbox.delete(0, tk.END)
        for user in self.completed_users:
            self.completed_listbox.insert(tk.END, f"{user['name']} (ID:{user['id']})")
        
        # 更新统计信息
        self.total_users_var.set(str(self.stats["total_users"]))
        self.processed_users_var.set(str(self.stats["processed_users"]))
        self.downloaded_images_var.set(str(self.stats["downloaded_images"]))
        self.failed_tasks_var.set(str(self.stats["failed_tasks"]))
        
        # 定期刷新
        self.root.after(1000, self.update_ui)
    
    def log_message(self, message, level="info"):
        """在日志区域添加消息"""
        self.log_area.configure(state='normal')
        
        # 添加时间戳
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        full_message = f"{timestamp} - {message}\n"
        
        # 根据日志级别设置颜色
        if level == "error":
            self.log_area.tag_config("error", foreground="red")
            self.log_area.insert(tk.END, full_message, "error")
        elif level == "warning":
            self.log_area.tag_config("warning", foreground="orange")
            self.log_area.insert(tk.END, full_message, "warning")
        else:
            self.log_area.insert(tk.END, full_message)
        
        # 滚动到底部
        self.log_area.see(tk.END)
        self.log_area.configure(state='disabled')
    
    def start_rolling(self):
        """开始轮询过程"""
        self.log_message("开始轮询任务...", "info")
        
        # 启动异步任务（在实际应用中替换为您的轮询逻辑）
        self.simulate_rolling_process()
    
    def pause_rolling(self):
        """暂停轮询过程"""
        self.log_message("轮询已暂停", "warning")
    
    def export_log(self):
        """导出日志到文件"""
        self.log_message("导出日志功能待实现", "info")
    
    def simulate_rolling_process(self):
        """模拟轮询过程（在实际应用中替换为您的轮询逻辑）"""
        # 初始化数据
        self.waiting_users = [
            {"id": 123, "name": "用户A"},
            {"id": 456, "name": "用户B"},
            {"id": 789, "name": "用户C"},
            {"id": 101, "name": "用户D"},
            {"id": 112, "name": "用户E"},
        ]
        
        self.processing_users = []
        self.completed_users = []
        
        self.stats = {
            "total_users": len(self.waiting_users),
            "processed_users": 0,
            "downloaded_images": 0,
            "failed_tasks": 0
        }
        
        # 模拟处理过程
        threading.Thread(target=self.simulate_processing, daemon=True).start()
    
    def simulate_processing(self):
        """模拟处理用户的过程"""
        for idx, user in enumerate(self.waiting_users[:]):
            # 更新状态：移动到处理中
            self.waiting_users.remove(user)
            self.processing_users.append(user)
            
            # 更新UI
            self.current_user_label.config(text=f"用户: {user['name']} (ID:{user['id']})")
            self.log_message(f"开始处理用户: {user['name']}")
            
            # 模拟处理动态
            total_dynamics = 3 + idx
            for dyn_idx in range(total_dynamics):
                self.dynamics_label.config(text=f"动态: {dyn_idx+1}/{total_dynamics}")
                self.log_message(f"获取到动态 #{dyn_idx+1}")
                
                # 模拟下载图片
                total_images = 2 + dyn_idx
                for img_idx in range(total_images):
                    self.images_label.config(text=f"图片: {img_idx+1}/{total_images}")
                    time.sleep(0.3)
                    
                    # 随机失败
                    if img_idx == 2 and dyn_idx == 1:
                        self.stats["failed_tasks"] += 1
                        self.log_message(f"下载图片失败: 动态#{dyn_idx+1} 图片#{img_idx+1}", "error")
                    else:
                        self.stats["downloaded_images"] += 1
                        self.log_message(f"下载图片成功: 动态#{dyn_idx+1} 图片#{img_idx+1}")
            
            # 完成处理
            self.processing_users.remove(user)
            self.completed_users.append(user)
            self.stats["processed_users"] += 1
            self.log_message(f"用户 {user['name']} 处理完成")
            
            # 重置进度显示
            self.dynamics_label.config(text="动态: -/-")
            self.images_label.config(text="图片: -/-")
            
            time.sleep(1)
        
        self.log_message("所有用户处理完成！", "info")
        self.current_user_label.config(text="用户: -")

if __name__ == "__main__":
    root = tk.Tk()
    app = BilibiliRollingUI(root)
    
    # 初始更新
    app.update_ui()
    
    root.mainloop()