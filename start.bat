@echo off
echo 🚀 股票数据分析平台启动脚本
echo ================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未找到 Python
    pause
    exit /b 1
)

REM 检查依赖
echo 📋 检查依赖...
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  依赖未安装，正在安装...
    pip install -r requirements.txt
)

REM 初始化数据库
echo 🗄️  初始化数据库...
python scripts/init_db.py

REM 启动应用
echo.
echo 🌟 启动应用...
echo 📍 访问地址: http://localhost:8000
echo 📖 API 文档: http://localhost:8000/docs
echo.
echo 按 Ctrl+C 停止
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
