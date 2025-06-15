@echo off
setlocal

:: 设置 Python 虚拟环境路径
:: 假设虚拟环境位于 backend 目录下的 venv 文件夹中
set VENV_PATH=%~dp0venv

:: 检查虚拟环境是否存在
if not exist "%VENV_PATH%\Scripts\activate.bat" (
    echo 错误：未找到 Python 虚拟环境。
    echo 请确保您已在当前目录下运行 'python -m venv venv' 创建了虚拟环境，
    echo 并执行 'pip install -r requirements.txt' 安装了依赖。
    pause
    exit /b 1
)

echo 激活 Python 虚拟环境...
call "%VENV_PATH%\Scripts\activate.bat"

echo 启动 FastAPI 后端服务器...
echo 访问地址: http://127.0.0.1:8000
echo (要停止服务，请在本窗口按 Ctrl+C)

:: 使用 uvicorn 启动 FastAPI 应用
:: main:app 指的是 main.py 文件中的 app 实例
:: --host 0.0.0.0 允许外部访问
:: --port 8000 设置端口号
:: --reload (可选) 仅用于开发，代码修改后自动重启，生产环境不建议使用
uvicorn main:app --host 0.0.0.0 --port 8000

echo 后端服务器已停止。
pause
endlocal