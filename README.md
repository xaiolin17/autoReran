# 股票数据分析平台

一个功能完整的股票数据分析平台，包含数据爬取、技术指标计算、机器学习预测、策略回测和期权分析功能。

## 功能特性

- 📊 **数据爬取**
  - 支持新浪财经和东方财富数据源
  - 获取真实的股票实时数据和历史数据

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
  - 多模型投票制预测

- 🔙 **策略回测**
  - KDJ 策略
  - MACD 策略
  - 组合策略
  - 详细回测报告

- 🎯 **期权分析** (新增)
  - 期权链数据获取（东方财富数据源）
  - 看涨/看跌期权对比
  - 多空比例分析
  - 最大痛点价位计算
  - 支持 510300、510500、510050 等 ETF 期权

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
│   │           ├── sample_data.py
│   │           └── options.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── logger.py
│   ├── schemas/
│   │   ├── stock.py
│   │   ├── indicator.py
│   │   ├── ml.py
│   │   ├── backtest.py
│   │   └── option.py
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
│   │   └── option_crawler.py
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
├── requirements.txt
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动应用

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 访问应用

- 主页: http://localhost:8000/
- API 文档: http://localhost:8000/docs

## 使用说明

### 数据查看页面

1. 输入股票/ETF 代码（如 510300、000001）
2. 点击"爬取数据"获取真实数据或"生成示例数据"
3. 查看价格走势、成交量及技术指标图表
4. 查看交易信号
5. **点击"加载期权数据"查看期权多空分析**（期权标的）

### 模型训练页面

1. 选择股票代码和模型参数
2. 点击"开始训练"训练机器学习模型
3. 在已训练模型列表中查看所有模型
4. 使用训练好的模型进行价格预测（支持单模型或多模型投票）

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

### 期权分析 (新增)

- `GET /api/v1/options/chain/{stock_code}` - 获取期权链数据
- `GET /api/v1/options/chain/{stock_code}/summary` - 获取期权摘要统计

### 示例数据

- `POST /api/v1/sample/generate/{stock_code}` - 生成示例数据

## 技术栈

- **后端**: FastAPI + SQLAlchemy
- **数据处理**: Pandas + NumPy
- **机器学习**: Scikit-learn
- **图表**: Chart.js
- **前端**: HTML + CSS + JavaScript (玻璃态设计)
- **数据库**: SQLite
- **数据源**: 新浪财经、东方财富

## 注意事项

- 本项目仅供学习和研究使用，不构成任何投资建议
- 实际使用时请遵守相关网站的数据使用条款
- 所有数据均来自真实数据源，非模拟数据
