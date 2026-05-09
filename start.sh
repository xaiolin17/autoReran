#!/bin/bash

echo "🚀 股票数据分析平台启动脚本"
echo "================================"

# 检查 Python 是否存在
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 python3"
    exit 1
fi

# 检查虚拟环境（可选）
if [ ! -d "venv" ]; then
    echo "📦 未检测到虚拟环境，使用系统 Python"
else
    echo "📦 激活虚拟环境..."
    source venv/bin/activate
fi

# 检查依赖
echo "📋 检查依赖..."
python3 -c "import fastapi" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  依赖未安装，正在安装..."
    pip3 install -r requirements.txt
fi

# 初始化数据库
echo "🗄️  初始化数据库..."
python3 scripts/init_db.py

# 启动应用
echo ""
echo "🌟 启动应用..."
echo "📍 访问地址: http://localhost:8000"
echo "📖 API 文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
