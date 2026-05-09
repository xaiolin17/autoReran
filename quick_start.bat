@echo off
echo ⚡ 股票数据分析平台 - 一键启动
echo ==================================
echo.
echo 💡 此脚本将自动完成所有设置并启动
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

REM 初始化数据库并生成示例数据
echo.
echo 🗄️  初始化数据库并生成示例数据...
python scripts/init_db.py --sample

REM 启动应用
echo.
echo 🌟 启动应用...
echo.
echo 📍 访问地址:
echo    主页:   http://localhost:8000
echo    文档:   http://localhost:8000/docs
echo.
echo 💡 功能说明:
echo    📊 主页:     查看 K线图、技术指标、实时数据
echo    🎯 训练:     标记买卖点、训练 ML 模型
echo    📈 回测:     回测交易策略
echo.
echo 按 Ctrl+C 停止
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause