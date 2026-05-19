# 股票数据分析平台

基于 FastAPI 构建，提供 A 股数据获取、K 线图表展示、机器学习预测、策略回测分析等功能。

## 功能特性

- 📊 **数据获取**
  - 基于 TickFlow SDK 获取 A 股实时/历史数据
  - 支持自动缺失数据检测与补全（基于 exchange-calendars 交易日历）
  - 数据清洗与去重（日期修正、重复数据合并）

- 📈 **K 线图表**
  - ECharts 渲染专业 K 线图
  - 支持鼠标右键标记买入/卖出标签
  - 标记数据持久化到数据库，用于后续模型训练

- 📉 **技术指标**
  - MACD 指标
  - KDJ 指标

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

## 技术栈

- **后端**: FastAPI + SQLAlchemy + SQLite
- **数据源**: TickFlow SDK（A 股数据）+ 东方财富（期权数据）
- **数据处理**: Pandas + NumPy + exchange-calendars（交易日判断）
- **机器学习**: Scikit-learn + joblib
- **前端图表**: ECharts 5（K 线图、技术指标）
- **实时通信**: WebSocket（下载进度通知）
- **任务调度**: APScheduler + Celery（可选）
- **缓存**: 内存 LRU 缓存
- **认证**: JWT (python-jose) + bcrypt

## 项目结构

```
autoReran/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── __init__.py          # API 路由注册
│   │   │   └── endpoints/
│   │   │       ├── backtest.py      # 回测 API
│   │   │       ├── cache.py         # 缓存 API
│   │   │       ├── indicators.py    # 技术指标 API（含缺失数据检测）
│   │   │       ├── ml.py            # 机器学习 API
│   │   │       ├── options.py       # 期权分析 API
│   │   │       ├── scheduler.py     # 定时任务 API
│   │   │       ├── stocks.py        # 股票数据 API（含 K 线标记）
│   │   │       └── test.py          # 测试/认证 API
│   │   ├── v2/
│   │   ├── __init__.py
│   │   └── deps.py                  # 依赖注入
│   ├── core/
│   │   ├── cache.py                 # LRU 缓存
│   │   ├── celery_app.py            # Celery 配置
│   │   ├── config.py                # 应用配置
│   │   ├── database.py              # SQLAlchemy 数据库
│   │   ├── database_async.py        # 异步数据库
│   │   ├── logger.py                # 日志系统（含 CallerFilter）
│   │   ├── security.py              # 安全/认证
│   │   ├── security_middleware.py   # 安全中间件
│   │   └── websocket_manager.py     # WebSocket 管理器
│   ├── crawlers/
│   │   ├── base.py                  # 爬虫基类
│   │   ├── data_processor.py        # 数据处理器（清洗/去重/日期修正）
│   │   ├── option_crawler.py        # 期权爬虫（东方财富）
│   │   ├── scheduler.py             # 爬虫调度器
│   │   └── tickflow_crawler.py      # TickFlow 数据爬虫
│   ├── models/
│   │   ├── backtest_result.py       # 回测结果模型
│   │   ├── ml_model.py              # ML 模型元数据
│   │   ├── stock_data.py            # 股票数据 + 股票代码映射
│   │   └── trade_mark.py            # 交易标记模型
│   ├── schemas/                     # Pydantic 数据模型
│   ├── services/
│   │   ├── backtest_service.py      # 回测服务
│   │   ├── indicator_service.py     # 指标计算 + 缺失检测
│   │   ├── initialization_service.py # 初始化服务
│   │   ├── ml_service.py            # 机器学习服务
│   │   ├── stock_service.py         # 股票数据服务
│   │   └── user_service.py          # 用户服务
│   ├── tasks/
│   │   └── stock_tasks.py           # Celery 任务
│   ├── utils/
│   │   ├── export.py                # 数据导出
│   │   └── technical_indicators.py  # 技术指标计算工具
│   └── main.py                      # FastAPI 入口
├── static/
│   ├── css/style.css
│   └── js/
│       ├── backtest.js
│       ├── main.js                  # ECharts K 线图 + WebSocket
│       ├── script.js
│       └── training.js
├── templates/
│   ├── backtest.html
│   ├── base.html
│   ├── index.html                   # 数据查看页（ECharts）
│   └── training.html
├── tests/                           # 测试目录
│   ├── __init__.py
│   ├── test_data_source.py
│   └── test_kline_mark.py
├── .github/workflows/ci.yml         # GitHub Actions CI/CD
├── requirements.txt
├── pytest.ini
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动应用

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
#uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 访问应用

- 主页: http://localhost:8000/
- API 文档: http://localhost:8000/docs

## 使用说明

### 数据查看页面

1. 输入股票/ETF 代码（如 000001、510300）
2. 点击"获取数据"下载历史数据
3. 查看 ECharts 渲染的 K 线图、成交量及技术指标
4. **右键点击 K 线**可标记买入/卖出标签

### 模型训练页面

1. 选择股票代码和模型参数
2. 点击"开始训练"训练机器学习模型
3. 在已训练模型列表中查看所有模型
4. 使用训练好的模型进行价格预测（支持单模型或多模型投票）

### 策略回测页面

1. 选择回测策略和时间范围
2. 运行回测并查看结果
3. 查看详细的交易记录和性能指标

## API 接口概览

### 数据

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/stocks/{stock_code}` | 获取数据 |
| POST | `/api/v1/stocks/fetch/{stock_code}` | 获取并保存数据 |
| POST | `/api/v1/stocks/fetch-async/{stock_code}` | 异步下载（WebSocket 通知进度） |
| POST | `/api/v1/stocks/refresh/{stock_code}` | 刷新数据 |
| POST | `/api/v1/stocks/force-refresh/{stock_code}` | 强制刷新历史数据 |
| POST | `/api/v1/stocks/deduplicate/{stock_code}` | 数据去重 |
| GET | `/api/v1/stocks/latest/{stock_code}` | 获取最新数据 |
| GET | `/api/v1/stocks/search` | 搜索 |
| GET | `/api/v1/stocks/marks` | 获取所有标记 |
| PUT | `/api/v1/stocks/mark` | 添加/更新标记 |

