# 股票数据分析平台部署指南

本文档提供了股票数据分析平台的完整部署说明，包括开发环境和生产环境的部署步骤。

## 目录

- [系统要求](#系统要求)
- [快速开始（Docker Compose）](#快速开始docker-compose)
- [手动部署](#手动部署)
- [生产环境部署](#生产环境部署)
- [监控配置](#监控配置)
- [维护与监控](#维护与监控)

---

## 系统要求

### 最低配置
- CPU: 2 核
- 内存: 4 GB
- 磁盘: 20 GB
- 操作系统: Linux / macOS / Windows (WSL2)

### 推荐配置
- CPU: 4 核或更多
- 内存: 8 GB 或更多
- 磁盘: 50 GB SSD
- 操作系统: Ubuntu 20.04+ / CentOS 8+

---

## 快速开始（Docker Compose）

这是最简单的部署方式，适合开发和测试环境。

### 前置条件

1. 安装 Docker (20.10+)
2. 安装 Docker Compose (2.0+)

### 部署步骤

1. **克隆或下载项目代码**
   ```bash
   cd /workspace
   ```

2. **配置环境变量**
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，根据需要修改配置
   nano .env
   ```

3. **启动所有服务**
   ```bash
   docker-compose up -d
   ```

4. **初始化数据库**
   ```bash
   docker-compose exec web python scripts/init_db.py
   ```

5. **访问应用**
   - 应用地址: http://localhost:8000
   - API 文档: http://localhost:8000/docs
   - 健康检查: http://localhost:8000/health
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3000 (默认账号: admin / admin123)

6. **查看服务状态**
   ```bash
   docker-compose ps
   ```

7. **查看日志**
   ```bash
   # 查看所有服务日志
   docker-compose logs -f
   
   # 查看特定服务日志
   docker-compose logs -f web
   docker-compose logs -f celery_worker
   ```

8. **停止服务**
   ```bash
   docker-compose down
   
   # 停止并删除数据卷（谨慎使用）
   docker-compose down -v
   ```

---

## 手动部署

适合需要更灵活控制的场景。

### 1. 环境准备

#### 1.1 安装 Python 3.11+
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev

# CentOS/RHEL
sudo yum install python311 python311-devel
```

#### 1.2 安装 PostgreSQL 15+
```bash
# Ubuntu/Debian
sudo apt install postgresql postgresql-contrib

# CentOS/RHEL
sudo yum install postgresql15 postgresql15-server
```

#### 1.3 安装 Redis 7+
```bash
# Ubuntu/Debian
sudo apt install redis-server

# CentOS/RHEL
sudo yum install redis
```

### 2. 数据库配置

#### 2.1 创建数据库和用户
```bash
sudo -u postgres psql
```
```sql
CREATE USER stock_user WITH PASSWORD 'your_secure_password';
CREATE DATABASE stock_db OWNER stock_user;
GRANT ALL PRIVILEGES ON DATABASE stock_db TO stock_user;
\q
```

### 3. 应用部署

#### 3.1 克隆项目
```bash
cd /opt
git clone <repository-url> stock-platform
cd stock-platform
```

#### 3.2 创建虚拟环境
```bash
python3.11 -m venv venv
source venv/bin/activate
```

#### 3.3 安装依赖
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 3.4 配置环境变量
```bash
cp .env.example .env
nano .env  # 修改配置，特别是数据库连接和密钥
```

#### 3.5 初始化数据库
```bash
python scripts/init_db.py
```

#### 3.6 启动应用服务

**方式一：使用 Gunicorn（推荐用于生产）**
```bash
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000
```

**方式二：直接使用 Uvicorn（开发环境）**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 3.7 启动 Celery Worker
```bash
celery -A app.core.celery_app.celery_app worker --loglevel=info
```

#### 3.8 启动 Celery Beat（可选，用于定时任务）
```bash
celery -A app.core.celery_app.celery_app beat --loglevel=info
```

### 4. 前端部署（可选）

#### 4.1 安装前端依赖
```bash
cd frontend
npm install
```

#### 4.2 开发模式运行
```bash
npm run dev
```

#### 4.3 生产构建
```bash
npm run build
# 使用 nginx 或其他服务器托管 dist 目录
```

---

## 生产环境部署

### 1. 使用 Nginx 作为反向代理

#### 1.1 安装 Nginx
```bash
sudo apt install nginx
```

#### 1.2 配置 Nginx
```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /opt/stock-platform/static;
        expires 30d;
    }
}
```

#### 1.3 启用配置
```bash
sudo ln -s /etc/nginx/sites-available/stock-platform /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 2. 使用 Systemd 管理服务

#### 2.1 创建应用服务文件
```bash
sudo nano /etc/systemd/system/stock-web.service
```
```ini
[Unit]
Description=Stock Analysis Platform Web Service
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=www-data
WorkingDirectory=/opt/stock-platform
Environment="PATH=/opt/stock-platform/venv/bin"
ExecStart=/opt/stock-platform/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 127.0.0.1:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

#### 2.2 创建 Celery Worker 服务文件
```bash
sudo nano /etc/systemd/system/stock-celery.service
```
```ini
[Unit]
Description=Stock Analysis Platform Celery Worker
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/stock-platform
Environment="PATH=/opt/stock-platform/venv/bin"
ExecStart=/opt/stock-platform/venv/bin/celery -A app.core.celery_app.celery_app worker --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
```

#### 2.3 启动并启用服务
```bash
sudo systemctl daemon-reload
sudo systemctl enable stock-web
sudo systemctl start stock-web
sudo systemctl enable stock-celery
sudo systemctl start stock-celery
```

### 3. SSL 证书配置（使用 Let's Encrypt）
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 4. 数据库备份
```bash
# 创建备份脚本
sudo nano /usr/local/bin/backup-db.sh
```
```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/var/backups/stock-db
mkdir -p $BACKUP_DIR
pg_dump -U stock_user stock_db | gzip > $BACKUP_DIR/stock_db_$DATE.sql.gz
find $BACKUP_DIR -name "stock_db_*.sql.gz" -mtime +7 -delete
```
```bash
sudo chmod +x /usr/local/bin/backup-db.sh

# 添加到 crontab
sudo crontab -e
# 添加以下行（每天凌晨 2 点备份）
0 2 * * * /usr/local/bin/backup-db.sh
```

---

## 监控配置

### 1. Prometheus 配置

#### 1.1 配置文件
项目根目录已包含 `prometheus.yml` 配置文件，默认配置会采集应用的指标数据。

#### 1.2 可用指标
- `http_requests_total` - HTTP 请求总数
- `http_request_duration_seconds` - HTTP 请求耗时
- `http_active_requests` - 活跃请求数
- `stock_data_fetches_total` - 股票数据获取次数
- `model_trains_total` - 模型训练次数
- `backtest_runs_total` - 回测执行次数
- `celery_tasks_total` - Celery 任务统计

### 2. Grafana 配置

#### 2.1 访问 Grafana
- URL: http://localhost:3000
- 默认账号: admin
- 默认密码: admin123

#### 2.2 数据源配置
Docker Compose 部署会自动配置 Prometheus 数据源。手动配置时：
- 名称: Prometheus
- 类型: Prometheus
- URL: http://prometheus:9090
- 访问方式: Server

#### 2.3 创建仪表板
可以导入以下常用仪表板模板：
- Node Exporter Full (ID: 1860) - 系统监控
- Nginx (ID: 12708) - Nginx 监控
- 自定义股票分析平台仪表板

### 3. 监控告警配置（可选）

可以在 Grafana 中配置告警规则，例如：
- 错误率超过 5%
- 响应时间超过 2 秒
- 系统 CPU 使用率超过 80%
- 内存使用率超过 90%

---

## 维护与监控

### 日志管理
- 应用日志: 配置在 `.env` 文件的 `LOG_FILE`
- Nginx 日志: `/var/log/nginx/`
- Systemd 服务日志: `journalctl -u stock-web -f`
- Prometheus 日志: 通过 Docker 日志查看

### 性能监控
- 使用 `htop` 监控系统资源
- 使用 `docker stats` 监控容器（如果使用 Docker）
- 使用 Prometheus + Grafana 监控应用指标
- 数据库性能: 使用 `pg_stat_statements` 扩展

### 常见问题排查

1. **应用无法连接数据库**
   - 检查数据库服务是否运行
   - 验证 `.env` 中的数据库连接字符串
   - 检查防火墙设置

2. **Celery 任务不执行**
   - 确认 Redis 服务运行正常
   - 检查 Celery Worker 日志
   - 验证 broker 连接配置

3. **内存占用过高**
   - 调整 Gunicorn worker 数量
   - 优化数据库查询
   - 检查是否有内存泄漏

4. **监控数据不显示**
   - 确认 Prometheus 正在采集数据
   - 检查 Grafana 数据源配置
   - 验证指标名称和标签

---

## 下一步

- 查看 [API 文档](http://localhost:8000/docs) 了解可用接口
- 阅读 [README.md](./README.md) 了解项目功能
- 查看 [COMPARISON.md](./COMPARISON.md) 了解项目改进历史
