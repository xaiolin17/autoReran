# simple数据分析平台

一个功能完整的股票数据分析平台，包含数据爬取、技术指标计算、机器学习预测和策略回测功能。

## 功能特性

- 📊 **数据爬取**
  - 支持新浪财经和东方财富数据源
  - 定时任务自动更新
  - 多源数据融合与平均

- 📈 **技术指标**
  - KDJ 指标
  - MACD 指标
  - RSI 指标
  - 布林带
  - 移动平均线

- 🤖 **机器学习**
  - 随机森林回归
  - 线性回归
  - 价格预测

- 🔙 **策略回测**
  - KDJ 策略
  - MACD 策略
  - 组合策略
  - 详细回测报告

## 项目结构

```
/workspace/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/
│   │           ├── stocks.py
│   │           ├── indicators.py
│   │           ├── ml.py
│   │           ├── backtest.py
│   │           ├── scheduler.py
│   │           └── sample_data.py
│   ├── core/
│   │   ├── config.py
│   │   └── database.py
│   ├── models/
│   │   ├── stock_data.py
│   │   ├── trade_mark.py
│   │   ├── ml_model.py
│   │   └── backtest_result.py
│   ├── schemas/
│   │   ├── stock.py
│   │   ├── trade_mark.py
│   │   ├── indicator.py
│   │   ├── ml.py
│   │   └── backtest.py
│   ├── services/
│   │   ├── stock_service.py
│   │   ├── indicator_service.py
│   │   ├── ml_service.py
│   │   └── backtest_service.py
│   ├── crawlers/
│   │   ├── base.py
│   │   ├── sina.py
│   │   ├── eastmoney.py
│   │   ├── data_processor.py
│   │   └── scheduler.py
│   ├── utils/
│   │   └── technical_indicators.py
│   └── main.py
├── templates/
│   ├── index.html
│   ├── training.html
│   └── backtest.html
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── chart.js
│       ├── main.js
│       ├── training.js
│       └── backtest.js
├── scripts/
│   └── init_db.py
├── requirements.txt
├── start.sh
├── start.bat
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 初始化数据库

```bash
python scripts/init_db.py
```

### 3. 启动应用

Linux/Mac:

```bash
./start.sh
```

Windows:

```bash
start.bat
```

或直接使用 Python 运行:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 访问应用

- 主页: http://localhost:8000/
- API 文档: http://localhost:8000/docs

## 使用说明

### 数据查看页面

1. 输入股票代码（默认使用示例数据 "SAMPLE"
2. 点击"生成示例数据"生成模拟数据
3. 查看价格走势、成交量及技术指标图表
4. 查看交易信号

### 模型训练页面

1. 选择股票代码和模型参数
2. 点击"开始训练"训练机器学习模型
3. 在已训练模型列表中查看所有模型
4. 使用训练好的模型进行价格预测

### 策略回测页面

1. 选择回测策略和时间范围
2. 运行回测并查看结果
3. 查看详细的交易记录和性能指标

## API 接口

### 股票数据

- `GET /api/v1/stocks/{stock_code}` - 获取股票数据
- `POST /api/v1/stocks/fetch/{stock_code}` - 爬取并保存数据
- `GET /api/v1/stocks/latest/{stock_code}` - 获取最新数据

### 技术指标

- `GET /api/v1/indicators/{stock_code}` - 获取带指标数据
- `GET /api/v1/indicators/signals/{stock_code}` - 获取交易信号

### 机器学习

- `POST /api/v1/ml/train` - 训练模型
- `POST /api/v1/ml/predict` - 预测价格
- `GET /api/v1/ml/models` - 获取模型列表
- `GET /api/v1/ml/models/{model_id}` - 获取模型详情
- `DELETE /api/v1/ml/models/{model_id}` - 删除模型

### 回测

- `POST /api/v1/backtest/run` - 运行回测
- `GET /api/v1/backtest/results` - 获取回测结果
- `GET /api/v1/backtest/results/{backtest_id}` - 获取回测详情
- `DELETE /api/v1/backtest/results/{backtest_id}` - 删除回测结果

### 调度器

- `GET /api/v1/scheduler/status` - 获取调度器状态
- `POST /api/v1/scheduler/start` - 启动调度器
- `POST /api/v1/scheduler/stop` - 停止调度器
- `POST /api/v1/scheduler/add/{stock_code}` - 添加股票
- `DELETE /api/v1/scheduler/remove/{stock_code}` - 移除股票

### 示例数据

- `POST /api/v1/sample/generate/{stock_code}` - 生成示例数据

## 技术栈

- **后端**: FastAPI + SQLAlchemy
- **数据处理**: Pandas + NumPy
- **机器学习**: Scikit-learn
- **图表**: Chart.js
- **前端**: HTML + CSS + JavaScript
- **数据库**: SQLite
- **定时任务**: APScheduler

## 注意事项

- 本项目仅供学习和研究使用，不构成任何投资建议
- 实际使用时请遵守相关网站的数据使用条款
- 示例数据为模拟数据，不代表真实股票走势