### 技术指标

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/indicators/{stock_code}` | 获取带指标数据 |
| GET | `/api/v1/indicators/{stock_code}/paged` | 分页获取指标数据 |
| GET | `/api/v1/indicators/{stock_code}/recent` | 获取最近数据 |
| GET | `/api/v1/indicators/signals/{stock_code}` | 获取信号 |

### 机器学习

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/ml/train` | 训练模型 |
| POST | `/api/v1/ml/predict` | 预测价格 |
| GET | `/api/v1/ml/models` | 获取模型列表 |
| GET | `/api/v1/ml/models/{model_id}` | 获取模型详情 |
| DELETE | `/api/v1/ml/models/{model_id}` | 删除模型 |

### 回测

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/backtest/run` | 运行回测 |
| GET | `/api/v1/backtest/results` | 获取回测结果 |
| GET | `/api/v1/backtest/results/{backtest_id}` | 获取回测详情 |
| DELETE | `/api/v1/backtest/results/{backtest_id}` | 删除回测结果 |

### 期权分析

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/options/chain/{stock_code}` | 获取期权链数据 |
| GET | `/api/v1/options/chain/{stock_code}/summary` | 获取期权摘要统计 |

### WebSocket

| 路径 | 说明 |
|------|------|
| `/ws/{client_id}` | 实时下载进度通知 |

## 数据流程

```
用户请求 → FastAPI → TickFlowCrawler → TickFlow SDK
                                    ↓
                              数据清洗/去重/日期修正
                                    ↓
                              SQLAlchemy → SQLite
                                    ↓
                              ECharts 前端展示
```

## 注意事项

- 本项目仅供学习和研究使用，不构成任何投资建议
- 实际使用时请遵守相关网站的数据使用条款
- K 线标记功能用于后续模型训练，标记数据会持久化到数据库
