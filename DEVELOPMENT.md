# 开发者指南

## 项目结构

```
/workspace/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/    # API端点
│   ├── core/                # 核心功能
│   ├── models/              # 数据模型
│   ├── schemas/             # Pydantic模式
│   ├── services/            # 业务逻辑
│   ├── tasks/               # 后台任务
│   └── utils/               # 工具函数
├── frontend/                # 前端代码
├── tests/                   # 测试文件
└── docs/                    # 文档
```

## 核心功能模块

### 1. 性能优化

#### 数据库索引优化
- 为 StockData 模型添加了复合索引 (stock_code, period, datetime)
- 为 BacktestResult 模型添加了索引 (stock_code, strategy_name)

#### 序列化优化
- 使用 orjson 替代标准 json 模块，提供更快的序列化性能
- 支持 msgpack 二进制序列化格式
- 实现了 ORJSONResponse 类用于 FastAPI

#### 异步数据库支持
- 创建了 database_async.py 模块
- 支持异步会话和异步查询

### 2. 安全加固

#### 速率限制
- 使用 SlowAPI + Limits 实现 API 速率限制
- 配置在 settings.py 中

#### 安全头部
- 实现了 SecurityHeadersMiddleware
- 添加了 CSP、X-Content-Type-Options、X-Frame-Options 等头部
- 配置在 security_middleware.py 中

#### 输入验证
- InputValidator 类提供全面的输入验证
- 支持股票代码、邮箱、用户名、密码等验证
- 提供 XSS 防护的字符串清理功能

### 3. 高级功能

#### 数据导出
- 支持 CSV 和 Excel 格式导出
- 可按股票代码和周期筛选数据
- 导出股票数据和回测结果

#### WebSocket 实时通知
- ConnectionManager 管理 WebSocket 连接
- 支持多频道广播
- 端点: `/api/v1/advanced/ws/{channel}`

#### 任务进度跟踪
- TaskStatus 模型跟踪任务状态
- 支持进度百分比、结果、错误信息
- 端点: `/api/v1/advanced/tasks`

#### 数据备份
- 支持全量数据备份
- 备份文件以 JSON 格式存储
- 可列出和管理备份文件

## API 使用示例

### 数据导出

```python
import requests

# 导出股票数据为 CSV
response = requests.get(
    "http://localhost:8000/api/v1/advanced/export/stocks/csv",
    params={"stock_code": "AAPL", "period": "1d"}
)
with open("stocks.csv", "wb") as f:
    f.write(response.content)

# 导出股票数据为 Excel
response = requests.get(
    "http://localhost:8000/api/v1/advanced/export/stocks/excel"
)
with open("stocks.xlsx", "wb") as f:
    f.write(response.content)
```

### WebSocket 使用

```javascript
// 连接到 WebSocket
const ws = new WebSocket('ws://localhost:8000/api/v1/advanced/ws/stocks');

ws.onopen = () => {
    console.log('Connected');
    ws.send('Hello Server');
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
};

ws.onclose = () => {
    console.log('Disconnected');
};
```

### 任务查询

```python
import requests

# 获取任务列表
response = requests.get("http://localhost:8000/api/v1/advanced/tasks")
tasks = response.json()["tasks"]

# 获取特定任务状态
task_id = "your-task-id"
response = requests.get(f"http://localhost:8000/api/v1/advanced/tasks/{task_id}")
task_status = response.json()
```

### 数据备份

```python
import requests

# 创建备份
response = requests.post("http://localhost:8000/api/v1/advanced/backup/create")
backup_info = response.json()

# 列出备份
response = requests.get("http://localhost:8000/api/v1/advanced/backup/list")
backups = response.json()["backups"]
```

## 测试指南

### 运行测试

```bash
# 安装测试依赖
pip install pytest pytest-cov pytest-asyncio httpx

# 运行所有测试
pytest tests/ -v

# 运行单元测试
pytest tests/ -v -m unit

# 运行集成测试
pytest tests/ -v -m integration

# 生成覆盖率报告
pytest tests/ --cov=app --cov-report=html
```

### 编写测试

测试文件位于 `tests/` 目录：
- `tests/test_validation.py` - 输入验证测试
- `tests/test_api.py` - API集成测试

## CI/CD 工作流

项目使用 GitHub Actions 进行自动化测试和部署：

1. **Lint 检查** - 运行 flake8、black、isort 检查
2. **测试** - 在 Python 3.10 和 3.11 上运行测试
3. **覆盖率** - 生成并上传测试覆盖率报告

工作流配置在 `.github/workflows/ci.yml`

## 开发环境设置

```bash
# 克隆仓库
git clone <repository-url>
cd /workspace

# 安装依赖
pip install -r requirements.txt

# 运行开发服务器
python -m uvicorn app.main:app --reload
```

## 配置说明

主要配置项在 `app/core/config.py`：
- DATABASE_URL - 数据库连接字符串
- RATE_LIMIT_ENABLED - 是否启用速率限制
- BACKUP_DIR - 备份文件目录
- CORS_ORIGINS - CORS 允许的源

## 性能优化建议

1. **数据库**
   - 使用 PostgreSQL 替代 SQLite 以获得更好的并发性能
   - 定期分析和优化数据库
   - 考虑使用数据库连接池

2. **缓存**
   - 配置 Redis 作为分布式缓存
   - 设置合理的缓存过期时间
   - 使用缓存预热提高首次访问速度

3. **异步处理**
   - 使用 Celery 处理耗时任务
   - 实现任务队列和结果存储
   - 使用异步 I/O 操作提高吞吐量
