# ARN 数据获取系统设计文档

**日期**: 2026-05-12  
**版本**: 1.0  
**状态**: 待审阅

## 1. 概述

### 1.1 项目背景
ARN（股票数据分析平台）需要一个可靠、高效的数据获取和处理系统，专注于使用真实数据源，避免模拟数据。

### 1.2 核心目标
1. ✅ **只使用真实数据**：彻底移除模拟数据，只使用 AkShare
2. ✅ **默认展示上证指数**：用户首次访问有数据看，页面不空
3. ✅ **数据持久化**：避免重复下载
4. ✅ **智能加载**：有数据直接显示，无数据异步下载
5. ✅ **进度通知**：通过 WebSocket 推送下载进度
6. ✅ **增量更新**：用户刷新只获取最新数据
7. ✅ **混合指标**：优先读取已计算的，缺失的实时计算

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (ECharts)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ K线 + MA   │  │ 副图(KDJ/MAC)│  │ 成交量     │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└────────────────────────────┬────────────────────────────────┘
                             │ WebSocket + REST API
┌────────────────────────────┴────────────────────────────────┐
│                     FastAPI 后端                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │                  API 层                                │ │
│  │  - /api/v1/stocks/*                                   │ │
│  │  - /api/v1/indicators/*                               │ │
│  │  - WebSocket 进度推送                                  │ │
│  └──────────────────────────┬────────────────────────────┘ │
│                             │                              │
│  ┌──────────────────────────┴────────────────────────────┐ │
│  │              服务层 (Services)                          │ │
│  │  ┌──────────────────┐  ┌──────────────────┐          │ │
│  │  │ StockService     │  │ IndicatorService │          │ │
│  │  │ - 数据获取       │  │ - 指标计算       │          │ │
│  │  │ - 增量更新       │  │ - 混合模式       │          │ │
│  │  │ - 数据持久化     │  │ - 后台补全       │          │ │
│  │  └──────────────────┘  └──────────────────┘          │ │
│  └──────────────────────────┬────────────────────────────┘ │
│                             │                              │
│  ┌──────────────────────────┴────────────────────────────┐ │
│  │              数据层 (Data Layer)                        │ │
│  │  ┌─────────────────────────────────────────────────┐ │ │
│  │  │ AkshareCrawler (唯一数据源)                       │ │ │
│  │  │ - 指数(000001/sh000001, 399001/sz399001)        │ │ │
│  │  │ - 股票(600xxx/sh, 000xxx/sz)                    │ │ │
│  │  │ - 周期(1h, 1d, 1w, 1M)                          │ │ │
│  │  └─────────────────────────────────────────────────┘ │ │
│  └──────────────────────────┬────────────────────────────┘ │
└─────────────────────────────┼──────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │      SQLite 数据库        │
                │  ┌───────────────────┐   │
                │  │   StockData      │   │
                │  │ - 基础K线数据     │   │
                │  │ - MA 均线         │   │
                │  │ - MACD 指标       │   │
                │  │ - KDJ 指标        │   │
                │  │ - RSI 指标        │   │
                │  │ - 布林带          │   │
                │  └───────────────────┘   │
                └───────────────────────────┘
```

---

## 3. 核心模块设计

### 3.1 模块 1: AkshareCrawler (重构)

**文件**: `app/crawlers/akshare_crawler.py`

**职责**:
- 作为唯一的数据源
- 正确调用 AkShare API
- 支持所有周期数据获取
- 统一数据格式化

**主要方法**:

```python
class AkshareCrawler(BaseCrawler):
    def fetch_stock_data(
        self, 
        stock_code: str, 
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """获取股票/指数数据"""
        
    def fetch_realtime_data(self, stock_code: str) -> Dict:
        """获取实时数据（预留接口）"""
        
    def fetch_stock_list(self) -> List[Dict]:
        """获取股票列表（预留接口）"""
        
    def _fetch_index_data(self, index_code: str, ...) -> pd.DataFrame:
        """内部：获取指数数据"""
        
    def _fetch_stock_data(self, stock_code: str, ...) -> pd.DataFrame:
        """内部：获取股票数据"""
```

**特殊处理**:
- **指数代码转换**:
  - `000001` → `sh000001` (上证指数)
  - `399001` → `sz399001` (深证成指)
- **股票代码前缀**:
  - 600/601/603/605/688 开头 → `sh`
  - 其他 → `sz`
- **AkShare API 调用**:
  - 日线: `ak.index_zh_a_hist()` / `ak.stock_zh_a_hist()`
  - 分钟线: `ak.index_zh_a_hist_min_em()` / `ak.stock_zh_a_hist_min_em()`

---

### 3.2 模块 2: StockService (重构)

**文件**: `app/services/stock_service.py`

**职责**:
- 初始化上证指数默认数据
- 智能数据获取（数据库优先）
- 增量更新
- 数据持久化

**主要方法**:

```python
class StockService:
    def __init__(self, db: Session):
        self.db = db
        self.crawler = AkshareCrawler()  # 唯一数据源
    
    def initialize_default_data(self):
        """
        初始化上证指数(000001)的默认数据
        应用启动时调用，确保用户首次访问有数据
        """
        # 检查是否已有上证指数数据
        # 如果没有，下载一年的历史数据(1d周期)
        # 计算并保存技术指标
    
    def get_stock_data(
        self,
        stock_code: str,
        period: str = "1d",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[StockData]:
        """获取股票数据，优先从数据库读取"""
    
    def fetch_and_save_stock_data(
        self,
        stock_code: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        incremental: bool = False
    ) -> List[StockData]:
        """
        获取并保存数据
        
        Args:
            incremental: 是否增量更新
                        - True: 只获取数据库最新日期之后的数据
                        - False: 获取完整数据
        """
    
    def get_latest_date(self, stock_code: str, period: str) -> Optional[datetime]:
        """获取数据库中最新的数据日期"""
    
    def has_data(self, stock_code: str, period: str) -> bool:
        """检查是否有数据"""
```

---

### 3.3 模块 3: IndicatorService (重构)

**文件**: `app/services/indicator_service.py`

**职责**:
- 混合模式的指标管理
- 实时计算缺失指标
- 后台批量补全
- 交易信号生成

**主要方法**:

```python
class IndicatorService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_stock_data_with_indicators(
        self,
        stock_code: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
        auto_save: bool = True
    ) -> List[Dict]:
        """
        获取带指标的数据
        
        混合模式：
        1. 从数据库读取，优先使用已计算的指标
        2. 缺失的指标实时计算
        3. 如果 auto_save=True，保存计算结果回数据库
        """
    
    def calculate_and_save_indicators(
        self,
        stock_code: str,
        period: str = "1d"
    ) -> int:
        """
        后台批量补全所有缺失的技术指标
        
        Returns:
            更新的记录数量
        """
    
    @staticmethod
    def calculate_indicators_for_df_static(df: pd.DataFrame) -> pd.DataFrame:
        """静态方法：计算DataFrame的所有技术指标"""
    
    @staticmethod
    def calculate_ma(df: pd.DataFrame) -> pd.DataFrame:
        """计算 MA5/MA10/MA20/MA30/MA60"""
    
    @staticmethod
    def calculate_macd(df: pd.DataFrame) -> pd.DataFrame:
        """计算 MACD (dif, dea, macd)"""
    
    @staticmethod
    def calculate_kdj(df: pd.DataFrame) -> pd.DataFrame:
        """计算 KDJ (k, d, j)"""
    
    @staticmethod
    def calculate_rsi(df: pd.DataFrame) -> pd.DataFrame:
        """计算 RSI6/RSI12/RSI24"""
    
    @staticmethod
    def calculate_boll(df: pd.DataFrame) -> pd.DataFrame:
        """计算布林带 (upper, middle, lower)"""
```

---

### 3.4 模块 4: API 端点 (更新)

**主要更新文件**:
- `app/api/v1/endpoints/stocks.py`
- `app/api/v1/endpoints/indicators.py`
- `app/main.py` (WebSocket)

**API 设计**:

```
# 股票数据相关
GET    /api/v1/stocks/{stock_code}          # 获取K线数据
POST   /api/v1/stocks/fetch/{stock_code}    # 同步获取并保存
POST   /api/v1/stocks/refresh/{stock_code}  # 增量刷新数据

# 指标相关
GET    /api/v1/indicators/{stock_code}/recent          # 获取最近数据(带指标)
GET    /api/v1/indicators/{stock_code}/refresh         # 后台刷新(触发WebSocket)
POST   /api/v1/indicators/{stock_code}/download        # 启动后台下载
GET    /api/v1/indicators/{stock_code}/calculate-all   # 批量补全指标
GET    /api/v1/indicators/{stock_code}/signals         # 获取交易信号

# WebSocket
WS     /ws/{client_id}    # WebSocket连接，接收下载进度推送
```

**WebSocket 消息格式**:

```json
{
  "type": "download_progress",
  "data": {
    "stock_code": "000001",
    "status": "downloading",    // downloading | calculating | completed | error
    "progress": 30,             // 0-100
    "message": "正在从 AkShare 获取数据...",
    "has_existing_data": true,  // 是否有旧数据可先展示
    "new_data_available": false // 完成后是否有新数据
  }
}
```

---

## 4. 数据流程

### 4.1 应用启动流程

```
1. FastAPI 启动
   ↓
2. 触发初始化服务
   ↓
3. 检查是否有上证指数(000001)数据
   ├─ 有数据 → 跳过
   └─ 无数据 → 下载一年历史数据 + 计算指标
   ↓
4. 服务就绪
```

### 4.2 用户请求数据流程

```
1. 用户访问页面 (默认加载 000001)
   ↓
2. 前端请求 /api/v1/indicators/{stock_code}/recent
   ↓
3. 后端检查数据库
   ├─ 有数据 → 直接返回 (混合模式读取指标)
   └─ 无数据 → 立即返回空，并启动后台下载
   ↓
4. 如果后台下载:
   ├─ 通过 WebSocket 推送进度
   └─ 完成后推送 "completed" 通知用户刷新
```

### 4.3 用户点击刷新流程

```
1. 用户点击"刷新数据"
   ↓
2. 前端请求 /api/v1/stocks/refresh/{stock_code}
   ↓
3. 后端:
   ├─ 查询数据库中最新日期
   ├─ 从该日期之后从 AkShare 获取新数据
   ├─ 保存新数据
   ├─ 重新计算新数据及之后所有记录的指标
   └─ WebSocket 推送完成通知
```

---

## 5. 数据库设计

### 5.1 StockData 表 (已存在，字段不变)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| stock_code | String(20) | 股票代码 |
| stock_name | String(100) | 股票名称 |
| period | String(10) | 周期 (1h/1d/1w/1M) |
| datetime | DateTime | 日期时间 |
| open_price | Float | 开盘价 |
| high_price | Float | 最高价 |
| low_price | Float | 最低价 |
| close_price | Float | 收盘价 |
| volume | Float | 成交量 |
| amount | Float | 成交额 |
| source | String(50) | 数据来源 ("akshare") |
| **技术指标字段** | | |
| ma5, ma10, ma20, ma30, ma60 | Float | 均线 |
| dif, dea, macd | Float | MACD |
| k, d, j | Float | KDJ |
| rsi6, rsi12, rsi24 | Float | RSI |
| upper, middle, lower | Float | 布林带 |

**索引**:
- (stock_code, period, datetime) - 唯一索引
- datetime - 单独索引

---

## 6. 文件清单与变更

### 6.1 新增文件
无（全部基于现有文件重构）

### 6.2 修改文件

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `app/crawlers/akshare_crawler.py` | 重构 | 完善成为唯一数据源 |
| `app/crawlers/data_processor.py` | 修改 | 移除模拟数据生成（或保留但禁用） |
| `app/services/stock_service.py` | 重构 | 移除其他数据源，实现增量更新 |
| `app/services/indicator_service.py` | 重构 | 实现混合模式指标管理 |
| `app/services/initialization_service.py` | 修改 | 初始化上证指数数据 |
| `app/api/v1/endpoints/stocks.py` | 更新 | 简化为只使用 Akshare |
| `app/api/v1/endpoints/indicators.py` | 更新 | 完善 WebSocket 推送 |
| `app/main.py` | 更新 | WebSocket 进度广播 |
| `static/js/main.js` | 更新 | 集成刷新功能，处理 WebSocket 进度 |

### 6.3 删除文件
- `app/crawlers/eastmoney.py` (可选，或保留但禁用)
- `app/crawlers/sina.py` (可选，或保留但禁用)

---

## 7. 实现优先级

### 阶段 1: 核心数据源 (高优先级)
1. ✅ 重构 `AkshareCrawler`，确保 API 调用正确
2. ✅ 移除其他数据源依赖
3. ✅ 实现数据持久化

### 阶段 2: 数据服务 (高优先级)
1. ✅ 初始化服务 - 默认上证指数
2. ✅ StockService - 智能获取 + 增量更新
3. ✅ IndicatorService - 混合模式

### 阶段 3: API & WebSocket (中优先级)
1. ✅ 更新 API 端点
2. ✅ WebSocket 进度推送
3. ✅ 错误处理

### 阶段 4: 前端集成 (中优先级)
1. ✅ 更新 main.js
2. ✅ 刷新按钮和进度显示
3. ✅ 集成 ECharts

---

## 8. 边界情况处理

### 8.1 网络问题
- AkShare 连接失败 → 抛出明确错误，不回退到模拟数据
- 提供友好提示："数据获取失败，请稍后重试"

### 8.2 数据库空
- 首次启动 → 初始化上证指数
- 新股票代码 → 启动后台下载 + WebSocket 推送

### 8.3 数据不完整
- 部分指标缺失 → 混合模式：实时计算 + 可选保存
- 支持后台批量补全

### 8.4 并发请求
- 同一股票多次请求下载 → 使用简单去重机制（基于股票代码+时间）

---

## 9. 非功能性需求

### 9.1 性能
- 有数据的请求响应时间: < 100ms
- 新数据下载时间: 取决于网络，通常 < 5秒
- 指标计算: 500条记录 < 1秒

### 9.2 可靠性
- 数据获取失败不崩溃应用
- 数据库操作有事务保护
- 有日志记录便于排查

### 9.3 可维护性
- 模块化设计，职责清晰
- 详细的代码注释
- 统一的错误处理

---

## 10. 验收标准

- [ ] 应用启动后，用户首次访问能看到上证指数数据
- [ ] 输入新股票代码，能正确从 AkShare 获取数据
- [ ] 数据保存到数据库，重复请求不重复下载
- [ ] 点击刷新，只获取增量数据
- [ ] 下载过程通过 WebSocket 实时推送进度
- [ ] 技术指标混合模式工作正常
- [ ] 彻底移除了模拟数据的使用

---

## 附录

### A. AkShare API 参考
- 指数日线: `ak.index_zh_a_hist(symbol="000001", period="daily")`
- 股票日线: `ak.stock_zh_a_hist(symbol="600519", period="daily")`
- 分钟线: `ak.index_zh_a_hist_min_em()` / `ak.stock_zh_a_hist_min_em()`

### B. 上证指数默认配置
- 股票代码: `000001`
- 内部代码: `sh000001`
- 默认周期: `1d`
- 历史范围: `最近一年`
