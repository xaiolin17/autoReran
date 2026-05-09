# 🚀 本地快速体验指南

此文档说明如何在 Windows 或 Mac/Linux 上快速体验股票数据分析平台，**无需安装任何外部依赖（PostgreSQL、Redis 等）**。

## 📋 前置要求

- **Python 3.8 或更高版本**
- 网络连接（用于安装依赖）

## ⚡ Windows 用户 - 超简单快速开始

### 方法一：一键启动（推荐）

1. 双击运行 `quick_start.bat`
2. 等待依赖安装和示例数据生成
3. 在浏览器打开 http://localhost:8000

### 方法二：手动启动

1. 双击运行 `start.bat`
2. 按提示选择是否生成示例数据
3. 在浏览器打开 http://localhost:8000

## 🐧 Mac/Linux 用户

### 方法一：使用启动脚本

```bash
# 给脚本执行权限
chmod +x start.sh

# 运行启动脚本
./start.sh
```

### 方法二：手动启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 初始化数据库并生成示例数据
python scripts/init_db.py --sample

# 3. 启动应用
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 🎯 体验功能

### 1. 📊 数据查看页面

**访问: http://localhost:8000**

功能:
- 查看 K线图（支持多种周期：1分、5分、15分、1小时、1天、1周）
- 切换技术指标（KDJ、MACD，可开关）
- 实时更新数据
- 点击 K线图标记买入/卖出点

### 2. 🎯 模型训练页面

**访问: http://localhost:8000/training**

功能:
- 在 K线图上标记买入/卖出点
- 查看所有标记记录
- 基于标记训练 ML 模型
- 管理已训练的模型

### 3. 📈 策略回测页面

**访问: http://localhost:8000/backtest**

功能:
- 选择训练好的模型
- 配置回测参数
- 运行回测
- 查看回测结果报表
- 可视化回测表现

### 4. 📖 API 文档

**访问: http://localhost:8000/docs**

功能:
- 完整的 OpenAPI 文档
- 在线测试 API 端点
- 查看请求/响应示例

## 🛠️ 本地环境配置说明

### 数据库

默认使用 **SQLite**，文件位置：
- `./stock_data.db`

无需安装 PostgreSQL！

### 缓存

- 使用内存 LRU 缓存（无需 Redis）
- 已配置缓存策略

### 任务调度

- 使用 APScheduler（内建）
- 无需 Celery + Redis

### 安全配置

- 本地环境已禁用速率限制（方便测试）
- CSP/CSRF 已禁用（方便开发）
- 仍支持 JWT 认证（可选使用）

## 📁 项目结构

```
/workspace/
├── app/                  # 应用代码
│   ├── api/             # API 端点
│   ├── core/            # 核心功能（配置、数据库等）
│   ├── models/          # 数据模型
│   ├── schemas/         # Pydantic 验证
│   ├── services/        # 业务逻辑
│   ├── crawlers/        # 爬虫
│   └── tasks/           # 异步任务
├── static/              # 静态资源
├── templates/           # HTML 模板
├── scripts/             # 工具脚本
├── tests/               # 测试
├── requirements.txt     # Python 依赖
├── .env                # 本地环境配置（已创建）
├── start.sh            # Mac/Linux 启动脚本
├── start.bat           # Windows 启动脚本
└── quick_start.bat     # Windows 一键启动
```

## 🔧 常见问题

### Q: 安装依赖失败？

A: 尝试使用国内镜像源：
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q: 端口被占用？

A: 修改启动脚本中的端口号，或关闭占用 8000 端口的程序。

### Q: 看不到示例数据？

A: 确保使用 `--sample` 参数运行了 `init_db.py`，或重新运行启动脚本。

### Q: 如何切换到生产环境？

A: 参考 `DEPLOYMENT.md`，使用 Docker Compose 部署完整环境。

## 📊 生产环境 vs 本地环境

| 功能 | 本地环境 | 生产环境 |
|------|---------|---------|
| 数据库 | SQLite | PostgreSQL |
| 缓存 | 内存 LRU | Redis |
| 任务调度 | APScheduler | Celery + Redis |
| 监控 | 可选 | Prometheus + Grafana |
| 安全 | 宽松 | 严格限制 |

## 🎉 开始体验

现在您可以：

1. **运行启动脚本**
2. **打开浏览器访问 http://localhost:8000**
3. **开始探索！**

如有问题，请查看其他文档或联系开发团队。

---

**祝您体验愉快！** 🎊