#!/bin/bash

echo "🚀 股票数据分析平台启动脚本"
echo "================================"
echo ""
echo "💡 提示: 这将启动纯本地环境，无需外部依赖"
echo ""

# 检查 Python 是否存在
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 python3"
    exit 1
fi

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "📝 创建环境配置文件..."
    cp .env.example .env
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
echo ""
echo "🗄️  初始化数据库..."
python3 scripts/init_db.py

# 询问是否生成示例数据
echo ""
read -p "❓ 是否生成示例股票数据? (y/n, 默认y): " GENERATE_SAMPLE
GENERATE_SAMPLE=${GENERATE_SAMPLE:-y}

if [ "$GENERATE_SAMPLE" = "y" ] || [ "$GENERATE_SAMPLE" = "Y" ]; then
    echo "📊 正在生成示例数据..."
    python3 scripts/init_db.py --sample
fi

# 启动应用
echo ""
echo "🌟 启动应用..."
echo "📍 主页:   http://localhost:8000"
echo "📖 文档:   http://localhost:8000/docs"
echo "📊 图表:   http://localhost:8000"
echo "🎯 训练:   http://localhost:8000/training"
echo "📈 回测:   http://localhost:8000/backtest"
echo ""
echo "💡 提示: 生成示例数据后可直接查看 K线图"
echo ""
echo "按 Ctrl+C 停止"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
