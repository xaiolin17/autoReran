@echo off
echo 🚀 股票数据分析平台启动脚本
echo ================================
echo.
echo 💡 提示: 这将启动纯本地环境，无需外部依赖
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未找到 Python
    echo 💡 请确保已安装 Python 3.8+
    pause
    exit /b 1
)

REM 检查 .env 文件
if not exist ".env" (
    echo 📝 创建环境配置文件...
    copy .env.example .env >nul
)

REM 检查依赖
echo 📋 检查依赖...
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  依赖未安装，正在安装...
    pip install -r requirements.txt
)

REM 初始化数据库
echo.
echo 🗄️  初始化数据库...
python scripts/init_db.py

REM 询问是否生成示例数据
echo.
set /p GENERATE_SAMPLE="❓ 是否生成示例股票数据? (y/n, 默认y): "
if "%GENERATE_SAMPLE%"=="" set GENERATE_SAMPLE=y
if /i "%GENERATE_SAMPLE%"=="y" (
    echo 📊 正在生成示例数据...
    python scripts/init_db.py --sample
)

REM 启动应用
echo.
echo 🌟 启动应用...
echo 📍 主页:   http://localhost:8000
echo 📖 文档:   http://localhost:8000/docs
echo 📊 图表:   http://localhost:8000
echo 🎯 训练:   http://localhost:8000/training
echo 📈 回测:   http://localhost:8000/backtest
echo.
echo 💡 提示: 生成示例数据后可直接查看 K线图
echo.
echo 按 Ctrl+C 停止
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
